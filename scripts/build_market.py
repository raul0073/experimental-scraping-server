"""Versus the market: the published probabilities measured against bookmaker
closing odds. A benchmark, never advice.

WHY THIS EXISTS. The track record says how often the model was right and
whether its confidence was honest. Neither says how GOOD it is, because
neither has a reference. The reference every forecaster is held to is the
closing price at a sharp bookmaker: by kickoff it has absorbed every public
model and every professional's money, and almost nothing beats it over a
season. So this script asks two questions and refuses to ask a third:

    1. On the fixtures the model priced, is it closer to what happened
       than the market was?               (log loss, Brier, accuracy)
    2. Does it know anything the market does not?
       Stack both and see if the model's weight is distinguishable from
       zero out of sample.                (information test)

It never asks "could you have made money", and the odds it downloads are
never written beside a fixture that has not been played.

THREE SAMPLES, from thinnest to deepest:

    live           predictions committed before kickoff this season
    reconstructed  this season's earlier rounds, priced after the fact by
                   a walk-forward rebuild (retro=true in the history)
    historical     eight frozen seasons, 18/19-25/26, from
                   experiment_walk_forward.py — every fixture priced by a
                   model that had never seen its season

The live rows are the only ones that are a true out-of-sample forecast in
the strict sense; the historical ones are where the statistics have power.

INPUTS
    data/history/predictions.jsonl           the live record (read only)
    data/reports/_walk_forward_rows.csv      must carry date, home, away
    data/market/raw/{league}/{season}.csv    football-data.co.uk (cached)
    data/config/market_team_names.json       explicit name table

OUTPUTS
    data/web/market.json
    data/reports/market_report.md

JSON SCHEMA (data/web/market.json)
    generated           ISO timestamp
    source              "football-data.co.uk"
    source_url          template of the CSVs read
    margin_method       "normalise" | "shin" — what every market triplet
                        on this page was de-margined with
    margin_methods      {n, normalise_log_loss, shin_log_loss, reason}
                        the comparison that chose margin_method, on the
                        joined historical rows
    odds_column_used    {live | historical | all: {pinnacle_closing,
                        pinnacle, average}}: how many joined rows came from
                        each column. Pinnacle left the sheet in Jan 2026, so
                        the current season is scored on the market average
                        while the frozen seasons are Pinnacle closing.
    live
      join              {graded, joined, rate, unjoined: [{league,
                        kickoff, home, away, retro}]}
      splits            {live | reconstructed | all: {n, model, market,
                        uniform, base_rate, gap}}; each scorer is
                        {log_loss, brier, accuracy}; gap = model minus
                        market log loss in nats (negative = model better)
      by_league         {league: {n, model, market, gap}} over all joined
                        graded rows
      disagreement
        threshold       0.08
        buckets         [{bucket, n, model_log_loss, market_log_loss,
                        better}] by the max |model - market| over the
                        three outcomes
        rows            [{league, kickoff, home, away, retro, model{h,d,a},
                        market{h,d,a}, max_diff, result, better}] every
                        GRADED row above threshold, largest first
      histogram         {bins: [{from, to, label}], home: [n], draw: [n],
                        away: [n]} of model minus market probability
    historical
      leagues           leagues in the walk-forward rows
      join              {rows, joined, rate, unjoined: [{season, league,
                        date, home, away}]}
      seasons           [{season, n, blend_log_loss, layer_log_loss,
                        market_log_loss, blend_gap, layer_gap}]
      pooled            same keys without season
    information_test
      arm               "blend"
      n, seasons        rows and seasons used
      weight_model      beta on the model's log-probabilities in the
                        stacked fit on every row
      weight_market     beta on the market's
      ci95              [lo, hi] bootstrap over fixtures for weight_model
      resamples         bootstrap count
      per_season        [{season, n, market_only, stacked}] leave-one-
                        season-out log loss
      pooled            {market_only, stacked}
      adds_information  bool: CI excludes zero AND stacked beats
                        market-only pooled out of sample
      verdict           one plain sentence

Usage:
    .venv/Scripts/python.exe scripts/build_market.py
    .venv/Scripts/python.exe scripts/build_market.py --no-download
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from services.market.football_data import (CODES, OUTCOMES, SOURCE, URL,
                                           add_probabilities, assert_names,
                                           download, load_name_map, parse)

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "history" / "predictions.jsonl"
WF_ROWS = ROOT / "data" / "reports" / "_walk_forward_rows.csv"
PROJECT_NAMES = ROOT / "data" / "config" / "team_name_map.json"
OUT_JSON = ROOT / "data" / "web" / "market.json"
OUT_MD = ROOT / "data" / "reports" / "market_report.md"

SEASONS = ["1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627"]
CURRENT = "2627"
# The current sheet grows every weekend; finished seasons never change.
CURRENT_MAX_AGE_H = 12.0
DISAGREE_THRESHOLD = 0.08
BUCKETS = [(0.0, 0.05, "<0.05"), (0.05, 0.10, "0.05–0.10"),
           (0.10, 0.15, "0.10–0.15"), (0.15, 9.0, "≥0.15")]
# Either side of zero in 0.05 steps, open-ended at the edges. Wider than
# the observed spread on purpose: a bin that is always empty is information.
HIST_EDGES = [-0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10,
              0.15, 0.20, 0.25, 0.30]
# Shin wins the site only if it moves log loss by more than this. Below
# it the two methods are the same number and the simpler one is clearer.
SHIN_MARGIN = 0.002
BOOTSTRAP = 500
MODEL_ARM = "blend"
ARMS = ("blend", "layer")
OUT_IDX = {"home": 0, "draw": 1, "away": 2}
Y_CODE = {"H": "home", "D": "draw", "A": "away"}


# ---------------------------------------------------------------------------
# odds
# ---------------------------------------------------------------------------
def canonical_names(project_map: dict) -> dict:
    """Every team name the project has ever used per league, after its own
    name table. Understat files carry the names the daily stores, which is
    already canonical except for a few early seasons ('Paderborn' before
    the table said 'Paderborn 07'), so the table is applied here too."""
    out: dict = defaultdict(set)
    for lg in CODES:
        pm = project_map.get(lg, {})
        for s in SEASONS:
            for sub in ("understat", "fixtures"):
                p = ROOT / "data" / sub / lg / f"{s}.json"
                if not p.exists():
                    continue
                for m in json.loads(p.read_text(encoding="utf-8"))["matches"]:
                    out[lg].add(pm.get(m["home_team"], m["home_team"]))
                    out[lg].add(pm.get(m["away_team"], m["away_team"]))
    return out


def load_odds(no_download: bool, project_map: dict) -> pd.DataFrame:
    name_map = load_name_map()
    canon = canonical_names(project_map)
    frames = []
    for lg in CODES:
        for s in SEASONS:
            if not no_download:
                try:
                    download(lg, s, max_age_hours=CURRENT_MAX_AGE_H if s == CURRENT else None)
                except Exception as e:                    # noqa: BLE001
                    print(f"  download {lg} {s} failed: {type(e).__name__}: {e}")
            try:
                f = parse(lg, s, name_map)
            except FileNotFoundError:
                print(f"  no odds file for {lg} {s}")
                continue
            # the football-data table first, then the project's own, so a
            # name that both know lands where the predictions put it
            pm = project_map.get(lg, {})
            f["home"] = f["home"].map(lambda n: pm.get(n, n))
            f["away"] = f["away"].map(lambda n: pm.get(n, n))
            assert_names(f, canon[lg], lg, s)        # raises: no silent misses
            frames.append(f)
    odds = add_probabilities(pd.concat(frames, ignore_index=True))
    odds["d"] = pd.to_datetime(odds["date"])
    return odds


class OddsIndex:
    """(league, home, away) -> rows, matched on kickoff within a day. A
    fixture is unique per season on those three keys, and the one-day
    slack covers the sheet dating a Friday-night game on the Saturday."""

    def __init__(self, odds: pd.DataFrame):
        self.by_key: dict = defaultdict(list)
        for r in odds.itertuples(index=False):
            self.by_key[(r.league, r.home, r.away)].append(r)

    def find(self, league: str, home: str, away: str, day: str):
        d = pd.Timestamp(day)
        best, best_gap = None, None
        for r in self.by_key.get((league, home, away), ()):
            gap = abs((r.d - d).days)
            if gap <= 1 and (best_gap is None or gap < best_gap):
                best, best_gap = r, gap
        return best


def market_triplet(row, method: str) -> dict:
    return {k: float(getattr(row, f"{method}_{k}")) for k in OUTCOMES}


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def ll(p: dict, y: str) -> float:
    return -math.log(max(p[y], 1e-9))


def brier(p: dict, y: str) -> float:
    return sum((p[k] - (1.0 if k == y else 0.0)) ** 2 for k in OUTCOMES)


def scorer(ps: list, ys: list) -> dict:
    if not ps:
        return {"log_loss": None, "brier": None, "accuracy": None}
    return {
        "log_loss": round(float(np.mean([ll(p, y) for p, y in zip(ps, ys)])), 4),
        "brier": round(float(np.mean([brier(p, y) for p, y in zip(ps, ys)])), 4),
        "accuracy": round(float(np.mean(
            [max(OUTCOMES, key=p.get) == y for p, y in zip(ps, ys)])), 4),
    }


def score_block(rows: list) -> dict:
    """Model, market and the two baselines on one set of joined rows. The
    base rate is the outcome frequency of THESE rows, so it is the best
    constant forecast with hindsight — a floor nothing should fall under."""
    ys = [r["y"] for r in rows]
    n = len(rows)
    if n == 0:
        return {"n": 0}
    freq = {k: ys.count(k) / n for k in OUTCOMES}
    uni = {k: 1 / 3 for k in OUTCOMES}
    model = scorer([r["model"] for r in rows], ys)
    market = scorer([r["market"] for r in rows], ys)
    return {
        "n": n,
        "model": model,
        "market": market,
        "uniform": scorer([uni] * n, ys),
        "base_rate": scorer([freq] * n, ys),
        "gap": round(model["log_loss"] - market["log_loss"], 4),
    }


# ---------------------------------------------------------------------------
# live record
# ---------------------------------------------------------------------------
def live_rows(idx: OddsIndex, method: str, project_map: dict) -> tuple:
    rows, unjoined, graded = [], [], 0
    for line in HIST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("status") != "graded" or r.get("outcome") not in OUTCOMES:
            continue
        graded += 1
        retro = r.get("retro")
        if retro is None:
            # 85 rows from the first week of recording predate the flag.
            # All were stamped before their kickoff, which is the flag's
            # whole meaning, so they count as live.
            retro = r["recorded_at"][:10] > r["kickoff"]
        pm = project_map.get(r["league"], {})
        home, away = pm.get(r["home"], r["home"]), pm.get(r["away"], r["away"])
        hit = idx.find(r["league"], home, away, r["kickoff"])
        base = {"league": r["league"], "kickoff": r["kickoff"],
                "home": r["home"], "away": r["away"], "retro": bool(retro)}
        if hit is None:
            unjoined.append(base)
            continue
        rows.append({**base, "y": r["outcome"],
                     "model": {k: float(r["probabilities"][k]) for k in OUTCOMES},
                     "market": market_triplet(hit, method),
                     "odds": {"home": round(float(hit.o_home), 2),
                              "draw": round(float(hit.o_draw), 2),
                              "away": round(float(hit.o_away), 2)},
                     "odds_column": hit.odds_column})
    return rows, unjoined, graded


def disagreement(rows: list) -> dict:
    for r in rows:
        r["max_diff"] = max(abs(r["model"][k] - r["market"][k]) for k in OUTCOMES)
        r["better"] = ("model" if ll(r["model"], r["y"]) < ll(r["market"], r["y"])
                       else "market")
    buckets = []
    for lo, hi, label in BUCKETS:
        sub = [r for r in rows if lo <= r["max_diff"] < hi]
        if not sub:
            buckets.append({"bucket": label, "n": 0, "model_log_loss": None,
                            "market_log_loss": None, "better": None})
            continue
        m = float(np.mean([ll(r["model"], r["y"]) for r in sub]))
        k = float(np.mean([ll(r["market"], r["y"]) for r in sub]))
        buckets.append({"bucket": label, "n": len(sub),
                        "model_log_loss": round(m, 4), "market_log_loss": round(k, 4),
                        "better": "model" if m < k else ("market" if k < m else "tie")})
    big = sorted((r for r in rows if r["max_diff"] >= DISAGREE_THRESHOLD),
                 key=lambda r: -r["max_diff"])
    table = [{"league": r["league"], "kickoff": r["kickoff"], "home": r["home"],
              "away": r["away"], "retro": r["retro"],
              "model": {k: round(r["model"][k], 3) for k in OUTCOMES},
              "market": {k: round(r["market"][k], 3) for k in OUTCOMES},
              # the prices behind the probabilities: the model's fair price
              # (what the round page published) and the closing odds as the
              # sheet carries them, margin still in. Shown only for played
              # fixtures, which every row here is.
              "fair": {k: round(1 / r["model"][k], 2) if r["model"][k] > 0 else None
                       for k in OUTCOMES},
              "odds": r.get("odds"),
              "odds_column": r.get("odds_column"),
              "max_diff": round(r["max_diff"], 3), "result": r["y"],
              "better": r["better"]} for r in big]
    return {"threshold": DISAGREE_THRESHOLD, "buckets": buckets, "rows": table}


def histogram(rows: list) -> dict:
    bins = []
    for i in range(len(HIST_EDGES) - 1):
        lo, hi = HIST_EDGES[i], HIST_EDGES[i + 1]
        bins.append({"from": lo, "to": hi, "label": f"{lo:+.2f}"})
    out = {"bins": bins}
    for k in OUTCOMES:
        diffs = [r["model"][k] - r["market"][k] for r in rows]
        counts = [0] * len(bins)
        for d in diffs:
            # clamp so a difference beyond the edges lands in the end bin
            j = int(np.clip(np.searchsorted(HIST_EDGES, d, side="right") - 1,
                            0, len(bins) - 1))
            counts[j] += 1
        out[k] = counts
    return out


# ---------------------------------------------------------------------------
# historical benchmark
# ---------------------------------------------------------------------------
def walk_forward_joined(idx: OddsIndex, project_map: dict) -> tuple:
    """Walk-forward rows with the matching odds row attached. Returns
    (joined, total, unjoined, note). Note is set when the CSV cannot be
    used. Unjoined rows are listed, not just counted: the two so far are a
    replayed abandonment and a fixture missing from the sheet, and a list
    is what shows the next one is as innocent."""
    if not WF_ROWS.exists():
        return [], 0, [], "no walk-forward rows on disk"
    with WF_ROWS.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or not {"date", "home", "away"} <= set(rows[0]):
        return [], len(rows), [], ("walk-forward rows carry no date/home/away — "
                                   "rerun scripts/experiment_walk_forward.py")
    joined, unjoined = [], []
    for r in rows:
        pm = project_map.get(r["league"], {})
        home, away = pm.get(r["home"], r["home"]), pm.get(r["away"], r["away"])
        hit = idx.find(r["league"], home, away, r["date"])
        if hit is None:
            unjoined.append({"season": r["season"], "league": r["league"],
                             "date": r["date"], "home": r["home"], "away": r["away"]})
            continue
        joined.append({"season": r["season"], "league": r["league"],
                       "y": Y_CODE[r["y"]], "odds": hit,
                       **{arm: {k: float(r[f"{arm}_{k[0].upper()}"]) for k in OUTCOMES}
                          for arm in ARMS}})
    return joined, len(rows), unjoined, None


def choose_margin(joined: list) -> tuple:
    """Pick the de-margining the site shows, on the deepest sample."""
    if not joined:
        return "normalise", {"n": 0, "reason": "no historical rows; default"}
    ys = [r["y"] for r in joined]
    out = {}
    for m in ("normalise", "shin"):
        key = "norm" if m == "normalise" else "shin"
        out[m] = float(np.mean([ll(market_triplet(r["odds"], key), y)
                                for r, y in zip(joined, ys)]))
    diff = out["normalise"] - out["shin"]                    # >0: Shin better
    if diff > SHIN_MARGIN:
        chosen, why = "shin", (f"Shin lowers market log loss by {diff:.4f} nats, "
                               f"past the {SHIN_MARGIN} threshold")
    else:
        chosen, why = "normalise", (
            f"Shin changes market log loss by {diff:+.4f} nats, inside the "
            f"±{SHIN_MARGIN} band where the simpler method is preferred")
    return chosen, {"n": len(joined), "normalise_log_loss": round(out["normalise"], 4),
                    "shin_log_loss": round(out["shin"], 4), "reason": why}


def historical(joined: list, total: int, unjoined: list, method: str,
               note: str | None) -> dict:
    key = "norm" if method == "normalise" else "shin"
    if not joined:
        return {"leagues": [], "join": {"rows": total, "joined": 0, "rate": None,
                                        "unjoined": unjoined},
                "seasons": [], "pooled": None, "note": note}
    for r in joined:
        r["market"] = market_triplet(r["odds"], key)

    def block(rows: list) -> dict:
        ys = [r["y"] for r in rows]
        mk = float(np.mean([ll(r["market"], y) for r, y in zip(rows, ys)]))
        out = {"n": len(rows), "market_log_loss": round(mk, 4)}
        for arm in ARMS:
            a = float(np.mean([ll(r[arm], y) for r, y in zip(rows, ys)]))
            out[f"{arm}_log_loss"] = round(a, 4)
            out[f"{arm}_gap"] = round(a - mk, 4)
        return out

    seasons = sorted({r["season"] for r in joined})
    return {
        "leagues": sorted({r["league"] for r in joined}),
        "join": {"rows": total, "joined": len(joined),
                 "rate": round(len(joined) / total, 4) if total else None,
                 "unjoined": unjoined},
        "seasons": [{"season": s, **block([r for r in joined if r["season"] == s])}
                    for s in seasons],
        "pooled": block(joined),
        "note": note,
    }


# ---------------------------------------------------------------------------
# information test
# ---------------------------------------------------------------------------
def _logp(rows: list, key: str) -> np.ndarray:
    return np.log(np.clip(np.array([[r[key][k] for k in OUTCOMES] for r in rows]), 1e-9, 1))


def _fit(X: list, y: np.ndarray) -> np.ndarray:
    """Conditional logit: score_k = a_k + sum_j beta_j * log p_jk, softmax
    over k, with a_home fixed at zero. One beta per SOURCE rather than one
    per source per outcome, so 'the model's weight' is a single number a
    reader can hold — and so the fit cannot learn a draw-specific trick
    from a few hundred rows."""
    n = len(y)
    J = len(X)
    onehot = np.zeros((n, 3))
    onehot[np.arange(n), y] = 1.0

    def unpack(theta):
        a = np.array([0.0, theta[0], theta[1]])
        return a, theta[2:]

    def nll_grad(theta):
        a, beta = unpack(theta)
        s = a[None, :] + sum(b * x for b, x in zip(beta, X))
        s -= s.max(axis=1, keepdims=True)
        e = np.exp(s)
        p = e / e.sum(axis=1, keepdims=True)
        nll = -np.sum(onehot * np.log(np.clip(p, 1e-12, 1))) / n
        resid = (p - onehot) / n
        ga = resid.sum(axis=0)[1:]
        gb = np.array([np.sum(resid * x) for x in X])
        return nll, np.concatenate([ga, gb])

    theta0 = np.concatenate([[0.0, 0.0], np.ones(J) / J])
    res = minimize(nll_grad, theta0, jac=True, method="L-BFGS-B")
    return res.x


def _predict(theta: np.ndarray, X: list) -> np.ndarray:
    a = np.array([0.0, theta[0], theta[1]])
    s = a[None, :] + sum(b * x for b, x in zip(theta[2:], X))
    s -= s.max(axis=1, keepdims=True)
    e = np.exp(s)
    return e / e.sum(axis=1, keepdims=True)


def information_test(joined: list, arm: str = MODEL_ARM) -> dict:
    if len(joined) < 200:
        return {"arm": arm, "n": len(joined), "verdict": "too few joined rows"}
    y = np.array([OUT_IDX[r["y"]] for r in joined])
    seasons = np.array([r["season"] for r in joined])
    Xm = _logp(joined, "market")
    Xa = _logp(joined, arm)

    def mean_ll(p, yy):
        return float(np.mean(-np.log(np.clip(p[np.arange(len(yy)), yy], 1e-12, 1))))

    per_season, pooled_mo, pooled_st = [], [], []
    for s in sorted(set(seasons)):
        tr, te = seasons != s, seasons == s
        th_m = _fit([Xm[tr]], y[tr])
        th_s = _fit([Xm[tr], Xa[tr]], y[tr])
        p_m, p_s = _predict(th_m, [Xm[te]]), _predict(th_s, [Xm[te], Xa[te]])
        per_season.append({"season": s, "n": int(te.sum()),
                           "market_only": round(mean_ll(p_m, y[te]), 4),
                           "stacked": round(mean_ll(p_s, y[te]), 4)})
        pooled_mo.append(-np.log(np.clip(p_m[np.arange(te.sum()), y[te]], 1e-12, 1)))
        pooled_st.append(-np.log(np.clip(p_s[np.arange(te.sum()), y[te]], 1e-12, 1)))
    pooled = {"market_only": round(float(np.concatenate(pooled_mo).mean()), 4),
              "stacked": round(float(np.concatenate(pooled_st).mean()), 4)}

    full = _fit([Xm, Xa], y)
    w_market, w_model = float(full[2]), float(full[3])
    rng = np.random.default_rng(0)
    boot = []
    for _ in range(BOOTSTRAP):
        i = rng.integers(0, len(y), len(y))
        boot.append(_fit([Xm[i], Xa[i]], y[i])[3])
    lo, hi = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
    adds = lo > 0 and pooled["stacked"] < pooled["market_only"]
    if adds:
        verdict = (f"The model adds information beyond the market: its weight in "
                   f"the stacked fit is {w_model:.2f} (95% CI {lo:.2f} to {hi:.2f}) and "
                   f"the stack beats the market alone out of sample by "
                   f"{pooled['market_only'] - pooled['stacked']:.4f} nats.")
    elif lo > 0:
        verdict = (f"The model's weight is positive ({w_model:.2f}, 95% CI {lo:.2f} to "
                   f"{hi:.2f}) but stacking does not beat the market alone out of "
                   f"sample, so the information is not usable.")
    else:
        verdict = (f"The model does not add information beyond the market: its "
                   f"weight is {w_model:.2f} with a 95% CI of {lo:.2f} to {hi:.2f}, "
                   f"which includes zero.")
    return {"arm": arm, "n": int(len(y)), "seasons": sorted(set(seasons.tolist())),
            "weight_model": round(w_model, 4), "weight_market": round(w_market, 4),
            "ci95": [round(lo, 4), round(hi, 4)], "resamples": BOOTSTRAP,
            "per_season": per_season, "pooled": pooled,
            "adds_information": bool(adds), "verdict": verdict}


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def fmt(v, nd=4) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def table(head: list, rows: list) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def write_report(d: dict) -> None:
    L = [f"# Versus the market\n", f"generated {d['generated']} · source {d['source']} · "
         f"margin removal: **{d['margin_method']}**\n"]
    mm = d["margin_methods"]
    L.append(f"Margin method on {mm.get('n', 0):,} joined historical rows: "
             f"normalise {fmt(mm.get('normalise_log_loss'))}, Shin "
             f"{fmt(mm.get('shin_log_loss'))}. {mm.get('reason', '')}\n")
    for sample, counts in d["odds_column_used"].items():
        L.append(f"Odds column used, {sample} rows: " + ", ".join(
            f"{k} {v:,}" for k, v in counts.items()) + "  ")
    L.append("")

    lv = d["live"]
    L.append("## Live record\n")
    j = lv["join"]
    L.append(f"Graded rows {j['graded']}, joined {j['joined']} "
             f"({(j['rate'] or 0) * 100:.1f}%).\n")
    if j["unjoined"]:
        L.append("Unjoined:\n")
        L.append(table(["league", "kickoff", "home", "away", "retro"],
                       [[u["league"], u["kickoff"], u["home"], u["away"], u["retro"]]
                        for u in j["unjoined"]]) + "\n")
    rows = []
    for name, b in lv["splits"].items():
        if b.get("n", 0) == 0:
            rows.append([name, 0] + ["—"] * 7)
            continue
        rows.append([name, b["n"], fmt(b["model"]["log_loss"]), fmt(b["market"]["log_loss"]),
                     fmt(b["gap"]), fmt(b["uniform"]["log_loss"]), fmt(b["base_rate"]["log_loss"]),
                     f"{fmt(b['model']['brier'])} / {fmt(b['market']['brier'])}",
                     f"{b['model']['accuracy'] * 100:.1f}% / {b['market']['accuracy'] * 100:.1f}%"])
    L.append(table(["split", "n", "model LL", "market LL", "gap", "uniform LL",
                    "base-rate LL", "Brier m / mkt", "acc m / mkt"], rows) + "\n")
    L.append("### By league (all joined graded rows)\n")
    L.append(table(["league", "n", "model LL", "market LL", "gap"],
                   [[lg, b["n"], fmt(b["model"]["log_loss"]), fmt(b["market"]["log_loss"]), fmt(b["gap"])]
                    for lg, b in lv["by_league"].items()]) + "\n")
    dg = lv["disagreement"]
    L.append("### Disagreement\n")
    L.append(table(["max |model − market|", "n", "model LL", "market LL", "better"],
                   [[b["bucket"], b["n"], fmt(b["model_log_loss"]), fmt(b["market_log_loss"]),
                     b["better"] or "—"] for b in dg["buckets"]]) + "\n")
    L.append(f"Rows above {dg['threshold']} (graded only):\n")
    L.append(table(["league", "kickoff", "home", "away", "retro", "model H/D/A", "market H/D/A",
                    "max diff", "result", "better"],
                   [[r["league"], r["kickoff"], r["home"], r["away"], r["retro"],
                     "/".join(f"{r['model'][k]:.3f}" for k in OUTCOMES),
                     "/".join(f"{r['market'][k]:.3f}" for k in OUTCOMES),
                     f"{r['max_diff']:.3f}", r["result"], r["better"]] for r in dg["rows"]]) + "\n")
    hg = lv["histogram"]
    L.append("### Model minus market, histogram\n")
    L.append(table(["bin from", "home", "draw", "away"],
                   [[b["label"], hg["home"][i], hg["draw"][i], hg["away"][i]]
                    for i, b in enumerate(hg["bins"])]) + "\n")

    h = d["historical"]
    L.append("## Historical benchmark (walk-forward, frozen seasons)\n")
    if h.get("note"):
        L.append(f"Note: {h['note']}\n")
    if h["seasons"]:
        L.append(f"Leagues: {', '.join(h['leagues'])}. Rows {h['join']['rows']:,}, joined "
                 f"{h['join']['joined']:,} ({h['join']['rate'] * 100:.2f}%).\n")
        if h["join"]["unjoined"]:
            L.append("Unjoined:\n")
            L.append(table(["season", "league", "date", "home", "away"],
                           [[u["season"], u["league"], u["date"], u["home"], u["away"]]
                            for u in h["join"]["unjoined"]]) + "\n")
        rows = [[s["season"], s["n"], fmt(s["blend_log_loss"]), fmt(s["layer_log_loss"]),
                 fmt(s["market_log_loss"]), fmt(s["blend_gap"]), fmt(s["layer_gap"])]
                for s in h["seasons"]]
        p = h["pooled"]
        rows.append(["pooled", p["n"], fmt(p["blend_log_loss"]), fmt(p["layer_log_loss"]),
                     fmt(p["market_log_loss"]), fmt(p["blend_gap"]), fmt(p["layer_gap"])])
        L.append(table(["season", "n", "blend LL", "layer LL", "market LL", "blend gap", "layer gap"],
                       rows) + "\n")

    it = d["information_test"]
    L.append("## Information test\n")
    L.append(it.get("verdict", "") + "\n")
    if "per_season" in it:
        L.append(f"Arm {it['arm']}, n={it['n']:,}, weight_model {it['weight_model']} "
                 f"(95% CI {it['ci95'][0]} to {it['ci95'][1]}, {it['resamples']} resamples), "
                 f"weight_market {it['weight_market']}.\n")
        rows = [[s["season"], s["n"], fmt(s["market_only"]), fmt(s["stacked"]),
                 fmt(s["market_only"] - s["stacked"])] for s in it["per_season"]]
        rows.append(["pooled", it["n"], fmt(it["pooled"]["market_only"]),
                     fmt(it["pooled"]["stacked"]),
                     fmt(it["pooled"]["market_only"] - it["pooled"]["stacked"])])
        L.append(table(["season", "n", "market-only LL", "stacked LL", "gain"], rows) + "\n")
    L.append("\nProbabilities and fair prices only — never betting advice.\n")
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true",
                    help="use the cached CSVs only")
    args = ap.parse_args()

    project_map = json.loads(PROJECT_NAMES.read_text(encoding="utf-8")) \
        if PROJECT_NAMES.exists() else {}
    print("odds...")
    odds = load_odds(args.no_download, project_map)
    print(f"  {len(odds):,} priced fixtures across {odds['league'].nunique()} leagues, "
          f"{odds['season'].nunique()} seasons")
    idx = OddsIndex(odds)

    print("historical rows...")
    wf, wf_total, wf_unjoined, note = walk_forward_joined(idx, project_map)
    print(f"  {len(wf):,} of {wf_total:,} walk-forward rows joined"
          + (f" — {note}" if note else ""))
    method, margin_methods = choose_margin(wf)
    print(f"  margin method: {method} ({margin_methods.get('reason')})")
    key = "norm" if method == "normalise" else "shin"

    print("live record...")
    rows, unjoined, graded = live_rows(idx, key, project_map)
    print(f"  {len(rows)} of {graded} graded rows joined, {len(unjoined)} unjoined")
    splits = {
        "live": score_block([r for r in rows if not r["retro"]]),
        "reconstructed": score_block([r for r in rows if r["retro"]]),
        "all": score_block(rows),
    }
    by_league = {}
    for lg in CODES:
        sub = [r for r in rows if r["league"] == lg]
        if sub:
            b = score_block(sub)
            by_league[lg] = {"n": b["n"], "model": b["model"], "market": b["market"],
                             "gap": b["gap"]}

    hist = historical(wf, wf_total, wf_unjoined, method, note)
    print("information test...")
    info = information_test(wf)
    print("  " + info.get("verdict", ""))

    # Counted per sample because they differ completely: the frozen seasons
    # are Pinnacle closing almost throughout, the current season has none.
    cols_live = Counter(r["odds_column"] for r in rows)
    cols_hist = Counter(r["odds"].odds_column for r in wf)
    col_keys = ("pinnacle_closing", "pinnacle", "average_closing", "average")

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": date.today().isoformat(),
        "source": SOURCE,
        "source_url": URL,
        "margin_method": method,
        "margin_methods": margin_methods,
        "odds_column_used": {
            "live": {k: cols_live.get(k, 0) for k in col_keys},
            "historical": {k: cols_hist.get(k, 0) for k in col_keys},
            "all": {k: cols_live.get(k, 0) + cols_hist.get(k, 0) for k in col_keys},
        },
        "live": {
            "join": {"graded": graded, "joined": len(rows),
                     "rate": round(len(rows) / graded, 4) if graded else None,
                     "unjoined": unjoined},
            "splits": splits,
            "by_league": by_league,
            "disagreement": disagreement(rows),
            "histogram": histogram(rows),
        },
        "historical": hist,
        "information_test": info,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(payload)
    lv = splits["live"]
    if lv.get("n"):
        print(f"\nlive n={lv['n']}  model {lv['model']['log_loss']:.4f}  "
              f"market {lv['market']['log_loss']:.4f}  gap {lv['gap']:+.4f}")
    print(f"-> {OUT_JSON}\n-> {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
