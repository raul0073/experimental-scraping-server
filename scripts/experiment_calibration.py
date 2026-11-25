"""Is the published triplet too timid, and does fixing that close the gap to
the closing line? Eight seasons, walk-forward, against the market.

WHY. data/reports/market_report.md (2026-11-24): over 547 graded live
games the bookmakers' closing line beats the model by 0.032 nats, and the
further the model strays from the market the worse it does. The biggest
disagreements are all the same shape - a strong favourite priced 48-51%
where the market says 75-78%. A multiplicative form model compresses the
extremes. If that is systematic, a calibration fitted on EARLIER seasons
should recover part of the gap on the next one, without new data.

CANDIDATES, each fitted on the seasons before S and scored on S, S in
1819..2526 (1819 has no earlier scored season, so it is scored with the
control's parameters only where a fit is needed - reported separately):
    blend            the shipped triplet, untouched (control)
    temp             one temperature t: p_k ^ t, renormalised. t > 1 sharpens
    temp-league      a temperature per league
    dirichlet        full 3x3 + intercept multinomial recalibration on log p
    arm w + temp     weight w on the Elo arm against the form arm (ship is
                     0.5), then a temperature; w and t fitted jointly
    market           the closing line, de-margined, as the bar

SCORED on the joined rows (walk-forward fixtures with football-data.co.uk
closing odds, the same join build_market.py uses): log-loss, accuracy of
the most likely outcome, gap to the market, per league and per season,
paired bootstrap of per-fixture log-loss against the control, and the
draw side kept honest: draws found in the top 10% by the candidate's P(draw).

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\experiment_calibration.py
Reads data/reports/_walk_forward_rows.csv and the odds already on disk.
Writes data/reports/experiment_calibration.{json,md}. Changes nothing.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy.optimize import minimize

from build_market import OddsIndex, PROJECT_NAMES, WF_ROWS, load_odds  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_calibration.json"
REPORT_MD = ROOT / "data" / "reports" / "experiment_calibration.md"
SEASONS = ["1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526"]
ARMS = ("ship", "elo_clf", "blend")
YI = {"H": 0, "D": 1, "A": 2}
MARKET = "norm"


# ------------------------------------------------------------------ loading

def load_rows() -> list:
    project_map = json.loads(PROJECT_NAMES.read_text(encoding="utf-8"))
    idx = OddsIndex(load_odds(no_download=True, project_map=project_map))
    with WF_ROWS.open(encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    rows, unjoined = [], 0
    for r in raw:
        pm = project_map.get(r["league"], {})
        hit = idx.find(r["league"], pm.get(r["home"], r["home"]), pm.get(r["away"], r["away"]), r["date"])
        if hit is None:
            unjoined += 1
            continue
        rows.append({
            "season": r["season"], "league": r["league"], "y": YI[r["y"]],
            **{arm: np.array([float(r[f"{arm}_H"]), float(r[f"{arm}_D"]), float(r[f"{arm}_A"])])
               for arm in ARMS},
            "market": np.array([float(getattr(hit, f"{MARKET}_home")),
                                float(getattr(hit, f"{MARKET}_draw")),
                                float(getattr(hit, f"{MARKET}_away"))]),
        })
    print(f"  {len(rows)} joined of {len(raw)} walk-forward rows ({unjoined} unjoined)", flush=True)
    return rows


# ------------------------------------------------------------ calibrators

def _norm(P: np.ndarray) -> np.ndarray:
    P = np.clip(P, 1e-9, None)
    return P / P.sum(axis=1, keepdims=True)


def temp_apply(P, t):
    return _norm(P ** t)


def fit_temp(P, y) -> float:
    def nll(t):
        Q = temp_apply(P, t[0])
        return -np.log(Q[np.arange(len(y)), y]).mean()
    return float(minimize(nll, x0=[1.0], method="Nelder-Mead").x[0])


def fit_dirichlet(P, y):
    """Multinomial logistic on log-probabilities: 3x3 weights + 3 intercepts,
    L2 1e-3, BFGS. The identity (W=I, b=0) reproduces the input."""
    X = np.log(np.clip(P, 1e-9, None))

    def unpack(w):
        return w[:9].reshape(3, 3), w[9:]

    def nll(w):
        W, b = unpack(w)
        Z = X @ W.T + b
        Z -= Z.max(axis=1, keepdims=True)
        logq = Z - np.log(np.exp(Z).sum(axis=1, keepdims=True))
        return -logq[np.arange(len(y)), y].mean() + 1e-3 * ((W - np.eye(3)) ** 2).sum()

    x0 = np.concatenate([np.eye(3).ravel(), np.zeros(3)])
    w = minimize(nll, x0=x0, method="BFGS").x

    def apply(Pt):
        W, b = unpack(w)
        Z = np.log(np.clip(Pt, 1e-9, None)) @ W.T + b
        Z -= Z.max(axis=1, keepdims=True)
        return _norm(np.exp(Z))
    return apply, w


def fit_arm_temp(S, E, y):
    """weight w on the Elo arm (0 = form only, 1 = Elo only) and temperature t."""
    def mix(w, t):
        return temp_apply(_norm((1 - w) * S + w * E), t)

    def nll(x):
        w = min(max(x[0], 0.0), 1.0)
        Q = mix(w, x[1])
        return -np.log(Q[np.arange(len(y)), y]).mean()
    x = minimize(nll, x0=[0.5, 1.0], method="Nelder-Mead").x
    w, t = min(max(float(x[0]), 0.0), 1.0), float(x[1])
    return (lambda St, Et: temp_apply(_norm((1 - w) * St + w * Et), t)), w, t


# ------------------------------------------------------------------ scoring

def score(Q, y):
    ll = -np.log(np.clip(Q[np.arange(len(y)), y], 1e-9, None))
    acc = (Q.argmax(axis=1) == y).mean()
    return ll, acc


def top10_draw(Q, y, seasons):
    hits = n = 0
    for s in sorted(set(seasons)):
        m = seasons == s
        order = np.argsort(-Q[m, 1])
        k = max(1, m.sum() // 10)
        hits += (y[m][order[:k]] == 1).sum()
        n += k
    return hits / n


def paired(a, b, seed=0):
    diff = b - a
    rng = np.random.default_rng(seed)
    draws = np.array([rng.choice(diff, size=len(diff), replace=True).mean() for _ in range(4000)])
    return {"mean_gain": round(float(diff.mean()), 5), "p_better": round(float((draws > 0).mean()), 4)}


# --------------------------------------------------------------------- main

def main() -> int:
    print("joining walk-forward rows to closing odds ...", flush=True)
    rows = load_rows()
    seasons = np.array([r["season"] for r in rows])
    leagues = np.array([r["league"] for r in rows])
    y = np.array([r["y"] for r in rows])
    P = {arm: np.array([r[arm] for r in rows]) for arm in ARMS}
    M = np.array([r["market"] for r in rows])

    # walk-forward: fit on seasons < S, apply on S. 1819 has nothing earlier,
    # so every candidate is identity there and 1819 is excluded from the
    # candidate comparison (kept in the control/market lines for reference).
    cand = {"blend": P["blend"].copy(), "market": M.copy()}
    for name in ("temp", "temp-league", "dirichlet", "arm w + temp"):
        cand[name] = P["blend"].copy()
    params = defaultdict(dict)
    for s in SEASONS[1:]:
        tr, te = seasons < s, seasons == s
        if not te.any():
            continue
        t = fit_temp(P["blend"][tr], y[tr]); params["temp"][s] = round(t, 4)
        cand["temp"][te] = temp_apply(P["blend"][te], t)
        for lg in sorted(set(leagues)):
            trl, tel = tr & (leagues == lg), te & (leagues == lg)
            if trl.sum() < 200 or not tel.any():
                cand["temp-league"][tel] = temp_apply(P["blend"][tel], t)
                continue
            tl = fit_temp(P["blend"][trl], y[trl]); params["temp-league"][f"{s} {lg[:3]}"] = round(tl, 4)
            cand["temp-league"][tel] = temp_apply(P["blend"][tel], tl)
        apply, w = fit_dirichlet(P["blend"][tr], y[tr]); params["dirichlet"][s] = [round(float(v), 3) for v in w]
        cand["dirichlet"][te] = apply(P["blend"][te])
        mix, wgt, t2 = fit_arm_temp(P["ship"][tr], P["elo_clf"][tr], y[tr])
        params["arm w + temp"][s] = {"w_elo": round(wgt, 3), "t": round(t2, 4)}
        cand["arm w + temp"][te] = mix(P["ship"][te], P["elo_clf"][te])

    scored = seasons >= SEASONS[1]
    out = {}
    lls = {}
    for name, Q in cand.items():
        ll, acc = score(Q[scored], y[scored])
        lls[name] = ll
        res = {"n": int(scored.sum()), "log_loss": round(float(ll.mean()), 5),
               "accuracy": round(float(acc), 4),
               "top10_draw_hit": round(top10_draw(Q[scored], y[scored], seasons[scored]), 4),
               "by_league": {}, "by_season": {}}
        for lg in sorted(set(leagues)):
            m = scored & (leagues == lg)
            l2, a2 = score(Q[m], y[m])
            res["by_league"][lg] = {"n": int(m.sum()), "log_loss": round(float(l2.mean()), 5), "accuracy": round(float(a2), 4)}
        for s in SEASONS[1:]:
            m = scored & (seasons == s)
            if m.any():
                l2, a2 = score(Q[m], y[m])
                res["by_season"][s] = {"log_loss": round(float(l2.mean()), 5), "accuracy": round(float(a2), 4)}
        out[name] = res
    mk = lls["market"]
    for name, res in out.items():
        res["gap_to_market"] = round(float(lls[name].mean() - mk.mean()), 5)
        for lg in res["by_league"]:
            m = scored & (leagues == lg)
            res["by_league"][lg]["gap"] = round(res["by_league"][lg]["log_loss"] - float(score(M[m], y[m])[0].mean()), 5)
        if name != "blend":
            res["vs_blend"] = paired(lls[name], lls["blend"])
    REPORT.write_text(json.dumps({"params": params, "results": out}, indent=2), encoding="utf-8")

    L = ["# Calibrating the published triplet against the closing line", "",
         f"{int(scored.sum())} joined fixtures, seasons {SEASONS[1]}..{SEASONS[-1]}, each candidate "
         "fitted on earlier seasons only. Gap = candidate log-loss minus market log-loss; "
         "negative beats the market.", "",
         "| candidate | log-loss | accuracy | gap to market | top-10% draws | vs blend p |",
         "|---|---|---|---|---|---|"]
    for name, res in out.items():
        L.append(f"| {name} | {res['log_loss']:.5f} | {res['accuracy']:.1%} | {res['gap_to_market']:+.4f} | "
                 f"{res['top10_draw_hit']:.1%} | {res.get('vs_blend', {}).get('p_better', '')} |")
    L += ["", "## Gap to market by league", "", "| candidate | " + " | ".join(lg.split('-')[-1] for lg in sorted(set(leagues))) + " |",
          "|---|" + "---|" * len(set(leagues))]
    for name, res in out.items():
        L.append(f"| {name} | " + " | ".join(f"{res['by_league'][lg]['gap']:+.4f} ({res['by_league'][lg]['accuracy']:.1%})"
                                             for lg in sorted(set(leagues))) + " |")
    L += ["", "## Fitted parameters", "", "```", json.dumps(params, indent=1), "```"]
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12]))
    print(f"\n-> {REPORT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
