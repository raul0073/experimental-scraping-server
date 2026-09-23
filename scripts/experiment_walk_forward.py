"""Does the layer really beat the shipped model? Asked eight times over.

THE PROBLEM THIS SOLVES. The layer was chosen on ONE season. The frozen draw
classifier was trained on 1415-2425, so 25/26 is the only season it has
never seen, and that caps the honest sample at 1,714 fixtures however many
leagues are pooled. On those the layer won by +0.0013 nats at P(better)=0.74
— it wins about three times in four if you resample, which is "probably"
and not a result anyone should ship on.

WHAT WALK-FORWARD DOES INSTEAD. For each evaluation season S, rebuild the
whole model as it would have existed the summer before S:

    boosts and rho   fitted on S-1
    draw classifier  trained only on seasons before S
    process Elo      fitted only on seasons before S
    then price every fixture of S

Nothing that scores S has seen S. Roll it from 18/19 to 25/26 across five
leagues and the sample goes from 1,714 to roughly 14,000 — eight times the
evidence, every match of it out of sample.

WHAT IT TESTS, AND WHAT IT DOES NOT. This tests the METHOD, not the artifact
on disk: each season gets its own classifier and its own Elo, so a win here
says "blending-then-layering beats the shipped recipe", not "the specific
file currently in data/config is better". That is the stronger scientific
claim and the weaker product one, and the two should not be confused.

Arms, the same four the one-season run compared:

    ship      the live pipeline as served
    elo_clf   the Elo's lambdas through the same classifier
    blend     ship and elo_clf averaged, renormalised
    layer     blend's home:away ratio carrying elo_clf's draw   <- shipped

Writes data/reports/experiment_walk_forward.json

Usage:
    .venv/Scripts/python.exe scripts/experiment_walk_forward.py
    .venv/Scripts/python.exe scripts/experiment_walk_forward.py --from 2223
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

from backtest_season import ALL_SEASONS, fit_params            # noqa: E402
from build_elo_all import fit as fit_elo                        # noqa: E402
from build_process_elo import matches_from_understat, outcome, walk  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_walk_forward.json"
# Every priced fixture, kept. The first run pooled the rows and wrote only
# season totals, so "how does it rate per league" could not be answered
# without paying the eighty minutes again. Scoring is cheap; pricing is not.
ROWS = ROOT / "data" / "reports" / "_walk_forward_rows.csv"
OUTCOMES = ["H", "D", "A"]
ARMS = ["ship", "elo_clf", "blend", "layer"]
LEAGUES_USED: list = []
# Before this there are too few prior seasons to fit an Elo on (it wants at
# least three) and the classifier is thin.
DEFAULT_FROM = "1819"


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
    """Every fixture of one season, priced by all four arms, by models that
    have never seen it."""
    idx = ALL_SEASONS.index(eval_season)
    fit_season = ALL_SEASONS[idx - 1]
    train_seasons = ALL_SEASONS[:idx]

    print(f"\n=== {eval_season}: params on {fit_season}, "
          f"classifier on {len(train_seasons)} seasons", flush=True)
    params = fit_params(fit_season)
    rho_ship = params["rho"]
    clf = DrawModel.train(list(LEAGUE_NAME_MAP), train_seasons, params,
                          out_path=None)
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
                   "y": "H" if hg > ag else ("A" if ag > hg else "D")}
            for name, p in (("ship", ship), ("elo_clf", elo_clf),
                            ("blend", blend), ("layer", layer)):
                row[f"{name}_H"] = p["home"]
                row[f"{name}_D"] = p["draw"]
                row[f"{name}_A"] = p["away"]
            out.append(row)
            n += 1
        print(f"    {league}: {n} fixtures", flush=True)
    return out


def paired(a: np.ndarray, b: np.ndarray, seed: int = 0) -> dict:
    """Is a better than b? Resample the PAIRS — two arms scored on the same
    fixtures share nearly all their variance, and treating them as
    independent samples is how a few thousandths becomes a finding."""
    diff = b - a
    rng = np.random.default_rng(seed)
    draws = np.array([rng.choice(diff, size=len(diff), replace=True).mean()
                      for _ in range(5000)])
    return {"mean_gain": round(float(diff.mean()), 5),
            "p_better": round(float((draws > 0).mean()), 4)}


def score(rows: list) -> dict:
    y = [r["y"] for r in rows]
    prior = {o: sum(1 for v in y if v == o) / len(y) for o in OUTCOMES}
    base = float(np.mean([-math.log(max(prior[v], 1e-9)) for v in y]))
    lls, out = {}, {}
    for arm in ARMS:
        ll = np.array([-math.log(max(r[f"{arm}_{r['y']}"], 1e-9)) for r in rows])
        called = [max(OUTCOMES, key=lambda o: r[f"{arm}_{o}"]) for r in rows]
        lls[arm] = ll
        out[arm] = {"log_loss": round(float(ll.mean()), 4),
                    "accuracy": round(float(np.mean(
                        [c == v for c, v in zip(called, y)])), 4)}
    head = {a: paired(lls[a], lls["ship"]) for a in ARMS if a != "ship"}
    return {"n": len(rows), "base_log_loss": round(base, 4),
            "arms": out, "vs_ship": head}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default=DEFAULT_FROM)
    ap.add_argument("--to", dest="end", default="2526")
    # LIGUE 1 IS EXCLUDED BY DEFAULT and it is a data decision, not a
    # preference: its fixture counts swing 273-375 across these seasons
    # (Covid curtailed 19/20, and it dropped to eighteen clubs in 23/24), so
    # a league-level figure for it would be comparing different sample sizes
    # and calling the difference a result.
    ap.add_argument("--league", action="append", dest="leagues",
                    help="leagues to score; default is the four with "
                         "consistent coverage")
    args = ap.parse_args()

    global LEAGUES_USED
    LEAGUES_USED = args.leagues or [
        "ENG-Premier League", "ESP-La Liga", "ITA-Serie A", "GER-Bundesliga",
    ]
    seasons = [s for s in ALL_SEASONS if args.start <= s <= args.end]
    print(f"leagues: {', '.join(LEAGUES_USED)}")
    print(f"walk-forward over {len(seasons)} seasons: {', '.join(seasons)}")

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
              f"layer {a['layer']['log_loss']:.4f}  "
              f"blend {a['blend']['log_loss']:.4f}", flush=True)
        # written every season, so an interrupted run still leaves evidence
        REPORT.write_text(json.dumps(
            {"seasons": per_season,
             "pooled": score(everything) if everything else None},
            indent=2), encoding="utf-8")

    if not everything:
        print("nothing scored")
        return 1

    # Rows on disk, so any later cut costs seconds instead of an hour.
    import csv
    with ROWS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(everything[0]))
        w.writeheader()
        w.writerows(everything)

    by_league = {}
    for lg in LEAGUES_USED:
        rows = [r for r in everything if r["league"] == lg]
        if rows:
            by_league[lg] = score(rows)

    print(chr(10) + "BY LEAGUE" + chr(10))
    print(f"{'league':<22}{'n':>7}{'base':>9}" +
          "".join(f"{a:>10}" for a in ARMS) + f"{'P(blend)':>10}")
    for lg, sc in by_league.items():
        a = sc["arms"]
        print(f"{lg:<22}{sc['n']:>7}{sc['base_log_loss']:>9.4f}"
              + "".join(f"{a[x]['log_loss']:>10.4f}" for x in ARMS)
              + f"{sc['vs_ship']['blend']['p_better']:>10.3f}")

    pooled = score(everything)
    print(f"\nPOOLED — {pooled['n']:,} fixtures, "
          f"base log-loss {pooled['base_log_loss']:.4f}\n")
    print(f"{'arm':<10}{'log-loss':>10}{'accuracy':>11}"
          f"{'gain vs ship':>14}{'P(better)':>11}")
    for arm in ARMS:
        a = pooled["arms"][arm]
        h = pooled["vs_ship"].get(arm)
        print(f"{arm:<10}{a['log_loss']:>10.4f}{a['accuracy'] * 100:>10.1f}%"
              + (f"{h['mean_gain']:>+14.5f}{h['p_better']:>11.3f}" if h else
                 f"{'—':>14}{'—':>11}"))

    REPORT.write_text(json.dumps(
        {"leagues_used": LEAGUES_USED, "seasons": per_season,
         "by_league": by_league, "pooled": pooled}, indent=2), encoding="utf-8")
    print(f"\n-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
