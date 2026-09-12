"""Draw-accuracy experiment matrix: training depth x model class.

Cells: logistic vs gradient boosting, trained on 4 seasons (2122-2425) vs
11 seasons (1415-2425). All evaluated identically: frozen, walk-forward,
top-4-per-week pick simulation on 25/26 (5-league pool) — the product metric.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\experiment_draw_models.py
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
from services.predictions.form_model import FormModel, MIN_MATCHES
from services.understat.understat_service import UnderstatService

SEASONS_SHORT = ["2122", "2223", "2324", "2425"]
SEASONS_LONG = ["1415", "1516", "1617", "1718", "1819", "1920", "2021"] + SEASONS_SHORT
EVAL_SEASON = "2526"
LEAGUE_IDX = {lg: i for i, lg in enumerate(LEAGUE_NAME_MAP)}


def build_xy(seasons, with_league=False):
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    X, y = [], []
    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        for season in seasons:
            if not UnderstatService.load(league, season):
                continue
            fm = FormModel(league, [season])
            data = UnderstatService.load(league, season)
            for m in data["matches"]:
                if m["home_goals"] is None:
                    continue
                ratings = fm.ratings_before(m["date"])
                rh, ra = ratings.get(m["home_team"]), ratings.get(m["away_team"])
                if not rh or not ra or rh["n"] < MIN_MATCHES or ra["n"] < MIN_MATCHES:
                    continue
                roll = DrawModel.rolling_stats(data["matches"], m["date"])
                ctx = DrawModel.season_context(data["matches"], m["date"],
                                               m["home_team"], m["away_team"])
                lam_h, lam_a, _ = fm.lambdas(ratings, m["home_team"], m["away_team"],
                                             boosts["home_boost"], boosts["away_boost"])
                feats = DrawModel.fixture_features(lam_h, lam_a, params["rho"],
                                                   roll[m["home_team"]], roll[m["away_team"]], ctx)
                if with_league:
                    feats = feats + [LEAGUE_IDX[league]]
                X.append(feats)
                y.append(1 if m["home_goals"] == m["away_goals"] else 0)
    return np.array(X), np.array(y)


def eval_samples():
    """(features, week, is_draw) rows for the eval season, walk-forward."""
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    rows = []
    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, ["2425", EVAL_SEASON])
        us = UnderstatService.load(league, EVAL_SEASON)
        fx = FixturesService.load(league, EVAL_SEASON)
        wk = {(m["home_team"], m["away_team"]): m["week"]
              for m in fx["matches"] if isinstance(m["week"], int)}
        for m in us["matches"]:
            if m["home_goals"] is None:
                continue
            week = wk.get((m["home_team"], m["away_team"]))
            if week is None:
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
            feats = DrawModel.fixture_features(lam_h, lam_a, params["rho"],
                                               roll[m["home_team"]], roll[m["away_team"]], ctx)
            rows.append({"f": feats, "league": league, "week": week,
                         "draw": m["home_goals"] == m["away_goals"]})
    return rows


def simulate(rows, probs):
    by_week = defaultdict(list)
    for r, p in zip(rows, probs):
        by_week[r["week"]].append((p, r["draw"]))
    dist = defaultdict(int)
    hits = total = 0
    for w, rs in by_week.items():
        if len(rs) < 4:
            continue
        picks = sorted(rs, key=lambda x: x[0], reverse=True)[:4]
        h = sum(1 for _, d in picks if d)
        dist[h] += 1
        hits += h
        total += 4
    return hits, total, dict(dist)


def main() -> int:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression

    rows = eval_samples()
    print(f"eval rows: {len(rows)}", flush=True)

    results = {}
    for depth_label, seasons in (("4 seasons", SEASONS_SHORT), ("11 seasons", SEASONS_LONG)):
        for model_label in ("logistic", "gbm"):
            with_league = model_label == "gbm"
            X, y = build_xy(seasons, with_league=with_league)
            if model_label == "logistic":
                mean, std = X.mean(axis=0), X.std(axis=0) + 1e-9
                clf = LogisticRegression(max_iter=2000, C=10.0)
                clf.fit((X - mean) / std, y)
                Xe = np.array([r["f"] for r in rows])
                probs = clf.predict_proba((Xe - mean) / std)[:, 1]
            else:
                clf = HistGradientBoostingClassifier(
                    max_iter=400, learning_rate=0.05, max_leaf_nodes=15,
                    l2_regularization=1.0, random_state=7)
                clf.fit(X, y)
                Xe = np.array([r["f"] + [LEAGUE_IDX[r["league"]]] for r in rows])
                probs = clf.predict_proba(Xe)[:, 1]
            hits, total, dist = simulate(rows, probs)
            key = f"{model_label} / {depth_label} (n={len(y)})"
            results[key] = (hits, total, dist)
            print(f"{key:38} pick hit rate {hits}/{total} = {hits/total:.1%}  "
                  f"dist {sorted(dist.items())}", flush=True)

    print("\nbaseline (shipping logistic/4s): 44/152 = 28.9%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
