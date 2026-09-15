"""Monte Carlo the rest of 2026/27: every remaining fixture priced by the
predictor (unified, classifier-calibrated probabilities at TODAY's ratings),
the season replayed N times -> per-team expected points, title / top-4 /
relegation odds, position distributions.

Honest caveats baked into the output: probabilities are frozen at current
ratings (no injuries/transfers/fatigue modeling); draws use the calibrated
classifier; goal margins for GD tiebreaks are simplified (margin = 1 +
Poisson(0.4) for wins).

Usage: .venv/Scripts/python scripts/simulate_season.py [--sims 5000]
Writes data/reports/season_sim_2627.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.prediction_service import SEASON, PredictionService

TOP_N = 4
REL_N = 3


def simulate_league(svc, league, n_sims, rng):
    fx = FixturesService.load(league, SEASON)
    played = [m for m in fx["matches"] if m["played"] and isinstance(m["week"], int)]
    todo = [m for m in fx["matches"] if not m["played"] and isinstance(m["week"], int)]

    teams = sorted({m["home_team"] for m in fx["matches"] if isinstance(m["week"], int)})
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)

    base_pts = np.zeros(T)
    base_gd = np.zeros(T)
    for m in played:
        h, a = idx[m["home_team"]], idx[m["away_team"]]
        gd = m["home_goals"] - m["away_goals"]
        base_gd[h] += gd
        base_gd[a] -= gd
        if gd > 0:
            base_pts[h] += 3
        elif gd < 0:
            base_pts[a] += 3
        else:
            base_pts[h] += 1
            base_pts[a] += 1

    preds = svc.predict_fixtures(league, todo)
    F = len(preds)
    probs = np.array([[p["probabilities"]["home"], p["probabilities"]["draw"],
                       p["probabilities"]["away"]] for p in preds])
    probs = probs / probs.sum(axis=1, keepdims=True)
    h_idx = np.array([idx[p["home"]] for p in preds])
    a_idx = np.array([idx[p["away"]] for p in preds])

    cum = probs.cumsum(axis=1)                    # (F, 3)
    u = rng.random((n_sims, F))
    out = (u[:, :, None] > cum[None, :, :]).sum(axis=2)   # 0=H,1=D,2=A
    margins = 1 + rng.poisson(0.4, size=(n_sims, F))

    pts = np.tile(base_pts, (n_sims, 1))
    gd = np.tile(base_gd, (n_sims, 1))
    sims = np.arange(n_sims)
    for f in range(F):
        o = out[:, f]
        hw, dr, aw = o == 0, o == 1, o == 2
        pts[sims[hw], h_idx[f]] += 3
        pts[sims[aw], a_idx[f]] += 3
        pts[sims[dr], h_idx[f]] += 1
        pts[sims[dr], a_idx[f]] += 1
        gd[sims[hw], h_idx[f]] += margins[hw, f]
        gd[sims[hw], a_idx[f]] -= margins[hw, f]
        gd[sims[aw], a_idx[f]] += margins[aw, f]
        gd[sims[aw], h_idx[f]] -= margins[aw, f]

    # rank per sim: points, then GD, then tiny noise
    key = pts * 10000 + gd * 10 + rng.random(pts.shape)
    order = np.argsort(-key, axis=1)
    pos = np.empty_like(order)
    rows = np.arange(n_sims)[:, None]
    pos[rows, order] = np.arange(T)[None, :] + 1

    result = []
    for t, i in idx.items():
        result.append({
            "team": t,
            "pts_now": int(base_pts[i]),
            "exp_pts": round(float(pts[:, i].mean()), 1),
            "p_title": round(float((pos[:, i] == 1).mean()) * 100, 1),
            "p_top4": round(float((pos[:, i] <= TOP_N).mean()) * 100, 1),
            "p_rel": round(float((pos[:, i] > T - REL_N).mean()) * 100, 1),
            "med_pos": int(np.median(pos[:, i])),
        })
    result.sort(key=lambda r: -r["exp_pts"])
    return result, F


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=5000)
    args = ap.parse_args()
    rng = np.random.default_rng(7)
    svc = PredictionService()
    out = {"season": SEASON, "sims": args.sims, "leagues": {}}
    from datetime import date
    out["as_of"] = date.today().isoformat()
    for league in LEAGUE_NAME_MAP:
        table, f = simulate_league(svc, league, args.sims, rng)
        out["leagues"][league] = table
        print(f"\n=== {league} ({f} fixtures simulated x {args.sims}) ===", flush=True)
        print(f"{'team':<22}{'now':>4}{'xPts':>7}{'title%':>8}{'top4%':>7}{'rel%':>6}")
        for r in table[:6]:
            print(f"{r['team']:<22}{r['pts_now']:>4}{r['exp_pts']:>7}"
                  f"{r['p_title']:>8}{r['p_top4']:>7}{r['p_rel']:>6}")
        print("  ...")
        for r in table[-3:]:
            print(f"{r['team']:<22}{r['pts_now']:>4}{r['exp_pts']:>7}"
                  f"{r['p_title']:>8}{r['p_top4']:>7}{r['p_rel']:>6}")
    path = Path("data/reports/season_sim_2627.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
