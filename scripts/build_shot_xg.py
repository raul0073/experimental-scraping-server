"""An xG of our own, from the WhoScored shots, so the model never again
waits on a free site.

WHY. Understat has served a maintenance page since 2026-11-01 and the
pipeline priced four rounds on xG that stopped on 10-31. Every shot of
every match since 2023-24 is on disk in data/whoscored/<league>/<season>
_stamped.parquet with coordinates, body part, situation and the assist
pass - everything a shot model needs except the one number Understat sold
us. No reader soccerdata offers carries xG any more (FBref lost Opta,
Sportmonks sells team totals from 2024-25 only), so the gap is filled from
here.

WHAT IT IS. A logistic shot model fitted on ~150,000 non-penalty, non-own-
goal shots: distance and angle to goal, body part, situation, big chance,
first touch, volley, one-on-one, assist type from the linked pass
(cross, through ball, chipped, long ball), and the zone label. Penalties
take the pooled conversion rate. Own goals carry no xG, as at Understat.
Match totals are then calibrated to Understat on the matches both sources
cover (2025-26 whole, 2026-27 to 10-31), one linear map per league, so a
filled match reads on Understat's scale rather than ours.

WHAT IT PRODUCES. For each league-season a sidecar
    data/understat/<league>/<season>.wsxg.json
of Understat-shaped rows for matches the Understat file lacks:
    date, home_team, away_team (canonical), home_goals, away_goals,
    home_xg, away_xg, home_npxg, away_npxg, ppda/deep/xpts None,
    understat_game_id None, source "whoscored_shot_xg", ws_game_id.
UnderstatService.load() appends the sidecar's rows for matches missing
from the Understat file, so every consumer - form model, draw classifier,
process Elo, history, zones context - sees a complete season without
knowing where a row came from. When Understat returns, its own rows win
and the sidecar shrinks to nothing on the next build.

WHAT IT IS NOT. Not a replacement for Understat's history (13 seasons stay
the training record) and not shot-level data for the site. The fit and
the calibration are reported in data/reports/shot_xg_report.md every run,
with the hold-out log-loss, the per-league scale and the match-level
agreement with Understat, so a drift shows up as a number.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\build_shot_xg.py            # fit + fill
    .venv\\Scripts\\python.exe scripts\\build_shot_xg.py --report   # fit only
Model weights: data/models/shot_xg.json. Idempotent; a few minutes.
"""
import argparse
import datetime as dt
import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from models.fbref.fbref_types import LEAGUE_NAME_MAP

ROOT = Path(__file__).resolve().parent.parent
WS_DIR = ROOT / "data" / "whoscored"
US_DIR = ROOT / "data" / "understat"
FX_DIR = ROOT / "data" / "fixtures"
CACHE = Path.home() / "soccerdata" / "data" / "WhoScored" / "events"
MODEL = ROOT / "data" / "models" / "shot_xg.json"
REPORT = ROOT / "data" / "reports" / "shot_xg_report.md"
SEASONS = ["2324", "2425", "2526", "2627"]
HOLDOUT = "2526"                     # fit on the rest, score here, then refit on all
CALIB_SEASONS = ["2526", "2627"]     # where Understat and WhoScored overlap

BODY = ["Head", "LeftFoot", "RightFoot", "OtherBodyPart"]
SIT = ["RegularPlay", "FromCorner", "SetPiece", "DirectFreekick", "Penalty", "FastBreak", "ThrowinSetPiece"]
FLAGS = ["OwnGoal", "Penalty", "BigChance", "FirstTouch", "Volley", "OneOnOne", "Assisted", "IndividualPlay"]
ASSIST = ["Cross", "Throughball", "Chipped", "Longball"]   # WhoScored spells it Throughball
ZONES = ["SmallBoxCentre", "SmallBoxLeft", "SmallBoxRight", "BoxCentre", "BoxLeft", "BoxRight",
         "DeepBoxLeft", "DeepBoxRight", "OutOfBoxCentre", "OutOfBoxLeft", "OutOfBoxRight",
         "OutOfBoxDeepLeft", "OutOfBoxDeepRight", "ThirtyFivePlusCentre", "ThirtyFivePlusLeft", "ThirtyFivePlusRight"]
# WhoScored's 0-100 grid on a 105 x 68 pitch; penalties sit at x=88.5 = 11.5 units = 12 yards
X_M, Y_M = 1.05, 0.68
GOAL_HALF_WIDTH_M = 3.66


# ------------------------------------------------------------------ loading

def qnames(q) -> set:
    if q is None or isinstance(q, float):          # None, or NaN after a failed merge
        return set()
    return {d["type"]["displayName"] for d in q}


def load_shots(league: str, season: str) -> pd.DataFrame:
    path = WS_DIR / league / f"{season}_stamped.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df = df[df["game_id"].notna()].copy()
    df["game_id"] = df["game_id"].astype("int64")
    df["is_shot"] = df["is_shot"].eq(True)          # arrow bool-with-nulls arrives as object
    df["is_goal"] = df["is_goal"].eq(True)
    sh = df[df["is_shot"]].copy()
    if sh.empty:
        return sh
    sh["q"] = sh["qualifiers"].map(qnames)
    sh["body"] = sh["q"].map(lambda s: next((b for b in BODY if b in s), "RightFoot"))
    sh["sit"] = sh["q"].map(lambda s: next((b for b in SIT if b in s), "RegularPlay"))
    sh["zone"] = sh["q"].map(lambda s: next((z for z in ZONES if z in s), "BoxCentre"))
    for f in FLAGS:
        sh[f] = sh["q"].map(lambda s, f=f: f in s)
    passes = df[df["type"] == "Pass"][["game_id", "team_id", "event_id", "qualifiers"]].rename(
        columns={"event_id": "related_event_id", "qualifiers": "assist_q"})
    sh = sh.merge(passes, on=["game_id", "team_id", "related_event_id"], how="left")
    aq = sh["assist_q"].map(qnames)
    for f in ASSIST:
        sh["a_" + f] = aq.map(lambda s, f=f: f in s)
    sh["league"] = league
    sh["season"] = season
    return sh.drop(columns=["qualifiers", "assist_q", "q"])


# ----------------------------------------------------------------- features

def feature_names() -> list:
    return (["log_dist", "dist", "angle", "angle_sq", "head_x_dist"]
            + [f"body_{b}" for b in BODY[:3]]                 # OtherBodyPart is the base
            + [f"sit_{s}" for s in SIT if s not in ("RegularPlay", "Penalty")]
            + ["BigChance", "FirstTouch", "Volley", "OneOnOne", "Assisted", "IndividualPlay"]
            + [f"a_{a}" for a in ASSIST]
            + [f"zone_{z}" for z in ZONES[1:]])               # SmallBoxCentre is the base


def features(sh: pd.DataFrame) -> np.ndarray:
    dx = (100.0 - sh["x"].to_numpy()) * X_M
    dy = (sh["y"].to_numpy() - 50.0) * Y_M
    dist = np.sqrt(dx ** 2 + dy ** 2)
    dist = np.clip(dist, 0.5, 60.0)
    # angle subtended by the goal mouth (Hughes-style), in radians
    a = np.arctan2(GOAL_HALF_WIDTH_M * 2 * dx, dx ** 2 + dy ** 2 - GOAL_HALF_WIDTH_M ** 2)
    a = np.where(a < 0, a + math.pi, a)
    head = (sh["body"] == "Head").to_numpy().astype(float)
    cols = [np.log(dist), dist, a, a ** 2, head * dist]
    cols += [(sh["body"] == b).to_numpy().astype(float) for b in BODY[:3]]
    cols += [(sh["sit"] == s).to_numpy().astype(float) for s in SIT if s not in ("RegularPlay", "Penalty")]
    cols += [sh[f].to_numpy().astype(float) for f in ["BigChance", "FirstTouch", "Volley", "OneOnOne", "Assisted", "IndividualPlay"]]
    cols += [sh["a_" + f].to_numpy().astype(float) for f in ASSIST]
    cols += [(sh["zone"] == z).to_numpy().astype(float) for z in ZONES[1:]]
    return np.column_stack(cols)


# ---------------------------------------------------------------------- fit

def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-4):
    mean, std = X.mean(axis=0), X.std(axis=0) + 1e-9
    Xn = np.hstack([np.ones((len(X), 1)), (X - mean) / std])

    def nll(w):
        z = Xn @ w
        p = np.clip(1 / (1 + np.exp(-z)), 1e-9, 1 - 1e-9)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean() + l2 * (w[1:] ** 2).sum()

    def grad(w):
        p = 1 / (1 + np.exp(-(Xn @ w)))
        g = Xn.T @ (p - y) / len(y)
        g[1:] += 2 * l2 * w[1:]
        return g

    res = minimize(nll, x0=np.zeros(Xn.shape[1]), jac=grad, method="L-BFGS-B")
    return {"coef": res.x.tolist(), "mean": mean.tolist(), "std": std.tolist(), "nll": float(res.fun)}


def predict(model: dict, X: np.ndarray) -> np.ndarray:
    Xn = np.hstack([np.ones((len(X), 1)), (X - np.array(model["mean"])) / np.array(model["std"])])
    return 1 / (1 + np.exp(-(Xn @ np.array(model["coef"]))))


def shot_xg(model: dict, sh: pd.DataFrame) -> np.ndarray:
    xg = np.zeros(len(sh))
    og = sh["OwnGoal"].to_numpy()
    pen = sh["Penalty"].to_numpy() & ~og
    reg = ~og & ~pen
    if reg.any():
        xg[reg] = predict(model, features(sh[reg]))
    xg[pen] = model["penalty_rate"]
    return xg


# ------------------------------------------------------------- match totals

def match_docs(league: str, season: str) -> dict:
    """game_id -> {date, home, away, hg, ag} for finished matches (statusCode 6)."""
    out = {}
    for f in glob.glob(str(CACHE / f"{league}_{season}" / "*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or d.get("statusCode") != 6:   # some cache docs are null
            continue
        try:
            hg, ag = [int(v) for v in d["ftScore"].split(":")]
        except Exception:
            continue
        out[int(Path(f).stem)] = {"date": d["startTime"][:10], "home": d["home"]["name"],
                                  "away": d["away"]["name"], "hg": hg, "ag": ag}
    return out


def learn_ws_to_canonical(league: str, docs_by_season: dict) -> dict:
    """WhoScored short name -> canonical (fixtures) name, by voting on
    (date, score) collisions with the fixtures files. Never by spelling."""
    votes = defaultdict(Counter)
    for season, docs in docs_by_season.items():
        fx_path = FX_DIR / league / f"{season}.json"
        if not fx_path.exists():
            continue
        fx = json.loads(fx_path.read_text(encoding="utf-8"))
        by_key = defaultdict(list)
        for m in fx["matches"]:
            if m.get("home_goals") is None:
                continue
            by_key[(m["date"], int(m["home_goals"]), int(m["away_goals"]))].append(m)
        for d in docs.values():
            cands = by_key.get((d["date"], d["hg"], d["ag"]), [])
            if len(cands) == 1:
                votes[d["home"]][cands[0]["home_team"]] += 1
                votes[d["away"]][cands[0]["away_team"]] += 1
    out = {}
    for ws, c in votes.items():
        name, n = c.most_common(1)[0]
        if n >= 2 and n / sum(c.values()) >= 0.8:
            out[ws] = name
    return out


def team_match_xg(model: dict, sh: pd.DataFrame) -> pd.DataFrame:
    sh = sh.copy()
    sh["xg"] = shot_xg(model, sh)
    sh["pen_xg"] = np.where(sh["Penalty"] & ~sh["OwnGoal"], sh["xg"], 0.0)
    g = sh.groupby(["game_id", "team_id", "team"], as_index=False).agg(xg=("xg", "sum"), pen_xg=("pen_xg", "sum"),
                                                                       shots=("xg", "size"))
    g["npxg"] = g["xg"] - g["pen_xg"]
    return g


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="fit and report; write no sidecars")
    args = ap.parse_args()
    t0 = dt.datetime.now()
    L = [f"# Shot xG from WhoScored events — {t0:%Y-%m-%d %H:%M}", ""]

    print("loading shots ...", flush=True)
    frames = [load_shots(lg, s) for lg in LEAGUE_NAME_MAP for s in SEASONS]
    shots = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    model_rows = shots[~shots["OwnGoal"] & ~shots["Penalty"]]
    pens = shots[shots["Penalty"] & ~shots["OwnGoal"]]
    pen_rate = float(pens["is_goal"].mean()) if len(pens) else 0.78
    print(f"  {len(shots):,} shots, {int(shots['is_goal'].sum()):,} goals; {len(pens):,} penalties at {pen_rate:.3f}", flush=True)
    L += [f"{len(shots):,} shots, {int(shots['is_goal'].sum()):,} goals over {len(SEASONS)} seasons and five leagues. "
          f"{len(model_rows):,} fitted (own goals and {len(pens):,} penalties aside; penalties take {pen_rate:.3f}).", ""]

    # hold-out: fit without HOLDOUT, score on it
    tr = model_rows[model_rows["season"] != HOLDOUT]
    te = model_rows[model_rows["season"] == HOLDOUT]
    m_ho = fit_logistic(features(tr), tr["is_goal"].to_numpy().astype(float))
    p = np.clip(predict(m_ho, features(te)), 1e-9, 1 - 1e-9)
    y = te["is_goal"].to_numpy().astype(float)
    ll = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    base = y.mean()
    ll0 = float(-(y * np.log(base) + (1 - y) * np.log(1 - base)).mean())
    # calibration by decile
    order = np.argsort(p)
    dec = [(float(p[o].mean()), float(y[o].mean()), len(o)) for o in np.array_split(order, 10)]
    L += [f"## Hold-out {HOLDOUT}", "",
          f"log-loss {ll:.4f} against {ll0:.4f} for the goal rate alone; mean xG {p.mean():.4f}, goal rate {base:.4f}.", "",
          "| decile | mean xG | goal rate | shots |", "|---|---|---|---|"]
    L += [f"| {i + 1} | {a:.3f} | {b:.3f} | {n} |" for i, (a, b, n) in enumerate(dec)]
    L.append("")

    # production fit on everything
    model = fit_logistic(features(model_rows), model_rows["is_goal"].to_numpy().astype(float))
    model.update({"features": feature_names(), "penalty_rate": pen_rate, "fitted": t0.isoformat(timespec="seconds"),
                  "n": int(len(model_rows)), "seasons": SEASONS, "holdout": {"season": HOLDOUT, "log_loss": round(ll, 5),
                                                                              "base_log_loss": round(ll0, 5)}})

    # team-match totals, documents, name maps
    print("match totals and Understat calibration ...", flush=True)
    docs = {lg: {s: match_docs(lg, s) for s in SEASONS} for lg in LEAGUE_NAME_MAP}
    ws2canon = {lg: learn_ws_to_canonical(lg, docs[lg]) for lg in LEAGUE_NAME_MAP}
    totals = team_match_xg(model, shots)
    by_game = {(r.game_id, r.team): r for r in totals.itertuples(index=False)}

    L += ["## Calibration to Understat (matches both cover)", "",
          "| league | matches | slope | intercept | r | mean abs diff after | WhoScored short names unmapped |", "|---|---|---|---|---|---|---|"]
    calib = {}
    filled_all = {}
    for lg in LEAGUE_NAME_MAP:
        pairs = []
        us_rows = {}
        for s in CALIB_SEASONS:
            us = json.loads((US_DIR / lg / f"{s}.json").read_text(encoding="utf-8")) if (US_DIR / lg / f"{s}.json").exists() else {}
            for m in us.get("matches", []):
                if m.get("home_xg") is not None:
                    us_rows[(m["date"], m["home_team"], m["away_team"])] = m
        unmapped = set()
        for s in CALIB_SEASONS:
            for gid, d in docs[lg][s].items():
                h, a = ws2canon[lg].get(d["home"]), ws2canon[lg].get(d["away"])
                if h is None:
                    unmapped.add(d["home"])
                if a is None:
                    unmapped.add(d["away"])
                m = us_rows.get((d["date"], h, a)) if h and a else None
                th, ta = by_game.get((gid, d["home"])), by_game.get((gid, d["away"]))
                if m is None:
                    continue
                # a side with no shot at all has xG 0, not a missing match
                pairs.append(((th.xg if th is not None else 0.0), float(m["home_xg"])))
                pairs.append(((ta.xg if ta is not None else 0.0), float(m["away_xg"])))
        if len(pairs) >= 50:
            x, yv = np.array(pairs).T
            slope, intercept = np.polyfit(x, yv, 1)
            r = float(np.corrcoef(x, yv)[0, 1])
            mad = float(np.abs((slope * x + intercept) - yv).mean())
        else:
            slope, intercept, r, mad = 1.0, 0.0, float("nan"), float("nan")
        calib[lg] = {"slope": round(float(slope), 4), "intercept": round(float(intercept), 4), "r": round(r, 4),
                     "n_team_matches": len(pairs), "mean_abs_diff": round(mad, 4)}
        L.append(f"| {lg} | {len(pairs) // 2} | {slope:.3f} | {intercept:+.3f} | {r:.3f} | {mad:.3f} | {', '.join(sorted(unmapped)) or '—'} |")
    L.append("")
    model["calibration"] = calib
    model["ws_to_canonical"] = ws2canon
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    MODEL.write_text(json.dumps(model, indent=1), encoding="utf-8")

    # sidecars: matches WhoScored has and Understat lacks
    L += ["## Filled", "", "| league | season | Understat rows | filled from WhoScored | first | last |", "|---|---|---|---|---|---|"]
    for lg in LEAGUE_NAME_MAP:
        c = calib[lg]
        for s in SEASONS:
            us_path = US_DIR / lg / f"{s}.json"
            if not us_path.exists():
                continue
            us = json.loads(us_path.read_text(encoding="utf-8"))
            # the ORDERED PAIR, not the date: a league season holds each pairing
            # once, and Understat's date can differ from WhoScored's on a
            # rescheduled match - matching on date would duplicate it
            have = {(m["home_team"], m["away_team"]) for m in us.get("matches", [])}
            rows = []
            for gid, d in sorted(docs[lg][s].items(), key=lambda kv: kv[1]["date"]):
                h, a = ws2canon[lg].get(d["home"]), ws2canon[lg].get(d["away"])
                if not h or not a or (h, a) in have:
                    continue
                th, ta = by_game.get((gid, d["home"])), by_game.get((gid, d["away"]))
                th_xg, th_pen = (th.xg, th.pen_xg) if th is not None else (0.0, 0.0)
                ta_xg, ta_pen = (ta.xg, ta.pen_xg) if ta is not None else (0.0, 0.0)
                hx = max(c["slope"] * th_xg + c["intercept"], 0.02)
                ax = max(c["slope"] * ta_xg + c["intercept"], 0.02)
                rows.append({"date": d["date"], "understat_date": d["date"], "home_team": h, "away_team": a,
                             "home_goals": d["hg"], "away_goals": d["ag"],
                             "home_xg": round(hx, 4), "away_xg": round(ax, 4),
                             "home_npxg": round(max(hx - c["slope"] * th_pen, 0.02), 4),
                             "away_npxg": round(max(ax - c["slope"] * ta_pen, 0.02), 4),
                             "home_ppda": None, "away_ppda": None, "home_deep": None, "away_deep": None,
                             "home_xpts": None, "away_xpts": None, "understat_game_id": None,
                             "source": "whoscored_shot_xg", "ws_game_id": gid})
            side = US_DIR / lg / f"{s}.wsxg.json"
            if not args.report:
                if rows:
                    side.write_text(json.dumps({"league": lg, "season": s, "source": "whoscored_shot_xg",
                                                "generated": t0.isoformat(timespec="seconds"),
                                                "match_count": len(rows), "matches": rows}, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
                elif side.exists():
                    side.unlink()
            filled_all[(lg, s)] = len(rows)
            if rows:
                L.append(f"| {lg} | {s} | {len(have)} | {len(rows)} | {rows[0]['date']} | {rows[-1]['date']} |")
    L.append("")
    L.append(f"model: `{MODEL.relative_to(ROOT)}` · {(dt.datetime.now() - t0).total_seconds():.0f}s"
             + (" · report only, no sidecars written" if args.report else ""))
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
