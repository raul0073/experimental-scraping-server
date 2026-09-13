"""Gated experiment: from ~GW5, should ratings use THIS season only?

User instinct (2026-09-13): 'we are close to GW5, move to this season's
stats only.' Counter-hypothesis: the rolling 38-match decayed window already
phases the prior season out gradually, and a hard cut at GW5 leaves ratings
on ~4 matches of evidence. Decide by replaying 25/26 from GW5 onward:
identical fixtures, identical shipping classifier — only the FormModel's
season list differs.

Usage: .venv/Scripts/python scripts/experiment_single_season.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel, MIN_MATCHES
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

EVAL = "2526"
FROM_WEEK = 5
HOME_LEAGUES = {"ENG-Premier League", "FRA-Ligue 1"}


def run_variant(label, seasons):
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    clf = DrawModel.load()
    rows = []
    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, seasons)
        us = UnderstatService.load(league, EVAL)
        fx = FixturesService.load(league, EVAL)
        wk = {(m["home_team"], m["away_team"]): m["week"]
              for m in fx["matches"] if isinstance(m["week"], int)}
        for m in us["matches"]:
            if m["home_goals"] is None:
                continue
            week = wk.get((m["home_team"], m["away_team"]))
            if week is None or week < FROM_WEEK:
                continue
            ratings = fm.ratings_before(m["date"])
            lam_h, lam_a, low = fm.lambdas(ratings, m["home_team"], m["away_team"],
                                           boosts["home_boost"], boosts["away_boost"])
            if low:
                continue
            roll = DrawModel.rolling_stats(fm.matches, m["date"])
            if m["home_team"] not in roll or m["away_team"] not in roll:
                continue
            ctx = DrawModel.season_context(us["matches"], m["date"],
                                           m["home_team"], m["away_team"])
            p_clf = clf.predict(DrawModel.fixture_features(
                lam_h, lam_a, params["rho"],
                roll[m["home_team"]], roll[m["away_team"]], ctx))
            probs = unified_probs(outcome_probs(lam_h, lam_a, params["rho"]), p_clf)
            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            rows.append({"league": league, "week": week, "probs": probs,
                         "p_draw": p_clf, "outcome": outcome})

    # outcome accuracy + GOLD tier
    hits = sum(1 for r in rows if max(r["probs"], key=r["probs"].get) == r["outcome"])
    gold = [r for r in rows if max(r["probs"].values()) >= 0.55]
    gold_hits = sum(1 for r in gold if max(r["probs"], key=r["probs"].get) == r["outcome"])
    # weekly top-4 draws (pooled) + top-3 homes (EPL+L1)
    by_week = defaultdict(list)
    for r in rows:
        by_week[r["week"]].append(r)
    d_h = d_n = h_h = h_n = 0
    for w, rs in by_week.items():
        ds = sorted(rs, key=lambda r: r["p_draw"], reverse=True)[:4]
        if len(ds) == 4:
            d_h += sum(1 for r in ds if r["outcome"] == "draw")
            d_n += 4
        hs = sorted((r for r in rs if r["league"] in HOME_LEAGUES),
                    key=lambda r: r["probs"]["home"], reverse=True)[:3]
        if len(hs) == 3:
            h_h += sum(1 for r in hs if r["outcome"] == "home")
            h_n += 3
    print(f"{label:28} n={len(rows):4}  outcome {hits/len(rows):.1%}  "
          f"GOLD {gold_hits}/{len(gold)} = {gold_hits/len(gold):.1%}  "
          f"draws top-4 {d_h}/{d_n} = {d_h/d_n:.1%}  "
          f"homes top-3 {h_h}/{h_n} = {h_h/h_n:.1%}", flush=True)


def main() -> int:
    print(f"replaying {EVAL} from GW{FROM_WEEK}, shipping classifier, "
          f"identical fixtures:", flush=True)
    run_variant("two-season rolling (ship)", ["2425", EVAL])
    run_variant("single-season only", [EVAL])
    print("\nGATE: hard-switch only if single-season is no worse on GOLD "
          "and outcome, and better somewhere.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
