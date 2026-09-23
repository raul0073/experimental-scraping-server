"""Does the process Elo hurt the draw call? And can the classifier fix it?

The Elo won the overall head-to-head on points of log-loss, but the product
is DRAW PICKS, and on the upcoming fixtures its draw numbers ran two to
three points under the shipped model's. That is not a rounding difference
for a four-fold: at p^4, three points off a 30% pick is a fifth of the
bonanza probability.

There is an obvious reason. The shipped model does not take its draw number
from the Poisson at all — `unified_probs` hands P(draw) entirely to a
logistic classifier trained on eleven seasons and 17,134 matches, and keeps
the Poisson only for the home:away RATIO. The Elo has been taking its draw
straight off the Dixon-Coles grid with nothing but rho to correct it.

So the fix writes itself: give the classifier the Elo's lambda pair. It is
the same function, fed a better ratio.

  shipped        as served: its own lambdas, its own classifier
  elo            Dixon-Coles draws off the Elo lambdas, no classifier
  elo+clf        the Elo's lambdas through the SAME classifier
  blend          shipped and elo+clf averaged

Judged on what a draw punter actually cares about: calibration, the binary
log-loss of draw-versus-not, and the hit rate of the top-ranked draw picks.

Writes data/reports/experiment_elo_draws.json

Usage: .venv/Scripts/python.exe scripts/experiment_elo_draws.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

from build_process_elo import CACHE, add_xg, outcome, walk    # noqa: E402
from experiment_predictor_stack_epl import align              # noqa: E402

LEAGUE = "ENG-Premier League"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_elo_draws.json"
TEST = "2526"
# What a weekly ticket actually takes. Ten per round over a season is 38
# picks, which is the same order as the four-a-week the product commits to.
PICKS = 40


def draw_stats(name: str, p: np.ndarray, is_draw: np.ndarray) -> dict:
    """Everything a draw punter would ask of a number."""
    p = np.clip(p, 1e-9, 1 - 1e-9)
    binary = float(np.mean(-(is_draw * np.log(p) + (1 - is_draw) * np.log(1 - p))))
    order = np.argsort(-p)[:PICKS]
    return {
        "arm": name,
        "mean_p": round(float(p.mean()), 4),
        "actual_rate": round(float(is_draw.mean()), 4),
        # a number that says 27% and lands 27% of the time is usable even if
        # it is never the argmax; one that says 33% and lands 24% is not
        "calibration_gap": round(float(p.mean() - is_draw.mean()), 4),
        "binary_log_loss": round(binary, 4),
        "top_picks": PICKS,
        "top_hit_rate": round(float(is_draw[order].mean()), 4),
        "top_mean_p": round(float(p[order].mean()), 4),
    }


def main() -> int:
    params = json.loads(
        (ROOT / "data" / "web" / "team" / "eng-premier-league" / "elo.json")
        .read_text(encoding="utf-8"))["params"]
    ship_params = json.loads((ROOT / "data" / "config" / "model_params.json")
                             .read_text(encoding="utf-8"))
    boosts = ship_params["leagues"][LEAGUE]
    rho_ship = ship_params["rho"]
    draw_model = DrawModel.load()
    if draw_model is None:
        print("no draw classifier on disk")
        return 1

    print("running the Elo…", flush=True)
    df = pd.read_json(CACHE, dtype={"season": str})
    df["season"] = df["season"].astype(str)
    df = add_xg(df, LEAGUE)
    rows, _A, _D = walk(df, params["k"], params["home_adv"],
                        params["decay"], "xg")
    rows["date"] = [str(k)[:10] for k in rows["kick"]]
    elo_rows = rows[rows["season"] == TEST]

    print("running the shipped pipeline…", flush=True)
    fm = FormModel(LEAGUE, ["2425", TEST])
    us = UnderstatService.load(LEAGUE, TEST)
    name = align({t for m in us["matches"]
                  for t in (m["home_team"], m["away_team"])},
                 set(df["home"]) | set(df["away"]))
    by_key = {(r.date, r.home, r.away): r
              for r in elo_rows.itertuples(index=False)}

    out = []
    for m in us["matches"]:
        if m["home_goals"] is None:
            continue
        h, a, date = m["home_team"], m["away_team"], str(m["date"])[:10]
        r = by_key.get((date, name.get(h), name.get(a)))
        if r is None:
            continue
        ratings = fm.ratings_before(m["date"])
        lam_h, lam_a, low = fm.lambdas(ratings, h, a,
                                       boosts["home_boost"], boosts["away_boost"])
        if low:
            continue
        roll = DrawModel.rolling_stats(fm.matches, m["date"])
        if h not in roll or a not in roll:
            continue
        ctx = DrawModel.season_context(us["matches"], m["date"], h, a)

        # shipped, exactly as served
        p_ship_poisson = outcome_probs(lam_h, lam_a, rho_ship)
        p_draw_ship = draw_model.predict(DrawModel.fixture_features(
            lam_h, lam_a, rho_ship, roll[h], roll[a], ctx))
        ship = unified_probs(p_ship_poisson, p_draw_ship)

        # the Elo's own lambdas
        elh = max(r.exp_hc * params["conv"], 1e-3)
        ela = max(r.exp_ac * params["conv"], 1e-3)
        elo_p = outcome(elh, ela, params["rho"])

        # THE FIX: the same classifier, fed the Elo's lambda pair
        p_draw_elo = draw_model.predict(DrawModel.fixture_features(
            elh, ela, params["rho"], roll[h], roll[a], ctx))
        elo_clf = unified_probs(
            {"home": float(elo_p[0]), "draw": float(elo_p[1]),
             "away": float(elo_p[2])}, p_draw_elo)

        out.append({
            "date": date, "home": h, "away": a,
            "is_draw": int(m["home_goals"] == m["away_goals"]),
            "ship": ship["draw"],
            "elo": float(elo_p[1]),
            "elo_clf": elo_clf["draw"],
        })

    if len(out) < 100:
        print(f"only {len(out)} fixtures matched")
        return 1
    d = pd.DataFrame(out)
    is_draw = d["is_draw"].values.astype(float)
    d["blend"] = (d["ship"] + d["elo_clf"]) / 2

    arms = ["ship", "elo", "elo_clf", "blend"]
    stats = [draw_stats(k, d[k].values, is_draw) for k in arms]

    print()
    print(f"TEST {TEST}, n={len(d)} — actual draw rate "
          f"{is_draw.mean() * 100:.1f}%")
    print(f"{'arm':<10}{'mean P':>9}{'gap':>8}{'binary LL':>11}"
          f"{'top40 hit':>11}{'top40 said':>12}")
    for s in stats:
        print(f"{s['arm']:<10}{s['mean_p'] * 100:>8.1f}%{s['calibration_gap'] * 100:>+7.1f}"
              f"{s['binary_log_loss']:>11.4f}{s['top_hit_rate'] * 100:>10.1f}%"
              f"{s['top_mean_p'] * 100:>11.1f}%")

    REPORT.write_text(json.dumps({
        "league": LEAGUE, "test_season": TEST, "n": len(d),
        "actual_draw_rate": round(float(is_draw.mean()), 4),
        "arms": stats,
    }, indent=2), encoding="utf-8")
    print()
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
