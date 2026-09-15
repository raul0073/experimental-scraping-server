"""Experiment A (user directive 2026-09-15: 'predictor must use zones'):
does zone STRUCTURE beat the scalar compression?

The shipping blend sums all nine zone matchups into ONE number before
fitting one gamma (0.02) — that tested a compression, not the structure.
Here each side gets four CHANNEL features, each with its own gamma:

    f_flank    = max(attL - their defR, attR - their defL)   best flank hole
    f_central  = attC - their defC                           central punch
    f_progress = midProgress - their midShield               plays through screen
    f_press    = midPress - their midProgress                wins it back high

    lam_side *= exp(sum_k gamma_k * z_k(side))    (z = standardized on FIT set)

Protocol (rules.md #5, same as the scalar): fit gammas on 24/25 walk-forward
(zones as-of-date, players excluded — leak-clean), evaluate FROZEN on 25/26.
Comparators on eval: form-only, SHIPPING scalar blend (gamma & stats from
data/config/zone_blend.json), channels. Ships only if channels beat the
shipping blend out-of-sample.

Usage: .venv/Scripts/python.exe scripts/experiment_zone_channels.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from scripts.calibrate_zone_blend import zone_advantage  # scalar comparator
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs
from services.understat.understat_service import UnderstatService
from services.zones.zones_engine import ZonesEngine

MIN_TEAM_MATCHES_IN_WINDOW = 8   # same zone-depth gate as the scalar fit
CHANNELS = ("flank", "central", "progress", "press")


def channel_feats(zones, team, opp):
    zt, zo = zones[team], zones[opp]
    r = lambda z, k: z[k]["rating"]
    return {
        "flank": max(r(zt, "attLeft") - r(zo, "defRight"),
                     r(zt, "attRight") - r(zo, "defLeft")) / 100.0,
        "central": (r(zt, "attCentral") - r(zo, "defCentral")) / 100.0,
        "progress": (r(zt, "midProgress") - r(zo, "midShield")) / 100.0,
        "press": (r(zt, "midPress") - r(zo, "midProgress")) / 100.0,
    }


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
            if not zones or m["home_team"] not in zones or m["away_team"] not in zones:
                continue
            adv = zone_advantage(zones, m["home_team"], m["away_team"])
            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            samples.append({"lam_h": lam_h, "lam_a": lam_a, "rho": rho,
                            "fh": channel_feats(zones, m["home_team"], m["away_team"]),
                            "fa": channel_feats(zones, m["away_team"], m["home_team"]),
                            "adv_h": adv[0], "adv_a": adv[1],
                            "outcome": outcome})
        print(f"  {league}: {len(samples)} cumulative samples", flush=True)
    return samples


def standardize(samples, stats=None):
    """z-score each channel; stats from the FIT set are frozen for eval."""
    if stats is None:
        stats = {}
        for c in CHANNELS:
            vals = [s["fh"][c] for s in samples] + [s["fa"][c] for s in samples]
            mean = sum(vals) / len(vals)
            std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
            stats[c] = (mean, std)
    for s in samples:
        s["zh"] = [(s["fh"][c] - stats[c][0]) / stats[c][1] for c in CHANNELS]
        s["za"] = [(s["fa"][c] - stats[c][0]) / stats[c][1] for c in CHANNELS]
    return stats


def nll_channels(samples, g):
    nll = 0.0
    for s in samples:
        bh = math.exp(sum(gi * zi for gi, zi in zip(g, s["zh"])))
        ba = math.exp(sum(gi * zi for gi, zi in zip(g, s["za"])))
        p = outcome_probs(s["lam_h"] * bh, s["lam_a"] * ba, s["rho"])
        nll -= math.log(max(p[s["outcome"]], 1e-9))
    return nll / len(samples)


def nll_scalar(samples, gamma, mean, std):
    nll = 0.0
    for s in samples:
        p = outcome_probs(s["lam_h"] * math.exp(gamma * (s["adv_h"] - mean) / std),
                          s["lam_a"] * math.exp(gamma * (s["adv_a"] - mean) / std),
                          s["rho"])
        nll -= math.log(max(p[s["outcome"]], 1e-9))
    return nll / len(samples)


def fit_gammas(samples):
    """Coordinate descent over a coarse-then-fine grid; 4 params on ~2k
    samples is comfortably identifiable and can't silently overfit much,
    but the frozen eval is the judge anyway."""
    g = [0.0, 0.0, 0.0, 0.0]
    best = nll_channels(samples, g)
    for step in (0.02, 0.01, 0.005):
        improved = True
        while improved:
            improved = False
            for k in range(4):
                for direction in (+1, -1):
                    cand = list(g)
                    cand[k] = round(cand[k] + direction * step, 4)
                    if abs(cand[k]) > 0.25:
                        continue
                    ll = nll_channels(samples, cand)
                    if ll < best - 1e-6:
                        g, best = cand, ll
                        improved = True
    return g, best


def main() -> int:
    print("building 24/25 fit samples (zone builds per date - several minutes)...", flush=True)
    fit = build_samples("2425")
    stats = standardize(fit)
    print(f"fit n={len(fit)}", flush=True)

    base_fit = nll_channels(fit, [0, 0, 0, 0])
    g, ll_fit = fit_gammas(fit)
    print(f"FIT: base {base_fit:.5f} -> channels {ll_fit:.5f}  gammas="
          f"{dict(zip(CHANNELS, g))}", flush=True)

    print("\nbuilding 25/26 eval samples...", flush=True)
    ev = build_samples("2526")
    standardize(ev, stats)   # frozen fit-set standardization
    print(f"eval n={len(ev)}", flush=True)

    zb = json.loads(Path("data/config/zone_blend.json").read_text(encoding="utf-8"))
    ll_form = nll_channels(ev, [0, 0, 0, 0])
    ll_ship = nll_scalar(ev, zb.get("gamma", 0.0), zb.get("adv_mean", 0.0),
                         zb.get("adv_std", 1.0) or 1.0)
    ll_chan = nll_channels(ev, g)

    print(f"\nEVAL 25/26 (frozen): form-only {ll_form:.5f} | shipping scalar "
          f"{ll_ship:.5f} | channels {ll_chan:.5f}")
    print(f"channels vs form:     {ll_chan - ll_form:+.5f}")
    print(f"channels vs shipping: {ll_chan - ll_ship:+.5f}")
    verdict = "KEEP-CHANNELS" if ll_chan <= ll_ship - 1e-4 else \
              "KEEP-SCALAR" if ll_ship <= ll_form else "REJECT-ALL"
    print(f"VERDICT: {verdict}")

    Path("data/reports/experiment_zone_channels.json").write_text(json.dumps({
        "gammas": dict(zip(CHANNELS, g)),
        "stats": {c: {"mean": round(stats[c][0], 4), "std": round(stats[c][1], 4)}
                  for c in CHANNELS},
        "fit_n": len(fit), "eval_n": len(ev),
        "fit_base": round(base_fit, 5), "fit_channels": round(ll_fit, 5),
        "eval_form_only": round(ll_form, 5), "eval_shipping": round(ll_ship, 5),
        "eval_channels": round(ll_chan, 5), "verdict": verdict,
    }, indent=2), encoding="utf-8")
    print("-> data/reports/experiment_zone_channels.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
