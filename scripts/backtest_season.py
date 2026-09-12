"""Generalized season backtest — a second (or Nth) out-of-sample season.

For an eval season S: boosts/rho are fit walk-forward on the season BEFORE S,
the draw classifier is trained only on seasons before S, and every fixture of
S is predicted from strictly-prior matches. Same discipline that produced the
25/26 numbers; no parameter ever sees its own evaluation season.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\backtest_season.py --eval 2425
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.optimize import minimize

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel, MIN_MATCHES
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

ALL_SEASONS = ["1415", "1516", "1617", "1718", "1819", "1920", "2021",
               "2122", "2223", "2324", "2425", "2526"]
DRAW_LEAGUES = list(LEAGUE_NAME_MAP)
HOME_LEAGUES = ["ENG-Premier League", "FRA-Ligue 1"]
RHO_GRID = [round(r, 2) for r in np.arange(-0.06, 0.07, 0.03)]


def fit_params(fit_season):
    samples_by_league = {}
    for league in LEAGUE_NAME_MAP:
        fm = FormModel(league, [fit_season])
        data = UnderstatService.load(league, fit_season)
        rows = []
        for m in data["matches"]:
            if m["home_goals"] is None:
                continue
            ratings = fm.ratings_before(m["date"])
            rh, ra = ratings.get(m["home_team"]), ratings.get(m["away_team"])
            if not rh or not ra or rh["n"] < MIN_MATCHES or ra["n"] < MIN_MATCHES:
                continue
            rows.append({
                "lh": rh["att"] * ra["def"] / rh["mu"],
                "la": ra["att"] * rh["def"] / rh["mu"],
                "out": "home" if m["home_goals"] > m["away_goals"] else
                       "away" if m["away_goals"] > m["home_goals"] else "draw",
            })
        samples_by_league[league] = rows

    def nll(x, rows, rho):
        hb, ab = x
        if not (0.3 < hb < 3 and 0.3 < ab < 3):
            return 1e9
        s = 0.0
        for r in rows:
            p = outcome_probs(r["lh"] * hb, r["la"] * ab, rho)
            s -= math.log(max(p[r["out"]], 1e-9))
        return s / len(rows)

    best = None
    for rho in RHO_GRID:
        fits, tot, n = {}, 0.0, 0
        for lg, rows in samples_by_league.items():
            res = minimize(nll, x0=[1.1, 0.95], args=(rows, rho), method="Nelder-Mead",
                           options={"xatol": 1e-3, "fatol": 1e-5})
            fits[lg] = {"home_boost": float(res.x[0]), "away_boost": float(res.x[1])}
            tot += res.fun * len(rows)
            n += len(rows)
        if best is None or tot / n < best[0]:
            best = (tot / n, rho, fits)
    return {"rho": best[1], "leagues": best[2], "fit_season": fit_season,
            "fit_log_loss": round(best[0], 5)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default="2425")
    args = ap.parse_args()
    eval_season = args.eval
    idx = ALL_SEASONS.index(eval_season)
    fit_season = ALL_SEASONS[idx - 1]
    train_seasons = ALL_SEASONS[:idx]

    print(f"eval {eval_season}: params fit on {fit_season}, classifier on {train_seasons}", flush=True)
    params = fit_params(fit_season)
    params_path = Path(f"data/config/model_params_eval{eval_season}.json")
    params_path.write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"params: rho={params['rho']} ll={params['fit_log_loss']}", flush=True)

    clf_path = Path(f"data/config/draw_model_eval{eval_season}.json")
    dm = DrawModel.train(list(LEAGUE_NAME_MAP), train_seasons, params, out_path=clf_path)
    print(f"classifier n={dm.w['train_n']}", flush=True)

    predictions = []
    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, [fit_season, eval_season])
        us = UnderstatService.load(league, eval_season)
        fx = FixturesService.load(league, eval_season)
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
            p = outcome_probs(lam_h, lam_a, params["rho"])
            roll = DrawModel.rolling_stats(fm.matches, m["date"])
            p_clf = None
            if m["home_team"] in roll and m["away_team"] in roll:
                ctx = DrawModel.season_context(us["matches"], m["date"],
                                               m["home_team"], m["away_team"])
                p_clf = dm.predict(DrawModel.fixture_features(
                    lam_h, lam_a, params["rho"],
                    roll[m["home_team"]], roll[m["away_team"]], ctx))
            pu = unified_probs(p, p_clf)
            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            predictions.append({"league": league, "week": week, "p": pu,
                                "p_clf": p_clf, "outcome": outcome})

    acc = sum(1 for r in predictions if max(r["p"], key=r["p"].get) == r["outcome"])
    print(f"\noutcome accuracy: {acc}/{len(predictions)} = {acc/len(predictions):.1%}", flush=True)
    gold = [r for r in predictions if max(r["p"].values()) >= 0.55]
    ghit = sum(1 for r in gold if max(r["p"], key=r["p"].get) == r["outcome"])
    print(f"GOLD tier (>=55%): {ghit}/{len(gold)} = {ghit/len(gold):.1%}" if gold else "no gold rows", flush=True)

    def simulate(leagues, key, n_picks, score_fn):
        by_week = defaultdict(list)
        for r in predictions:
            if r["league"] in leagues and score_fn(r) is not None:
                by_week[r["week"]].append(r)
        hits = total = 0
        dist = defaultdict(int)
        for w, rs in by_week.items():
            if len(rs) < n_picks:
                continue
            picks = sorted(rs, key=score_fn, reverse=True)[:n_picks]
            h = sum(1 for r in picks if r["outcome"] == key)
            hits += h; total += n_picks; dist[h] += 1
        return hits, total, dict(sorted(dist.items()))

    h, t, d = simulate(HOME_LEAGUES, "home", 3, lambda r: r["p"]["home"])
    print(f"home picks top-3: {h}/{t} = {h/t:.1%}  dist {d}", flush=True)
    h2, t2, d2 = simulate(DRAW_LEAGUES, "draw", 4, lambda r: r["p_clf"])
    print(f"draw picks top-4: {h2}/{t2} = {h2/t2:.1%}  dist {d2}", flush=True)

    out = {"eval_season": eval_season, "fit_season": fit_season,
           "outcome_acc": round(acc / len(predictions), 4), "n": len(predictions),
           "gold": {"hits": ghit, "n": len(gold)},
           "home_picks": {"hits": h, "n": t, "dist": d},
           "draw_picks": {"hits": h2, "n": t2, "dist": d2}}
    Path(f"data/reports/backtest_{eval_season}.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(f"-> data/reports/backtest_{eval_season}.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
