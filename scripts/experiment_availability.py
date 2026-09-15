"""Experiment C (user directive: mental/roster signal must reach the model):
does AVAILABILITY SHOCK add anything on top of the shipping model?

THE HONEST CONSTRAINT: at prediction time we do not know tonight's XI —
we scrape no lineup or injury feed. So the only leak-free version of this
signal is the team's RECENT absence state, computed strictly from matches
before the fixture:

    core(T,D)   = players whose minutes share (before D) >= CORE_SHARE
    shock1(T,D) = core minutes-mass that did NOT appear in the last match
    shock2(T,D) = core minutes-mass absent from BOTH of the last two
                  (rotation shows up in shock1; injuries persist into shock2)

Absence is modelled on both sides — my missing men cost me goals, their
missing men buy me goals:

    lam_home *= exp(a1*z_s1_home + b1*z_s1_away + a2*z_s2_home + b2*z_s2_away)
    lam_away *= mirror

Baseline is the SHIPPING model (zone channels blended in), so this measures
what availability adds ON TOP of what already ships. Protocol is weaker
than Experiment A by necessity: Understat rosters only exist from 25/26, so
this is a within-season forward holdout — fit weeks 5-21, FROZEN eval
weeks 22-38 — not a whole unseen season. Stated in the verdict.

Usage: .venv/Scripts/python.exe scripts/experiment_availability.py
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
from services.understat.rosters_service import RostersService
from services.understat.understat_service import UnderstatService
from services.zones.zones_engine import ZonesEngine, channel_boosts

FIT_SEASON = "2425"        # rosters backfilled 2026-09-15 (1,750 matches)
EVAL_SEASON = "2526"       # whole unseen season — same standard zones passed
FROM_WEEK = 5
MIN_TEAM_MATCHES_IN_WINDOW = 8
MIN_PRIOR_MATCHES = 5      # shock needs a squad picture first
CORE_SHARE = 0.5           # a "regular": >= 50% of available minutes so far
PARAMS = ("own_s1", "opp_s1", "own_s2", "opp_s2")


def team_timelines(league, season):
    """team -> [(date, {player: minutes}), ...] ordered by date."""
    data = RostersService.load(league, season) or {}
    tl = defaultdict(list)
    for m in data.get("matches", {}).values():
        for side, team in (("h", m["home_team"]), ("a", m["away_team"])):
            mins = {p["player"]: (p.get("minutes") or 0)
                    for p in m["rosters"].get(side, [])}
            if mins:
                tl[team].append((m["date"], mins))
    for t in tl:
        tl[t].sort(key=lambda x: x[0])
    return tl


def shocks(timeline, date):
    """(shock1, shock2) for a team as of `date` — strictly prior matches."""
    prior = [x for x in timeline if x[0] < date]
    if len(prior) < MIN_PRIOR_MATCHES:
        return None
    total = defaultdict(float)
    for _, mins in prior:
        for p, mn in mins.items():
            total[p] += mn
    cap = 90.0 * len(prior)
    share = {p: v / cap for p, v in total.items()}
    core = {p: s for p, s in share.items() if s >= CORE_SHARE}
    if not core:
        return None
    mass = sum(core.values())
    last = {p for p, mn in prior[-1][1].items() if mn > 0}
    prev = {p for p, mn in prior[-2][1].items() if mn > 0} if len(prior) >= 2 else last
    s1 = sum(s for p, s in core.items() if p not in last) / mass
    s2 = sum(s for p, s in core.items() if p not in last and p not in prev) / mass
    return s1, s2


def build_samples(season):
    params = json.loads(Path("data/config/model_params.json").read_text(encoding="utf-8"))
    rho = params["rho"]
    zb = json.loads(Path("data/config/zone_blend.json").read_text(encoding="utf-8"))
    samples = []
    skipped = 0
    for league in LEAGUE_NAME_MAP:
        boosts = params["leagues"][league]
        fm = FormModel(league, (["2425", season] if season != "2425" else [season]))
        us = UnderstatService.load(league, season)
        fx = FixturesService.load(league, season)
        wk = {(m["home_team"], m["away_team"]): m["week"]
              for m in fx["matches"] if isinstance(m["week"], int)}
        eng = ZonesEngine(league, season)
        tl = team_timelines(league, season)
        zcache = {}
        counts = {}
        for m in sorted(us["matches"], key=lambda x: x["date"]):
            if m["home_goals"] is None:
                continue
            h, a, d = m["home_team"], m["away_team"], m["date"]
            nh, na = counts.get(h, 0), counts.get(a, 0)
            counts[h], counts[a] = nh + 1, na + 1
            week = wk.get((h, a))
            if week is None or week < FROM_WEEK:
                continue
            ratings = fm.ratings_before(d)
            lam_h, lam_a, low = fm.lambdas(ratings, h, a,
                                           boosts["home_boost"], boosts["away_boost"])
            if low:
                continue
            roll = DrawModel.rolling_stats(fm.matches, d)
            if h not in roll or a not in roll:
                continue
            sh, sa = shocks(tl.get(h, []), d), shocks(tl.get(a, []), d)
            if sh is None or sa is None:
                skipped += 1
                continue
            # shipping baseline: zone channels blended in
            if nh >= MIN_TEAM_MATCHES_IN_WINDOW and na >= MIN_TEAM_MATCHES_IN_WINDOW:
                if d not in zcache:
                    try:
                        zcache[d] = eng.build(as_of_date=d, persist=False,
                                              include_players=False)["teams"]
                    except Exception:
                        zcache[d] = None
                zones = zcache[d]
                if zones and zb.get("mode") == "channels":
                    b = channel_boosts(zones, h, a, zb)
                    if b:
                        lam_h, lam_a = lam_h * b[0], lam_a * b[1]
            ctx = DrawModel.season_context(us["matches"], d, h, a)
            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            samples.append({"week": week, "lam_h": lam_h, "lam_a": lam_a, "rho": rho,
                            "roll_h": roll[h], "roll_a": roll[a], "ctx": ctx,
                            "s1h": sh[0], "s2h": sh[1], "s1a": sa[0], "s2a": sa[1],
                            "outcome": outcome})
        print(f"  {league}: {len(samples)} cumulative (skipped {skipped})", flush=True)
    return samples


def standardize(samples, stats=None):
    keys = (("s1h", "s1a"), ("s2h", "s2a"))
    if stats is None:
        stats = {}
        for hk, ak in keys:
            vals = [s[hk] for s in samples] + [s[ak] for s in samples]
            mean = sum(vals) / len(vals)
            std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
            stats[hk[:2]] = (mean, std)
    for s in samples:
        for hk, ak in keys:
            mu, sd = stats[hk[:2]]
            s["z_" + hk] = (s[hk] - mu) / sd
            s["z_" + ak] = (s[ak] - mu) / sd
    return stats


def boosted(s, g, mode="full"):
    """mode 'full': own+opponent effects fit freely (4 params).
    mode 'diff': DIFFERENTIAL only (2 params) — absences move the balance
    between the teams but cannot move total goals. Pre-specified follow-up:
    if 'full' fits own and opponent with the SAME sign it has found a
    'fewer goals tonight' effect, not a 'who wins' effect."""
    if mode == "diff":
        d1, d2 = g[0], g[1]
        e = d1 * (s["z_s1a"] - s["z_s1h"]) + d2 * (s["z_s2a"] - s["z_s2h"])
        return s["lam_h"] * math.exp(e), s["lam_a"] * math.exp(-e)
    a1, b1, a2, b2 = g
    bh = math.exp(a1 * s["z_s1h"] + b1 * s["z_s1a"] + a2 * s["z_s2h"] + b2 * s["z_s2a"])
    ba = math.exp(a1 * s["z_s1a"] + b1 * s["z_s1h"] + a2 * s["z_s2a"] + b2 * s["z_s2h"])
    return s["lam_h"] * bh, s["lam_a"] * ba


def nll(samples, g, clf=None, mode="full"):
    """Poisson-only when clf is None; full stack (unified probs) when given."""
    total = 0.0
    for s in samples:
        lh, la = boosted(s, g, mode)
        p = outcome_probs(lh, la, s["rho"])
        if clf is not None:
            p = unified_probs(p, clf.predict(DrawModel.fixture_features(
                lh, la, s["rho"], s["roll_h"], s["roll_a"], s["ctx"])))
        total -= math.log(max(p[s["outcome"]], 1e-9))
    return total / len(samples)


def fit_gammas(samples, mode="full"):
    k_params = 2 if mode == "diff" else 4
    g = [0.0] * k_params
    best = nll(samples, g, mode=mode)
    for step in (0.04, 0.02, 0.01, 0.005):
        improved = True
        while improved:
            improved = False
            for k in range(k_params):
                for direction in (+1, -1):
                    cand = list(g)
                    cand[k] = round(cand[k] + direction * step, 4)
                    if abs(cand[k]) > 0.3:
                        continue
                    ll = nll(samples, cand, mode=mode)
                    if ll < best - 1e-6:
                        g, best = cand, ll
                        improved = True
    return g, best


def metrics(samples, g, clf, mode="full"):
    """Full-stack money metrics, same shape as the zone-channel gate."""
    rs = []
    for s in samples:
        lh, la = boosted(s, g, mode)
        p = unified_probs(outcome_probs(lh, la, s["rho"]),
                          clf.predict(DrawModel.fixture_features(
                              lh, la, s["rho"], s["roll_h"], s["roll_a"], s["ctx"])))
        rs.append({"week": s["week"], "probs": p, "outcome": s["outcome"]})
    n = len(rs)
    acc = sum(1 for r in rs if max(r["probs"], key=r["probs"].get) == r["outcome"]) / n
    ll = -sum(math.log(max(r["probs"][r["outcome"]], 1e-9)) for r in rs) / n
    gold = [r for r in rs if max(r["probs"], key=r["probs"].get) in ("home", "away")
            and max(r["probs"].values()) >= 0.55]
    g_hit = sum(1 for r in gold if max(r["probs"], key=r["probs"].get) == r["outcome"])
    by_week = defaultdict(list)
    for r in rs:
        by_week[r["week"]].append(r)
    d_h = d_n = 0
    for _, ws in by_week.items():
        top4 = sorted(ws, key=lambda r: r["probs"]["draw"], reverse=True)[:4]
        if len(top4) == 4:
            d_h += sum(1 for r in top4 if r["outcome"] == "draw")
            d_n += 4
    return {"n": n, "acc": round(acc * 100, 2), "log_loss": round(ll, 5),
            "draws_top4": round(d_h / d_n * 100, 2) if d_n else None,
            "draws_top4_n": d_n, "gold_n": len(gold),
            "gold": round(g_hit / len(gold) * 100, 2) if gold else None}


def cached_samples(season):
    path = Path(f"data/reports/_availability_samples_{season}.json")
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
        print(f"loaded {len(rows)} cached samples for {season}", flush=True)
        return rows
    print(f"building {season} samples with the SHIPPING model as baseline "
          "(zone builds — several minutes)...", flush=True)
    rows = build_samples(season)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def main() -> int:
    clf = DrawModel.load()
    fit = cached_samples(FIT_SEASON)
    ev = cached_samples(EVAL_SEASON)
    stats = standardize(fit)
    standardize(ev, stats)
    print(f"fit n={len(fit)} ({FIT_SEASON}) | eval n={len(ev)} ({EVAL_SEASON}, "
          f"whole unseen season)", flush=True)

    s1 = [s["s1h"] for s in fit] + [s["s1a"] for s in fit]
    s2 = [s["s2h"] for s in fit] + [s["s2a"] for s in fit]
    print(f"shock1 mean {sum(s1)/len(s1):.3f} max {max(s1):.3f} | "
          f"shock2 mean {sum(s2)/len(s2):.3f} max {max(s2):.3f}", flush=True)

    base_ev = nll(ev, [0, 0, 0, 0])
    m_base = metrics(ev, [0, 0, 0, 0], clf)
    print(f"\n shipping     : eval-nll {base_ev:.5f} | acc {m_base['acc']}% "
          f"ll {m_base['log_loss']} draws top-4 {m_base['draws_top4']}% "
          f"GOLD {m_base['gold']}% (n={m_base['gold_n']})")

    out = {
        "protocol": f"fit {FIT_SEASON} (GW{FROM_WEEK}+), FROZEN eval {EVAL_SEASON} "
                    f"whole season — same standard the zone channels passed",
        "stats": {k: {"mean": round(v[0], 4), "std": round(v[1], 4)}
                  for k, v in stats.items()},
        "fit_n": len(fit), "eval_n": len(ev),
        "eval_shipping": round(base_ev, 5), "metrics_shipping": m_base,
        "variants": {},
    }
    verdicts = {}
    for mode, names in (("full", PARAMS), ("diff", ("d_s1", "d_s2"))):
        base_fit = nll(fit, [0] * len(names), mode=mode)
        g, ll_fit = fit_gammas(fit, mode)
        ev_nll = nll(ev, g, mode=mode)
        m = metrics(ev, g, clf, mode)
        ship = (ev_nll <= base_ev - 1e-4
                and m["log_loss"] <= m_base["log_loss"]
                and m["draws_top4"] >= m_base["draws_top4"] - 0.5
                and (m["gold"] or 0) >= (m_base["gold"] or 0) - 1.0)
        verdicts[mode] = "SHIP" if ship else "REJECT"
        print(f" {mode:<12}: eval-nll {ev_nll:.5f} ({ev_nll - base_ev:+.5f}) | "
              f"acc {m['acc']}% ll {m['log_loss']} draws top-4 {m['draws_top4']}% "
              f"GOLD {m['gold']}% (n={m['gold_n']})  gammas={dict(zip(names, g))}"
              f"  -> {verdicts[mode]}", flush=True)
        out["variants"][mode] = {
            "gammas": dict(zip(names, g)),
            "fit_base": round(base_fit, 5), "fit_fitted": round(ll_fit, 5),
            "eval_nll": round(ev_nll, 5), "metrics": m, "verdict": verdicts[mode],
        }

    out["verdict"] = ("SHIP-" + max(verdicts, key=lambda k: verdicts[k] == "SHIP").upper()
                      if "SHIP" in verdicts.values() else "REJECT-ALL")
    print(f"\nVERDICT: {out['verdict']}  (fit {FIT_SEASON} -> frozen {EVAL_SEASON}; "
          f"nothing touches live picks mid-cycle — any SHIP is wired during the "
          f"international break and frozen before the Oct 7 booking)")
    Path("data/reports/experiment_availability.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print("-> data/reports/experiment_availability.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
