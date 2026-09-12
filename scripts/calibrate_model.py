"""Stage 5 calibration: fit per-league home/away boosts + global Dixon-Coles
rho on season 24/25, walk-forward (each fixture predicted from strictly-prior
matches only). Frozen output params are then evaluated out-of-sample on 25/26
by scripts/backtest_2526.py.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\calibrate_model.py
"""
import json
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.optimize import minimize

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.predictions.form_model import FormModel, MIN_MATCHES
from services.predictions.probability_service import outcome_probs
from services.understat.understat_service import UnderstatService

FIT_SEASON = "2425"
RHO_GRID = [round(r, 2) for r in np.arange(-0.18, 0.07, 0.03)]


def league_samples(league):
    """Walk-forward (att, def, mu, outcome) samples for the fit season."""
    fm = FormModel(league, [FIT_SEASON])
    data = UnderstatService.load(league, FIT_SEASON)
    samples = []
    for m in data["matches"]:
        if m["home_goals"] is None:
            continue
        ratings = fm.ratings_before(m["date"])
        rh, ra = ratings.get(m["home_team"]), ratings.get(m["away_team"])
        if not rh or not ra or rh["n"] < MIN_MATCHES or ra["n"] < MIN_MATCHES:
            continue
        outcome = "home" if m["home_goals"] > m["away_goals"] else \
                  "away" if m["away_goals"] > m["home_goals"] else "draw"
        samples.append({
            "lam_h_core": rh["att"] * ra["def"] / rh["mu"],
            "lam_a_core": ra["att"] * rh["def"] / rh["mu"],
            "outcome": outcome,
        })
    return samples


def neg_log_loss(params, samples, rho):
    hb, ab = params
    if hb <= 0.3 or ab <= 0.3 or hb > 3 or ab > 3:
        return 1e9
    nll = 0.0
    for s in samples:
        p = outcome_probs(s["lam_h_core"] * hb, s["lam_a_core"] * ab, rho)
        nll -= math.log(max(p[s["outcome"]], 1e-9))
    return nll / len(samples)


def main() -> int:
    all_samples = {lg: league_samples(lg) for lg in LEAGUE_NAME_MAP}
    for lg, s in all_samples.items():
        print(f"{lg}: {len(s)} walk-forward fit samples")

    best = None
    for rho in RHO_GRID:
        total, fits = 0.0, {}
        for lg, samples in all_samples.items():
            res = minimize(neg_log_loss, x0=[1.1, 0.95], args=(samples, rho),
                           method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-5})
            fits[lg] = {"home_boost": round(float(res.x[0]), 4),
                        "away_boost": round(float(res.x[1]), 4),
                        "log_loss": round(float(res.fun), 5)}
            total += res.fun * len(samples)
        n = sum(len(s) for s in all_samples.values())
        avg = total / n
        print(f"rho={rho:+.2f}  weighted log-loss={avg:.5f}")
        if best is None or avg < best[0]:
            best = (avg, rho, fits)

    avg, rho, fits = best
    params = {
        "fit_season": FIT_SEASON,
        "fit_date": date.today().isoformat(),
        "fit_log_loss": round(avg, 5),
        "rho": rho,
        "decay": 0.985,
        "window": 38,
        "min_matches": MIN_MATCHES,
        "leagues": fits,
    }
    out = Path("data/config/model_params.json")
    out.write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"\nbest rho={rho}, weighted log-loss={avg:.5f}")
    for lg, f in fits.items():
        print(f"  {lg}: home_boost={f['home_boost']} away_boost={f['away_boost']} ll={f['log_loss']}")
    print(f"params -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
