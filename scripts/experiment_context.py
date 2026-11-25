"""Does context - rest, congestion, European involvement, what is at stake,
how late in the season - move the published triplet closer to the closing
line? Eight seasons, walk-forward, against the market.

WHY. experiment_calibration.py (2026-11-25) showed the shipped triplet is
not timid: recalibration recovers 0.003 of a 0.018-nat gap to the closing
line and no accuracy. What the market has and we do not is information.
The user's thesis is that motivation is the biggest missing piece. This
tests the part of it that can be computed from history we already hold.

FEATURES, all computed strictly from matches dated before the fixture:
    rest_h, rest_a        days since each side's previous league match
                          (capped at 14; the international-break reset)
    congested_h/a         third league match inside 8 days
    europe_h/a            finished top 6 the previous season (proxy for a
                          European campaign: no continental fixtures on disk)
    midweek               fixture on Tue/Wed/Thu (cup and European weeks)
    ppg_h, ppg_a          points a game this season so far
    gap_title_h/a         points behind the leader, per game left (0 if leading)
    gap_europe_h/a        points behind 4th place, per game left (negative = above)
    gap_drop_h/a          points above 18th place, per game left (negative = below)
    season_frac           games played / 38
    dead_h/a              late (season_frac >= 0.75) and more than 3 points a
                          game out of every race: nothing to play for
    derby                 same city or classic rivalry list (small, explicit)

MODEL. A multinomial logistic on [log p_blend (3), features], fitted on the
seasons before S and scored on S - the same stacker as the 'dirichlet'
candidate in experiment_calibration, so the marginal value of context is
the difference between the two. Features are standardised on the training
rows. L2 1e-3 on everything but the log-probability weights.

SCORED against the closing line as before, plus the confident tier: calls
at >= 55% and >= 60% published probability, how many and how often they
land, for the shipped triplet and the context stacker.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\experiment_context.py
Writes data/reports/experiment_context.{json,md}. Changes nothing.
"""
import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy.optimize import minimize

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.understat.understat_service import UnderstatService

from backtest_season import ALL_SEASONS                       # noqa: E402
from build_market import OddsIndex, PROJECT_NAMES, WF_ROWS, load_odds   # noqa: E402
from experiment_calibration import fit_dirichlet, paired, score         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_context.json"
REPORT_MD = ROOT / "data" / "reports" / "experiment_context.md"
SEASONS = ["1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526"]
YI = {"H": 0, "D": 1, "A": 2}
FEATURES = ["rest_h", "rest_a", "congested_h", "congested_a", "europe_h", "europe_a",
            "midweek", "ppg_h", "ppg_a", "gap_title_h", "gap_title_a", "gap_europe_h",
            "gap_europe_a", "gap_drop_h", "gap_drop_a", "season_frac", "dead_h", "dead_a",
            "derby"]
DERBIES = {
    ("Manchester City", "Manchester Utd"), ("Liverpool", "Everton"), ("Arsenal", "Tottenham"),
    ("Chelsea", "Tottenham"), ("Arsenal", "Chelsea"), ("Newcastle", "Sunderland"),
    ("Real Madrid", "Barcelona"), ("Real Madrid", "Atlético Madrid"), ("Sevilla", "Real Betis"),
    ("Athletic Club", "Real Sociedad"), ("Valencia", "Levante"), ("Barcelona", "Espanyol"),
    ("Inter", "Milan"), ("Roma", "Lazio"), ("Juventus", "Torino"), ("Genoa", "Sampdoria"),
    ("Juventus", "Inter"), ("Bayern Munich", "Dortmund"), ("Schalke 04", "Dortmund"),
    ("Hamburger SV", "Werder Bremen"), ("Bayern Munich", "Augsburg"), ("Paris Saint Germain", "Marseille"),
    ("Lyon", "Saint-Etienne"), ("Nice", "Monaco"),
}
DERBY_KEYS = {frozenset(p) for p in DERBIES}


# --------------------------------------------------------------- standings

def league_tables(league: str) -> dict:
    """(season) -> ordered list of matches and, per team, the finish rank
    of the previous season. Everything else is computed per fixture."""
    out = {}
    finish = {}
    for season in ALL_SEASONS:
        data = UnderstatService.load(league, season) or {}
        ms = sorted((m for m in data.get("matches", []) if m.get("home_goals") is not None),
                    key=lambda m: m["date"])
        if not ms:
            continue
        pts = defaultdict(int)
        for m in ms:
            h, a, hg, ag = m["home_team"], m["away_team"], int(m["home_goals"]), int(m["away_goals"])
            pts[h] += 3 if hg > ag else 1 if hg == ag else 0
            pts[a] += 3 if ag > hg else 1 if hg == ag else 0
        order = sorted(pts, key=lambda t: -pts[t])
        out[season] = {"matches": ms, "prev_finish": dict(finish)}
        finish = {t: i + 1 for i, t in enumerate(order)}
    return out


def context_for(league_data: dict, season: str, date: str, home: str, away: str) -> list:
    ms = league_data[season]["matches"]
    prev = league_data[season]["prev_finish"]
    pts, played, last = defaultdict(int), defaultdict(int), {}
    recent = defaultdict(list)
    d0 = dt.date.fromisoformat(date[:10])
    for m in ms:
        if m["date"] >= date:
            break
        h, a, hg, ag = m["home_team"], m["away_team"], int(m["home_goals"]), int(m["away_goals"])
        pts[h] += 3 if hg > ag else 1 if hg == ag else 0
        pts[a] += 3 if ag > hg else 1 if hg == ag else 0
        played[h] += 1
        played[a] += 1
        md = dt.date.fromisoformat(str(m["date"])[:10])
        last[h] = last[a] = md
        recent[h].append(md)
        recent[a].append(md)
    n_teams = max(len(pts), 18)
    games = 2 * (n_teams - 1)

    def rest(t):
        return min((d0 - last[t]).days, 14) if t in last else 14

    def congested(t):
        return 1.0 if sum(1 for x in recent[t] if (d0 - x).days <= 8) >= 2 else 0.0

    def ppg(t):
        return pts[t] / played[t] if played[t] else 1.3

    ranked = sorted(pts.values(), reverse=True)
    leader = ranked[0] if ranked else 0
    fourth = ranked[3] if len(ranked) > 3 else 0
    drop = ranked[n_teams - 3] if len(ranked) >= n_teams - 2 else 0
    frac = min((played[home] + played[away]) / 2 / games, 1.0)

    def per_left(t, diff):
        left = max(games - played[t], 1)
        return diff / left

    def gaps(t):
        return (per_left(t, max(leader - pts[t], 0)),
                per_left(t, fourth - pts[t]),
                per_left(t, pts[t] - drop))

    def dead(t):
        gt, ge, gd = gaps(t)
        return 1.0 if frac >= 0.75 and gt > 3 and ge > 3 and gd > 3 else 0.0

    gh, ga = gaps(home), gaps(away)
    return [rest(home), rest(away), congested(home), congested(away),
            1.0 if prev.get(home, 20) <= 6 else 0.0, 1.0 if prev.get(away, 20) <= 6 else 0.0,
            1.0 if d0.weekday() in (1, 2, 3) else 0.0,
            ppg(home), ppg(away), gh[0], ga[0], gh[1], ga[1], gh[2], ga[2], frac,
            dead(home), dead(away), 1.0 if frozenset((home, away)) in DERBY_KEYS else 0.0]


# ------------------------------------------------------------------ stacker

def fit_stacker(P, F, y, l2=1e-3):
    X = np.hstack([np.log(np.clip(P, 1e-9, None)), F])
    mean, std = X.mean(axis=0), X.std(axis=0) + 1e-9
    mean[:3] = 0.0
    std[:3] = 1.0                       # log-probabilities enter raw, as in dirichlet
    Xn = np.hstack([np.ones((len(X), 1)), (X - mean) / std])
    k = Xn.shape[1]

    def unpack(w):
        return w.reshape(3, k)

    def nll(w):
        W = unpack(w)
        Z = Xn @ W.T
        Z -= Z.max(axis=1, keepdims=True)
        logq = Z - np.log(np.exp(Z).sum(axis=1, keepdims=True))
        pen = ((W[:, 1:4] - np.eye(3)) ** 2).sum() + (W[:, 4:] ** 2).sum() + (W[:, 0] ** 2).sum()
        return -logq[np.arange(len(y)), y].mean() + l2 * pen

    w0 = np.zeros((3, k))
    w0[:, 1:4] = np.eye(3)
    w = minimize(nll, x0=w0.ravel(), method="L-BFGS-B").x
    W = unpack(w)

    def apply(Pt, Ft):
        Xt = np.hstack([np.log(np.clip(Pt, 1e-9, None)), Ft])
        Xt = np.hstack([np.ones((len(Xt), 1)), (Xt - mean) / std])
        Z = Xt @ W.T
        Z -= Z.max(axis=1, keepdims=True)
        Q = np.exp(Z)
        return Q / Q.sum(axis=1, keepdims=True)
    return apply, W


def tier(Q, y, cut):
    top = Q.max(axis=1)
    m = top >= cut
    return {"n": int(m.sum()), "share": round(float(m.mean()), 4),
            "hit": round(float((Q[m].argmax(axis=1) == y[m]).mean()), 4) if m.any() else None,
            "expected": round(float(top[m].mean()), 4) if m.any() else None}


# --------------------------------------------------------------------- main

def main() -> int:
    print("rows + closing odds ...", flush=True)
    project_map = json.loads(PROJECT_NAMES.read_text(encoding="utf-8"))
    idx = OddsIndex(load_odds(no_download=True, project_map=project_map))
    with WF_ROWS.open(encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    tables = {lg: league_tables(lg) for lg in LEAGUE_NAME_MAP}
    rows = []
    for r in raw:
        pm = project_map.get(r["league"], {})
        hit = idx.find(r["league"], pm.get(r["home"], r["home"]), pm.get(r["away"], r["away"]), r["date"])
        if hit is None or r["season"] not in tables[r["league"]]:
            continue
        rows.append({
            "season": r["season"], "league": r["league"], "y": YI[r["y"]],
            "p": [float(r["blend_H"]), float(r["blend_D"]), float(r["blend_A"])],
            "m": [float(getattr(hit, "norm_home")), float(getattr(hit, "norm_draw")), float(getattr(hit, "norm_away"))],
            "f": context_for(tables[r["league"]], r["season"], r["date"], r["home"], r["away"]),
        })
    print(f"  {len(rows)} fixtures with context", flush=True)
    seasons = np.array([r["season"] for r in rows])
    leagues = np.array([r["league"] for r in rows])
    y = np.array([r["y"] for r in rows])
    P = np.array([r["p"] for r in rows])
    M = np.array([r["m"] for r in rows])
    F = np.array([r["f"] for r in rows])

    cand = {"blend": P.copy(), "market": M.copy(), "dirichlet": P.copy(), "context": P.copy()}
    weights = {}
    for s in SEASONS[1:]:
        tr, te = seasons < s, seasons == s
        if not te.any():
            continue
        apply_d, _ = fit_dirichlet(P[tr], y[tr])
        cand["dirichlet"][te] = apply_d(P[te])
        apply_c, W = fit_stacker(P[tr], F[tr], y[tr])
        cand["context"][te] = apply_c(P[te], F[te])
        weights[s] = {f: [round(float(W[o, 4 + i]), 3) for o in range(3)] for i, f in enumerate(FEATURES)}
    scored = seasons >= SEASONS[1]

    out, lls = {}, {}
    for name, Q in cand.items():
        ll, acc = score(Q[scored], y[scored])
        lls[name] = ll
        out[name] = {"n": int(scored.sum()), "log_loss": round(float(ll.mean()), 5), "accuracy": round(float(acc), 4),
                     "tier55": tier(Q[scored], y[scored], 0.55), "tier60": tier(Q[scored], y[scored], 0.60),
                     "by_league": {}}
        for lg in sorted(set(leagues)):
            m = scored & (leagues == lg)
            l2, a2 = score(Q[m], y[m])
            out[name]["by_league"][lg] = {"log_loss": round(float(l2.mean()), 5), "accuracy": round(float(a2), 4),
                                          "gap": round(float(l2.mean() - score(M[m], y[m])[0].mean()), 5)}
    for name in out:
        out[name]["gap_to_market"] = round(float(lls[name].mean() - lls["market"].mean()), 5)
        if name != "blend":
            out[name]["vs_blend"] = paired(lls[name], lls["blend"])
    out["context"]["vs_dirichlet"] = paired(lls["context"], lls["dirichlet"])
    # which features carry weight: mean |w| across seasons and outcomes
    importance = {f: round(float(np.mean([abs(v) for s in weights for v in weights[s][f]])), 3) for f in FEATURES}
    REPORT.write_text(json.dumps({"features": FEATURES, "importance": importance, "weights": weights,
                                  "results": out}, indent=2), encoding="utf-8")

    L = ["# Context layer against the closing line", "",
         f"{int(scored.sum())} fixtures, seasons {SEASONS[1]}..{SEASONS[-1]}, walk-forward. "
         "'dirichlet' is the same stacker without context, so context's marginal value is "
         "context minus dirichlet.", "",
         "| candidate | log-loss | accuracy | gap to market | calls >=55%: n / hit / expected | calls >=60%: n / hit / expected | vs blend p |",
         "|---|---|---|---|---|---|---|"]
    for name, res in out.items():
        t5, t6 = res["tier55"], res["tier60"]
        L.append(f"| {name} | {res['log_loss']:.5f} | {res['accuracy']:.1%} | {res['gap_to_market']:+.4f} | "
                 f"{t5['n']} / {t5['hit']:.1%} / {t5['expected']:.1%} | {t6['n']} / {t6['hit']:.1%} / {t6['expected']:.1%} | "
                 f"{res.get('vs_blend', {}).get('p_better', '')} |")
    L.append(f"\ncontext vs dirichlet: {out['context']['vs_dirichlet']}")
    L += ["", "## Gap to market by league", "", "| candidate | " + " | ".join(lg.split('-')[-1] for lg in sorted(set(leagues))) + " |",
          "|---|" + "---|" * len(set(leagues))]
    for name, res in out.items():
        L.append(f"| {name} | " + " | ".join(f"{res['by_league'][lg]['gap']:+.4f} ({res['by_league'][lg]['accuracy']:.1%})"
                                             for lg in sorted(set(leagues))) + " |")
    L += ["", "## Feature weight (mean |w| over seasons and outcomes, standardised inputs)", ""]
    for f, v in sorted(importance.items(), key=lambda kv: -kv[1]):
        L.append(f"- {f}: {v}")
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:11]))
    print(f"\n-> {REPORT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
