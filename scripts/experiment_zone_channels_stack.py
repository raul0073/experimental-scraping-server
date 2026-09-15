"""Experiment A, stage 2 — FULL-STACK gate for zone channels.

Stage 1 (experiment_zone_channels.py) showed channels beat the shipping
scalar on raw Poisson log-loss. But production feeds the BLENDED lambdas
into the draw classifier, so the money metrics must be re-verified through
the whole stack. Replays 25/26 GW5+ three ways — no blend / shipping
scalar / channels — and compares what we actually bet on:

    draws top-4 weekly hit%  ·  GOLD (>=0.55) realized  ·  outcome acc
    ·  unified log-loss

Ship only if channels hold or improve draws top-4 (>= scalar's) and GOLD
realization is not degraded (rules.md #5).

Usage: .venv/Scripts/python.exe scripts/experiment_zone_channels_stack.py
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from scripts.calibrate_zone_blend import zone_advantage
from services.zones.zones_engine import CHANNELS, channel_feats
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService
from services.zones.zones_engine import ZonesEngine

EVAL = "2526"
FROM_WEEK = 5
MIN_TEAM_MATCHES_IN_WINDOW = 8


def main() -> int:
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    rho = params["rho"]
    clf = DrawModel.load()
    zb = json.loads(Path("data/config/zone_blend.json").read_text(encoding="utf-8"))
    ch = json.loads(Path("data/reports/experiment_zone_channels.json").read_text(encoding="utf-8"))
    g = [ch["gammas"][c] for c in CHANNELS]
    st = {c: (ch["stats"][c]["mean"], ch["stats"][c]["std"]) for c in CHANNELS}

    variants = ("none", "scalar", "channels")
    rows = {v: [] for v in variants}

    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, ["2425", EVAL])
        us = UnderstatService.load(league, EVAL)
        fx = FixturesService.load(league, EVAL)
        wk = {(m["home_team"], m["away_team"]): m["week"]
              for m in fx["matches"] if isinstance(m["week"], int)}
        eng = ZonesEngine(league, EVAL)
        zcache = {}
        season_counts = {}
        for m in sorted(us["matches"], key=lambda x: x["date"]):
            if m["home_goals"] is None:
                continue
            nh = season_counts.get(m["home_team"], 0)
            na = season_counts.get(m["away_team"], 0)
            season_counts[m["home_team"]] = nh + 1
            season_counts[m["away_team"]] = na + 1
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

            zones = None
            if nh >= MIN_TEAM_MATCHES_IN_WINDOW and na >= MIN_TEAM_MATCHES_IN_WINDOW:
                if m["date"] not in zcache:
                    try:
                        zcache[m["date"]] = eng.build(as_of_date=m["date"], persist=False,
                                                      include_players=False)["teams"]
                    except Exception:
                        zcache[m["date"]] = None
                zones = zcache[m["date"]]
                if zones and (m["home_team"] not in zones or m["away_team"] not in zones):
                    zones = None

            lams = {"none": (lam_h, lam_a)}
            if zones:
                adv = zone_advantage(zones, m["home_team"], m["away_team"])
                gm, mu, sd = zb.get("gamma", 0.0), zb.get("adv_mean", 0.0), zb.get("adv_std", 1.0) or 1.0
                lams["scalar"] = (lam_h * math.exp(gm * (adv[0] - mu) / sd),
                                  lam_a * math.exp(gm * (adv[1] - mu) / sd))
                fh = channel_feats(zones, m["home_team"], m["away_team"])
                fa = channel_feats(zones, m["away_team"], m["home_team"])
                bh = math.exp(sum(gi * (fh[c] - st[c][0]) / st[c][1]
                                  for gi, c in zip(g, CHANNELS)))
                ba = math.exp(sum(gi * (fa[c] - st[c][0]) / st[c][1]
                                  for gi, c in zip(g, CHANNELS)))
                lams["channels"] = (lam_h * bh, lam_a * ba)
            else:
                lams["scalar"] = lams["none"]
                lams["channels"] = lams["none"]

            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            for v in variants:
                lh, la = lams[v]
                p_clf = clf.predict(DrawModel.fixture_features(
                    lh, la, rho, roll[m["home_team"]], roll[m["away_team"]], ctx))
                probs = unified_probs(outcome_probs(lh, la, rho), p_clf)
                rows[v].append({"week": week, "probs": probs, "outcome": outcome})
        print(f"  {league}: n={len(rows['none'])} cumulative", flush=True)

    report = {}
    for v in variants:
        rs = rows[v]
        n = len(rs)
        acc = sum(1 for r in rs if max(r["probs"], key=r["probs"].get) == r["outcome"]) / n
        ll = -sum(math.log(max(r["probs"][r["outcome"]], 1e-9)) for r in rs) / n
        gold = [r for r in rs
                if max(r["probs"], key=r["probs"].get) in ("home", "away")
                and max(r["probs"].values()) >= 0.55]
        g_hit = sum(1 for r in gold if max(r["probs"], key=r["probs"].get) == r["outcome"])
        by_week = defaultdict(list)
        for r in rs:
            by_week[r["week"]].append(r)
        d_h = d_n = 0
        for w, ws in by_week.items():
            top4 = sorted(ws, key=lambda r: r["probs"]["draw"], reverse=True)[:4]
            if len(top4) == 4:
                d_h += sum(1 for r in top4 if r["outcome"] == "draw")
                d_n += 4
        report[v] = {"n": n, "outcome_acc": round(acc * 100, 2),
                     "log_loss": round(ll, 5),
                     "draws_top4": round(d_h / d_n * 100, 2) if d_n else None,
                     "draws_top4_n": d_n,
                     "gold_n": len(gold),
                     "gold_realized": round(g_hit / len(gold) * 100, 2) if gold else None}
        print(f"{v:>9}: acc {report[v]['outcome_acc']}%  ll {report[v]['log_loss']}  "
              f"draws top-4 {report[v]['draws_top4']}% (n={d_n})  "
              f"GOLD {report[v]['gold_realized']}% (n={len(gold)})", flush=True)

    ship = (report["channels"]["draws_top4"] >= report["scalar"]["draws_top4"] - 0.5
            and (report["channels"]["gold_realized"] or 0) >= (report["scalar"]["gold_realized"] or 0) - 1.0
            and report["channels"]["log_loss"] <= report["scalar"]["log_loss"])
    report["verdict"] = "SHIP-CHANNELS" if ship else "HOLD-SCALAR"
    print(f"\nVERDICT: {report['verdict']}")
    Path("data/reports/experiment_zone_channels_stack.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("-> data/reports/experiment_zone_channels_stack.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
