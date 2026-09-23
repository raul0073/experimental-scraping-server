"""How many seasons should the Elo's goal level be calibrated on?

THE SYMPTOM. `conv` means "goals per unit of expected chances" — a pure
level calibration. `build_elo_all.fit` solves it as goals/lam over every
training season, and on the 25/26 holdout that over-projects in all five
leagues: 1.03x in the Bundesliga up to 1.15x in Serie A, about 1.08x on
average. The Premier League projects 3.01 goals a match against an actual
2.75, which is the discrepancy that has been carried as a known issue.

THE CAUSE IS DRIFT, NOT A BUG. Scoring is not stationary — Serie A actually
returned 2.43 goals a match in 25/26 — so a level fitted on twelve seasons
is an average of a era that has passed. The longer the lookback, the more
confidently it is wrong about now.

WHY THIS IS A SEPARATE SCRIPT AND NOT A NUMBER I PICKED. The obvious move is
to try each lookback against the holdout and keep the best, which is exactly
how a test set stops being a test set. So the lookback is chosen INSIDE the
training seasons by walk-forward — for each candidate N and each training
season s, calibrate on the N seasons before s and see how far the projection
lands from what s actually produced — and the holdout is then scored once,
as confirmation rather than as the selection criterion.

Judged on |log ratio| so that over- and under-projecting by the same factor
cost the same, which plain ratio error does not.

Writes data/reports/elo_conv_calibration.json and, with --apply, updates
conv in data/config/elo_params.json.

Usage:
    .venv/Scripts/python.exe scripts/calibrate_elo_conv.py
    .venv/Scripts/python.exe scripts/calibrate_elo_conv.py --apply
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from build_process_elo import matches_from_understat, score_arm, walk  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "data" / "config" / "elo_params.json"
REPORT = ROOT / "data" / "reports" / "elo_conv_calibration.json"
HOLDOUT = "2526"
# "all" stays in the running so the current behaviour has to win on merit
CANDIDATES = [1, 2, 3, 4, 6, 8, "all"]
# a season needs this many scored rows before its ratio means anything
MIN_ROWS = 200


def conv_from(rows, seasons) -> float | None:
    """Goals per unit of expected chances, over the given seasons."""
    sub = rows[rows["season"].isin(seasons)]
    if len(sub) < MIN_ROWS:
        return None
    lam = float((sub["exp_hc"] + sub["exp_ac"]).mean())
    goals = float((sub["hg"] + sub["ag"]).mean())
    return goals / lam if lam else None


def ratio_on(rows, season: str, conv: float) -> float | None:
    """Projected total goals over actual, for one season."""
    sub = rows[rows["season"] == season]
    if sub.empty:
        return None
    proj = float(((sub["exp_hc"] + sub["exp_ac"]) * conv).mean())
    act = float((sub["hg"] + sub["ag"]).mean())
    return proj / act if act else None


def lookback(train: list, season: str, n) -> list:
    """The N training seasons immediately before `season` ('all' = every
    one before it)."""
    prior = [s for s in train if s < season]
    return prior if n == "all" else prior[-n:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the chosen conv back into elo_params.json")
    ap.add_argument("--holdout", default=HOLDOUT)
    args = ap.parse_args()

    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    report, chosen = {}, {}

    for league, p in params.items():
        df = matches_from_understat(league)
        if df.empty:
            continue
        rows, _A, _D = walk(df, p["k"], p["home_adv"], p["decay"], "xg")
        seasons = sorted(rows["season"].unique())
        train = [s for s in seasons if s < args.holdout]

        # ---- choose N using ONLY the training seasons --------------------
        # The first few are skipped: a rating needs history before its
        # expected-chance numbers mean anything, and the earliest seasons
        # have no lookback to calibrate from anyway.
        probe = train[4:]
        scores = {}
        for n in CANDIDATES:
            errs = []
            for s in probe:
                back = lookback(train, s, n)
                if not back:
                    continue
                c = conv_from(rows, back)
                if c is None:
                    continue
                r = ratio_on(rows, s, c)
                if r and r > 0:
                    errs.append(abs(math.log(r)))
            if errs:
                scores[str(n)] = round(float(np.mean(errs)), 5)

        best = min(scores, key=scores.get)
        best_n = "all" if best == "all" else int(best)

        # ---- apply it, then look at the holdout ONCE ---------------------
        new_conv = conv_from(rows, lookback(train, args.holdout, best_n))
        old_conv = p["conv"]
        te = rows[rows["season"] == args.holdout]
        old_ll, old_acc, _, _ = score_arm(te, old_conv, p["rho"])
        new_ll, new_acc, _, _ = score_arm(te, new_conv, p["rho"])

        report[league] = {
            "train_scores_by_lookback": scores,
            "chosen_lookback": best_n,
            "conv_old": round(old_conv, 5),
            "conv_new": round(new_conv, 5),
            "holdout_ratio_old": round(ratio_on(rows, args.holdout, old_conv), 4),
            "holdout_ratio_new": round(ratio_on(rows, args.holdout, new_conv), 4),
            "holdout_log_loss_old": round(old_ll, 4),
            "holdout_log_loss_new": round(new_ll, 4),
            "holdout_acc_old": round(old_acc, 4),
            "holdout_acc_new": round(new_acc, 4),
        }
        chosen[league] = new_conv

        r = report[league]
        print(f"{league:<22} N={str(best_n):<4} "
              f"conv {old_conv:.3f}->{new_conv:.3f}  "
              f"goals x{r['holdout_ratio_old']:.3f}->x{r['holdout_ratio_new']:.3f}  "
              f"LL {old_ll:.4f}->{new_ll:.4f}")

    if args.apply:
        for league, c in chosen.items():
            params[league]["conv"] = round(c, 5)
            params[league]["conv_lookback"] = report[league]["chosen_lookback"]
        PARAMS.write_text(json.dumps(params, indent=2), encoding="utf-8")
        print(f"\n-> {PARAMS} updated")

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
