"""Walk-forward pricing, but with the fixture's IDENTITY kept.

WHY THIS FILE EXISTS AT ALL. scripts/experiment_walk_forward.py is the file
of record for a settled result and is not edited here. But the rows it left
on disk — data/reports/_walk_forward_rows.csv, 11,311 fixtures — carry only
season, league, y and four arms' probabilities. NO TEAM AND NO DATE. So the
one question you would most want to ask of a per-fixture error series —
"is the model wronger on THIS team, in THIS week?" — cannot be asked of it,
because there is nothing to join on.

This is that harness copied verbatim in its modelling and changed in exactly
one way: each row also carries home, away and date. Nothing about the
pricing differs, so a re-run over the same seasons reproduces the original
numbers; the only cost is that the rows are now joinable.

SCOPE, AND WHY IT IS NARROW. The style metrics this feeds live in
data/whoscored/{league}/{season}_stamped.parquet, which exists for 2324
onward only. Seasons the event stream cannot reach are not worth pricing
here, so the default range is 2324-2526 and the default league is one.

Writes data/reports/_shift_error_rows.csv

Usage:
    .venv/Scripts/python.exe scripts/experiment_shift_error.py
    .venv/Scripts/python.exe scripts/experiment_shift_error.py --league "ESP-La Liga"
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

from backtest_season import ALL_SEASONS, fit_params            # noqa: E402
from build_elo_all import fit as fit_elo                        # noqa: E402
from build_process_elo import matches_from_understat, outcome, walk  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROWS = ROOT / "data" / "reports" / "_shift_error_rows.csv"
REPORT = ROOT / "data" / "reports" / "experiment_shift_error_pricing.json"
# NOT the production classifier, and NOT the other harness's scratch file
# either — another job may be running that one right now.
SCRATCH_CLF = ROOT / "data" / "reports" / "_shift_scratch_clf.json"
OUTCOMES = ["H", "D", "A"]
ARMS = ["ship", "elo_clf", "blend", "layer"]
LEAGUES_USED: list = []


def elo_for(league: str, eval_season: str):
    """Elo ratings fitted ONLY on seasons before the one being scored."""
    df = matches_from_understat(league)
    if df.empty:
        return None
    fit_seasons = {s for s in df["season"].unique() if s < eval_season}
    if len(fit_seasons) < 3:
        return None
    got = fit_elo(df, fit_seasons, 3)
    if not got:
        return None
    _ll, k, home_adv, decay, conv, rho, _acc = got
    rows, _A, _D = walk(df, k, home_adv, decay, "xg")
    rows = rows.copy()
    rows["date"] = [str(x)[:10] for x in rows["kick"]]
    te = rows[rows["season"] == eval_season]
    return {"conv": conv, "rho": rho,
            "by_key": {(r.date, r.home, r.away): r
                       for r in te.itertuples(index=False)}}


def season_rows(eval_season: str) -> list:
    idx = ALL_SEASONS.index(eval_season)
    fit_season = ALL_SEASONS[idx - 1]
    train_seasons = ALL_SEASONS[:idx]

    print(f"\n=== {eval_season}: params on {fit_season}, "
          f"classifier on {len(train_seasons)} seasons", flush=True)
    params = fit_params(fit_season)
    rho_ship = params["rho"]
    # out_path=None would WRITE THE PRODUCTION CLASSIFIER. Always a scratch
    # path here; see the warning in experiment_walk_forward.py.
    clf = DrawModel.train(list(LEAGUE_NAME_MAP), train_seasons, params,
                          out_path=SCRATCH_CLF)
    print(f"    classifier n={clf.w['train_n']}", flush=True)

    out = []
    for league in LEAGUES_USED:
        elo = elo_for(league, eval_season)
        if elo is None:
            print(f"    {league}: no Elo, skipped", flush=True)
            continue
        boosts = params["leagues"][league]
        fm = FormModel(league, [fit_season, eval_season])
        us = UnderstatService.load(league, eval_season)

        n = 0
        for m in us["matches"]:
            if m["home_goals"] is None:
                continue
            h, a, date = m["home_team"], m["away_team"], str(m["date"])[:10]
            r = elo["by_key"].get((date, h, a))
            if r is None:
                continue
            ratings = fm.ratings_before(m["date"])
            lam_h, lam_a, low = fm.lambdas(
                ratings, h, a, boosts["home_boost"], boosts["away_boost"])
            if low:
                continue
            roll = DrawModel.rolling_stats(fm.matches, m["date"])
            if h not in roll or a not in roll:
                continue
            ctx = DrawModel.season_context(us["matches"], m["date"], h, a)

            ship = unified_probs(
                outcome_probs(lam_h, lam_a, rho_ship),
                clf.predict(DrawModel.fixture_features(
                    lam_h, lam_a, rho_ship, roll[h], roll[a], ctx)))

            elh = max(r.exp_hc * elo["conv"], 1e-3)
            ela = max(r.exp_ac * elo["conv"], 1e-3)
            ep = outcome(elh, ela, elo["rho"])
            elo_clf = unified_probs(
                {"home": float(ep[0]), "draw": float(ep[1]), "away": float(ep[2])},
                clf.predict(DrawModel.fixture_features(
                    elh, ela, elo["rho"], roll[h], roll[a], ctx)))

            blend = {k: (ship[k] + elo_clf[k]) / 2 for k in ("home", "draw", "away")}
            tot = sum(blend.values()) or 1.0
            blend = {k: v / tot for k, v in blend.items()}
            layer = unified_probs(blend, elo_clf["draw"])

            hg, ag = int(m["home_goals"]), int(m["away_goals"])
            row = {"season": eval_season, "league": league,
                   # the three columns this whole file exists for
                   "date": date, "home": h, "away": a,
                   "y": "H" if hg > ag else ("A" if ag > hg else "D"),
                   # kept so an analysis can control on how good the sides
                   # were thought to be without refitting anything
                   "lam_h": round(lam_h, 5), "lam_a": round(lam_a, 5)}
            for name, p in (("ship", ship), ("elo_clf", elo_clf),
                            ("blend", blend), ("layer", layer)):
                row[f"{name}_H"] = p["home"]
                row[f"{name}_D"] = p["draw"]
                row[f"{name}_A"] = p["away"]
            out.append(row)
            n += 1
        print(f"    {league}: {n} fixtures", flush=True)
    return out


def score(rows: list) -> dict:
    y = [r["y"] for r in rows]
    prior = {o: sum(1 for v in y if v == o) / len(y) for o in OUTCOMES}
    base = float(np.mean([-math.log(max(prior[v], 1e-9)) for v in y]))
    out = {}
    for arm in ARMS:
        ll = np.array([-math.log(max(r[f"{arm}_{r['y']}"], 1e-9)) for r in rows])
        called = [max(OUTCOMES, key=lambda o: r[f"{arm}_{o}"]) for r in rows]
        out[arm] = {"log_loss": round(float(ll.mean()), 4),
                    "accuracy": round(float(np.mean(
                        [c == v for c, v in zip(called, y)])), 4)}
    return {"n": len(rows), "base_log_loss": round(base, 4), "arms": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2324")
    ap.add_argument("--to", dest="end", default="2526")
    ap.add_argument("--league", action="append", dest="leagues")
    args = ap.parse_args()

    global LEAGUES_USED
    LEAGUES_USED = args.leagues or ["ENG-Premier League"]
    seasons = [s for s in ALL_SEASONS if args.start <= s <= args.end]
    print(f"leagues: {', '.join(LEAGUES_USED)}")
    print(f"seasons: {', '.join(seasons)}")

    everything, per_season = [], {}
    for s in seasons:
        try:
            rows = season_rows(s)
        except Exception as e:                        # noqa: BLE001
            print(f"    FAILED {s}: {type(e).__name__}: {e}", flush=True)
            continue
        if not rows:
            continue
        everything += rows
        per_season[s] = score(rows)
        a = per_season[s]["arms"]
        print(f"    -> n={len(rows)}  ship {a['ship']['log_loss']:.4f}  "
              f"layer {a['layer']['log_loss']:.4f}", flush=True)
        # written every season, so an interrupted run still leaves rows
        with ROWS.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(everything[0]))
            w.writeheader()
            w.writerows(everything)

    if not everything:
        print("nothing scored")
        return 1

    pooled = score(everything)
    REPORT.write_text(json.dumps(
        {"leagues_used": LEAGUES_USED, "seasons": per_season,
         "pooled": pooled}, indent=2), encoding="utf-8")
    print(f"\nPOOLED n={pooled['n']} base={pooled['base_log_loss']:.4f}")
    for arm in ARMS:
        print(f"  {arm:<10}{pooled['arms'][arm]['log_loss']:.4f}")
    print(f"-> {ROWS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
