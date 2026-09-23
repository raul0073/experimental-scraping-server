from __future__ import annotations

"""Manager ranking — the scoring half, built in the shape of dependability.py.

The unit is a SPELL: a club under one man, stitched out of WhoScored's
per-match `managerName` by services/mental/spells.py. It is built here with
`absorb_short=False`, deliberately: the default rule relabels an interior run
shorter than ten matches with its longer neighbour, which does not merely
leave a sacked-in-October manager unranked, it DELETES him and credits his
football to somebody else. For a manager ranking that is not a missing row,
it is a wrong one in another man's name. A brief reign is handled where it
belongs — by shrinkage, which says "we do not know yet" rather than "this
did not happen".

Three rules this file exists to enforce:

  * PERCENTILE WITHIN LEAGUE, never across. The event feed is the same in
    five leagues; the football is not.
  * ONLY DIRECTIONAL METRICS ARE SCORED. The fingerprint metrics get
    percentiles too — the page draws a profile from them — but they never
    reach the total, because a table that ranks directness is asserting that
    one way of playing football is correct, which is an opinion wearing a
    number (services/mental/team_metrics.py already refuses this).
  * EVIDENCE SHRINKAGE ON MATCHES, K = 8, and it is REPORTED, not hidden:
    every row carries score_raw (before), kept (the factor) and score
    (after). A 38-match spell keeps 83% of its deviation from 50, a 4-match
    caretaker 33%.

The metric VALUES are not computed here. services/managers/metrics.py owns
that — the ratio-of-sums aggregation, the league-wide opponent adjustment,
the game-state windows — and this module asks it for one mapping:

    {spell.key: {metric_key: float | None}}

A metric it cannot compute comes back None. None is never punished: it
scores a neutral percentile of 50 and is published as a null raw beside it,
so the reader can see the hole rather than being sold a number.

Usage:
    from services.managers.ranking import build_payload
    payload = build_payload("ENG-Premier League")
"""

import inspect
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from services.mental.spells import Spell
from services.mental.spells import build as build_spells

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "data" / "config" / "manager_rank.json"

# Shrinkage on MATCHES. matches/(matches+8): 4 -> 0.33, 10 -> 0.56,
# 19 -> 0.70, 38 -> 0.83, 76 -> 0.90. A caretaker is pulled two thirds of
# the way back to neutral and still appears, which is the honest answer.
K_EVIDENCE = 8.0

LEAGUES = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A",
           "GER-Bundesliga", "FRA-Ligue 1"]

# ---------------------------------------------------------------------------
# THE BANK — IMPORTED, NOT RESTATED.
#
# 🐛 THIS FILE USED TO CARRY ITS OWN COPY OF IT, AND THE TWO HAD DRIFTED.
# metrics.py computed 25 metrics while this knew 22, and _normalise() iterates
# THESE keys — so regain_time, regain_5s and squad_used were measured on every
# league-season and silently dropped before they could reach the payload.
# Eleven dimension strings disagreed as well ("set_pieces" here against
# "set-pieces" there), and the richer help text was the copy being discarded.
#
# The drift is not the dangerous part. `directional` and `invert` happened to
# agree, but nothing made them: a future disagreement would have one module
# measuring one direction while the other percentiled the opposite, with no
# error raised anywhere and a table that was simply wrong.
#
# metrics.py measures them, so metrics.py owns what they ARE. This file owns
# only what a reader is allowed to change.
from services.managers.metrics import METRICS as _BANK       # noqa: E402

# Starting weights for the eight directional metrics; the live values live in
# data/config/manager_rank.json and are the reader's to edit. Fingerprints are
# never scored and stay at zero.
DEFAULT_WEIGHT: Dict[str, float] = {
    "card_rate": 18,
    "set_piece_balance": 16,
    "lead_protection": 15,
    "deficit_response": 13,
    "half_time_correction": 11,
    "sub_impact": 10,
    "sendings_off": 9,
    "self_inflicted": 8,
}

METRICS: Dict[str, Dict[str, Any]] = {
    k: {**m, "weight": DEFAULT_WEIGHT.get(k, 0), "enabled": True}
    for k, m in _BANK.items()
}

# Derived from the bank rather than listed, so a new dimension can never be a
# dimension the page cannot group.
DIMENSION_LABEL: Dict[str, str] = {
    d: d.replace("-", " ").replace("_", " ")
    for d in sorted({m["dimension"] for m in METRICS.values()})
}

# The contract's own order: directional first, then fingerprint. Payloads and
# config files are written in this order so a diff stays readable.
METRIC_KEYS: List[str] = (
    [k for k, m in METRICS.items() if m["directional"]]
    + [k for k, m in METRICS.items() if not m["directional"]]
)
DIRECTIONAL_KEYS: List[str] = [k for k, m in METRICS.items() if m["directional"]]
FINGERPRINT_KEYS: List[str] = [k for k, m in METRICS.items() if not m["directional"]]

_missing_w = sorted(set(DEFAULT_WEIGHT) - set(METRICS))
if _missing_w:
    raise RuntimeError(f"DEFAULT_WEIGHT names metrics the bank has not got: {_missing_w}")

# what the config file carries per metric, in this order
CONFIG_FIELDS = ("label", "unit", "dimension", "directional", "invert",
                 "enabled", "weight", "help")
# what the PAYLOAD carries per metric — the contract, exactly
PAYLOAD_FIELDS = ("label", "dimension", "directional", "invert", "unit", "help")

CONFIG_NOTES = [
    "Manager ranking recipe. Editable: `weight` and `enabled`. Everything "
    "else is documentation copied from services/managers/ranking.py, which "
    "stays authoritative — changing `invert` or `directional` here does "
    "nothing, because those are facts about the metric rather than "
    "preferences.",
    "Only metrics with directional=true are scored. The rest are "
    "fingerprints: they are percentiled and drawn on the page as a profile, "
    "with no good or bad end, so their weight is ignored and left at 0.",
    "score = sum(weight_i / sum(weights) * percentile_i) over the enabled "
    "directional metrics, percentiled WITHIN THE LEAGUE, then shrunk toward "
    "50 by matches/(matches+8).",
    "A metric that is null for a spell scores a neutral 50 and is never "
    "punished for being missing.",
    "`enabled` means PUBLISHED: an enabled metric is written to the payload "
    "with its raw value and its league percentile, and — if it is "
    "directional and carries a weight — counted in the score. Turning one "
    "off removes it from the page as well as from the total.",
]


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def default_components() -> List[Dict[str, Any]]:
    return [{"key": k, **{f: METRICS[k][f] for f in CONFIG_FIELDS}}
            for k in METRIC_KEYS]


def load_config(path: Path = CONFIG_PATH) -> List[Dict[str, Any]]:
    """The bank with the reader's weights folded in.

    Metadata always comes from METRICS, so a fixed label or a corrected help
    string reaches the page without anyone editing JSON; only `weight` and
    `enabled` are taken from disk. A metric added to the bank AFTER the file
    was written arrives disabled if it is directional — a new scored metric
    must never silently move every manager's score — and enabled if it is a
    fingerprint, which only adds a line to the profile."""
    stored: Dict[str, Dict[str, Any]] = {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for c in doc.get("metrics", []):
            if c.get("key") in METRICS:
                stored[c["key"]] = c
    except (OSError, ValueError, AttributeError):
        save_config(default_components(), path)
        return default_components()

    out: List[Dict[str, Any]] = []
    for k in METRIC_KEYS:
        base = {"key": k, **{f: METRICS[k][f] for f in CONFIG_FIELDS}}
        s = stored.get(k)
        if s is None:
            base["enabled"] = not METRICS[k]["directional"]
        else:
            if isinstance(s.get("weight"), (int, float)):
                base["weight"] = s["weight"]
            if isinstance(s.get("enabled"), bool):
                base["enabled"] = s["enabled"]
        out.append(base)
    return out


def save_config(components: Sequence[Dict[str, Any]],
                path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"v": 1, "_notes": CONFIG_NOTES,
                                "shrinkage_k": K_EVIDENCE,
                                "metrics": list(components)},
                               indent=1, ensure_ascii=False),
                    encoding="utf-8")


def scored_components(components: Sequence[Dict[str, Any]]
                      ) -> List[Dict[str, Any]]:
    """The ones that actually make the score: directional, on, weighted.

    `directional` is re-read from METRICS rather than from the component, so
    no edit to the config file can promote a fingerprint into the total."""
    return [c for c in components
            if METRICS[c["key"]]["directional"]
            and c.get("enabled") and (c.get("weight") or 0) > 0]


# ---------------------------------------------------------------------------
# the metric values — owned by services/managers/metrics.py
# ---------------------------------------------------------------------------
ENTRY_POINTS = ("spell_metrics", "build", "build_metrics",
                "metrics_for_league", "compute")


def _entry_point(mod) -> Any:
    for name in ENTRY_POINTS:
        fn = getattr(mod, name, None)
        if callable(fn):
            return name, fn
    raise RuntimeError(
        "services/managers/metrics.py exposes none of "
        f"{', '.join(ENTRY_POINTS)} — the ranking cannot find the function "
        "that returns {spell.key: {metric_key: value}}.")


def _positional(fn) -> int:
    kinds = (inspect.Parameter.POSITIONAL_ONLY,
             inspect.Parameter.POSITIONAL_OR_KEYWORD)
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return 2
    return sum(1 for p in params if p.kind in kinds and p.default is p.empty)


def _normalise(result: Any, spells: Sequence[Spell]
               ) -> Dict[str, Dict[str, Optional[float]]]:
    """Whatever metrics.py returned, as {spell.key: {metric: value|None}}.

    Accepts a mapping keyed by spell key, or a list of row dicts that name
    their spell with `key`/`spell`/`spell_key`. A row that names none of those
    is placed by (team, manager) ONLY while that pair belongs to exactly one
    spell. Nothing is dropped quietly: a row this cannot put on exactly one
    spell raises, because the one thing worse than a missing row is a
    published one holding another man's football."""
    by_key = {sp.key: sp for sp in spells}

    # (team, manager) -> EVERY spell key that pair names. Usually one, and the
    # exceptions are the whole point of this function's care: a manager who
    # came back, or a caretaker who did two separate stints, holds two spells
    # at one club and the pair no longer identifies either of them.
    by_pair: Dict[tuple, List[str]] = {}
    for sp in spells:
        by_pair.setdefault((sp.team, sp.manager), []).append(sp.key)

    rows: List[tuple] = []
    if isinstance(result, dict):
        rows = list(result.items())
    elif isinstance(result, (list, tuple)):
        for r in result:
            if not isinstance(r, dict):
                continue
            ident = r.get("key") or r.get("spell") or r.get("spell_key")
            if ident is None:
                # 🐛 (TEAM, MANAGER) IS NOT AN IDENTITY, AND THIS USED TO
                # TREAT IT AS ONE — `by_pair.setdefault(...)` kept the FIRST
                # spell of a repeated pair and handed it to both rows, so the
                # second row overwrote the first and the second spell was
                # published with every metric null and no score. Eleven spells
                # across the five leagues went out that way, Sarri's 38 matches
                # at Lazio among them, while Rusk's one match at Southampton
                # carried the seven-match spell's numbers. The fallback is kept
                # only where it is actually an identity — a pair held by one
                # spell — and says so out loud where it is not.
                pair = (r.get("team"), r.get("manager"))
                held = by_pair.get(pair, ())
                if len(held) == 1:
                    ident = held[0]
                elif len(held) > 1:
                    raise RuntimeError(
                        "services/managers/metrics.py returned a row with no "
                        f"`key` for {pair[1]!r} at {pair[0]!r}, and that pair "
                        f"is {len(held)} separate spells "
                        f"({', '.join(held)}). The row cannot be placed "
                        "without guessing which one it measured — emit "
                        "spell.key on every row.")
                else:
                    # No key, and no spell answers to the pair either. Carry a
                    # readable stand-in so the row is named in the report
                    # below instead of appearing there as None.
                    ident = (f"<no key; team={pair[0]!r} "
                             f"manager={pair[1]!r}>")
            # 🐛 THE ROW IS NOT THE VALUES. Every metric came back null for
            # every manager — 0 scored spells of 71 — while metrics.py was
            # computing 1,492 of them perfectly, because this read
            # r["press_height"] when the contract nests the numbers under
            # r["raw"]. The identity fields sit at the top level and the
            # values one layer down, so the lookup found nothing and the
            # "not computable, published as null" path reported it as a data
            # problem. The two halves were written to the same contract by
            # different hands, and this is the one seam between them.
            vals = r.get("raw") if isinstance(r.get("raw"), dict) else r
            rows.append((ident, vals))
    else:
        raise RuntimeError(
            "services/managers/metrics.py returned "
            f"{type(result).__name__}; expected a mapping of spell key to "
            "metric values, or a list of rows.")

    out: Dict[str, Dict[str, Optional[float]]] = {}
    lost: List[str] = []
    for ident, vals in rows:
        if not isinstance(vals, dict):
            lost.append(f"{ident!r}: values are "
                        f"{type(vals).__name__}, not a mapping")
            continue
        if ident not in by_key:
            lost.append(f"{ident!r}: no such spell in this league's pool "
                        f"of {len(by_key)}")
            continue
        if ident in out:
            # Two rows, one spell. Left alone the later one wins and the
            # earlier spell silently ships someone else's numbers, which is
            # the defect above wearing a different hat.
            raise RuntimeError(
                f"two metric rows both claim spell {ident!r}; "
                "one row per spell, or the published table is wrong.")
        clean: Dict[str, Optional[float]] = {}
        for k in METRIC_KEYS:
            v = vals.get(k)
            if v is None:
                clean[k] = None
                continue
            try:
                f = float(v)
            except (TypeError, ValueError):
                clean[k] = None
                continue
            clean[k] = None if f != f else f      # NaN is a hole, not a value
        out[ident] = clean
    if lost:
        # A dropped row is a spell published as all-null — indistinguishable
        # on the page from one the data genuinely cannot measure. It stops the
        # build instead. (A caller that deliberately narrows `spells` to part
        # of the league lands here too: narrow what metrics.py is asked for,
        # not what is done with its answer.)
        raise RuntimeError(
            f"{len(lost)} metric row(s) could not be placed on a spell:\n  "
            + "\n  ".join(lost[:10])
            + (f"\n  ... and {len(lost) - 10} more" if len(lost) > 10 else ""))
    return out


def raw_metrics(league: str, seasons: Sequence[str], spells: Sequence[Spell]
                ) -> Dict[str, Dict[str, Optional[float]]]:
    """Ask services/managers/metrics.py for every spell's metric values.

    That module is written by another hand to the same contract; this one
    only scores what it returns. Imported here rather than at module level so
    the scoring half can be exercised on stubbed values."""
    from services.managers import metrics as metrics_mod

    _name, fn = _entry_point(metrics_mod)
    result = (fn(league, list(seasons), list(spells))
              if _positional(fn) >= 3 else fn(league, list(seasons)))
    return _normalise(result, spells)


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def percentile_column(rows: Sequence[Dict[str, Any]], key: str,
                      invert: bool) -> None:
    """Write rows[i]['pct'][key]: 0-100 within this pool.

    Ties SHARE a percentile, so a metric where half the league sits on zero
    cannot invent spread between identical managers. A missing value scores a
    neutral 50 — never punished for a hole in the data — and keeps its null
    in `raw` beside it so the reader can see which it is."""
    have = [r for r in rows if r["raw"].get(key) is not None]
    for r in rows:
        if r["raw"].get(key) is None:
            r["pct"][key] = 50.0
    n = len(have)
    if n < 2:
        for r in have:
            r["pct"][key] = 50.0
        return
    ordered = sorted(have, key=lambda r: r["raw"][key], reverse=invert)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1]["raw"][key] == ordered[i]["raw"][key]:
            j += 1
        share = (i + j) / 2.0 / (n - 1) * 100.0
        for k in range(i, j + 1):
            ordered[k]["pct"][key] = round(share, 1)
        i = j + 1


def score_rows(rows: Sequence[Dict[str, Any]],
               components: Sequence[Dict[str, Any]],
               k_evidence: float = K_EVIDENCE) -> None:
    """Percentile every published metric within this pool, then score the
    directional ones and shrink on matches. Mutates rows in place.

    The pool IS the league and nothing else. Percentiling across leagues
    would rank the same feed as if it were the same football."""
    if not rows:
        return
    for key in rows[0]["raw"]:
        percentile_column(rows, key, METRICS[key]["invert"]
                          and METRICS[key]["directional"])

    scored = [c for c in scored_components(components)
              if c["key"] in rows[0]["raw"]]
    w_sum = sum(c["weight"] for c in scored)
    for r in rows:
        kept = r["matches"] / (r["matches"] + k_evidence) if r["matches"] else 0.0
        r["kept"] = round(kept, 3)
        if not scored or w_sum <= 0:
            r["score_raw"], r["score"] = 50.0, None
            continue
        raw = sum(c["weight"] / w_sum * r["pct"][c["key"]] for c in scored)
        r["score_raw"] = round(raw, 1)
        # every scored metric missing means we measured nothing: the 50 that
        # falls out is arithmetic, not a finding, so no score is published
        if all(r["raw"].get(c["key"]) is None for c in scored):
            r["score"] = None
        else:
            # shrunk from the PUBLISHED score_raw and kept, not from the full-
            # precision ones, so a reader who multiplies the three numbers on
            # the page gets the fourth back. The cost is under 0.05 of a point
            # and the gain is that the arithmetic is checkable.
            r["score"] = round(50.0 + (r["score_raw"] - 50.0) * r["kept"], 1)


# ---------------------------------------------------------------------------
# payload
# ---------------------------------------------------------------------------
def spell_rows(league: str, seasons: Sequence[str],
               raw: Optional[Dict[str, Dict[str, Optional[float]]]] = None,
               spells: Optional[Sequence[Spell]] = None,
               keys: Optional[Sequence[str]] = None
               ) -> List[Dict[str, Any]]:
    """One row per spell, with raw values attached and nothing scored yet.

    `absorb_short=False` — see the module docstring. Every spell in the
    league is kept in the pool, including the four-match ones: percentiles
    are rank-based, so a caretaker takes a rank without stretching the scale,
    and shrinkage is what answers his small sample."""
    if spells is None:
        spells = build_spells(league, list(seasons), absorb_short=False)
    if raw is None:
        raw = raw_metrics(league, seasons, spells)
    keys = list(keys) if keys is not None else METRIC_KEYS
    rows = []
    for sp in spells:
        rows.append({
            "manager": sp.manager, "team": sp.team, "matches": sp.matches,
            "short": sp.short, "start": sp.start, "end": sp.end,
            "seasons": list(sp.seasons),
            "raw": {k: (raw.get(sp.key) or {}).get(k) for k in keys},
            "pct": {},
        })
    return rows


def build_payload(league: str, seasons: Optional[Sequence[str]] = None,
                  components: Optional[Sequence[Dict[str, Any]]] = None,
                  raw: Optional[Dict[str, Dict[str, Optional[float]]]] = None,
                  spells: Optional[Sequence[Spell]] = None,
                  generated: Optional[str] = None) -> Dict[str, Any]:
    """The contract payload for one league, scored and ordered."""
    from datetime import date

    if seasons is None:
        from services.mental.role_bank import seasons_on_disk
        seasons = seasons_on_disk(league)
    components = list(components) if components is not None else load_config()

    # `enabled` is what gets published, so metrics[], raw and pct always
    # describe exactly the same set of keys — a page that reads metrics[] and
    # indexes raw by it can never miss
    keys = [c["key"] for c in components if c.get("enabled")]
    rows = spell_rows(league, seasons, raw=raw, spells=spells, keys=keys)
    score_rows(rows, components)
    # scored first, best down; the unscorable sit at the bottom in a stable
    # order rather than being dropped
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0.0),
                             r["team"], r["manager"]))

    metrics_out = [{"key": k, **{f: METRICS[k][f] for f in PAYLOAD_FIELDS}}
                   for k in keys]
    return {
        "league": league,
        "generated": generated or date.today().isoformat(),
        "metrics": metrics_out,
        "managers": rows,
    }
