"""Which arm RANKS draws best — the question the log-loss table cannot answer.

The walk-forward scores each arm on the full 1X2 triplet, which is the right
test for "is this model good". It is the wrong test for how this model is
actually used: four draw picks a gameweek. An arm can lose on pooled log
loss and still be the one you want, because a trixy never asks for a
calibrated probability on all ten fixtures — it asks which four are most
likely to finish level, and only the ORDER matters.

So this reads the per-fixture rows the walk-forward already wrote and scores
the arms on that ordering instead. No refitting, no refetching: every number
here comes from out-of-sample predictions that experiment produced.

WHAT IT CANNOT DO. The rows carry no date, so a real gameweek cannot be
reconstructed and "top four this Saturday" is not directly measurable. The
stand-in is precision at the top k% of each league-season, which asks the
same question — when this arm is most confident of a draw, is it right? — at
the same selectivity. Four picks from a five-league weekend of ~46 fixtures
is about the top 9%, which is why 5% and 10% are the columns to read.

Confidence intervals resample LEAGUE-SEASONS, not fixtures. Precision at a
cutoff is a property of a whole ranked set; resampling individual matches
would break the ranking that is the thing being measured.

Usage:
    .venv/Scripts/python.exe scripts/analyse_draw_ranking.py
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ROWS = ROOT / "data" / "reports" / "_walk_forward_rows.csv"
OUT = ROOT / "data" / "reports" / "draw_ranking.json"

ARMS = ["ship", "elo_clf", "blend", "layer"]
CUTOFFS = [0.05, 0.10, 0.20]
BOOT = 4000
SEED = 20260923          # fixed: a "which arm wins" answer that moves between
                         # runs of the same data is not an answer


def load() -> list:
    if not ROWS.exists():
        sys.exit(f"missing {ROWS} — run scripts/experiment_walk_forward.py first")
    with ROWS.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def precision_at(block: list, arm: str, frac: float) -> tuple:
    """Draws found in the top `frac` of one league-season, ranked by P(draw).

    Ties at the cutoff are taken in file order rather than broken randomly —
    with continuous probabilities exact ties are vanishingly rare, and a
    random tiebreak would put noise into a number being compared across arms.
    """
    k = max(1, round(len(block) * frac))
    ranked = sorted(block, key=lambda r: -float(r[f"{arm}_D"]))[:k]
    hits = sum(1 for r in ranked if r["y"] == "D")
    return hits, k


def draw_scores(rows: list, arm: str) -> dict:
    """Binary draw-vs-not calibration, independent of the ranking."""
    p = np.array([float(r[f"{arm}_D"]) for r in rows])
    y = np.array([1.0 if r["y"] == "D" else 0.0 for r in rows])
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return {
        "log_loss": round(float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()), 4),
        "brier": round(float(((p - y) ** 2).mean()), 4),
        "mean_p": round(float(p.mean()), 4),
    }


def main() -> int:
    rows = load()
    base = sum(1 for r in rows if r["y"] == "D") / len(rows)

    blocks = defaultdict(list)
    for r in rows:
        blocks[(r["league"], r["season"])].append(r)
    keys = sorted(blocks)

    # hits/k per block per arm per cutoff — computed once, reused by every
    # bootstrap draw, which is what makes 4,000 resamples cheap
    tally = {
        (arm, frac): {k: precision_at(blocks[k], arm, frac) for k in keys}
        for arm in ARMS for frac in CUTOFFS
    }

    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(keys), size=(BOOT, len(keys)))

    print(f"\n{len(rows):,} fixtures · {len(keys)} league-seasons · "
          f"base draw rate {base:.1%}\n")
    print(f"{'arm':10} {'draw LL':>9} {'brier':>7} {'mean p':>7}", end="")
    for f in CUTOFFS:
        print(f" {'top ' + format(f, '.0%'):>16}", end="")
    print()

    report = {"n": len(rows), "base_draw_rate": round(base, 4),
              "league_seasons": len(keys), "arms": {}}

    for arm in ARMS:
        cal = draw_scores(rows, arm)
        line = (f"{arm:10} {cal['log_loss']:9.4f} {cal['brier']:7.4f} "
                f"{cal['mean_p']:7.3f}")
        entry = dict(cal, precision={})
        for frac in CUTOFFS:
            t = tally[(arm, frac)]
            hits = sum(t[k][0] for k in keys)
            n = sum(t[k][1] for k in keys)
            point = hits / n
            # resample league-seasons, recompute the pooled ratio each time
            h = np.array([t[k][0] for k in keys], dtype=float)
            d = np.array([t[k][1] for k in keys], dtype=float)
            boots = h[idx].sum(axis=1) / d[idx].sum(axis=1)
            lo, hi = np.percentile(boots, [2.5, 97.5])
            entry["precision"][f"{frac:.0%}"] = {
                "hits": hits, "n": n, "rate": round(point, 4),
                "ci95": [round(float(lo), 4), round(float(hi), 4)],
                "lift_vs_base": round(point / base, 3),
            }
            line += f"  {point:.1%} [{lo:.1%}-{hi:.1%}]"
        report["arms"][arm] = entry
        print(line)

    # ---- head-to-head on the metric that matters, paired by league-season --
    print(f"\nP(arm ranks draws better than ship), paired by league-season:")
    print(f"{'arm':10}" + "".join(f" {'top ' + format(f, '.0%'):>10}"
                                  for f in CUTOFFS))
    report["vs_ship"] = {}
    for arm in ARMS:
        if arm == "ship":
            continue
        line, entry = f"{arm:10}", {}
        for frac in CUTOFFS:
            ta, ts = tally[(arm, frac)], tally[("ship", frac)]
            ha = np.array([ta[k][0] for k in keys], dtype=float)
            hs = np.array([ts[k][0] for k in keys], dtype=float)
            d = np.array([ta[k][1] for k in keys], dtype=float)
            # the SAME resampled blocks for both arms — an unpaired test here
            # would measure season-to-season variance, which dwarfs the gap
            ba = ha[idx].sum(axis=1) / d[idx].sum(axis=1)
            bs = hs[idx].sum(axis=1) / d[idx].sum(axis=1)
            p = float((ba > bs).mean())
            entry[f"{frac:.0%}"] = round(p, 3)
            line += f" {p:10.3f}"
        report["vs_ship"][arm] = entry
        print(line)

    # ---- per league, at the trixy-like cutoff ---------------------------
    print(f"\nPrecision at top 10%, by league:")
    leagues = sorted({k[0] for k in keys})
    print(f"{'league':22}" + "".join(f" {a:>9}" for a in ARMS))
    report["by_league"] = {}
    for lg in leagues:
        lk = [k for k in keys if k[0] == lg]
        line, entry = f"{lg:22}", {}
        for arm in ARMS:
            t = tally[(arm, 0.10)]
            hits = sum(t[k][0] for k in lk)
            n = sum(t[k][1] for k in lk)
            entry[arm] = round(hits / n, 4)
            line += f" {hits / n:8.1%}"
        report["by_league"][lg] = entry
        print(line)

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
