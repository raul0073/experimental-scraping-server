"""Gated experiment: does the draw classifier improve with per-league terms?

Serie A and Ligue 1 draw at structurally different base rates; the pooled
model may be leaving intercept on the table. Variant = logistic + 4 league
one-hot dummies (ENG reference). Same frozen protocol as every model change:
train on past seasons, evaluate walk-forward on 25/26, product metric =
top-4-per-week pick hit rate, plus log-loss.

Usage: .venv/Scripts/python scripts/experiment_league_terms.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from experiment_draw_models import (LEAGUE_IDX, SEASONS_LONG, SEASONS_SHORT,
                                    build_xy, eval_samples, simulate)


def onehot(idx_col):
    d = np.zeros((len(idx_col), len(LEAGUE_IDX) - 1))
    for r, i in enumerate(idx_col.astype(int)):
        if i > 0:  # league 0 = reference
            d[r, i - 1] = 1.0
    return d


def logloss(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def main() -> int:
    from sklearn.linear_model import LogisticRegression

    rows = eval_samples()
    ye = np.array([1.0 if r["draw"] else 0.0 for r in rows])
    Xe_base = np.array([r["f"] for r in rows])
    Xe_lg = np.hstack([Xe_base, onehot(np.array([LEAGUE_IDX[r["league"]] for r in rows]))])
    print(f"eval rows: {len(rows)}", flush=True)

    for depth, seasons in (("4s", SEASONS_SHORT), ("11s", SEASONS_LONG)):
        Xl, y = build_xy(seasons, with_league=True)
        X = Xl[:, :-1]
        Xd = np.hstack([X, onehot(Xl[:, -1])])
        for label, Xtr, Xev in (("base ", X, Xe_base), ("+lg  ", Xd, Xe_lg)):
            mean, std = Xtr.mean(axis=0), Xtr.std(axis=0) + 1e-9
            clf = LogisticRegression(max_iter=2000, C=10.0)
            clf.fit((Xtr - mean) / std, y)
            probs = clf.predict_proba((Xev - mean) / std)[:, 1]
            hits, total, dist = simulate(rows, probs)
            print(f"{label}/{depth} (n={len(y)}): picks {hits}/{total} = {hits / total:.1%}  "
                  f"logloss {logloss(ye, probs):.5f}  dist {sorted(dist.items())}", flush=True)
    print("\nGATE: keep league terms only if picks AND logloss are no worse, "
          "and at least one is clearly better.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
