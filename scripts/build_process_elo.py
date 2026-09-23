"""Process Elo — one rating spine for the predictor, updated on PROCESS.

The expanding-season-mean the experiments have been using has three faults,
and all three are structural rather than tuning problems: it resets every
August, it needs a hand-picked `PRIOR = 6` to seed the new season from the
old, and it needs a separate opponent-adjustment pass to stop a side being
flattered by an easy run. An online rating has none of those. It carries
across seasons because nothing tells it not to, it needs no seed because the
update IS the seed, and it is opponent-aware by construction because the
update is a surprise against a specific opponent.

WHY PROCESS AND NOT RESULTS. A standard Elo updates on the result. Results
are the noisiest thing on the pitch — a half-season of points predicts the
next half at 0.59, while the process metrics predict it at 0.78. Feeding the
rating the better signal is free.

THE FORM IS MULTIPLICATIVE, not additive, because the predictor needs a
SCORELINE and not just a winner:

    log lambda_home = A_home - D_away + HOME
    log lambda_away = A_away - D_home

so every rating is a log-multiplier on chances, and the pair of lambdas drops
straight into the Dixon-Coles grid the predictor already has. After a match
each rating moves by the log-residual — how far the chances actually created
were from what the ratings expected:

    A_home += K * log(actual_home / expected_home)
    D_away -= K * log(actual_home / expected_home)

A side that creates more than its rating said gains, and the defence that
allowed it loses exactly as much. Nothing is normalised afterwards; the home
term absorbs the level.

This is walk-forward BY CONSTRUCTION. A rating at any point has only ever
seen earlier matches, so there is no window to get wrong and no seed to leak
through — which is the other reason to prefer it to what it replaces.

Writes data/reports/process_elo.json   (the fit and how it scored)
       data/web/team/{league}/elo.json (current ratings, for the site)

Usage: .venv/Scripts/python.exe scripts/build_process_elo.py
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.mental.positions import load_match
from services.mental.role_bank import RAW, seasons_on_disk
from services.mental.team_metrics import match_rows
from services.mental.zones import CELLS, match_zones

# WHAT THE RATING IS FED. Chance ORIGINS say nothing about whether a chance
# was a tap-in or a thirty-yard hit, so fed origins the ratings compress and
# Arsenal against Manchester City projects much like Tottenham against Aston
# Villa. QUALITY-WEIGHTED observables fix that: big chances 1.0323 and
# Understat xG 1.0304, against origins' 1.0372 and box entries' 1.0456.
#
# AN EARLIER RUN OF THIS COMPARISON CONCLUDED THE OPPOSITE — that big
# chances were the worst of the four at 1.0631, and that volume beat
# weighting. That was an artefact of `conv` being gridded rather than
# solved. A big chance is worth about one goal in its own units and the grid
# stopped at 0.5, so the arm was forced to a level half of what it needed
# and lost on the handicap. Once conv is solved from the data the ordering
# inverts. The lesson is about the harness, not about football: a parameter
# that means "the level" must be fitted to the level, never to a criterion
# that is nearly blind to it.
#
# `xg` is the one observable not derived from our own event stream. It is
# Understat's, and it is the thing every other arm has lost to all week, so
# it is here to answer the last open question: is the shipped model ahead
# because of its INPUT or because of its STRUCTURE? Feed the online rating
# the same xG the shipped model uses and the two differ only in structure.
OBSERVABLE = {
    "origins": ("zone chance origins", None),
    "bigchance": ("big chances", "bigchance_op_90"),
    "shots": ("open-play shots", "shot_op_90"),
    "boxentry": ("box entries", "box_entry_op_90"),
    "xg": ("Understat xG", "__understat__"),
}


def _tokens(name: str) -> list:
    drop = ("fc", "afc", "cf")
    same = {"utd": "united"}
    return [same.get(w, w)
            for w in "".join(c if c.isalnum() else " " for c in name.lower()).split()
            if w not in drop]


def add_xg(df: pd.DataFrame, league: str) -> pd.DataFrame:
    """Join Understat's xG onto our matches, by date and aligned names.

    Two feeds, two spellings — "Leeds United" against "Leeds", "Manchester
    Utd" against "Man Utd" — so the same token rule as the crest and injury
    matchers does the joining, and an ambiguous name is dropped rather than
    guessed."""
    from services.understat.understat_service import UnderstatService

    ours = set(df["home"]) | set(df["away"])
    rows = {}
    for season in sorted(df["season"].unique()):
        try:
            us = UnderstatService.load(league, season)
        except Exception:
            continue
        theirs = {m["home_team"] for m in us["matches"]} | \
                 {m["away_team"] for m in us["matches"]}

        def fits(short, long):
            used = set()
            for w in short:
                hit = next((i for i, v in enumerate(long)
                            if i not in used and (v.startswith(w) or w.startswith(v))),
                           None)
                if hit is None:
                    return False
                used.add(hit)
            return True

        name = {}
        for a in theirs:
            if a in ours:
                name[a] = a
                continue
            ta = _tokens(a)
            hit = [b for b in ours if fits(ta, _tokens(b)) or fits(_tokens(b), ta)]
            if len(hit) == 1:
                name[a] = hit[0]
        for m in us["matches"]:
            if m.get("home_xg") is None:
                continue
            h, a = name.get(m["home_team"]), name.get(m["away_team"])
            if not h or not a:
                continue
            rows[(str(m["date"])[:10], h, a)] = (float(m["home_xg"]),
                                                 float(m["away_xg"]))
    xh, xa = [], []
    for r in df.itertuples(index=False):
        got = rows.get((str(r.kick)[:10], r.home, r.away))
        xh.append(got[0] if got else float("nan"))
        xa.append(got[1] if got else float("nan"))
    df = df.copy()
    df["xg_h"], df["xg_a"] = xh, xa
    have = df["xg_h"].notna().sum()
    print(f"  xG joined for {have} of {len(df)} matches "
          f"({100 * have / max(len(df), 1):.0f}%)")
    return df

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "process_elo.json"
OUT = ROOT / "data" / "web" / "team"
PUB = ROOT / "web" / "public" / "data" / "team"
CACHE = ROOT / "data" / "reports" / "_elo_matches.json"

OUTCOMES = ["H", "D", "A"]
MAX_GOALS = 8
# A club promoted this summer has no rating. Starting it at the league mean
# would call it average, which it is not; starting it at the bottom would be
# a guess. This is the measured gap — promoted sides create about 22% fewer
# chances than the league in their first season — applied once and then
# corrected by the ratings themselves within a few rounds.
PROMOTED = math.log(0.78)


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def matches_from_understat(league: str, seasons: list | None = None) -> pd.DataFrame:
    """The same frame, built from Understat alone.

    THIS IS WHAT MAKES THE RATING SHIPPABLE. The winning observable is
    Understat's xG, and Understat carries the date, both teams, the score and
    the xG pair — so none of the event stream is needed. The event data
    exists for one league and four seasons; Understat has THIRTEEN seasons of
    all five, which is about 4,500 matches a league to fit on instead of 380,
    and it is refreshed by the weekly run that already exists.

    The event-derived observables stay in `matches()` for the comparison that
    chose xG in the first place. Nothing that ships depends on them.
    """
    from services.understat.understat_service import UnderstatService

    folder = ROOT / "data" / "understat" / league
    have = sorted(p.stem for p in folder.glob("*.json")
                  if p.stem.isdigit() and len(p.stem) == 4)
    rows = []
    for season in (seasons or have):
        try:
            us = UnderstatService.load(league, season)
        except Exception:
            continue
        for m in us["matches"]:
            if m.get("home_goals") is None or m.get("home_xg") is None:
                continue
            hg, ag = int(m["home_goals"]), int(m["away_goals"])
            rows.append({
                "season": season, "game_id": m.get("understat_game_id"),
                "kick": str(m["date"])[:10],
                "home": m["home_team"], "away": m["away_team"],
                "hg": hg, "ag": ag,
                "xg_h": float(m["home_xg"]), "xg_a": float(m["away_xg"]),
                "y": "H" if hg > ag else ("A" if ag > hg else "D"),
            })
    df = pd.DataFrame(rows).sort_values("kick").reset_index(drop=True)
    print(f"  {league}: {len(df)} matches over "
          f"{df['season'].nunique() if len(df) else 0} seasons")
    return df


def matches(league: str, seasons: list) -> pd.DataFrame:
    """Every match in kickoff order: who, the chances each side created, the
    score. Chance ORIGINS, the same quantity the versus maps are built on —
    where the move that led to a shot began."""
    rows = []
    for season in seasons:
        df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
        for gid, m in df.groupby("game_id", sort=False):
            doc = load_match(league, season, gid)
            if doc is None:
                continue
            home = (doc.get("home") or {}).get("name")
            away = (doc.get("away") or {}).get("name")
            hg = ((doc.get("home") or {}).get("scores") or {}).get("fulltime")
            ag = ((doc.get("away") or {}).get("scores") or {}).get("fulltime")
            kick = doc.get("startTime") or doc.get("startDate") or ""
            if not home or not away or hg is None or ag is None or not kick:
                continue
            z = {r["team"]: r for r in match_zones(m)}
            mr = {r["team"]: r for r in match_rows(m)}
            if home not in z or away not in z:
                continue
            row = {
                "season": season, "game_id": int(gid), "kick": kick,
                "home": home, "away": away,
                "hg": int(hg), "ag": int(ag),
                "origins_h": float(sum(z[home][f"zo_{c}"] for c in CELLS)),
                "origins_a": float(sum(z[away][f"zo_{c}"] for c in CELLS)),
                "y": "H" if hg > ag else ("A" if ag > hg else "D"),
            }
            for key, (_label, col) in OBSERVABLE.items():
                if col and home in mr and away in mr:
                    row[f"{key}_h"] = float(mr[home].get(col) or 0.0)
                    row[f"{key}_a"] = float(mr[away].get(col) or 0.0)
            rows.append(row)
        print(f"  read {season}  ({len(rows)} matches)", flush=True)
    return pd.DataFrame(rows).sort_values("kick").reset_index(drop=True)


def walk(df: pd.DataFrame, k: float, home_adv: float, decay: float = 1.0,
         obs: str = "origins"):
    """Run the ratings through the season in order, recording each match's
    PRE-match state. Returns the per-fixture expectations plus the final
    table.

    `decay` pulls every rating a little way back toward the league mean at
    each season boundary. A squad turns over in the summer and a side is
    never quite the one that finished in May; without it, a rating built over
    four years is slower to accept that a club has changed than the evidence
    warrants."""
    A: dict = defaultdict(float)
    D: dict = defaultdict(float)
    seen: set = set()
    out = []
    season = None
    for r in df.itertuples(index=False):
        if season is not None and r.season != season:
            for t in A:
                A[t] *= decay
                D[t] *= decay
        season = r.season
        for t in (r.home, r.away):
            if t not in seen:
                # never rated before: promoted, or our data just started
                seen.add(t)
                if A[t] == 0.0 and D[t] == 0.0:
                    A[t], D[t] = PROMOTED, -PROMOTED
        lh = A[r.home] - D[r.away] + home_adv
        la = A[r.away] - D[r.home]
        out.append({
            "game_id": r.game_id, "season": r.season, "kick": r.kick,
            "home": r.home, "away": r.away, "y": r.y,
            "hg": r.hg, "ag": r.ag,
            "exp_hc": math.exp(lh), "exp_ac": math.exp(la),
            "A_home": A[r.home], "D_home": D[r.home],
            "A_away": A[r.away], "D_away": D[r.away],
        })
        # the surprise, in log terms; +0.5 keeps a blank afternoon finite
        hc = getattr(r, f"{obs}_h")
        ac = getattr(r, f"{obs}_a")
        # A match the observable does not cover — an xG feed that missed a
        # fixture — leaves the ratings where they were rather than moving
        # them on a nan. The expectation above is still recorded, so the
        # match is still scored; only the learning is skipped.
        if hc != hc or ac != ac:
            continue
        rh = math.log((hc + 0.5) / max(math.exp(lh), 1e-6))
        ra = math.log((ac + 0.5) / max(math.exp(la), 1e-6))
        A[r.home] += k * rh
        D[r.away] -= k * rh
        A[r.away] += k * ra
        D[r.home] -= k * ra
    return pd.DataFrame(out), A, D


def _dc_tau(h, a, lh, la, rho):
    """Dixon-Coles low-score correction — the one place a Poisson is plainly
    wrong about football is 0-0, 1-0, 0-1 and 1-1."""
    if h == 0 and a == 0:
        return 1 - lh * la * rho
    if h == 0 and a == 1:
        return 1 + lh * rho
    if h == 1 and a == 0:
        return 1 + la * rho
    if h == 1 and a == 1:
        return 1 - rho
    return 1.0


def grid(lh: float, la: float, rho: float) -> np.ndarray:
    ph = np.array([math.exp(-lh) * lh ** i / math.factorial(i)
                   for i in range(MAX_GOALS + 1)])
    pa = np.array([math.exp(-la) * la ** i / math.factorial(i)
                   for i in range(MAX_GOALS + 1)])
    g = np.outer(ph, pa)
    for h in range(2):
        for a in range(2):
            g[h, a] *= _dc_tau(h, a, lh, la, rho)
    return g / g.sum()


def outcome(lh: float, la: float, rho: float) -> np.ndarray:
    g = grid(lh, la, rho)
    return np.array([np.tril(g, -1).sum(), np.trace(g), np.triu(g, 1).sum()])


def score_arm(rows: pd.DataFrame, conv: float, rho: float) -> tuple:
    """Chances -> goals -> a scoreline distribution -> the triplet."""
    ix = {o: i for i, o in enumerate(OUTCOMES)}
    per = []
    probs = []
    for r in rows.itertuples(index=False):
        p = outcome(max(r.exp_hc * conv, 1e-3), max(r.exp_ac * conv, 1e-3), rho)
        p = np.clip(p, 1e-9, 1)
        probs.append(p)
        per.append(-math.log(p[ix[r.y]]))
    probs = np.array(probs)
    called = [OUTCOMES[i] for i in probs.argmax(axis=1)]
    return (float(np.mean(per)),
            float(np.mean([a == b for a, b in zip(called, rows["y"])])),
            probs, np.array(per))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--obs", default="origins", choices=list(OBSERVABLE))
    ap.add_argument("--compare", action="store_true",
                    help="fit every observable and print them side by side")
    args = ap.parse_args()
    seasons = seasons_on_disk(args.league)

    if args.cached and CACHE.exists():
        df = pd.read_json(CACHE, dtype={"season": str})
        df["season"] = df["season"].astype(str)
    else:
        df = matches(args.league, seasons)
        CACHE.write_text(df.to_json(orient="records"), encoding="utf-8")
    df = add_xg(df, args.league)
    print(f"{len(df)} matches, {df['season'].nunique()} seasons")

    # Everything is fitted on the seasons BEFORE the test one and never on
    # the test one. 26/27 is four rounds old and is carried so the shipped
    # ratings are current, but it is never scored.
    test_season = "2526"
    fit_rows = df[df["season"].isin([s for s in seasons if s < test_season])]
    if fit_rows.empty:
        print("nothing to fit on")
        return 1

    def fit_one(obs: str):
        """Grid the four parameters on the fit seasons only.

        `conv` ranges wide because it means different things per observable:
        a big chance is scored about four times in ten, a chance origin about
        one and a half."""
        best = None
        for k in (0.04, 0.08, 0.12, 0.16, 0.22, 0.28, 0.35):
            for home_adv in (0.05, 0.10, 0.15, 0.20):
                for decay in (1.0, 0.9, 0.8):
                    rows, _A, _D = walk(df, k, home_adv, decay, obs)
                    tr = rows[rows["season"].isin(fit_rows["season"].unique())]
                    # burn-in: the first rounds of the first season are
                    # ratings that have seen nothing, and fitting on them
                    # fits noise
                    tr = tr.iloc[40:]
                    if len(tr) < 100:
                        continue
                    # `conv` is SOLVED, not gridded. It means "goals per unit
                    # of the observable", so it is a pure level calibration —
                    # and log-loss is nearly blind to the level, because an
                    # outcome depends on the RATIO of the two lambdas. Fitted
                    # by log-loss it came out at 1.0 and the page projected
                    # 3.77 goals a game against an actual 2.75: every scoreline
                    # shown was a third too generous while the probabilities
                    # beside it were fine. Matching the mean fixes the level
                    # and leaves the ratio, which is what log-loss earned,
                    # untouched.
                    lam = (tr["exp_hc"] + tr["exp_ac"]).mean()
                    goals = (tr["hg"] + tr["ag"]).mean()
                    conv = float(goals / lam) if lam else 1.0
                    for rho in (0.0, -0.05, -0.10, -0.15):
                        ll, acc, _p, _per = score_arm(tr, conv, rho)
                        if best is None or ll < best[0]:
                            best = (ll, k, home_adv, decay, conv, rho, acc)
        return best

    if args.compare:
        print(f"\n{'observable':<12}{'train':>9}{'TEST':>9}{'acc':>8}"
              f"   K / home / decay / conv / rho")
        for name in OBSERVABLE:
            got = fit_one(name)
            if not got:
                continue
            _ll, k, h, dc, cv, rh, _a = got
            rows, _A, _D = walk(df, k, h, dc, name)
            te = rows[rows["season"] == test_season]
            t_ll, t_acc, _p, _per = score_arm(te, cv, rh)
            print(f"{name:<12}{_ll:>9.4f}{t_ll:>9.4f}{t_acc * 100:>7.1f}%"
                  f"   {k} / {h} / {dc} / {cv} / {rh}")
        return 0

    obs = args.obs
    best = fit_one(obs)
    ll, k, home_adv, decay, conv, rho, acc = best
    print(f"fitted on {sorted(fit_rows['season'].unique())} using "
          f"{OBSERVABLE[obs][0]}: K={k} home={home_adv} decay={decay} "
          f"conv={conv} rho={rho}  (train log-loss {ll:.4f})")

    rows, A, D = walk(df, k, home_adv, decay, obs)
    test = rows[rows["season"] == test_season]
    t_ll, t_acc, probs, per = score_arm(test, conv, rho)
    base = df[df["season"] < test_season]["y"].value_counts(normalize=True)
    b = np.array([base.get(o, 1 / 3) for o in OUTCOMES])
    b_ll = float(np.mean([-math.log(b[OUTCOMES.index(y)]) for y in test["y"]]))

    print()
    print(f"TEST {test_season}: n={len(test)}")
    print(f"  base rate       log-loss {b_ll:.4f}")
    print(f"  process Elo     log-loss {t_ll:.4f}   accuracy {t_acc * 100:.1f}%")

    # current ratings, for the site and for versus
    table = sorted(
        ({"team": t, "attack": round(A[t], 4), "defence": round(D[t], 4),
          "rating": round(A[t] + D[t], 4)} for t in A),
        key=lambda d: -d["rating"])
    # EVERY club we have ever rated ships, not only this season's twenty.
    # The versus page lets a reader pick any side that played in the period
    # they chose, so filtering to the current league silently removed the
    # projection for anyone relegated — Burnley against Liverpool simply had
    # no forecast and no explanation of why.
    current = set(df[df["season"] == seasons[-1]]["home"]) | \
        set(df[df["season"] == seasons[-1]]["away"])
    for t in table:
        t["current"] = t["team"] in current
    print()
    print("  current process Elo (attack + defence, log-chance units)")
    for t in table[:5]:
        print(f"    {t['team']:<20}{t['rating']:+.3f}  "
              f"att {t['attack']:+.3f}  def {t['defence']:+.3f}")
    print("    ...")
    for t in table[-3:]:
        print(f"    {t['team']:<20}{t['rating']:+.3f}  "
              f"att {t['attack']:+.3f}  def {t['defence']:+.3f}")

    params = {"k": k, "home_adv": home_adv, "decay": decay,
              "conv": conv, "rho": rho}
    report = {
        "league": args.league, "params": params,
        "fit_seasons": sorted(fit_rows["season"].unique().tolist()),
        "test_season": test_season, "n_test": int(len(test)),
        "base_log_loss": round(b_ll, 4),
        "log_loss": round(t_ll, 4), "accuracy": round(t_acc, 4),
        "table": table,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    lk = slug(args.league)
    for root in (OUT, PUB):
        (root / lk).mkdir(parents=True, exist_ok=True)
        (root / lk / "elo.json").write_text(
            json.dumps({"params": params, "table": table}, ensure_ascii=False),
            encoding="utf-8")
    print()
    print(f"-> {REPORT}")
    print(f"-> {OUT / lk / 'elo.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
