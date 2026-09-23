"""QUESTION 1: does team style actually shift, sharply and often enough to matter?

Measurement only. Nothing here is imported by the app and nothing is published.

WHAT IS MEASURED. For every team-match we take eight style metrics straight off
services.managers.metrics — its own per-match counters, folded with its own
ratio-of-sums rule — then compare the SIX matches before a fixture against the
TWENTY before those. The gap between those two windows, in units of the
league-season's own spread, is the "style shift" at that fixture.

Everything uses matches STRICTLY PRIOR to the focal fixture, so the same number
could be handed to a predictor before kickoff. That costs nothing here and is
what the second leg of this check needs.

THE TRAP THIS SCRIPT IS BUILT AROUND. Six matches differ from twenty even when a
team's style is perfectly constant: six is a small sample, and six against a
different set of opponents is a smaller one still. A fat tail of "shifts" proves
nothing on its own. So every fixture is scored against its OWN EXACT PERMUTATION
NULL: hold the same 26 matches, split them 20/6 at random, and measure the shift
that random split produces. Same team, same opponents, same season, same sample
sizes — the only thing destroyed is that the six were the most RECENT six. The
observed shift is then reported as a percentile of that fixture's own null, which
is the only version of this measurement that can come back negative honestly.

  a first null — shuffling a team's whole season — was wrong and was replaced.
  It kept the season blocks in place, so a window crossing the summer crossed a
  real between-season change in the null as well as in the data, and the null
  therefore absorbed exactly the changes most worth finding. The 20/6 split
  pools the 26 whatever seasons they come from, so a summer change survives in
  the observed arm and not in the null.

LEAGUE DRIFT IS REMOVED, not left to cancel. If a whole league presses higher in
2526 than 2425, a window straddling the summer would read as a style shift for
every side at once. Each window's expected value is therefore the league-season
mean for the seasons its matches actually come from, weighted by how many come
from each, and subtracted before the two windows are compared.

  .venv/Scripts/python.exe scripts/experiment_style_shift.py [draws]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.managers import metrics as M            # noqa: E402
from services.mental import spells as SP              # noqa: E402

LEAGUES = ["ENG-Premier League", "ESP-La Liga"]
SEASONS = ["2324", "2425", "2526", "2627"]

SHORT_W = 6      # the recent window
LONG_W = 20      # the reference window, immediately before the short one
NEED = SHORT_W + LONG_W
MAX_GAP_DAYS = 150   # a summer is ~90 days; longer means a season in another
                     # division, and the two ends are not one sequence

# since-change band where the short window is ENTIRELY the new manager's while
# the long window is still mostly the old one's. Below SHORT_W the "new" window
# is a blend of the two men, which would understate the proxy.
BAND = (SHORT_W, SHORT_W + 8)

LEN_BINS = 2001      # pass Length rounded to 0.1, clipped at 200.0

# ---------------------------------------------------------------- the metrics
# (key, numerator field, denominator field, scale). Definitions are metrics.py's
# own, reused field for field — see _fold there.
RATIOS: List[Tuple[str, str, str, float]] = [
    ("press_height", "def_x_sum", "def_n", 1.0),
    ("ppda", "opp_pass_own60_n", "def_high_n", 1.0),
    ("directness", "direct_n", "pass_end_n", 100.0),
    ("territory", "touch_f3_n", "touch_n", 100.0),
    ("fast_break", "shot_fb_n", "shot_n", 100.0),
    ("regain_time", "regain_sum", "regain_n", 1.0),
    ("regain_5s", "regain_fast_n", "regain_n", 100.0),
]
# pass_length is a distribution statistic, not a rate — pooled median, as in
# metrics.py — which is why it is carried as a histogram rather than a ratio.
STYLE_KEYS = [k for k, *_ in RATIOS] + ["pass_length"]
FIELDS = sorted({f for _k, n, d, _s in RATIOS for f in (n, d)})
F_IDX = {f: i for i, f in enumerate(FIELDS)}
K = len(STYLE_KEYS)
KI = {k: i for i, k in enumerate(STYLE_KEYS)}

# the five resting on thousands of events a window, and unambiguously about HOW
# a side plays. fast_break is about five events a window and regain_* are two
# readings of one thing, so a "core" composite says whether the answer depends
# on the noisy ones.
CORE_KEYS = ["press_height", "ppda", "directness", "territory", "pass_length"]
CORE_IDX = [KI[k] for k in CORE_KEYS]


# ------------------------------------------------------------------ the frame
def team_sequences(league: str) -> Dict[str, List[Dict[str, Any]]]:
    """team -> its matches in kickoff order, each carrying the raw counters.

    Ordering comes from spells._match_managers, which sorts by kickoff and not
    by game id: inside a season the ids are not chronological, and a sequence
    sorted by id would put a manager's matches in the wrong order and invent
    shifts that never happened."""
    records: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for season in SEASONS:
        for key, rec in M._season_records(league, season).items():
            records.setdefault(key, rec)

    out: Dict[str, List[Dict[str, Any]]] = {}
    for team, rows in SP._match_managers(league, SEASONS).items():
        seq = []
        seen: Dict[str, int] = defaultdict(int)
        for kick, gid, season, _mgr in rows:
            rec = records.get((gid, team))
            if rec is not None:
                seq.append({"kick": kick, "gid": gid, "season": season,
                            "round": seen[season], "rec": rec})
                seen[season] += 1
        if seq:
            out[team] = seq
    return out


def pack(seq: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
    """(scalar counters, pass-length histogram), one row per match."""
    n = len(seq)
    scal = np.zeros((n, len(FIELDS)), dtype=np.float64)
    hist = np.zeros((n, LEN_BINS), dtype=np.float64)
    for i, m in enumerate(seq):
        rec = m["rec"]
        for f, j in F_IDX.items():
            scal[i, j] = float(rec[f])
        for length, count in rec["pass_len"].items():
            b = int(round(float(length) * 10.0))
            if 0 <= b < LEN_BINS:
                hist[i, b] += count
    return scal, hist


def metrics_from(sums: np.ndarray, hists: np.ndarray) -> np.ndarray:
    """(rows, K) style vectors from already-summed counters.

    RATIO OF SUMS, metrics.py's house rule: a window's directness is all its
    direct passes over all its passes, never the mean of six per-match rates.
    The median is metrics.py's _median_from_counter, vectorised — the first
    length whose running count reaches half the total."""
    rows = sums.shape[0]
    out = np.full((rows, K), np.nan)
    for key, num, den, scale in RATIOS:
        d = sums[:, F_IDX[den]]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[:, KI[key]] = np.where(d > 0, sums[:, F_IDX[num]] / d * scale, np.nan)
    total = hists.sum(axis=1)
    cum = np.cumsum(hists, axis=1)
    med = (cum < (total / 2.0)[:, None]).sum(axis=1) / 10.0
    out[:, KI["pass_length"]] = np.where(total > 0, med, np.nan)
    return out


def eligible(seq: List[Dict[str, Any]], i: int) -> bool:
    """Is fixture i preceded by 26 matches that form one continuous run?

    A team relegated and promoted has a two-year hole in its sequence; joining
    the two ends would compare 2023 football with 2025 football and call the
    difference a style shift."""
    if i < NEED:
        return False
    days = pd.to_datetime([seq[j]["kick"] for j in range(i - NEED, i + 1)],
                          errors="coerce", utc=True)
    if days.isna().any():
        return False
    return bool(np.diff(days.values).max() / np.timedelta64(1, "D") <= MAX_GAP_DAYS)


# ------------------------------------------------------------- manager changes
def _norm(name: str) -> List[str]:
    import unicodedata
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return [t for t in s.replace("-", " ").replace(".", " ").split() if t]


def same_man(a: str, b: str) -> bool:
    """Is this the same manager under two spellings of his name?

    NOT a fuzzy matcher for two different men — it is only ever asked about
    CONSECUTIVE spells at ONE club, where the prior probability of two distinct
    managers sharing a surname is negligible and the probability of the feed
    writing one man two ways is not. WhoScored has Villarreal going from
    "Marcelino Garcia Toral" to "Marcelino Garcia" and Barcelona from
    "Hans-Dieter Flick" to "Hansi Flick", and both were being counted as a
    change of manager — the second of them landing in the top decile of style
    shifts with a permutation p of 0.010, which is to say the strongest kind of
    evidence for a proxy firing on a man who never left.

    Same surname plus either a first name that is a prefix of the other's
    ("hans" of "hansi") or one full name contained in the other."""
    ta, tb = _norm(a), _norm(b)
    if not ta or not tb:
        return False
    if ta == tb or set(ta) <= set(tb) or set(tb) <= set(ta):
        return True
    if ta[-1] != tb[-1] and not (set(ta) & set(tb[1:])):
        return False
    common = set(ta) & set(tb)
    if not common:
        return False
    fa, fb = ta[0], tb[0]
    n = min(len(fa), len(fb), 4)
    return n >= 3 and fa[:n] == fb[:n] and bool(common - {fa, fb})


def change_points(league: str, seq_of: Dict[str, List[Dict[str, Any]]]
                  ) -> Dict[str, List[Dict[str, Any]]]:
    """team -> [{index, manager, prev, length, date}] for every NEW manager.

    A team's first spell inside the data window is not a change, it is where the
    recording starts, so it is excluded. absorb_short=False per the module's own
    instruction: absorbing a short interior spell credits a sacked manager's
    matches to someone else, which for a question about WHEN the man changed
    destroys the fact being measured.

    Consecutive spells that are one man under two spellings are stitched back
    together before anything is called a change."""
    by_team: Dict[str, List[Any]] = defaultdict(list)
    for sp in SP.build(league, SEASONS, absorb_short=False):
        by_team[sp.team].append(sp)

    out: Dict[str, List[Dict[str, Any]]] = {}
    for team, sps in by_team.items():
        seq = seq_of.get(team)
        if not seq:
            continue
        pos = {m["gid"]: i for i, m in enumerate(seq)}
        runs: List[Dict[str, Any]] = []
        for sp in sorted(sps, key=lambda s: s.start):
            idx = sorted(pos[g] for g in sp.games if g in pos)
            if not idx:
                continue
            if runs and same_man(runs[-1]["manager"], sp.manager):
                runs[-1]["idx"].extend(idx)
                continue
            runs.append({"manager": sp.manager, "idx": idx})
        rows = []
        for n, run in enumerate(runs):
            if n == 0:
                continue
            rows.append({"index": min(run["idx"]), "manager": run["manager"],
                         "prev": runs[n - 1]["manager"], "length": len(run["idx"]),
                         "date": seq[min(run["idx"])]["kick"][:10]})
        out[team] = rows
    return out


# ------------------------------------------------------------------ the engine
def league_scale(seq_of, packed) -> Dict[str, Dict[str, np.ndarray]]:
    """season -> {'mean': (K,), 'sd': (K,)} for this league.

    The mean comes from the twenty-match windows, which are the stabler
    estimate of where the league sits; the sd from the six-match windows,
    because that is the spread a six-match reading is being judged against."""
    long_vals: Dict[str, List[np.ndarray]] = defaultdict(list)
    short_vals: Dict[str, List[np.ndarray]] = defaultdict(list)
    for team, seq in seq_of.items():
        scal, hist = packed[team]
        cs = np.vstack([np.zeros((1, scal.shape[1])), np.cumsum(scal, 0)])
        ch = np.vstack([np.zeros((1, hist.shape[1])), np.cumsum(hist, 0)])
        for w, bucket in ((SHORT_W, short_vals), (LONG_W, long_vals)):
            starts = np.arange(0, len(seq) - w + 1)
            if not len(starts):
                continue
            vals = metrics_from(cs[starts + w] - cs[starts],
                                ch[starts + w] - ch[starts])
            for s, v in zip(starts, vals):
                # the window is credited to the season of its LAST match,
                # which is the fixture it would be used to predict
                bucket[seq[s + w - 1]["season"]].append(v)
    out = {}
    for season in set(long_vals) | set(short_vals):
        lv = np.array(long_vals.get(season) or [[np.nan] * K])
        sv = np.array(short_vals.get(season) or [[np.nan] * K])
        out[season] = {"mean": np.nanmean(lv, axis=0),
                       "sd": np.nanstd(sv, axis=0, ddof=1)}
    return out


def fixture_shift(scal: np.ndarray, hist: np.ndarray, means: np.ndarray,
                  sd: np.ndarray, i: int, draws: np.ndarray
                  ) -> Optional[Dict[str, Any]]:
    """The observed shift at fixture i, and the same statistic for `draws`
    random 20/6 splits of the very same 26 matches.

    `means` is the per-match league-season mean vector, so a window's expected
    value follows the seasons its matches actually came from. Subtracting it
    from each window before differencing removes league-wide drift, which would
    otherwise make every side in the division look like it changed style on the
    same August weekend."""
    block_s = scal[i - NEED:i]
    block_h = hist[i - NEED:i]
    block_m = means[i - NEED:i]
    tot_s, tot_h, tot_m = block_s.sum(0), block_h.sum(0), block_m.sum(0)

    def delta(short_s, short_h, short_m):
        long_v = metrics_from((tot_s - short_s), (tot_h - short_h))
        short_v = metrics_from(short_s, short_h)
        exp_short = short_m / SHORT_W
        exp_long = (tot_m - short_m) / LONG_W
        return ((short_v - exp_short) - (long_v - exp_long)) / sd

    obs = delta(block_s[-SHORT_W:].sum(0)[None, :],
                block_h[-SHORT_W:].sum(0)[None, :],
                block_m[-SHORT_W:].sum(0)[None, :])[0]
    if not np.isfinite(obs).all():
        return None

    pick = draws                      # (R, SHORT_W) indices into the 26
    ss = block_s[pick].sum(axis=1)
    sh = block_h[pick].sum(axis=1)
    sm = block_m[pick].sum(axis=1)
    nul = delta(ss, sh, sm)
    ok = np.isfinite(nul).all(axis=1)
    nul = nul[ok]
    if not len(nul):
        return None

    def rms(a, idx=None):
        b = a if idx is None else (a[..., idx] if a.ndim > 1 else a[idx])
        return np.sqrt(np.mean(np.square(b), axis=-1))

    o_all, o_core = float(rms(obs)), float(rms(obs, CORE_IDX))
    n_all, n_core = rms(nul), rms(nul, CORE_IDX)
    return {"z": obs, "shift": o_all, "shift_core": o_core,
            "null": n_all, "null_core": n_core,
            # the per-metric noise variance for THIS fixture: what a shift of
            # this size looks like when only the split point is random
            "null_sq": np.square(nul).mean(axis=0),
            "p": float((n_all >= o_all).mean()),
            "p_core": float((n_core >= o_core).mean())}


def opponent_style(seq_of, packed, scale) -> Tuple[Dict[Tuple[int, str], str],
                                                   Dict[Tuple[str, str], np.ndarray]]:
    """((game, team) -> opponent, (team, season) -> that side's season-long z).

    The control for the one alternative explanation a permutation null cannot
    reach. A fixture list is not a random ordering: six straight games against
    deep-blocking sides pushes a team's territory down without anything about
    that team having changed. The permutation holds the same 26 matches but
    still compares a CONTIGUOUS six against the rest, so a run of similar
    opponents survives it. Measuring how much the opponents themselves differed
    between the two windows says whether that is what the excess is made of."""
    sides: Dict[int, List[str]] = defaultdict(list)
    for team, seq in seq_of.items():
        for m in seq:
            sides[m["gid"]].append(team)
    opp_of = {(gid, t): [o for o in ts if o != t][0]
              for gid, ts in sides.items() if len(ts) == 2 for t in ts}

    season_z: Dict[Tuple[str, str], np.ndarray] = {}
    for team, seq in seq_of.items():
        scal, hist = packed[team]
        by_season: Dict[str, List[int]] = defaultdict(list)
        for i, m in enumerate(seq):
            by_season[m["season"]].append(i)
        for season, idx in by_season.items():
            if len(idx) < 5:
                continue
            v = metrics_from(scal[idx].sum(0)[None, :], hist[idx].sum(0)[None, :])[0]
            season_z[(team, season)] = (v - scale[season]["mean"]) / scale[season]["sd"]
    return opp_of, season_z


def run_league(league: str, draws: int, rng: np.random.Generator) -> Dict[str, Any]:
    seq_of = team_sequences(league)
    packed = {t: pack(s) for t, s in seq_of.items()}
    scale = league_scale(seq_of, packed)
    changes = change_points(league, seq_of)
    opp_of, season_z = opponent_style(seq_of, packed, scale)

    rows: List[Dict[str, Any]] = []
    null_pool: List[np.ndarray] = []
    null_core_pool: List[np.ndarray] = []
    for team, seq in seq_of.items():
        scal, hist = packed[team]
        means = np.array([scale[m["season"]]["mean"] for m in seq])
        for i in range(NEED, len(seq)):
            if not eligible(seq, i):
                continue
            sd = scale[seq[i]["season"]]["sd"]
            pick = np.argsort(rng.random((draws, NEED)), axis=1)[:, :SHORT_W]
            r = fixture_shift(scal, hist, means, sd, i, pick)
            if r is None:
                continue
            null_pool.append(r.pop("null"))
            null_core_pool.append(r.pop("null_core"))
            r.update({"team": team, "index": i, "season": seq[i]["season"],
                      "date": seq[i]["kick"][:10], "gid": seq[i]["gid"],
                      "round": seq[i]["round"], "league": league,
                      "crosses_summer": len({seq[j]["season"]
                                             for j in range(i - NEED, i)}) > 1})

            def opp_mean(a: int, b: int):
                vs = [season_z[(opp_of[(seq[j]["gid"], team)], seq[j]["season"])]
                      for j in range(a, b)
                      if (seq[j]["gid"], team) in opp_of
                      and (opp_of[(seq[j]["gid"], team)], seq[j]["season"]) in season_z]
                return np.mean(vs, axis=0) if len(vs) >= (b - a) // 2 else None

            new, old = opp_mean(i - SHORT_W, i), opp_mean(i - NEED, i - SHORT_W)
            r["opp_shift"] = (float(np.sqrt(np.mean(np.square(new - old))))
                              if new is not None and old is not None else None)

            def behind(a: int, b: int):
                num = sum(seq[j]["rec"]["min_state"]["behind"] for j in range(a, b))
                den = sum(sum(seq[j]["rec"]["min_state"].values())
                          for j in range(a, b))
                return num / den if den else None

            bn, bo = behind(i - SHORT_W, i), behind(i - NEED, i - SHORT_W)
            r["state_shift"] = (bn - bo) if bn is not None and bo is not None else None
            rows.append(r)

    return {"league": league, "rows": rows, "changes": changes,
            "null": np.concatenate(null_pool) if null_pool else np.array([]),
            "null_core": (np.concatenate(null_core_pool)
                          if null_core_pool else np.array([])),
            "scale": scale, "teams": len(seq_of)}


# ---------------------------------------------------------------------- report
def describe(vals) -> Dict[str, float]:
    a = np.asarray(vals, dtype=float)
    if not a.size:
        return {"n": 0}
    return {"n": int(a.size), "median": float(np.percentile(a, 50)),
            "p75": float(np.percentile(a, 75)), "p90": float(np.percentile(a, 90)),
            "p99": float(np.percentile(a, 99)), "max": float(a.max()),
            "mean": float(a.mean())}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    draws = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    rng = np.random.default_rng(20260923)

    per_league: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    null = []
    null_core = []
    for league in LEAGUES:
        res = run_league(league, draws, rng)
        per_league[league] = res
        rows.extend(res["rows"])
        null.append(res["null"])
        null_core.append(res["null_core"])
    null = np.concatenate(null)
    null_core = np.concatenate(null_core)

    obs = np.array([r["shift"] for r in rows])
    obs_core = np.array([r["shift_core"] for r in rows])
    out: Dict[str, Any] = {"config": {
        "leagues": LEAGUES, "seasons": SEASONS, "short_window": SHORT_W,
        "long_window": LONG_W, "band": list(BAND), "draws_per_fixture": draws,
        "metrics": STYLE_KEYS, "core": CORE_KEYS}}

    out["distribution"] = {
        "observed": describe(obs), "null": describe(null),
        "observed_core": describe(obs_core), "null_core": describe(null_core),
        "per_league": {lg: {"observed": describe([r["shift"] for r in res["rows"]]),
                            "null": describe(res["null"])}
                       for lg, res in per_league.items()},
    }
    # under the null of "the last six are just six of these twenty-six", the
    # per-fixture permutation p is uniform: 10% below 0.10, 5% below 0.05.
    ps = np.array([r["p"] for r in rows])
    ps_core = np.array([r["p_core"] for r in rows])
    out["distribution"]["permutation"] = {
        "share_p_le_0.10": float((ps <= 0.10).mean()),
        "share_p_le_0.05": float((ps <= 0.05).mean()),
        "share_p_le_0.01": float((ps <= 0.01).mean()),
        "core_share_p_le_0.10": float((ps_core <= 0.10).mean()),
        "core_share_p_le_0.05": float((ps_core <= 0.05).mean()),
        "core_share_p_le_0.01": float((ps_core <= 0.01).mean()),
        "mean_p": float(ps.mean()),
    }

    # WHERE the excess lives: a window wholly inside one season tests whether
    # football changes DURING a season; a window straddling the summer tests
    # whether a close season changes it. They are different questions and the
    # answers are allowed to differ.
    out["by_window"] = {}
    for label, sel in (("within_season", [r for r in rows if not r["crosses_summer"]]),
                       ("crosses_summer", [r for r in rows if r["crosses_summer"]])):
        p = np.array([r["p"] for r in sel]) if sel else np.array([])
        out["by_window"][label] = {
            "n": len(sel),
            "shift": describe([r["shift"] for r in sel]),
            "share_p_le_0.10": float((p <= 0.10).mean()) if p.size else None,
            "share_p_le_0.05": float((p <= 0.05).mean()) if p.size else None,
            "share_p_le_0.01": float((p <= 0.01).mean()) if p.size else None,
        }

    # HOW MUCH OF THE MOVEMENT IS THE WHOLE LEAGUE AT ONCE. Winter pitches, a
    # congested December, a mid-season rule emphasis — anything that moves every
    # side together is not a team changing its style, and a per-season mean does
    # not remove it. The share of each metric's shift variance carried by the
    # league-season-matchweek mean answers it; with about twenty teams a group,
    # pure noise already produces ~1/20.
    # HOW BIG IS THE REAL MOVEMENT. The observed shift in a metric is the true
    # movement plus the noise of reading six matches; the null measures that
    # noise on the same fixtures. Subtracting the variances leaves the part
    # that is football, in units of how far apart two teams in the division sit.
    nsq = np.array([r["null_sq"] for r in rows])
    zz = np.array([r["z"] for r in rows])
    out["signal_size"] = {}
    for k in STYLE_KEYS:
        tot = float(np.mean(np.square(zz[:, KI[k]])))
        noise = float(np.mean(nsq[:, KI[k]]))
        out["signal_size"][k] = {
            "observed_rms_sd": tot ** 0.5, "noise_rms_sd": noise ** 0.5,
            "real_rms_sd": max(tot - noise, 0.0) ** 0.5,
            "share_of_variance_real": max(tot - noise, 0.0) / tot if tot else 0.0}
    for r in rows:
        r.pop("null_sq", None)

    groups: Dict[tuple, List[int]] = defaultdict(list)
    for n, r in enumerate(rows):
        groups[(r["league"], r["season"], r["round"])].append(n)
    common = np.zeros((len(rows), K))
    sizes = []
    for g in groups.values():
        common[g] = zz[g].mean(axis=0)
        sizes.append(len(g))
    out["league_common_component"] = {
        "share_of_variance": {k: float(common[:, KI[k]].var() / zz[:, KI[k]].var())
                              for k in STYLE_KEYS},
        "noise_floor": float(1.0 / np.mean(sizes)),
        "mean_group_size": float(np.mean(sizes)),
    }

    out["per_metric"] = {
        k: {"median_abs_z": float(np.median(np.abs(zz[:, KI[k]]))),
            "p90_abs_z": float(np.percentile(np.abs(zz[:, KI[k]]), 90)),
            "p99_abs_z": float(np.percentile(np.abs(zz[:, KI[k]]), 99)),
            "sd_raw_units": {lg: {s: round(float(res["scale"][s]["sd"][KI[k]]), 3)
                                  for s in sorted(res["scale"])}
                             for lg, res in per_league.items()}}
        for k in STYLE_KEYS}

    # ------------------------------------------------ the proxy, both ways round
    big = float(np.percentile(obs, 90))
    lo, hi = BAND
    for lg, res in per_league.items():
        for r in res["rows"]:
            best = None
            best_sub = None
            for c in res["changes"].get(r["team"], []):
                d = r["index"] - c["index"]
                if d < 0:
                    continue
                if best is None or d < best:
                    best = d
                # a caretaker who lasted two matches cannot put six of his own
                # matches in the short window, so his change point can only
                # dilute the band; counted separately, not silently dropped
                if c["length"] >= SHORT_W and (best_sub is None or d < best_sub):
                    best_sub = d
            r["since_change"] = best
            r["in_band"] = best is not None and lo <= best < hi
            r["in_band_sub"] = best_sub is not None and lo <= best_sub < hi

    big_rows = [r for r in rows if r["shift"] >= big]
    banded = [r for r in rows if r["in_band"]]
    quiet = [r for r in rows if r["since_change"] is None or r["since_change"] >= NEED]

    out["proxy"] = {
        "big_threshold_p90": big,
        "share_of_big_shifts_following_a_change": (
            float(np.mean([r["in_band"] for r in big_rows])) if big_rows else None),
        "base_rate_of_band_fixtures": float(np.mean([r["in_band"] for r in rows])),
        "share_of_big_shifts_following_a_substantive_change": (
            float(np.mean([r["in_band_sub"] for r in big_rows])) if big_rows else None),
        "base_rate_of_substantive_band": float(np.mean([r["in_band_sub"] for r in rows])),
        "n_big": len(big_rows), "n_band": len(banded),
        "band_distribution": describe([r["shift"] for r in banded]),
        "quiet_distribution": describe([r["shift"] for r in quiet]),
        "band_mean_p": float(np.mean([r["p"] for r in banded])) if banded else None,
        "quiet_mean_p": float(np.mean([r["p"] for r in quiet])) if quiet else None,
        "band_share_p_le_0.05": (float(np.mean([r["p"] <= 0.05 for r in banded]))
                                 if banded else None),
        "quiet_share_p_le_0.05": (float(np.mean([r["p"] <= 0.05 for r in quiet]))
                                  if quiet else None),
    }

    # one row per manager change, scored by its best fixture inside the band, so
    # a change is credited if it moved the football anywhere the measurement
    # could see it
    per_change = []
    for lg, res in per_league.items():
        idx = {(r["team"], r["index"]): r for r in res["rows"]}
        for team, crows in res["changes"].items():
            for c in crows:
                band = [idx[(team, c["index"] + d)] for d in range(lo, hi)
                        if (team, c["index"] + d) in idx]
                if not band:
                    continue
                best = max(band, key=lambda r: r["shift"])
                per_change.append({
                    "league": lg, "team": team, "manager": c["manager"],
                    "prev": c["prev"], "date": c["date"],
                    "spell_length": c["length"], "best": best["shift"],
                    "best_p": best["p"], "n_fixtures": len(band),
                    "big": bool(best["shift"] >= big)})
    real = [c for c in per_change if c["spell_length"] >= SHORT_W]
    out["proxy"].update({
        "share_of_changes_producing_a_big_shift": (
            float(np.mean([c["big"] for c in real])) if real else None),
        "n_changes_measurable": len(real), "n_changes_all": len(per_change),
        "share_all_changes_producing_a_big_shift": (
            float(np.mean([c["big"] for c in per_change])) if per_change else None),
    })
    out["changes"] = sorted(per_change, key=lambda c: -c["best"])

    prof: Dict[int, List[float]] = defaultdict(list)
    for r in rows:
        if r["since_change"] is not None and r["since_change"] < 26:
            prof[r["since_change"]].append(r["shift"])
    out["since_change_profile"] = {
        str(d): {"n": len(v), "median": float(np.percentile(v, 50)),
                 "p90": float(np.percentile(v, 90))}
        for d, v in sorted(prof.items())}

    stable: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        if r["since_change"] is None or r["since_change"] >= NEED:
            stable[r["team"]].append(r["shift"])
    out["stable_tenures"] = {
        t: {"n": len(v), "median": round(float(np.percentile(v, 50)), 3),
            "p90": round(float(np.percentile(v, 90)), 3)}
        for t, v in sorted(stable.items()) if len(v) >= 20}

    # ------------------------------------------------------------ named cases
    # Reality checks, fixed BEFORE the numbers were looked at and kept whatever
    # they said. Each is a change whose direction anyone following these leagues
    # would call before the measurement: Slot taking Klopp's press apart, Flick's
    # famous high line at Barcelona, Amorim's immediate back three — against
    # tenures that ran for years with one idea.
    want = [("Liverpool", "Slot"), ("Brighton", "Hürzeler"), ("Everton", "Moyes"),
            ("Barcelona", "Flick"), ("Chelsea", "Maresca"),
            ("Man Utd", "Ruben"), ("Man Utd", "Nistelrooij"),
            ("Tottenham", "Frank"), ("Real Madrid", "Xabi"),
            ("West Ham", "Lopetegui"), ("Crystal Palace", "Glasner"),
            ("Nottingham Forest", "Nuno"), ("Real Sociedad", "Sergio Francisco")]
    named = []
    for team, who in want:
        hit = [c for c in per_change
               if c["team"] == team and who.lower() in c["manager"].lower()]
        for c in sorted(hit, key=lambda c: c["date"]):
            named.append({**c, "percentile": round(float(
                (obs <= c["best"]).mean()) * 100, 1)})
    out["named_changes"] = named
    out["named_stable"] = {
        t: out["stable_tenures"].get(t)
        for t in ("Arsenal", "Man City", "Atletico", "Aston Villa", "Bournemouth",
                  "Liverpool", "Brentford", "Girona", "Newcastle", "Fulham",
                  "Real Madrid", "Barcelona", "Athletic Club", "Villarreal")
        if out["stable_tenures"].get(t)}

    # is the excess just the fixture list? split by how much the opponents
    # themselves changed between the two windows
    have = [r for r in rows if r.get("opp_shift") is not None]
    if have:
        os_ = np.array([r["opp_shift"] for r in have])
        sh = np.array([r["shift"] for r in have])
        pv = np.array([r["p"] for r in have])
        cuts = np.percentile(os_, [33.3, 66.7])
        out["opponent_mix"] = {
            "opp_shift": describe(os_),
            "corr_with_shift": float(np.corrcoef(os_, sh)[0, 1]),
            "terciles": [
                {"opp_shift_median": float(np.median(os_[m])), "n": int(m.sum()),
                 "shift_median": float(np.median(sh[m])),
                 "share_p_le_0.05": float((pv[m] <= 0.05).mean())}
                for m in (os_ <= cuts[0], (os_ > cuts[0]) & (os_ <= cuts[1]),
                          os_ > cuts[1])],
        }

    # IS THE SHIFT JUST THE SCORELINE. A six-match window is also a results run,
    # and a side that has been losing chases games: it passes longer, goes more
    # direct, presses higher late. That is not a change of style, it is the same
    # team in a worse position, and it would ride into any feature built on this.
    # min_state comes stamped on the events, so the share of minutes spent behind
    # is free — its shift is correlated against each metric's.
    gs = np.array([[r["state_shift"]] for r in rows if r.get("state_shift") is not None])
    if gs.size:
        sel = [r for r in rows if r.get("state_shift") is not None]
        g = np.array([r["state_shift"] for r in sel])
        zs = np.array([r["z"] for r in sel])
        out["game_state_confound"] = {
            "behind_share_shift_sd": float(g.std()),
            "corr_with_metric": {k: float(np.corrcoef(g, zs[:, KI[k]])[0, 1])
                                 for k in STYLE_KEYS},
            "corr_with_composite": float(np.corrcoef(
                np.abs(g), [r["shift"] for r in sel])[0, 1]),
            "n": len(sel),
        }

    # the ten biggest, metric by metric, so an outlier can be read rather than
    # trusted — a single feed glitch would show as one metric carrying it all
    out["top_fixtures"] = [
        {"team": r["team"], "date": r["date"], "season": r["season"],
         "shift": round(r["shift"], 3), "p": r["p"],
         "since_change": r["since_change"],
         "z": {k: round(float(r["z"][KI[k]]), 2) for k in STYLE_KEYS}}
        for r in sorted(rows, key=lambda r: -r["shift"])[:12]]

    path = ROOT / "data" / "reports" / "experiment_style_shift.json"
    path.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")

    # ------------------------------------------------------------------ print
    d = out["distribution"]
    print(f"\nfixtures measured: {len(rows)}   null draws: {null.size}")
    print("\nCOMPOSITE STYLE SHIFT (RMS sd over the metrics)")
    print(f"{'':11s} {'median':>8s} {'p75':>8s} {'p90':>8s} {'p99':>8s} {'max':>8s}")
    for name, key in (("observed", "observed"), ("null 20/6", "null"),
                      ("obs core", "observed_core"), ("null core", "null_core")):
        s = d[key]
        print(f"{name:11s} {s['median']:8.3f} {s['p75']:8.3f} {s['p90']:8.3f} "
              f"{s['p99']:8.3f} {s['max']:8.3f}")
    pm = d["permutation"]
    print(f"\nper-fixture permutation p (uniform if the last six are just six of "
          f"the twenty-six):")
    print(f"  p<=0.10 {pm['share_p_le_0.10']:.1%} (10%)   "
          f"p<=0.05 {pm['share_p_le_0.05']:.1%} (5%)   "
          f"p<=0.01 {pm['share_p_le_0.01']:.1%} (1%)   mean p {pm['mean_p']:.3f}")
    print(f"  core:  p<=0.10 {pm['core_share_p_le_0.10']:.1%}   "
          f"p<=0.05 {pm['core_share_p_le_0.05']:.1%}   "
          f"p<=0.01 {pm['core_share_p_le_0.01']:.1%}")

    print("\nWHERE THE EXCESS LIVES")
    for label, v in out["by_window"].items():
        print(f"  {label:15s} n={v['n']:<5d} median {v['shift']['median']:.3f}"
              f"  p90 {v['shift']['p90']:.3f}   p<=.10 {v['share_p_le_0.10']:.1%}"
              f"  p<=.05 {v['share_p_le_0.05']:.1%}  p<=.01 {v['share_p_le_0.01']:.1%}")

    lc = out["league_common_component"]
    print(f"\nSHARE OF EACH METRIC'S SHIFT THAT IS THE WHOLE LEAGUE MOVING AT ONCE"
          f"  (noise floor {lc['noise_floor']:.1%})")
    print("  " + "  ".join(f"{k}={v:.1%}" for k, v in
                           lc["share_of_variance"].items()))

    om = out.get("opponent_mix")
    if om:
        print(f"\nIS IT THE FIXTURE LIST? opponent-mix shift median "
              f"{om['opp_shift']['median']:.3f}, correlation with the team's own "
              f"shift {om['corr_with_shift']:+.3f}")
        for n, t in enumerate(om["terciles"]):
            print(f"  opponents changed {['least', 'middling', 'most'][n]:<9s} "
                  f"(opp {t['opp_shift_median']:.3f})  team shift median "
                  f"{t['shift_median']:.3f}  p<=.05 {t['share_p_le_0.05']:.1%}")

    gc = out.get("game_state_confound")
    if gc:
        print(f"\nIS IT JUST THE SCORELINE? shift in the share of minutes spent "
              f"BEHIND: sd {gc['behind_share_shift_sd']:.3f}, "
              f"|state shift| vs composite r={gc['corr_with_composite']:+.3f}")
        print("  " + "  ".join(f"{k}={v:+.2f}" for k, v in
                               gc["corr_with_metric"].items()))

    print("\nTHE TWELVE BIGGEST, METRIC BY METRIC")
    print(f"  {'team':<17s}{'date':<12s}{'shift':>6s}  "
          + " ".join(f"{k[:6]:>6s}" for k in STYLE_KEYS))
    for f in out["top_fixtures"]:
        print(f"  {f['team']:<17s}{f['date']:<12s}{f['shift']:6.2f}  "
              + " ".join(f"{f['z'][k]:6.2f}" for k in STYLE_KEYS))

    print("\nPER METRIC (|short - long| in league-season sd)")
    print(f"  {'':14s} {'median':>7s} {'p90':>7s} {'p99':>7s} |{'observed':>9s}"
          f"{'noise':>8s}{'REAL':>8s}{'real var':>10s}")
    for k, v in out["per_metric"].items():
        s = out["signal_size"][k]
        print(f"  {k:14s} {v['median_abs_z']:7.3f} {v['p90_abs_z']:7.3f} "
              f"{v['p99_abs_z']:7.3f} |{s['observed_rms_sd']:9.3f}"
              f"{s['noise_rms_sd']:8.3f}{s['real_rms_sd']:8.3f}"
              f"{s['share_of_variance_real']:9.1%}")

    p = out["proxy"]
    print(f"\nTHE PROXY  (big = top decile, composite >= {p['big_threshold_p90']:.3f};"
          f" band = matches {lo}-{hi - 1} after a new manager's first game)")
    print(f"  of the {p['n_big']} big shifts, "
          f"{p['share_of_big_shifts_following_a_change']:.1%} follow a manager "
          f"change (base rate {p['base_rate_of_band_fixtures']:.1%})")
    print(f"     counting only changes where the new man got >= {SHORT_W} matches: "
          f"{p['share_of_big_shifts_following_a_substantive_change']:.1%} "
          f"(base rate {p['base_rate_of_substantive_band']:.1%})")
    print(f"  of the {p['n_changes_measurable']} measurable manager changes, "
          f"{p['share_of_changes_producing_a_big_shift']:.1%} produce a big shift")
    print(f"  band   median {p['band_distribution']['median']:.3f}  "
          f"p90 {p['band_distribution']['p90']:.3f}  n={p['band_distribution']['n']}"
          f"  mean p {p['band_mean_p']:.3f}  share p<=.05 {p['band_share_p_le_0.05']:.1%}")
    print(f"  quiet  median {p['quiet_distribution']['median']:.3f}  "
          f"p90 {p['quiet_distribution']['p90']:.3f}  n={p['quiet_distribution']['n']}"
          f"  mean p {p['quiet_mean_p']:.3f}  share p<=.05 {p['quiet_share_p_le_0.05']:.1%}")

    print("\nBIGGEST MEASURED SHIFTS AFTER A MANAGER CHANGE")
    for c in out["changes"][:18]:
        print(f"  {c['best']:6.3f} p={c['best_p']:.3f}  {c['team']:<16s} "
              f"{c['prev'][:17]:<18s} -> {c['manager'][:20]:<21s} {c['date']}"
              f"  ({c['spell_length']}m)")
    print("\nSMALLEST")
    for c in out["changes"][-10:]:
        print(f"  {c['best']:6.3f} p={c['best_p']:.3f}  {c['team']:<16s} "
              f"{c['prev'][:17]:<18s} -> {c['manager'][:20]:<21s} {c['date']}"
              f"  ({c['spell_length']}m)")

    print("\nNAMED CASES — changes whose direction was called before measuring")
    for c in out["named_changes"]:
        print(f"  {c['best']:6.3f} p={c['best_p']:.3f} pctile {c['percentile']:5.1f}"
              f"  {c['team']:<16s} {c['prev'][:16]:<17s} -> {c['manager'][:20]:<21s}"
              f" {c['date']}  ({c['spell_length']}m)")
    print("\nNAMED CASES — settled tenures (median shift, league median "
          f"{float(np.percentile(obs, 50)):.3f})")
    for t, v in out["named_stable"].items():
        print(f"  {v['median']:6.3f}  {t}  (n={v['n']}, p90 {v['p90']:.3f})")

    print("\nSHIFT BY MATCHES SINCE A NEW MANAGER'S FIRST GAME")
    for k, v in out["since_change_profile"].items():
        if int(k) <= 20:
            print(f"  +{int(k):<3d} n={v['n']:<5d} median {v['median']:.3f}"
                  f"  p90 {v['p90']:.3f}")

    print("\nSTEADIEST / LEAST STEADY TEAMS (median shift, settled fixtures)")
    ranked = sorted(out["stable_tenures"].items(), key=lambda kv: kv[1]["median"])
    for t, v in ranked[:7]:
        print(f"  {v['median']:6.3f}  {t}  (n={v['n']})")
    print("  ...")
    for t, v in ranked[-7:]:
        print(f"  {v['median']:6.3f}  {t}  (n={v['n']})")

    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
