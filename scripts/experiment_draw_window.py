"""Which window should the draw classifier read a team's draw rate and goal
volume over? Asked on thirteen seasons, walk-forward, not on two screenshots.

WHY THIS EXISTS. On 2026-11-20 two draw candidates tied at 30.74% and a
results page settled it by eye: Deportivo had drawn 6 of 12 and 4 of their
last 8, Rennes' away games ran at 5.25 goals with no draws in four. The
classifier ALREADY reads both signals - `drawrate_h/a` and `goals_total_h/a`
in DrawModel.FEATURES - but over WINDOW=38 matches with DECAY=0.985, which
is close to a flat season, all venues mixed. The page that decided the tie
used eight matches and split home from away. Nobody had measured which
reading predicts draws better. This does.

WHAT IT HOLDS FIXED. Everything but the rolling window: the same fixtures,
the same Poisson lambdas (FormModel on the previous and current season, as
production prices a fixture), the same per-season boosts and rho fitted on
the season before (backtest_season.fit_params, as experiment_walk_forward
does), the same standings context, the same logistic fit (L2 1e-3, BFGS) as
DrawModel.train, the same walk-forward: a classifier scoring season S is
trained on seasons before S only, for S in 1819..2526.

WHAT VARIES. The per-team rolling features (draw rate, average total goals,
ppda) are rebuilt per variant from each team's match history, carried
across seasons as production carries it:
    window   last N matches (38 = ship, 1000 = uncapped)
    decay    per-match weight (0.985 = ship, 1.0 = flat)
    venue    the home side read from its HOME matches only, the away side
             from its AWAY matches only (the stats-page split)
    std      season-to-date: history resets at the season boundary

WHAT IS SCORED, pooled over the eight evaluation seasons and five leagues:
    log-loss and Brier of P(draw)      the honest scoring rules
    top-10% hit rate (per season)      "draws found at the cut the product uses"
    top-4-per-week hit rate            four draws a week across the pool,
                                       weeks by ISO calendar week (fixtures
                                       carry gameweeks only from 24/25)
    calls at P(draw) >= 0.31           how many a week, how often they land
    paired bootstrap vs ship           on per-fixture log-loss, because every
                                       variant scores the same fixtures

Usage (from repo root; a few minutes, fit_params cached on first run):
    .venv\\Scripts\\python.exe scripts\\experiment_draw_window.py
Writes data/reports/experiment_draw_window.json and .md. Touches nothing in
data/config. Never writes a classifier anywhere.
"""
import datetime as dt
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy.optimize import minimize

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import MIN_MATCHES, FormModel
from services.predictions.probability_service import outcome_probs
from services.understat.understat_service import UnderstatService

from backtest_season import ALL_SEASONS, fit_params  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_draw_window.json"
REPORT_MD = ROOT / "data" / "reports" / "experiment_draw_window.md"
PARAMS_CACHE = ROOT / "data" / "reports" / "_draw_window_params.json"
EVAL_FROM = "1819"
CALL_MIN = 0.31          # probability_service.DRAW_CALL_MIN, not imported so a
                         # future change there does not silently move this bar

# name, window, decay, venue split, season-to-date
VARIANTS = [
    ("ship  w38 d.985", 38, 0.985, False, False),
    ("flat  w38", 38, 1.0, False, False),
    ("w19 d.985", 19, 0.985, False, False),
    ("w12 d.985", 12, 0.985, False, False),
    ("w8  d.985", 8, 0.985, False, False),
    ("w5  d.985", 5, 0.985, False, False),
    ("flat  w8", 8, 1.0, False, False),
    ("flat  w5", 5, 1.0, False, False),
    ("decay .95 uncapped", 1000, 0.95, False, False),
    ("decay .90 uncapped", 1000, 0.90, False, False),
    ("decay .80 uncapped", 1000, 0.80, False, False),
    ("venue w38 d.985", 38, 0.985, True, False),
    ("venue w12 d.985", 12, 0.985, True, False),
    ("venue w8  d.985", 8, 0.985, True, False),
    ("venue w6  d.985", 6, 0.985, True, False),
    ("season-to-date flat", 1000, 1.0, False, True),
    ("season-to-date venue", 1000, 1.0, True, True),
]


# ----------------------------------------------------------------- base rows

def build_rows() -> list:
    """One row per priced fixture, with everything that does NOT depend on
    the window: lambdas at boost 1, standings context, outcome, keys, and
    the team-history pointers the variants read."""
    rows = []
    for league in LEAGUE_NAME_MAP:
        # every season's matches, chronological, with a season tag - this is
        # the history the rolling features read, carried across seasons
        timeline = []
        for season in ALL_SEASONS:
            data = UnderstatService.load(league, season)
            if not data:
                continue
            for m in data["matches"]:
                if m["home_goals"] is None or m.get("home_xg") is None:
                    continue
                timeline.append({**m, "season": season})
        timeline.sort(key=lambda m: m["date"])
        # per-team history as (gf, ga, ppda, is_home, season), appended as
        # the timeline is walked, so each row sees only earlier matches
        hist: dict = defaultdict(list)
        by_season: dict = defaultdict(list)
        for m in timeline:
            by_season[m["season"]].append(m)
        fms = {}
        for i, season in enumerate(ALL_SEASONS):
            if season not in by_season:
                continue
            prev = ALL_SEASONS[i - 1] if i and ALL_SEASONS[i - 1] in by_season else None
            fms[season] = FormModel(league, [s for s in (prev, season) if s])
        kept = 0
        for m in timeline:
            season, h, a = m["season"], m["home_team"], m["away_team"]
            fm = fms[season]
            ratings = fm.ratings_before(m["date"])
            rh, ra = ratings.get(h), ratings.get(a)
            ok = (rh and ra and rh["n"] >= MIN_MATCHES and ra["n"] >= MIN_MATCHES
                  and len(hist[h]) >= MIN_MATCHES and len(hist[a]) >= MIN_MATCHES)
            if ok:
                lam_h, lam_a, low = fm.lambdas(ratings, h, a, 1.0, 1.0)
                if not low:
                    ctx = DrawModel.season_context(by_season[season], m["date"], h, a)
                    d = dt.date.fromisoformat(str(m["date"])[:10])
                    iso = d.isocalendar()
                    rows.append({
                        "league": league, "season": season, "date": str(m["date"])[:10],
                        "home": h, "away": a, "week": f"{iso[0]}-{iso[1]:02d}",
                        "lam_h0": lam_h, "lam_a0": lam_a,
                        "ctx": [ctx["ppg_gap"], ctx["season_frac"], ctx["mutual_comfort"]],
                        "y": 1.0 if m["home_goals"] == m["away_goals"] else 0.0,
                        # pointers into the shared histories: the first hn
                        # entries of HIST[hk] are what the home side had
                        # played before this fixture (a copy per row was
                        # gigabytes)
                        "hk": (league, h), "hn": len(hist[h]),
                        "ak": (league, a), "an": len(hist[a]),
                    })
                    kept += 1
            gh, ga_ = int(m["home_goals"]), int(m["away_goals"])
            hist[h].append((gh, ga_, m.get("home_ppda"), True, season))
            hist[a].append((ga_, gh, m.get("away_ppda"), False, season))
        for team, hs in hist.items():
            HIST[(league, team)] = hs
        print(f"  {league}: {kept} fixtures priced", flush=True)
    return rows


HIST: dict = {}   # (league, team) -> [(gf, ga, ppda, is_home, season), ...] in order


# -------------------------------------------------------------- rolling read

def rolling(key, upto: int, window: int, decay: float, venue, season_only, season):
    """drawrate, goals_total, ppda over the chosen slice of a team's history:
    the first `upto` entries of HIST[key], newest last. `venue` is None (all
    matches), True (home matches) or False (away)."""
    rows = HIST[key][:upto]
    if season_only:
        rows = [r for r in rows if r[4] == season]
    if venue is not None:
        v = [r for r in rows if r[3] is venue]
        if v:
            rows = v
    rows = rows[-window:]
    if not rows:
        return None
    w_total = draws = totals = ppda = ppda_w = 0.0
    for i, (gf, ga, pp, _, _) in enumerate(reversed(rows)):
        w = decay ** i
        w_total += w
        draws += w * (gf == ga)
        totals += w * (gf + ga)
        if pp is not None:
            ppda += w * pp
            ppda_w += w
    return (draws / w_total, totals / w_total, (ppda / ppda_w) if ppda_w else 10.0)


def roll_feats(row, window, decay, venue, std) -> list:
    """The five window-dependent features of a row. Independent of the
    evaluation season, so computed once per variant."""
    s = row["season"]
    rh = rolling(row["hk"], row["hn"], window, decay, True if venue else None, std, s)
    ra = rolling(row["ak"], row["an"], window, decay, False if venue else None, std, s)
    if rh is None:   # season-to-date on opening day: fall back to the full history
        rh = rolling(row["hk"], row["hn"], window, decay, None, False, s)
    if ra is None:
        ra = rolling(row["ak"], row["an"], window, decay, None, False, s)
    return [rh[0], ra[0], rh[1], ra[1], rh[2] + ra[2]]


def features(row, params, rf: list) -> list:
    """Full feature vector in DrawModel.FEATURES order: the three lambda
    features under this season's boosts and rho, the five rolling ones,
    the three standings ones."""
    boosts = params["leagues"][row["league"]]
    lam_h = max(row["lam_h0"] * boosts["home_boost"], 0.05)
    lam_a = max(row["lam_a0"] * boosts["away_boost"], 0.05)
    return [outcome_probs(lam_h, lam_a, params["rho"])["draw"],
            lam_h + lam_a, abs(lam_h - lam_a), *rf, *row["ctx"]]


# ------------------------------------------------------------------- fitting

def fit(X: np.ndarray, y: np.ndarray):
    """DrawModel.train's fit, verbatim in substance: standardise, intercept,
    L2 1e-3 on the slopes, BFGS."""
    mean, std = X.mean(axis=0), X.std(axis=0) + 1e-9
    Xn = np.hstack([np.ones((len(X), 1)), (X - mean) / std])

    def nll(w):
        p = np.clip(1 / (1 + np.exp(-(Xn @ w))), 1e-9, 1 - 1e-9)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean() + 1e-3 * (w[1:] ** 2).sum()

    res = minimize(nll, x0=np.zeros(Xn.shape[1]), method="BFGS")
    w = res.x

    def predict(Xt):
        Xt = np.hstack([np.ones((len(Xt), 1)), (Xt - mean) / std])
        return 1 / (1 + np.exp(-(Xt @ w)))
    return predict


def run_variant(rows, params_by_season, window, decay, venue, std):
    """P(draw) for every evaluation fixture, each season scored by a
    classifier that has seen only earlier seasons."""
    out = []
    rf = [roll_feats(r, window, decay, venue, std) for r in rows]
    for s in [s for s in ALL_SEASONS if s >= EVAL_FROM]:
        params = params_by_season[s]
        train = [(r, f) for r, f in zip(rows, rf) if r["season"] < s]
        test = [(r, f) for r, f in zip(rows, rf) if r["season"] == s]
        if not test:
            continue
        X = np.array([features(r, params, f) for r, f in train])
        y = np.array([r["y"] for r, _ in train])
        Xt = np.array([features(r, params, f) for r, f in test])
        p = fit(X, y)(Xt)
        test = [r for r, _ in test]
        for r, pi in zip(test, p):
            out.append({"season": s, "league": r["league"], "week": r["week"],
                        "date": r["date"], "home": r["home"], "away": r["away"],
                        "y": r["y"], "p": float(pi)})
    return out


# ------------------------------------------------------------------- scoring

def score(pred: list) -> dict:
    y = np.array([r["y"] for r in pred])
    p = np.clip(np.array([r["p"] for r in pred]), 1e-9, 1 - 1e-9)
    ll = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    seasons = sorted({r["season"] for r in pred})
    top10_h = top10_n = 0
    for s in seasons:
        rs = sorted((r for r in pred if r["season"] == s), key=lambda r: -r["p"])
        cut = rs[:max(1, len(rs) // 10)]
        top10_h += sum(r["y"] for r in cut)
        top10_n += len(cut)
    by_week = defaultdict(list)
    for r in pred:
        by_week[(r["season"], r["week"])].append(r)
    t4_h = t4_n = 0
    for rs in by_week.values():
        if len(rs) < 4:
            continue
        picks = sorted(rs, key=lambda r: -r["p"])[:4]
        t4_h += sum(r["y"] for r in picks)
        t4_n += 4
    calls = [r for r in pred if r["p"] >= CALL_MIN]
    weeks = len({(r["season"], r["week"]) for r in pred})
    return {
        "n": len(pred), "draw_rate": round(float(y.mean()), 4),
        "log_loss": round(float(ll.mean()), 5),
        "brier": round(float(((p - y) ** 2).mean()), 5),
        "top10_hit": round(top10_h / top10_n, 4) if top10_n else None,
        "top4_week_hit": round(t4_h / t4_n, 4) if t4_n else None,
        "top4_weeks": t4_n // 4,
        "calls_per_week": round(len(calls) / weeks, 2) if weeks else None,
        "calls_hit": round(sum(r["y"] for r in calls) / len(calls), 4) if calls else None,
        "_ll": ll,
    }


def paired(a: np.ndarray, b: np.ndarray, seed: int = 0) -> dict:
    diff = b - a
    rng = np.random.default_rng(seed)
    draws = np.array([rng.choice(diff, size=len(diff), replace=True).mean()
                      for _ in range(4000)])
    return {"mean_gain": round(float(diff.mean()), 5),
            "p_better": round(float((draws > 0).mean()), 4)}


# ---------------------------------------------------------------------- main

def main() -> int:
    t0 = time.time()
    print("base rows (lambdas, context, histories) ...", flush=True)
    rows = build_rows()
    print(f"  {len(rows)} fixtures, {time.time() - t0:.0f}s", flush=True)

    if PARAMS_CACHE.exists():
        params_by_season = json.loads(PARAMS_CACHE.read_text(encoding="utf-8"))
    else:
        params_by_season = {}
    for s in [s for s in ALL_SEASONS if s >= EVAL_FROM]:
        if s not in params_by_season:
            fit_season = ALL_SEASONS[ALL_SEASONS.index(s) - 1]
            print(f"  params for {s} on {fit_season} ...", flush=True)
            params_by_season[s] = fit_params(fit_season)
            PARAMS_CACHE.write_text(json.dumps(params_by_season, indent=1), encoding="utf-8")

    results, lls = {}, {}
    for name, window, decay, venue, std in VARIANTS:
        t = time.time()
        pred = run_variant(rows, params_by_season, window, decay, venue, std)
        sc = score(pred)
        lls[name] = sc.pop("_ll")
        results[name] = sc
        print(f"  {name:22} ll {sc['log_loss']:.5f}  top10 {sc['top10_hit']:.3f}  "
              f"top4/wk {sc['top4_week_hit']:.3f}  calls/wk {sc['calls_per_week']:>5}  "
              f"hit {sc['calls_hit']}  ({time.time() - t:.0f}s)", flush=True)
    ship = VARIANTS[0][0]
    for name in results:
        if name != ship:
            results[name]["vs_ship"] = paired(lls[name], lls[ship])

    REPORT.write_text(json.dumps({"generated": dt.datetime.now().isoformat(timespec="seconds"),
                                  "eval_seasons": [s for s in ALL_SEASONS if s >= EVAL_FROM],
                                  "variants": results}, indent=2), encoding="utf-8")
    lines = ["# Draw-classifier rolling window, walk-forward 1819..2526, five leagues", "",
             f"{results[ship]['n']} fixtures, draw rate {results[ship]['draw_rate']:.1%}. "
             "Lower log-loss is better; paired bootstrap p is P(variant beats ship).", "",
             "| variant | log-loss | Brier | top 10% hit | top-4/week hit | calls/week | calls hit | vs ship p |",
             "|---|---|---|---|---|---|---|---|"]
    for name, sc in results.items():
        vs = sc.get("vs_ship", {})
        lines.append(f"| {name} | {sc['log_loss']:.5f} | {sc['brier']:.5f} | {sc['top10_hit']:.1%} | "
                     f"{sc['top4_week_hit']:.1%} | {sc['calls_per_week']} | "
                     f"{(sc['calls_hit'] or 0):.1%} | {vs.get('p_better', '')} |")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n-> {REPORT}\n-> {REPORT_MD}\n{time.time() - t0:.0f}s total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
