"""The process Elo for every league, fitted per league, from Understat alone.

`build_process_elo.py` proved the idea on one league against the event
stream. This ships it: the winning observable is Understat xG, Understat has
thirteen seasons of all five leagues, so the rating needs no event data and
no Monday scrape — and it fits on about 4,500 matches a league instead of
380.

FITTED PER LEAGUE, not once and copied. Home advantage is not the same in
the Bundesliga as in Serie A, scoring levels differ, and a single set of
parameters would be a fifth model that is wrong everywhere by a little.

THE HELD-OUT SEASON IS NEVER FITTED ON. Everything before it trains; it
scores; the ratings that ship then carry on through the current season so
they are up to date, and that carry is never scored.

NO DRAW CLASSIFIER. The Elo's draws come straight off the Dixon-Coles grid.
Passing them through the classifier improved the calibrated probability and
DEGRADED the ranking — top-40 draw picks fell from 32.5% to 22.5% while
binary log-loss barely moved — and the product ranks picks rather than
reading probabilities off one fixture.

Writes data/config/elo_params.json     (what the predictor reads)
       data/web/team/{league}/elo.json (the table the site draws)
       data/reports/elo_all.json       (how each league scored)

Usage: .venv/Scripts/python.exe scripts/build_elo_all.py
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from build_process_elo import (                                # noqa: E402
    OUTCOMES, matches_from_understat, outcome, score_arm, slug, walk,
)

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "data" / "config" / "elo_params.json"
REPORT = ROOT / "data" / "reports" / "elo_all.json"
OUT = ROOT / "data" / "web" / "team"
PUB = ROOT / "web" / "public" / "data" / "team"

LEAGUES = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga",
           "GER-Bundesliga", "FRA-Ligue 1"]
HOLDOUT = "2526"          # the last COMPLETE season


# How many of the most recent training seasons the goal LEVEL is calibrated
# on. Solving conv over every training season was over-projecting the 25/26
# holdout in all five leagues — 1.03x in the Bundesliga to 1.15x in Serie A,
# the Premier League's 3.01 goals against an actual 2.75 — because scoring
# drifts and a twelve-season average describes an era that has passed.
# `calibrate_elo_conv.py` chose the lookback per league by walk-forward
# INSIDE the training seasons (never against the holdout) and the error curve
# came out monotone: "all" was the worst setting in every league. 3 is the
# default for a league with no calibrated value yet.
CONV_SEASONS_DEFAULT = 3


def fit(df, fit_seasons: set, conv_seasons=CONV_SEASONS_DEFAULT):
    """Grid K, home advantage and the season decay; solve conv; grid rho.

    conv is SOLVED rather than gridded because it means "goals per unit of
    the observable" — a pure level calibration — and log-loss is nearly
    blind to the level. Gridded, it settled somewhere that projected 3.77
    goals a match against an actual 2.75.

    That blindness cuts both ways: because log-loss barely notices the
    level, the grid below cannot be trusted to fix it, which is why conv is
    solved SEPARATELY and over recent seasons only. See CONV_SEASONS_DEFAULT.
    """
    ordered = sorted(fit_seasons)
    recent = ordered if conv_seasons == "all" else ordered[-int(conv_seasons):]
    best = None
    for k in (0.04, 0.06, 0.08, 0.10, 0.12, 0.16, 0.22):
        for home_adv in (0.05, 0.10, 0.15, 0.20, 0.25):
            for decay in (1.0, 0.95, 0.9, 0.8):
                rows, _A, _D = walk(df, k, home_adv, decay, "xg")
                tr = rows[rows["season"].isin(fit_seasons)].iloc[40:]
                if len(tr) < 200:
                    continue
                # the LEVEL from recent seasons; the SHAPE still fitted on
                # everything, because k/home_adv/decay/rho want all the data
                lvl = rows[rows["season"].isin(recent)]
                if len(lvl) < 200:
                    lvl = tr
                lam = (lvl["exp_hc"] + lvl["exp_ac"]).mean()
                goals = (lvl["hg"] + lvl["ag"]).mean()
                conv = float(goals / lam) if lam else 1.0
                for rho in (0.0, -0.05, -0.10, -0.15):
                    ll, acc, _p, _per = score_arm(tr, conv, rho)
                    if best is None or ll < best[0]:
                        best = (ll, k, home_adv, decay, conv, rho, acc)
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", action="append", dest="leagues")
    ap.add_argument("--holdout", default=HOLDOUT)
    ap.add_argument("--force", action="store_true",
                    help="refit even when the matches have not changed; "
                         "use after editing the fitting code, which a data "
                         "fingerprint cannot detect")
    args = ap.parse_args()
    leagues = args.leagues or LEAGUES

    # Carry forward each league's calibrated conv lookback. Without this the
    # daily run silently reverts calibrate_elo_conv.py's work every morning.
    prior = {}
    if PARAMS.exists():
        try:
            prior = json.loads(PARAMS.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
    prior_report = {}
    if REPORT.exists():
        try:
            prior_report = json.loads(REPORT.read_text(encoding="utf-8"))
        except Exception:
            prior_report = {}

    # 🐛 THESE USED TO START EMPTY AND BE WRITTEN WHOLE, so a run with
    # --league replaced elo_params.json with ONLY that league and deleted the
    # other four. Nothing complained: the predictor simply lost its Elo arm
    # for the leagues that had vanished, and the next full run refitted them
    # from defaults — which is how the calibrated conv_lookback values kept
    # reverting to 3 overnight. Exactly the failure the ratings index had.
    # Start from what is already on disk and update in place.
    all_params = dict(prior)
    report = dict(prior_report)
    print(f"holding out {args.holdout}; everything before it trains\n")
    for league in leagues:
        df = matches_from_understat(league)
        if df.empty:
            print(f"  {league}: nothing on disk")
            continue
        seasons = sorted(df["season"].unique())
        fit_seasons = {s for s in seasons if s < args.holdout}
        if len(fit_seasons) < 3:
            print(f"  {league}: too few seasons to fit")
            continue

        conv_seasons = (prior.get(league) or {}).get(
            "conv_lookback", CONV_SEASONS_DEFAULT)

        # 🐛 THE FIT RAN EVERY MORNING WHETHER OR NOT ANYTHING HAD CHANGED.
        # It is a grid of 7 k x 5 home_adv x 4 decay, each a full walk over
        # ~4,500 matches, then 4 rho per cell — 560 walks a league — and it
        # measured 217s for the five. On a day when no match was played the
        # answer is arithmetically identical to yesterday's.
        #
        # The fingerprint is the match count and the latest kickoff: the fit
        # is a pure function of the matches, so if neither has moved neither
        # has the result. Cheap to compute because the frame is already
        # loaded, and --force ignores it whenever the fitting code itself
        # changes, which no data fingerprint could notice.
        fingerprint = f"{len(df)}:{df['kick'].max()}"
        was = prior.get(league) or {}
        if (not args.force and was.get("fingerprint") == fingerprint
                and was.get("conv_lookback") == conv_seasons):
            print(f"  {league}: unchanged ({len(df)} matches) — keeping fit")
            all_params[league] = was
            if league in prior_report:
                report[league] = prior_report[league]
            continue

        got = fit(df, fit_seasons, conv_seasons)
        if not got:
            continue
        tr_ll, k, home_adv, decay, conv, rho, _acc = got
        rows, A, D = walk(df, k, home_adv, decay, "xg")
        te = rows[rows["season"] == args.holdout]
        ll, acc, _p, _per = score_arm(te, conv, rho)

        prior = df[df["season"] < args.holdout]["y"].value_counts(normalize=True)
        b = np.array([prior.get(o, 1 / 3) for o in OUTCOMES])
        b_ll = float(np.mean([-math.log(b[OUTCOMES.index(y)])
                              for y in te["y"]]))

        # draws, which are the product: how often the tightest picks land
        dp = np.array([outcome(max(r.exp_hc * conv, 1e-3),
                               max(r.exp_ac * conv, 1e-3), rho)[1]
                       for r in te.itertuples(index=False)])
        is_draw = (te["hg"] == te["ag"]).values.astype(float)
        top = np.argsort(-dp)[:40]

        params = {"fingerprint": fingerprint,
                  "k": k, "home_adv": home_adv, "decay": decay,
                  "conv": round(conv, 5), "conv_lookback": conv_seasons,
                  "rho": rho,
                  "fit_seasons": sorted(fit_seasons), "holdout": args.holdout,
                  "n_matches": int(len(df))}
        all_params[league] = params
        report[league] = {
            **params, "train_log_loss": round(tr_ll, 4),
            "base_log_loss": round(b_ll, 4),
            "log_loss": round(ll, 4), "accuracy": round(acc, 4),
            "n_test": int(len(te)),
            "draw_base": round(float(is_draw.mean()), 4),
            "draw_top40_hit": round(float(is_draw[top].mean()), 4),
            "draw_top40_said": round(float(dp[top].mean()), 4),
        }
        print(f"  fit K={k} home={home_adv} decay={decay} "
              f"conv={conv:.3f} rho={rho}")
        print(f"  {args.holdout}: log-loss {ll:.4f} (base {b_ll:.4f})  "
              f"acc {acc * 100:.1f}%  draws top40 "
              f"{is_draw[top].mean() * 100:.1f}% vs base "
              f"{is_draw.mean() * 100:.1f}%")

        current = set(df[df["season"] == seasons[-1]]["home"]) | \
            set(df[df["season"] == seasons[-1]]["away"])
        table = sorted(
            ({"team": t, "attack": round(A[t], 4), "defence": round(D[t], 4),
              "rating": round(A[t] + D[t], 4), "current": t in current}
             for t in A), key=lambda d: -d["rating"])
        lk = slug(league)
        for root in (OUT, PUB):
            (root / lk).mkdir(parents=True, exist_ok=True)
            (root / lk / "elo.json").write_text(
                json.dumps({"params": params, "table": table},
                           ensure_ascii=False), encoding="utf-8")
        print()

    PARAMS.write_text(json.dumps(all_params, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{'league':<22}{'log-loss':>10}{'base':>9}{'acc':>8}"
          f"{'draw top40':>12}{'draw base':>11}")
    for lg, r in report.items():
        print(f"{lg:<22}{r['log_loss']:>10.4f}{r['base_log_loss']:>9.4f}"
              f"{r['accuracy'] * 100:>7.1f}%{r['draw_top40_hit'] * 100:>11.1f}%"
              f"{r['draw_base'] * 100:>10.1f}%")
    print()
    print(f"-> {PARAMS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
