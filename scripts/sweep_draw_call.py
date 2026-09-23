"""Where should DRAW_CALL_MIN sit, on 1,714 fixtures instead of 194?

THE RULE IT IS TUNING. A pure argmax essentially never says draw — draws cap
around 32-35% of probability while a win side spreads past 36% — so the
model would report a ~26%-draw sport as having almost none. The rule is:
once P(draw) reaches a threshold, the call is a draw regardless of argmax.

WHY IT NEEDED REDOING. The shipped 0.32 was swept on the 194 graded live
rows available in September, and the write-up noted a suspicious cliff —
0.30 supposedly costing six points of accuracy. A six-point cliff between
adjacent thresholds is what a sample of 194 looks like when it is asked a
question it is too small to answer, not what a real decision boundary looks
like. These are the same 1,714 walk-forward fixtures the arm comparison
used, and they are priced by the model that now ships.

WHAT COUNTS AS BETTER. Two things in tension: calling more draws costs
overall accuracy (a draw call is usually overruling a favourite that is more
likely than not to win), and calling too few makes the draw picks scarce.
The threshold is chosen as the LOWEST one whose draw calls still beat the
base draw rate by a clear margin while overall accuracy stays within a
tolerance of its peak — lowest, because the product needs four draw calls a
week and a threshold that yields two is useless however pure it is.

Reads  data/reports/_draw_arms_rows.csv (written by
       experiment_draw_arms_all.py)
Writes data/reports/sweep_draw_call.json

Usage: .venv/Scripts/python.exe scripts/sweep_draw_call.py [--arm layer]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
ROWS = ROOT / "data" / "reports" / "_draw_arms_rows.csv"
REPORT = ROOT / "data" / "reports" / "sweep_draw_call.json"
OUTCOMES = ["H", "D", "A"]
# how much overall accuracy we are willing to give up against the best
# threshold on the grid, in percentage points
ACC_TOLERANCE = 0.005
# a draw rule that fires less often than this over a season is not a product
MIN_CALL_RATE = 0.08


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="layer",
                    help="which arm's probabilities to sweep (default: the "
                         "one that ships)")
    args = ap.parse_args()

    if not ROWS.exists():
        print(f"no rows at {ROWS} — run experiment_draw_arms_all.py first")
        return 1
    d = pd.read_csv(ROWS)
    arm = args.arm
    cols = [f"{arm}_{o}" for o in OUTCOMES]
    if any(c not in d.columns for c in cols):
        print(f"arm '{arm}' not in the rows file")
        return 1

    p = d[cols].values
    truth = np.array([OUTCOMES.index(v) for v in d["y"]])
    is_draw = (truth == 1).astype(float)
    base = float(is_draw.mean())
    argmax = p.argmax(axis=1)

    grid = [round(x, 2) for x in np.arange(0.20, 0.45, 0.01)]
    out = []
    for t in grid:
        fires = p[:, 1] >= t
        call = np.where(fires, 1, argmax)
        acc = float((call == truth).mean())
        n = int(fires.sum())
        hit = float(is_draw[fires].mean()) if n else 0.0
        pv = (stats.binomtest(int(is_draw[fires].sum()), n, base,
                              alternative="greater").pvalue if n else 1.0)
        out.append({
            "threshold": t, "accuracy": round(acc, 4),
            "draw_calls": n, "call_rate": round(n / len(d), 4),
            "draw_call_hit": round(hit, 4),
            "lift_over_base": round(hit - base, 4),
            "p_better": round(float(pv), 4),
        })

    best_acc = max(r["accuracy"] for r in out)
    ok = [r for r in out
          if r["accuracy"] >= best_acc - ACC_TOLERANCE
          and r["call_rate"] >= MIN_CALL_RATE
          and r["lift_over_base"] > 0]
    chosen = min(ok, key=lambda r: r["threshold"]) if ok else None

    print(f"arm={arm}  n={len(d):,}  base draw rate {base:.1%}  "
          f"argmax-only accuracy {float((argmax == truth).mean()):.1%}\n")
    print(f"{'thr':>6}{'acc':>9}{'calls':>8}{'rate':>8}{'hit':>9}"
          f"{'lift':>8}{'p':>9}")
    for r in out:
        mark = " <-" if chosen and r["threshold"] == chosen["threshold"] else ""
        print(f"{r['threshold']:>6.2f}{r['accuracy'] * 100:>8.1f}%"
              f"{r['draw_calls']:>8}{r['call_rate'] * 100:>7.1f}%"
              f"{r['draw_call_hit'] * 100:>8.1f}%{r['lift_over_base'] * 100:>+8.1f}"
              f"{r['p_better']:>9.4f}{mark}")

    if chosen:
        print(f"\nchosen {chosen['threshold']:.2f} — accuracy "
              f"{chosen['accuracy'] * 100:.1f}% (best on grid "
              f"{best_acc * 100:.1f}%), {chosen['draw_calls']} draw calls "
              f"hitting {chosen['draw_call_hit'] * 100:.1f}% vs {base * 100:.1f}% base")
    else:
        print("\nno threshold satisfies the criteria")

    REPORT.write_text(json.dumps({
        "arm": arm, "n": int(len(d)), "base_draw_rate": round(base, 4),
        "acc_tolerance": ACC_TOLERANCE, "min_call_rate": MIN_CALL_RATE,
        "argmax_accuracy": round(float((argmax == truth).mean()), 4),
        "chosen": chosen, "grid": out,
    }, indent=2), encoding="utf-8")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
