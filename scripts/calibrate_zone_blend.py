"""Zone-blend calibration: does matchup-specific zone signal improve the
lambda estimates beyond pure form?

    lam_final = lam_form * exp(gamma * zone_advantage_std)

gamma is fit on 24/25 walk-forward (zones from that season's shots,
include_players=False to stay leakage-clean), then evaluated FROZEN on 25/26.
Ships only if out-of-sample log-loss holds or improves (rules.md #5).

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\calibrate_zone_blend.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from models.zones.zones_config import ZONE_IMPORTANCE, ZONE_MATCHUPS
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs
from services.understat.understat_service import UnderstatService
from services.zones.zones_engine import ZonesEngine

MIN_TEAM_MATCHES_IN_WINDOW = 8  # zones need some season depth before trusted


def zone_advantage(zones, home, away):
    """Importance-weighted matchup delta sum for each side (symmetric)."""
    if home not in zones or away not in zones:
        return None
    zh, za = zones[home], zones[away]
    adv_h = sum(ZONE_IMPORTANCE.get(a, 1.0) * (zh[a]["rating"] - za[d]["rating"]) / 100.0
                for a, d in ZONE_MATCHUPS.items())
    adv_a = sum(ZONE_IMPORTANCE.get(a, 1.0) * (za[a]["rating"] - zh[d]["rating"]) / 100.0
                for a, d in ZONE_MATCHUPS.items())
    return adv_h, adv_a


def build_samples(season):
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    rho = params["rho"]
    samples = []
    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, (["2425", season] if season != "2425" else [season]))
        us = UnderstatService.load(league, season)
        eng = ZonesEngine(league, season)
        zcache = {}
        season_counts = {}
        for m in sorted(us["matches"], key=lambda x: x["date"]):
            if m["home_goals"] is None:
                continue
            nh = season_counts.get(m["home_team"], 0)
            na = season_counts.get(m["away_team"], 0)
            season_counts[m["home_team"]] = nh + 1
            season_counts[m["away_team"]] = na + 1
            if nh < MIN_TEAM_MATCHES_IN_WINDOW or na < MIN_TEAM_MATCHES_IN_WINDOW:
                continue
            ratings = fm.ratings_before(m["date"])
            lam_h, lam_a, low = fm.lambdas(ratings, m["home_team"], m["away_team"],
                                           boosts["home_boost"], boosts["away_boost"])
            if low:
                continue
            if m["date"] not in zcache:
                try:
                    zcache[m["date"]] = eng.build(as_of_date=m["date"], persist=False,
                                                  include_players=False)["teams"]
                except Exception:
                    zcache[m["date"]] = None
            zones = zcache[m["date"]]
            if not zones:
                continue
            adv = zone_advantage(zones, m["home_team"], m["away_team"])
            if adv is None:
                continue
            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            samples.append({"lam_h": lam_h, "lam_a": lam_a, "rho": rho,
                            "adv_h": adv[0], "adv_a": adv[1], "outcome": outcome})
        print(f"  {league}: {sum(1 for s in samples)} cumulative samples", flush=True)

    advs = [s["adv_h"] for s in samples] + [s["adv_a"] for s in samples]
    mean = sum(advs) / len(advs)
    std = (sum((a - mean) ** 2 for a in advs) / len(advs)) ** 0.5 or 1.0
    for s in samples:
        s["zh"] = (s["adv_h"] - mean) / std
        s["za"] = (s["adv_a"] - mean) / std
    return samples, mean, std


def log_loss(samples, gamma):
    nll = 0.0
    for s in samples:
        p = outcome_probs(s["lam_h"] * math.exp(gamma * s["zh"]),
                          s["lam_a"] * math.exp(gamma * s["za"]), s["rho"])
        nll -= math.log(max(p[s["outcome"]], 1e-9))
    return nll / len(samples)


def main() -> int:
    print("building 24/25 fit samples (zone builds per date — several minutes)...", flush=True)
    fit, mean, std = build_samples("2425")
    print(f"fit samples: {len(fit)}", flush=True)

    grid = [round(g, 3) for g in [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20]]
    results = [(g, log_loss(fit, g)) for g in grid]
    for g, ll in results:
        print(f"  gamma={g:+.3f}  fit log-loss={ll:.5f}", flush=True)
    best_g, best_ll = min(results, key=lambda x: x[1])

    print("\nbuilding 25/26 eval samples...", flush=True)
    eval_s, _, _ = build_samples("2526")
    base_ll = log_loss(eval_s, 0.0)
    zone_ll = log_loss(eval_s, best_g)
    print(f"\nFIT (24/25): best gamma={best_g} (log-loss {best_ll:.5f} vs gamma=0 {results[0][1]:.5f})")
    print(f"EVAL (25/26, frozen): form-only {base_ll:.5f} vs blended {zone_ll:.5f}  "
          f"delta {zone_ll - base_ll:+.5f}  (n={len(eval_s)})")

    verdict = "KEEP" if (best_g > 0 and zone_ll <= base_ll + 1e-4) else "REJECT"
    out = {"gamma": best_g if verdict == "KEEP" else 0.0,
           "adv_mean": round(mean, 4), "adv_std": round(std, 4),
           "fit_log_loss": round(best_ll, 5),
           "eval_form_only": round(base_ll, 5), "eval_blended": round(zone_ll, 5),
           "verdict": verdict}
    Path("data/config/zone_blend.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nVERDICT: {verdict} -> data/config/zone_blend.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
