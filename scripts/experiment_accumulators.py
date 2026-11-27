"""Accumulators of the model's strongest calls, against four draws a week.
Eight seasons, walk-forward, at fair prices and at what the book paid.

THE QUESTIONS (user, 2026-11-27):
  1. How many legs of an accumulator of the model's best calls actually win?
  2. Where should the cap on accumulator size sit?
  3. Is four draws a week on שיטה 2/4 the most profitable structure overall?

THE DATA. data/reports/_walk_forward_rows.csv: every fixture of 1819..2526
in five leagues priced by the shipped blend, each season by a model that
never saw it. Joined to football-data.co.uk closing odds (Pinnacle closing
where present, market-average closing otherwise) - the same join as
build_market.py. "Fair" = 1/p at the model's own probability, which is the
only price this project will quote. "Book" = the closing odds as listed,
margin included, which is what a slip actually pays. Both are shown
because the user bets at a book and the project prices at fair.

THE STRUCTURES, one ticket a week, weeks = ISO weeks pooled across leagues,
no team twice on a ticket:
  acca N        the N most confident calls (largest probability), one
                combined line; N = 1..8; stake 1 unit a week
  acca N @55    the same, drawn only from calls at >= 55%
  system 2/N    every double among the N strongest calls (Winner שיטה 2/N),
                1 unit a line
  draws 2/4     the four likeliest draws, six doubles, 1 unit a line - the
                monkey's mandate
  draws 3/4     the same four, four trebles
  draws 1/4     the four as singles

THE MEASURES, per structure over all weeks: units staked, units returned
at fair and at book, ROI at each, share of weeks in profit, worst
drawdown in units, and for accumulators the distribution of legs landed
(mean, and how often all N land, against the probability the model
implied). Ties and cut lines are deterministic.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\experiment_accumulators.py
Writes data/reports/experiment_accumulators.{json,md}. Changes nothing.
"""
import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from build_market import OddsIndex, PROJECT_NAMES, WF_ROWS, load_odds   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_accumulators.json"
REPORT_MD = ROOT / "data" / "reports" / "experiment_accumulators.md"
SIDES = ["home", "draw", "away"]
YI = {"H": "home", "D": "draw", "A": "away"}
ODDS = {"home": "o_home", "draw": "o_draw", "away": "o_away"}
MAX_N = 8


def load_rows() -> list:
    project_map = json.loads(PROJECT_NAMES.read_text(encoding="utf-8"))
    idx = OddsIndex(load_odds(no_download=True, project_map=project_map))
    with WF_ROWS.open(encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    rows = []
    for r in raw:
        pm = project_map.get(r["league"], {})
        hit = idx.find(r["league"], pm.get(r["home"], r["home"]), pm.get(r["away"], r["away"]), r["date"])
        if hit is None:
            continue
        p = {s: float(r[f"blend_{s[0].upper()}"]) for s in SIDES}
        d = dt.date.fromisoformat(r["date"])
        iso = d.isocalendar()
        rows.append({"season": r["season"], "league": r["league"], "week": f"{iso[0]}-{iso[1]:02d}",
                     "home": r["home"], "away": r["away"], "y": YI[r["y"]], "p": p,
                     "o": {s: float(getattr(hit, ODDS[s])) for s in SIDES}})
    return rows


# ------------------------------------------------------------------ tickets

def strongest(week_rows: list, n: int, min_p: float = 0.0) -> list:
    """The n most confident calls of the week, no team twice."""
    cands = sorted(week_rows, key=lambda r: -max(r["p"].values()))
    out, used = [], set()
    for r in cands:
        side = max(r["p"], key=r["p"].get)
        if r["p"][side] < min_p or r["home"] in used or r["away"] in used:
            continue
        used.update((r["home"], r["away"]))
        out.append((r, side))
        if len(out) == n:
            break
    return out


def top_draws(week_rows: list, n: int = 4) -> list:
    cands = sorted(week_rows, key=lambda r: -r["p"]["draw"])
    out, used = [], set()
    for r in cands:
        if r["home"] in used or r["away"] in used:
            continue
        used.update((r["home"], r["away"]))
        out.append((r, "draw"))
        if len(out) == n:
            break
    return out


def leg(r, side):
    return {"hit": r["y"] == side, "p": r["p"][side], "fair": 1.0 / r["p"][side], "book": r["o"][side]}


def settle_system(legs: list, k: int) -> dict:
    """Every k-fold among the legs, 1 unit a line, at fair and at book."""
    lines = list(combinations(legs, k))
    stake = len(lines)
    fair = sum(np.prod([l["fair"] for l in c]) for c in lines if all(l["hit"] for l in c))
    book = sum(np.prod([l["book"] for l in c]) for c in lines if all(l["hit"] for l in c))
    return {"stake": stake, "fair": float(fair), "book": float(book)}


# ------------------------------------------------------------------ scoring

def summarise(name: str, weeks: list) -> dict:
    """weeks: list of {stake, fair, book, hits, n, p_all}"""
    stake = sum(w["stake"] for w in weeks)
    fair = sum(w["fair"] for w in weeks)
    book = sum(w["book"] for w in weeks)
    profit_weeks = sum(1 for w in weeks if w["book"] > w["stake"])
    bal, peak, dd = 0.0, 0.0, 0.0
    for w in weeks:
        bal += w["book"] - w["stake"]
        peak = max(peak, bal)
        dd = min(dd, bal - peak)
    out = {"weeks": len(weeks), "staked": stake,
           "roi_fair": round(fair / stake - 1, 4) if stake else None,
           "roi_book": round(book / stake - 1, 4) if stake else None,
           "weeks_in_profit": round(profit_weeks / len(weeks), 4) if weeks else None,
           "worst_drawdown_units": round(dd, 1)}
    if weeks and "hits" in weeks[0]:
        hits = np.array([w["hits"] for w in weeks])
        n = weeks[0]["n"]
        out.update({"legs": n, "mean_legs_landed": round(float(hits.mean()), 3),
                    "all_landed": round(float((hits == n).mean()), 4),
                    "all_landed_expected": round(float(np.mean([w["p_all"] for w in weeks])), 4),
                    "legs_landed_dist": {int(k): int(v) for k, v in zip(*np.unique(hits, return_counts=True))}})
    return out


def main() -> int:
    print("rows + closing odds ...", flush=True)
    rows = load_rows()
    by_week = defaultdict(list)
    for r in rows:
        by_week[(r["season"], r["week"])].append(r)
    weeks = [k for k in sorted(by_week) if len(by_week[k]) >= 10]
    print(f"  {len(rows)} fixtures, {len(weeks)} weeks with 10+ fixtures", flush=True)

    results, per_leg = {}, {}
    # accumulators of the strongest calls
    for min_p, tag in ((0.0, ""), (0.55, " @55")):
        for n in range(1, MAX_N + 1):
            wk = []
            for key in weeks:
                legs = [leg(r, s) for r, s in strongest(by_week[key], n, min_p)]
                if len(legs) < n:
                    continue
                hits = sum(l["hit"] for l in legs)
                allhit = hits == n
                wk.append({"stake": 1.0, "n": n, "hits": hits,
                           "p_all": float(np.prod([l["p"] for l in legs])),
                           "fair": float(np.prod([l["fair"] for l in legs])) if allhit else 0.0,
                           "book": float(np.prod([l["book"] for l in legs])) if allhit else 0.0})
            results[f"acca {n}{tag}"] = summarise(f"acca {n}{tag}", wk)
    # per-leg truth for the strongest calls: realised against stated, by rank
    for n in (1, 2, 3, 4, 6, 8):
        ls = [leg(r, s) for key in weeks for r, s in strongest(by_week[key], n)]
        per_leg[f"top {n}"] = {"legs": len(ls), "stated": round(float(np.mean([l["p"] for l in ls])), 4),
                               "landed": round(float(np.mean([l["hit"] for l in ls])), 4),
                               "book_roi_singles": round(float(np.mean([l["book"] if l["hit"] else 0 for l in ls])) - 1, 4)}
    # systems 2/N on strong calls
    for n in (3, 4, 5):
        wk = []
        for key in weeks:
            legs = [leg(r, s) for r, s in strongest(by_week[key], n)]
            if len(legs) < n:
                continue
            wk.append(settle_system(legs, 2))
        results[f"system 2/{n} strong"] = summarise(f"system 2/{n}", wk)
    # draws
    for k, label in ((1, "draws 1/4 (singles)"), (2, "draws 2/4"), (3, "draws 3/4"), (4, "draws 4/4")):
        wk = []
        for key in weeks:
            legs = [leg(r, s) for r, s in top_draws(by_week[key], 4)]
            if len(legs) < 4:
                continue
            s = settle_system(legs, k)
            s.update({"n": 4, "hits": sum(l["hit"] for l in legs), "p_all": float(np.prod([l["p"] for l in legs]))})
            wk.append(s)
        results[label] = summarise(label, wk)
    ls = [leg(r, s) for key in weeks for r, s in top_draws(by_week[key], 4)]
    per_leg["top 4 draws"] = {"legs": len(ls), "stated": round(float(np.mean([l["p"] for l in ls])), 4),
                              "landed": round(float(np.mean([l["hit"] for l in ls])), 4),
                              "book_roi_singles": round(float(np.mean([l["book"] if l["hit"] else 0 for l in ls])) - 1, 4)}

    REPORT.write_text(json.dumps({"weeks": len(weeks), "fixtures": len(rows), "results": results,
                                  "per_leg": per_leg}, indent=2), encoding="utf-8")
    L = ["# Accumulators of the strongest calls against four draws a week", "",
         f"{len(rows)} fixtures, {len(weeks)} betting weeks, 1819..2526, walk-forward. One ticket a week. "
         "Fair = 1/p at the model's probability. Book = closing odds as listed, margin included.", "",
         "## Per leg: what the strongest calls are worth", "",
         "| pool | legs | stated | landed | ROI as singles at book |", "|---|---|---|---|---|"]
    for k, v in per_leg.items():
        L.append(f"| {k} | {v['legs']} | {v['stated']:.1%} | {v['landed']:.1%} | {v['book_roi_singles']:+.1%} |")
    L += ["", "## Structures", "",
          "| structure | weeks | legs landed (mean) | all landed | model said | ROI fair | ROI book | weeks in profit | worst drawdown |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in results.items():
        L.append(f"| {k} | {v['weeks']} | {v.get('mean_legs_landed', '')} | "
                 f"{v['all_landed']:.1%} | {v['all_landed_expected']:.1%} | " if 'all_landed' in v else
                 f"| {k} | {v['weeks']} |  |  |  | ")
        L[-1] += f"{v['roi_fair']:+.1%} | {v['roi_book']:+.1%} | {v['weeks_in_profit']:.0%} | {v['worst_drawdown_units']} |"
    L += ["", "## Legs landed, distribution (weeks)", ""]
    for k, v in results.items():
        if "legs_landed_dist" in v:
            L.append(f"- {k}: " + ", ".join(f"{h} of {v['legs']}: {c}" for h, c in sorted(v["legs_landed_dist"].items())))
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
