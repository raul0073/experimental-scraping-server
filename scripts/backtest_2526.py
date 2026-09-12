"""Stage 5 go/no-go: evaluate the frozen 24/25-calibrated model walk-forward
on season 25/26, then simulate the actual product — top-4 draw picks
(EPL + Serie A) and top-3 home-win picks (EPL + Ligue 1) per matchweek.

No leakage: every fixture is predicted from strictly-prior matches (the
rolling window crosses into 24/25 naturally). Promoted/early teams run on
league-average priors and are excluded from picks (low confidence).

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\backtest_2526.py
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

SEASON = "2526"
# keep in sync with services/predictions/prediction_service.py
from services.predictions.prediction_service import DRAW_LEAGUES, HOME_LEAGUES  # noqa: E402
N_DRAWS, N_HOME = 4, 3


def main() -> int:
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    rho = params["rho"]

    draw_model = DrawModel.load()

    predictions = []
    base_rates = {}
    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, ["2425", SEASON])
        us = UnderstatService.load(league, SEASON)
        fx = FixturesService.load(league, SEASON)
        week_by_pair = {(m["home_team"], m["away_team"]): m["week"]
                        for m in fx["matches"] if isinstance(m["week"], int)}

        prior = UnderstatService.load(league, "2425")
        n = len(prior["matches"])
        base_rates[league] = {
            "draw": sum(1 for m in prior["matches"] if m["home_goals"] == m["away_goals"]) / n,
            "home": sum(1 for m in prior["matches"] if m["home_goals"] > m["away_goals"]) / n,
        }

        for m in us["matches"]:
            if m["home_goals"] is None:
                continue
            week = week_by_pair.get((m["home_team"], m["away_team"]))
            if week is None:
                continue
            ratings = fm.ratings_before(m["date"])
            lam_h, lam_a, low_conf = fm.lambdas(
                ratings, m["home_team"], m["away_team"],
                boosts["home_boost"], boosts["away_boost"])
            p = outcome_probs(lam_h, lam_a, rho)
            p_draw_clf = None
            if draw_model and not low_conf:
                roll = DrawModel.rolling_stats(fm.matches, m["date"])
                if m["home_team"] in roll and m["away_team"] in roll:
                    # standings context from THIS season's matches only
                    ctx = DrawModel.season_context(us["matches"], m["date"],
                                                   m["home_team"], m["away_team"])
                    p_draw_clf = draw_model.predict(DrawModel.fixture_features(
                        lam_h, lam_a, rho, roll[m["home_team"]], roll[m["away_team"]], ctx))
            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            p = unified_probs(p, p_draw_clf)  # official triplet, as served live
            predictions.append({
                "p_draw_clf": p_draw_clf,
                "league": league, "week": week, "date": m["date"],
                "home": m["home_team"], "away": m["away_team"],
                "lam_h": round(lam_h, 3), "lam_a": round(lam_a, 3),
                "p": p, "low_conf": low_conf, "outcome": outcome,
                "score": f"{m['home_goals']}-{m['away_goals']}",
                "real_xg": f"{m['home_xg']:.2f}-{m['away_xg']:.2f}",
            })

    # ---- global calibration quality
    lines = [f"# Backtest 25/26 — frozen params fit on 24/25", ""]
    for subset, label in ((predictions, "all fixtures"),
                          ([p for p in predictions if not p["low_conf"]], "confident only")):
        ll = -sum(math.log(max(p["p"][p["outcome"]], 1e-9)) for p in subset) / len(subset)
        base_ll = -sum(math.log(max(base_rates[p["league"]][p["outcome"]]
                                    if p["outcome"] != "away"
                                    else 1 - base_rates[p["league"]]["home"] - base_rates[p["league"]]["draw"], 1e-9))
                       for p in subset) / len(subset)
        lines.append(f"- log-loss ({label}, n={len(subset)}): **{ll:.4f}** vs base-rate predictor {base_ll:.4f}")
    lines.append("")

    # ---- pick simulation
    def simulate(leagues, key, n_picks, title, score_fn=None):
        score_fn = score_fn or (lambda p: p["p"][key])
        by_week = defaultdict(list)
        for p in predictions:
            if p["league"] in leagues and not p["low_conf"] and score_fn(p) is not None:
                by_week[p["week"]].append(p)
        weeks = sorted(w for w, rows in by_week.items() if len(rows) >= n_picks)
        hits = total = 0
        weekly = []
        pick_log = []
        for w in weeks:
            picks = sorted(by_week[w], key=score_fn, reverse=True)[:n_picks]
            h = sum(1 for p in picks if p["outcome"] == key)
            hits += h
            total += n_picks
            weekly.append(h)
            for rank, p in enumerate(picks, 1):
                pick_log.append({**{k: p[k] for k in ("league", "week", "date", "home", "away", "score", "real_xg", "outcome")},
                                 "rank": rank, "prob": score_fn(p),
                                 "hit": p["outcome"] == key, "pick_type": key})
        rate = hits / total if total else 0.0
        pooled_base = sum(base_rates[lg][key] for lg in leagues) / len(leagues)
        avg_prob = sum(pl["prob"] for pl in pick_log) / len(pick_log)
        lines.extend([
            f"## {title}",
            "",
            f"- weeks simulated: {len(weeks)}; picks: {total}",
            f"- **hit rate: {rate:.1%}** (base rate ~ {pooled_base:.1%}; edge {rate - pooled_base:+.1%})",
            f"- avg predicted probability of picks: {avg_prob:.1%} (calibration: should track hit rate)",
            f"- weekly hits distribution: " + ", ".join(
                f"{k}/{n_picks}×{sum(1 for x in weekly if x == k)}" for k in range(n_picks + 1)),
            "",
        ])
        return pick_log

    log_draws = simulate(DRAW_LEAGUES, "draw", N_DRAWS,
                         f"Draw picks — top {N_DRAWS} ({len(DRAW_LEAGUES)} leagues), Poisson-ranked")
    if draw_model:
        log_draws = simulate(DRAW_LEAGUES, "draw", N_DRAWS,
                             f"Draw picks — top {N_DRAWS} ({len(DRAW_LEAGUES)} leagues), CLASSIFIER-ranked",
                             score_fn=lambda p: p["p_draw_clf"])
    log_home = simulate(HOME_LEAGUES, "home", N_HOME, f"Home-win picks — top {N_HOME} (EPL + Ligue 1)")

    Path("data/reports/backtest_2526_picks.json").write_text(
        json.dumps({"draws": log_draws, "home_wins": log_home}, indent=2), encoding="utf-8")
    Path("data/reports/backtest_2526.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("report -> data/reports/backtest_2526.md  (full pick log in backtest_2526_picks.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
