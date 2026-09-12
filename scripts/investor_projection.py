"""Season Monte Carlo for the flagship strategy (שיטה 2/4, four draw picks,
6 double lines x 10 units) across honest hit-rate and odds scenarios.

Grounding (validated in this repo, see progress.md):
- per-pick draw hit rate: 24.8% pooled base; 28.9% classifier-ranked backtest
  (5-league pool, 25/26 frozen); ~32% is the measured sport ceiling.
- draw hits are independent (week clustering tested random, overdisp ~1.0),
  so hits/window ~ Binomial(4, p).
- payout: lines_won = C(hits,2), each returns UNIT * o^2 (both legs at odds o).
- EV per window (analytic): stake * (p^2 * o^2 - 1) with stake = 6 * UNIT.
- odds band 2.65-3.15 was volunteered by the user; we never ingest odds feeds.

Usage: .venv/Scripts/python scripts/investor_projection.py
Writes data/reports/investor_projection.json and prints the grid.
"""
from __future__ import annotations

import json
from itertools import product
from math import comb
from pathlib import Path

import numpy as np

UNIT = 10.0
LEGS, K = 4, 2
LINES = comb(LEGS, K)          # 6
STAKE = LINES * UNIT           # 60 per window
START = 1000.0
N_SIM = 200_000
SEED = 7

P_GRID = [0.25, 0.29, 0.32]
O_GRID = [2.65, 2.90, 3.15]
W_GRID = [18, 30]

LINES_WON = np.array([comb(h, K) if h >= K else 0 for h in range(LEGS + 1)])


def simulate(p: float, o: float, windows: int, rng: np.random.Generator) -> dict:
    hits = rng.binomial(LEGS, p, size=(N_SIM, windows))
    pnl = LINES_WON[hits] * UNIT * o * o - STAKE
    cum = np.cumsum(pnl, axis=1) + START
    final = cum[:, -1]
    ruined = (cum < STAKE).any(axis=1)  # cannot fund the next full slip
    maxdd = (np.maximum.accumulate(cum, axis=1) - cum).max(axis=1)
    return {
        "p": p, "odds": o, "windows": windows,
        "ev_per_window": round(STAKE * (p * p * o * o - 1.0), 2),
        "ev_pct": round((p * o) ** 2 * 100 - 100, 1),
        "p_profit": round(float((final > START).mean()) * 100, 1),
        "p_ruin": round(float(ruined.mean()) * 100, 1),
        "final_median": round(float(np.median(final)), 0),
        "final_p5": round(float(np.percentile(final, 5)), 0),
        "final_p95": round(float(np.percentile(final, 95)), 0),
        "maxdd_median": round(float(np.median(maxdd)), 0),
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    rows = [simulate(p, o, w, rng) for w, p, o in product(W_GRID, P_GRID, O_GRID)]
    out = {
        "unit": UNIT, "stake_per_window": STAKE, "start_pot": START,
        "n_sim": N_SIM, "seed": SEED,
        "breakeven_odds_per_p": {str(p): round(1 / p, 2) for p in P_GRID},
        "gold_home_breakeven": round(1 / 0.66, 2),
        "rows": rows,
    }
    path = Path("data/reports/investor_projection.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"{'W':>3} {'p':>5} {'odds':>5} | {'EV/win':>7} {'EV%':>6} | "
          f"{'P(profit)':>9} {'P(ruin)':>7} | {'med':>6} {'p5':>6} {'p95':>6} | {'medDD':>6}")
    for r in rows:
        print(f"{r['windows']:>3} {r['p']:>5} {r['odds']:>5} | {r['ev_per_window']:>7} {r['ev_pct']:>6} | "
              f"{r['p_profit']:>8}% {r['p_ruin']:>6}% | {r['final_median']:>6.0f} {r['final_p5']:>6.0f} "
              f"{r['final_p95']:>6.0f} | {r['maxdd_median']:>6.0f}")
    print(f"\nbreakeven odds: {out['breakeven_odds_per_p']}  gold-home breakeven: {out['gold_home_breakeven']}")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
