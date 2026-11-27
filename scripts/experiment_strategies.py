"""Which betting strategy makes sense for this model? A grid, eight seasons,
walk-forward, scored the way a bankroll feels it.

THE QUESTION (user, 2026-11-27): the draw 2/4 at this week's prices has a
+7% expectation and finishes a season anywhere between 350 and 2,100 from
1,000. Is there a selection, structure and stake for THIS model that gives
a better typical season with a bad season one can survive?

"MAKES SENSE" IS DEFINED, so the search cannot find a lottery ticket:
    rank by expected LOG growth over a 34-week season from a 1,000 bankroll
    (positive expectation rewarded, variance punished, ruin punished hard),
    and report the median and 10th-percentile season end beside it.

TWO PRICE REGIMES, because the answer flips between them:
    closing      football-data.co.uk closing odds as listed (Pinnacle where
                 present, market average otherwise): 3-5% margin
    winner-like  an ASSUMPTION from the eight Winner prices the user showed
                 on 2026-11-27: draws paid ~3% OVER fair (3.20-3.30 against
                 3.11-3.17), favourites 5-21% UNDER (1.15-1.25 against
                 1.32-1.51), so: closing x 1.03 on draws, x 0.87 on legs the
                 market makes >= 50%, x 0.92 otherwise. To be replaced by
                 measured Winner prices as the user supplies them.

THE GRID, one ticket a week over the 292 weeks of 1819..2526:
    pools        draws: top n by P(draw), n in 3..6, floor 0 / .30 / .31 / .32
                 strongest: top n by max probability, n in 2..5, floor
                 .55 / .60 / .65 (home/away/draw alike)
    structures   singles, every k-of-n system, the n-fold
    staking      60 a week split evenly over the lines; and 10 a line
    bankroll     1,000, flat stakes (no compounding; a stake the bankroll
                 cannot cover is skipped and the season counts as busted)

SEASONS are the eight real ones (weeks in order); for the spread, 4,000
bootstrap seasons of 34 weeks drawn from all 292.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\experiment_strategies.py
Writes data/reports/experiment_strategies.{json,md}. Changes nothing.
"""
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from experiment_accumulators import load_rows   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_strategies.json"
REPORT_MD = ROOT / "data" / "reports" / "experiment_strategies.md"
BANKROLL = 1000.0
SEASON_WEEKS = 34
BOOTS = 4000
WINNER = {"draw_mult": 1.03, "fav_mult": 0.87, "dog_mult": 0.92, "fav_from": 0.50}


def winner_price(closing: float, side: str, p_market: float) -> float:
    if side == "draw":
        return closing * WINNER["draw_mult"]
    return closing * (WINNER["fav_mult"] if p_market >= WINNER["fav_from"] else WINNER["dog_mult"])


# ------------------------------------------------------------------ tickets

def pool_draws(week_rows, n, floor):
    cands = sorted(week_rows, key=lambda r: -r["p"]["draw"])
    out, used = [], set()
    for r in cands:
        if r["p"]["draw"] < floor:
            break
        if r["home"] in used or r["away"] in used:
            continue
        used.update((r["home"], r["away"]))
        out.append((r, "draw"))
        if len(out) == n:
            break
    return out


def pool_strong(week_rows, n, floor):
    cands = sorted(week_rows, key=lambda r: -max(r["p"].values()))
    out, used = [], set()
    for r in cands:
        side = max(r["p"], key=r["p"].get)
        if r["p"][side] < floor:
            break
        if r["home"] in used or r["away"] in used:
            continue
        used.update((r["home"], r["away"]))
        out.append((r, side))
        if len(out) == n:
            break
    return out


def settle(legs, k, prices):
    """Return multiple of ONE unit per line: (lines, units returned)."""
    lines = list(combinations(range(len(legs)), k))
    ret = 0.0
    for c in lines:
        if all(legs[i]["hit"] for i in c):
            ret += float(np.prod([prices[i] for i in c]))
    return len(lines), ret


def week_results(by_week, weeks, pool_fn, n, floor, k, regime):
    """Per week: (stake_lines, return_units) at 1 unit a line; None when the
    pool was short (the strategy sits out)."""
    out = []
    for key in weeks:
        picks = pool_fn(by_week[key], n, floor)
        if len(picks) < n:
            out.append(None)
            continue
        legs, prices = [], []
        for r, side in picks:
            o = r["o"][side]
            inv = sum(1 / v for v in r["o"].values())
            p_mkt = (1 / o) / inv
            price = o if regime == "closing" else winner_price(o, side, p_mkt)
            legs.append({"hit": r["y"] == side, "p": r["p"][side]})
            prices.append(price)
        out.append(settle(legs, k, prices))
    return out


# ------------------------------------------------------------------ scoring

def season_paths(results, stake_mode, rng):
    """P&L series per week at the chosen staking, then: real seasons (by
    calendar order of the 292 weeks, split into 8 blocks) and bootstrap
    seasons of SEASON_WEEKS weeks."""
    pnl = []
    for r in results:
        if r is None:
            pnl.append(0.0)
            continue
        lines, ret_units = r
        unit = 60.0 / lines if stake_mode == "60/week" else 10.0
        pnl.append(ret_units * unit - lines * unit)
    pnl = np.array(pnl)
    idx = rng.integers(0, len(pnl), size=(BOOTS, SEASON_WEEKS))
    boot = BANKROLL + pnl[idx].cumsum(axis=1)
    busted = (boot <= 0).any(axis=1)
    end = np.where(busted, 0.0, boot[:, -1])
    with np.errstate(divide="ignore"):
        logg = np.where(end > 0, np.log(np.maximum(end, 1e-9) / BANKROLL), -5.0)
    staked = sum((60.0 if stake_mode == "60/week" else 10.0 * r[0]) for r in results if r)
    returned = sum((r[1] * (60.0 / r[0]) if stake_mode == "60/week" else r[1] * 10.0) for r in results if r)
    return {
        "roi": round(returned / staked - 1, 4) if staked else None,
        "weeks_bet": int(sum(1 for r in results if r)),
        "weeks_profit": round(float(np.mean([x > 0 for x in pnl])), 4),
        "log_growth": round(float(logg.mean()), 4),
        "median_end": round(float(np.median(end)), 0),
        "p10_end": round(float(np.percentile(end, 10)), 0),
        "p90_end": round(float(np.percentile(end, 90)), 0),
        "p_season_up": round(float((end > BANKROLL).mean()), 4),
        "p_bust": round(float(busted.mean()), 4),
        "worst_week": round(float(pnl.min()), 1),
        "best_week": round(float(pnl.max()), 1),
    }


def main() -> int:
    print("rows + closing odds ...", flush=True)
    rows = load_rows()
    by_week = defaultdict(list)
    for r in rows:
        by_week[(r["season"], r["week"])].append(r)
    weeks = [k for k in sorted(by_week) if len(by_week[k]) >= 10]
    print(f"  {len(rows)} fixtures, {len(weeks)} weeks", flush=True)
    rng = np.random.default_rng(0)

    grid = []
    for n in (3, 4, 5, 6):
        for floor in (0.0, 0.30, 0.31, 0.32):
            for k in range(1, n + 1):
                grid.append(("draws", n, floor, k))
    for n in (2, 3, 4, 5):
        for floor in (0.55, 0.60, 0.65):
            for k in range(1, n + 1):
                grid.append(("strong", n, floor, k))

    results = []
    for pool, n, floor, k in grid:
        fn = pool_draws if pool == "draws" else pool_strong
        for regime in ("closing", "winner-like"):
            wr = week_results(by_week, weeks, fn, n, floor, k, regime)
            if sum(1 for r in wr if r) < 100:
                continue
            for stake_mode in ("60/week", "10/line"):
                sc = season_paths(wr, stake_mode, rng)
                name = f"{pool} top{n}{'' if floor == 0 else f' >={floor:.2f}'} · {'singles' if k == 1 else (f'{n}-fold' if k == n else f'system {k}/{n}')}"
                results.append({"strategy": name, "pool": pool, "n": n, "floor": floor, "k": k,
                                "regime": regime, "stake": stake_mode, **sc})
        print(f"  {pool} n={n} floor={floor} k={k} done", flush=True)

    REPORT.write_text(json.dumps({"bankroll": BANKROLL, "season_weeks": SEASON_WEEKS, "winner_assumption": WINNER,
                                  "results": results}, indent=1), encoding="utf-8")
    L = ["# Which strategy makes sense for this model", "",
         f"{len(rows)} fixtures, {len(weeks)} weeks, 1819..2526, walk-forward. Bankroll {BANKROLL:.0f}, "
         f"{SEASON_WEEKS}-week seasons bootstrapped {BOOTS} times from all weeks. Ranked by expected log growth "
         "(positive expectation rewarded, variance and ruin punished).", "",
         f"Winner-like regime is an ASSUMPTION from eight prices seen on 2026-11-27: {WINNER}.", ""]
    for regime in ("winner-like", "closing"):
        for stake_mode in ("60/week", "10/line"):
            sub = sorted([r for r in results if r["regime"] == regime and r["stake"] == stake_mode],
                         key=lambda r: -r["log_growth"])
            L += [f"## {regime} prices, {stake_mode}", "",
                  "| strategy | ROI | weeks bet | week in profit | median end | 10th pct | 90th pct | season up | bust |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for r in sub[:12]:
                L.append(f"| {r['strategy']} | {r['roi']:+.1%} | {r['weeks_bet']} | {r['weeks_profit']:.0%} | {r['median_end']:.0f} | "
                         f"{r['p10_end']:.0f} | {r['p90_end']:.0f} | {r['p_season_up']:.0%} | {r['p_bust']:.1%} |")
            L += ["", "worst five by the same measure:", ""]
            for r in sub[-5:]:
                L.append(f"- {r['strategy']}: ROI {r['roi']:+.1%}, median end {r['median_end']:.0f}, bust {r['p_bust']:.1%}")
            L.append("")
    # the reference: draws top4 system 2/4 in each regime
    L += ["## The current mandate, for reference (draws top4 · system 2/4)", "",
          "| regime | stake | ROI | median end | 10th | 90th | season up |", "|---|---|---|---|---|---|---|"]
    for r in results:
        if r["pool"] == "draws" and r["n"] == 4 and r["floor"] == 0.0 and r["k"] == 2:
            L.append(f"| {r['regime']} | {r['stake']} | {r['roi']:+.1%} | {r['median_end']:.0f} | {r['p10_end']:.0f} | {r['p90_end']:.0f} | {r['p_season_up']:.0%} |")
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:40]))
    print(f"\n-> {REPORT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
