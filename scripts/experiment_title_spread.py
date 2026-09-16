"""Is the season simulator over-confident?

User challenge (2026-09-16): Arsenal 69% for the title after four matches
looks far too aggressive. The simulator samples match outcomes from FIXED
probabilities, which means it models the randomness of RESULTS but not the
uncertainty in our estimate of team STRENGTH, nor the drift of that strength
across a season (injuries, transfers, form, a new manager).

If that is the flaw, the sim's internal spread of final points will be
narrower than the error this method actually makes. Measure both on a season
we know the answer to:

    internal SD  — sqrt(sum of per-match points variance) at frozen lambdas
    real RMSE    — projected final points at the same stage vs what happened

Any gap is uncertainty the simulator is ignoring, and its size tells us how
much per-team season noise to add.

Usage: .venv/Scripts/python.exe scripts/experiment_title_spread.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

EVAL = "2526"
AFTER_WEEK = 4          # same stage as now: four rounds played


def main() -> int:
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    rho = params["rho"]
    clf = DrawModel.load()
    rows = []

    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, ["2425", EVAL])
        us = UnderstatService.load(league, EVAL)
        fx = FixturesService.load(league, EVAL)
        matches = [m for m in fx["matches"] if isinstance(m["week"], int)]
        cutoff = max(m["date"] for m in matches if m["week"] <= AFTER_WEEK)

        banked = defaultdict(int)
        actual = defaultdict(int)
        for m in matches:
            if not m["played"]:
                continue
            hg, ag = m["home_goals"], m["away_goals"]
            ph = 3 if hg > ag else 1 if hg == ag else 0
            pa = 3 if ag > hg else 1 if hg == ag else 0
            actual[m["home_team"]] += ph
            actual[m["away_team"]] += pa
            if m["date"] <= cutoff:
                banked[m["home_team"]] += ph
                banked[m["away_team"]] += pa

        exp_pts = defaultdict(float)
        var_pts = defaultdict(float)
        ratings = fm.ratings_before(cutoff)   # frozen, exactly like the sim
        for m in matches:
            if m["date"] <= cutoff:
                continue
            lam = fm.lambdas(ratings, m["home_team"], m["away_team"],
                             boosts["home_boost"], boosts["away_boost"])
            if lam is None:
                continue
            lam_h, lam_a, _ = lam
            probs = outcome_probs(lam_h, lam_a, rho)
            roll = DrawModel.rolling_stats(fm.matches, cutoff)
            if clf and m["home_team"] in roll and m["away_team"] in roll:
                ctx = DrawModel.season_context(us["matches"], cutoff,
                                               m["home_team"], m["away_team"])
                probs = unified_probs(probs, clf.predict(DrawModel.fixture_features(
                    lam_h, lam_a, rho, roll[m["home_team"]], roll[m["away_team"]], ctx)))
            for team, win, lose in ((m["home_team"], "home", "away"),
                                    (m["away_team"], "away", "home")):
                p3, p1 = probs[win], probs["draw"]
                mean = 3 * p3 + p1
                second = 9 * p3 + p1
                exp_pts[team] += mean
                var_pts[team] += second - mean ** 2

        for team in actual:
            rows.append({
                "league": league, "team": team,
                "proj": banked[team] + exp_pts[team],
                "internal_sd": var_pts[team] ** 0.5,
                "actual": actual[team],
            })
        print(f"  {league}: {len(actual)} teams", flush=True)

    err = np.array([r["actual"] - r["proj"] for r in rows])
    internal = np.array([r["internal_sd"] for r in rows])
    rmse = float(np.sqrt((err ** 2).mean()))
    mean_internal = float(internal.mean())
    extra = float(np.sqrt(max(0.0, rmse ** 2 - mean_internal ** 2)))

    print(f"\n=== {EVAL} projected from after GW{AFTER_WEEK} (n={len(rows)} teams)")
    print(f"  simulator's internal SD of final points : {mean_internal:5.2f}")
    print(f"  ACTUAL error of those projections (RMSE): {rmse:5.2f}")
    print(f"  bias (mean actual - projected)          : {err.mean():+5.2f}")
    print(f"  -> uncertainty the sim ignores          : {extra:5.2f} pts per team")
    print(f"  -> sim is {rmse / mean_internal:.2f}x too confident")

    worst = sorted(rows, key=lambda r: abs(r["actual"] - r["proj"]), reverse=True)[:8]
    print("\n  biggest misses:")
    for r in worst:
        print(f"    {r['team']:<18} projected {r['proj']:5.1f}  actual {r['actual']:3d}"
              f"  ({r['actual'] - r['proj']:+.1f})")

    Path("data/reports/experiment_title_spread.json").write_text(json.dumps({
        "eval_season": EVAL, "after_week": AFTER_WEEK, "n_teams": len(rows),
        "internal_sd": round(mean_internal, 3), "actual_rmse": round(rmse, 3),
        "bias": round(float(err.mean()), 3),
        "missing_sd_pts": round(extra, 3),
        "overconfidence_factor": round(rmse / mean_internal, 3),
    }, indent=2), encoding="utf-8")
    print("\n-> data/reports/experiment_title_spread.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
