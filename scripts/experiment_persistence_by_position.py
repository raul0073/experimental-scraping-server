"""Reliability and persistence WITHIN position — because a winger and a
centre-back are not doing the same job.

The pooled test was wrong: a left winger attempts 3.7 take-ons per 90, a
centre-back 0.28. Pooling them means most players in the sample barely
perform the action at all, so a "when behind" index divides a near-zero by
a near-zero and the result is arithmetic noise rather than a finding about
football.

Each position is therefore tested on the actions that position actually
performs, and compared only against its own kind.

    --split-half SEASON   does the metric agree with itself inside one
                          season (can we measure it at all?)
    default               does a player keep his ranking from one season
                          to the next (is it a trait?)

Usage: .venv/Scripts/python.exe scripts/experiment_persistence_by_position.py
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import scripts.experiment_persistence as E

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path.home() / "soccerdata" / "data" / "WhoScored" / "events"

# Opta position codes grouped by the job actually being done.
GROUPS = {
    "GK": "GK",
    "DC": "CB",
    "DL": "FB", "DR": "FB", "DML": "FB", "DMR": "FB",
    "DMC": "CM", "MC": "CM", "ML": "WM", "MR": "WM",
    "AMC": "AM",
    "AML": "WIDE", "AMR": "WIDE", "FWL": "WIDE", "FWR": "WIDE",
    "FW": "ST",
}
# what is worth asking of each group: a centre-back's intent is not a
# winger's, so they are not judged on the same actions
RELEVANT = {
    "WIDE": ["takeon_90", "takeon_behind_idx", "duel_90", "duel_behind_idx",
             "dispossessed_90", "pass_pct"],
    "AM":   ["takeon_90", "takeon_behind_idx", "duel_90", "duel_behind_idx",
             "dispossessed_90", "pass_pct"],
    "ST":   ["duel_90", "duel_behind_idx", "aerial_pct", "takeon_90",
             "dispossessed_90"],
    "CM":   ["pass_90", "pass_pct", "pass_pct_behind_idx", "duel_90",
             "duel_behind_idx", "recovery_90"],
    "FB":   ["takeon_90", "duel_90", "duel_behind_idx", "pass_pct",
             "recovery_90"],
    "CB":   ["duel_90", "duel_behind_idx", "aerial_pct", "pass_pct",
             "recovery_90", "foul_90"],
    "GK":   ["pass_90", "pass_pct"],
}


def position_map(league: str, season: str) -> dict:
    """A player's usual ROLE, from the line-ups in the match cache.

    Group each appearance first, THEN take the most common group — not the
    other way round. Domínguez started AML 6 times, MC 5 and DMC 4: his
    single most common position is wide, but he is plainly a central
    midfielder, and grouping last put him top of a winger ranking on duels
    while sitting in the 4th percentile for running at anyone."""
    counts = defaultdict(Counter)
    folder = CACHE / f"{league}_{season}"
    for path in folder.glob("*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for side in ("home", "away"):
            for p in d.get(side, {}).get("players", []):
                grp = GROUPS.get(p.get("position") or "")
                if grp:
                    counts[p["name"]][grp] += 1
    return {name: c.most_common(1)[0][0] for name, c in counts.items() if c}


def rho(x: pd.Series, y: pd.Series) -> tuple:
    ok = x.notna() & y.notna()
    n = int(ok.sum())
    if n < 20:
        return n, None
    return n, round(float(x[ok].rank().corr(y[ok].rank())), 3)


def report(title: str, pairs: dict, results: list) -> None:
    print(f"\n{title}")
    print(f"{'group':<7}{'metric':<22}{'n':>5}{'rho':>8}   verdict")
    print("-" * 66)
    for r in results:
        if r["rho"] is None:
            print(f"{r['group']:<7}{r['metric']:<22}{r['n']:>5}{'--':>8}   too few players")
            continue
        v = ("STRONG" if r["rho"] >= 0.6 else
             "moderate" if r["rho"] >= 0.4 else
             "weak" if r["rho"] >= 0.25 else
             "noise")
        print(f"{r['group']:<7}{r['metric']:<22}{r['n']:>5}{r['rho']:>8.3f}   {v}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--seasons", nargs=2, default=["2425", "2526"])
    ap.add_argument("--split-half", metavar="SEASON", default=None)
    args = ap.parse_args()
    raw = ROOT / "data" / "whoscored" / args.league

    if args.split_half:
        E.MIN_MINUTES = 450
        p = raw / f"{args.split_half}_stamped.parquet"
        a, b = E.season_table(p, "odd"), E.season_table(p, "even")
        pos = position_map(args.league, args.split_half)
        title = (f"CAN WE MEASURE IT? odd v even matches within "
                 f"{args.split_half}, by position")
    else:
        E.MIN_MINUTES = 900
        a = E.season_table(raw / f"{args.seasons[0]}_stamped.parquet")
        b = E.season_table(raw / f"{args.seasons[1]}_stamped.parquet")
        pos = position_map(args.league, args.seasons[0])
        title = (f"IS IT A TRAIT? {args.seasons[0]} v {args.seasons[1]}, "
                 f"by position")

    a["grp"] = a.index.map(pos)
    b["grp"] = b.index.map(pos)
    shared = a.index.intersection(b.index)

    results = []
    for grp in ["WIDE", "AM", "ST", "CM", "FB", "CB"]:
        players = [p for p in shared if a.at[p, "grp"] == grp]
        if len(players) < 20:
            continue
        for metric in RELEVANT.get(grp, []):
            if metric not in a.columns or metric not in b.columns:
                continue
            n, r = rho(a.loc[players, metric], b.loc[players, metric])
            results.append({"group": grp, "metric": metric, "n": n, "rho": r})

    report(title, {}, results)
    out = ROOT / "data" / "reports" / (
        "experiment_position_reliability.json" if args.split_half
        else "experiment_position_persistence.json")
    out.write_text(json.dumps({"league": args.league, "results": results},
                              indent=2), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
