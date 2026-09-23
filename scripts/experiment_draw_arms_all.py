"""Which arm should rank the draw picks? Asked on five leagues, not one.

WHY THIS EXISTS. `experiment_elo_draws.py` answered the same question on
`LEAGUE = "ENG-Premier League"` and `TEST = "2526"` — 372 fixtures, 40 picks.
At that size the shipped model's top-40 draw hit rate came out at 15.0%
against a 27.7% base (binomial p=0.047, i.e. significantly BAD) and the Elo's
at 32.5% (p=0.30, i.e. unremarkable). Neither number was safe to act on: one
was a borderline tail and the other was noise, and a four-fold ticket is
built entirely out of this ranking.

Nothing was stopping the wider test except two constants. Understat carries
thirteen seasons of all five leagues — 21,819 played fixtures — and
`matches_from_understat` builds the Elo's frame from it with no event stream
involved, which is what makes the rating shippable in the first place. Using
that loader also removes the name-alignment step the old script needed, since
both sides are then reading Understat's own spellings.

THE HOLDOUT IS NOT NEGOTIABLE AND IT IS WHY THIS IS 25/26 ONLY. The shipped
draw classifier on disk was trained on 1415…2425 — eleven seasons. Scoring
the shipped arm on any of those would be marking its own homework. 25/26 is
the one complete season the frozen artifact has never seen, so that is the
test season; widening happens across LEAGUES, which multiplies the sample by
five without touching the leakage boundary.

Four arms, the same four as before:

  ship        the live pipeline: its lambdas, its classifier
  elo         Dixon-Coles draws off the Elo lambdas, no classifier
  elo_clf     the Elo's lambdas through the SAME classifier
  blend       ship and elo_clf averaged

TWO WAYS OF COUNTING PICKS, because they answer different questions. Top-40
per league summed to 200 is the comparable-to-last-time number. A single
pooled ranking across all five leagues is what the product actually does —
four picks a week, taken from wherever they are best — and it is the one to
decide on.

Writes data/reports/experiment_draw_arms_all.json

Usage: .venv/Scripts/python.exe scripts/experiment_draw_arms_all.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scipy import stats

from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService
from services.zones.zones_engine import ZonesEngine, channel_boosts

from build_process_elo import matches_from_understat, outcome, walk  # noqa: E402

OUTCOMES = ["H", "D", "A"]
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_draw_arms_all.json"
# Every priced fixture, kept so that anything else wanting to sweep a
# threshold over these 1,714 rows does not have to rebuild walk-forward
# zones for ten minutes to get them.
ROWS = ROOT / "data" / "reports" / "_draw_arms_rows.csv"
TEST = "2526"
#  ship      the live pipeline, as served
#  elo       Dixon-Coles off the Elo lambdas, no classifier
#  elo_clf   the Elo's lambdas through the shipped classifier
#  blend     ship and elo_clf averaged
#  mix_se    SHIP's home:away ratio, ELO's draw
#  mix_es    ELO's home:away ratio, SHIP's draw
#
# The last two are the layering: `unified_probs` already exists to take a
# triplet and substitute a P(draw) while preserving the home:away ratio —
# that is precisely how the shipped model is built, Poisson for the ratio
# and a classifier for the draw. So if one arm wins the overall triplet and
# a different one wins the draw ranking, the combination is not a new model
# to build, it is one call with different arguments, and it can be measured
# here rather than assumed to help.
#  layer     BLEND's home:away ratio, ELO_CLF's draw
ARMS = ["ship", "elo", "elo_clf", "blend", "mix_se", "mix_es", "layer"]
# 40 a league matches the earlier run; 4 a week over a 38-week season is the
# product, and across five leagues that is what a pooled 200 represents.
PER_LEAGUE_PICKS = 40
POOLED_PICKS = 200

# 🐛 THE FIRST RUN OF THIS SCRIPT COMPARED AGAINST THE WRONG SHIP.
# Production multiplies the form lambdas by zone-channel boosts before the
# Dixon-Coles grid and the draw classifier ever see them, and the first
# version of this experiment left that out — so "ship" was really
# "ship minus zones", which their own gate puts at about 0.0024 nats worse
# (1.00145 form-only vs 0.99903 channels). Blend's margin over ship was
# +0.0018. Omitting a component worth more than the margin being measured is
# not a detail; it could have reversed the answer.
#
# Zones cannot simply be loaded, either: the live engine builds them from
# ZONES_SOURCE_SEASON = ["2526", "2627"], so using them to score 25/26 would
# be scoring a season with knowledge of itself. They are rebuilt per date
# instead, cached, exactly as experiment_zone_channels_stack.py does.
ZONE_MIN_MATCHES = 8


def pick_stats(p: np.ndarray, is_draw: np.ndarray, n_picks: int) -> dict:
    """What the top-ranked picks actually did, and whether it means anything.

    The binomial is one-sided in BOTH directions because the interesting
    result last time was a rate significantly BELOW base — a ranking that is
    reliably worse than chance is a finding, not a null."""
    order = np.argsort(-p)[:n_picks]
    hits = int(is_draw[order].sum())
    base = float(is_draw.mean())
    return {
        "picks": int(n_picks),
        "hits": hits,
        "hit_rate": round(hits / n_picks, 4),
        "said": round(float(p[order].mean()), 4),
        "base_rate": round(base, 4),
        "lift": round(hits / n_picks - base, 4),
        "p_better": round(stats.binomtest(
            hits, n_picks, base, alternative="greater").pvalue, 4),
        "p_worse": round(stats.binomtest(
            hits, n_picks, base, alternative="less").pvalue, 4),
    }


def triplet_ll(d: pd.DataFrame, arm: str) -> np.ndarray:
    """Per-fixture log loss over the full H/D/A triplet — the number that
    decides what gets PUBLISHED, as opposed to what ranks the picks."""
    return np.array([-np.log(max(row[f"{arm}_{row['y']}"], 1e-9))
                     for _, row in d.iterrows()])


def paired(a: np.ndarray, b: np.ndarray, seed: int = 0) -> dict:
    """Is arm a really better than arm b? Resample the PAIRS, not the arms.

    Two models scored on the same fixtures share almost all of their
    variance; comparing their means as if they were independent samples is
    how a difference of a few thousandths gets reported as a finding."""
    diff = b - a
    rng = np.random.default_rng(seed)
    draws = np.array([rng.choice(diff, size=len(diff), replace=True).mean()
                      for _ in range(5000)])
    return {
        "mean_gain": round(float(diff.mean()), 5),
        "p_better": round(float((draws > 0).mean()), 4),
    }


def prob_stats(p: np.ndarray, is_draw: np.ndarray) -> dict:
    """The probability itself, independent of any ranking."""
    q = np.clip(p, 1e-9, 1 - 1e-9)
    return {
        "mean_p": round(float(q.mean()), 4),
        "actual_rate": round(float(is_draw.mean()), 4),
        "calibration_gap": round(float(q.mean() - is_draw.mean()), 4),
        "binary_log_loss": round(float(np.mean(
            -(is_draw * np.log(q) + (1 - is_draw) * np.log(1 - q)))), 4),
    }


def league_rows(league: str, elo_params: dict, ship_params: dict,
                draw_model: DrawModel, zone_blend: dict | None) -> pd.DataFrame:
    """Every 25/26 fixture of one league, priced by every arm."""
    params = elo_params[league]
    boosts = ship_params["leagues"][league]
    rho_ship = ship_params["rho"]

    df = matches_from_understat(league)
    if df.empty:
        return pd.DataFrame()

    rows, _A, _D = walk(df, params["k"], params["home_adv"],
                        params["decay"], "xg")
    rows["date"] = [str(k)[:10] for k in rows["kick"]]
    te = rows[rows["season"] == TEST]
    by_key = {(r.date, r.home, r.away): r
              for r in te.itertuples(index=False)}

    # the season before the test one, so form has somewhere to start
    seasons = sorted(df["season"].unique())
    prior = [s for s in seasons if s < TEST]
    fm = FormModel(league, ([prior[-1]] if prior else []) + [TEST])
    us = UnderstatService.load(league, TEST)

    eng = ZonesEngine(league, TEST) if zone_blend else None
    zcache: dict = {}
    seen: dict = {}

    out = []
    for m in sorted(us["matches"], key=lambda x: x["date"]):
        if m["home_goals"] is None:
            continue
        h, a, date = m["home_team"], m["away_team"], str(m["date"])[:10]
        nh, na = seen.get(h, 0), seen.get(a, 0)
        seen[h], seen[a] = nh + 1, na + 1
        # Understat names on both sides now, so no alignment table is needed
        r = by_key.get((date, h, a))
        if r is None:
            continue

        ratings = fm.ratings_before(m["date"])
        lam_h, lam_a, low = fm.lambdas(ratings, h, a,
                                       boosts["home_boost"], boosts["away_boost"])
        if low:
            continue

        # ZONES, WALK-FORWARD — the live path's channel boost, rebuilt from
        # only what had happened by this date. Early in a season there is not
        # enough of a window, and production falls back to the plain form
        # lambdas there too, so the fallback is faithful rather than a gap.
        if eng and nh >= ZONE_MIN_MATCHES and na >= ZONE_MIN_MATCHES:
            if date not in zcache:
                try:
                    zcache[date] = eng.build(as_of_date=m["date"], persist=False,
                                             include_players=False)["teams"]
                except Exception:
                    zcache[date] = None
            zones = zcache[date]
            if zones and h in zones and a in zones:
                b = channel_boosts(zones, h, a, zone_blend)
                if b:
                    lam_h *= b[0]
                    lam_a *= b[1]
        roll = DrawModel.rolling_stats(fm.matches, m["date"])
        if h not in roll or a not in roll:
            continue
        ctx = DrawModel.season_context(us["matches"], m["date"], h, a)

        # shipped, exactly as served
        p_ship = unified_probs(
            outcome_probs(lam_h, lam_a, rho_ship),
            draw_model.predict(DrawModel.fixture_features(
                lam_h, lam_a, rho_ship, roll[h], roll[a], ctx)))

        # the Elo's own lambdas, straight off the grid
        elh = max(r.exp_hc * params["conv"], 1e-3)
        ela = max(r.exp_ac * params["conv"], 1e-3)
        elo_p = outcome(elh, ela, params["rho"])

        # and the same classifier fed the Elo's lambda pair
        elo_clf = unified_probs(
            {"home": float(elo_p[0]), "draw": float(elo_p[1]),
             "away": float(elo_p[2])},
            draw_model.predict(DrawModel.fixture_features(
                elh, ela, params["rho"], roll[h], roll[a], ctx)))

        # THE LAYERS: each model's home:away ratio carrying the other's draw
        elo_trip = {"home": float(elo_p[0]), "draw": float(elo_p[1]),
                    "away": float(elo_p[2])}
        mix_se = unified_probs(p_ship, float(elo_p[1]))
        mix_es = unified_probs(elo_trip, p_ship["draw"])

        hg, ag = int(m["home_goals"]), int(m["away_goals"])
        row = {
            "league": league, "date": date, "home": h, "away": a,
            "y": "H" if hg > ag else ("A" if ag > hg else "D"),
            "is_draw": int(hg == ag),
            # THE WHOLE TRIPLET, not just the draw. Which arm to ship is two
            # questions — what to publish as probabilities, and what to rank
            # the four weekly picks with — and they can have different
            # answers, so both have to be measurable from the same rows.
            "ship_H": p_ship["home"], "ship_D": p_ship["draw"],
            "ship_A": p_ship["away"],
            "elo_H": float(elo_p[0]), "elo_D": float(elo_p[1]),
            "elo_A": float(elo_p[2]),
            "elo_clf_H": elo_clf["home"], "elo_clf_D": elo_clf["draw"],
            "elo_clf_A": elo_clf["away"],
            "mix_se_H": mix_se["home"], "mix_se_D": mix_se["draw"],
            "mix_se_A": mix_se["away"],
            "mix_es_H": mix_es["home"], "mix_es_D": mix_es["draw"],
            "mix_es_A": mix_es["away"],
        }
        out.append(row)

    d = pd.DataFrame(out)
    if d.empty:
        return d
    # the blend is the two averaged then renormalised — averaging triplets
    # componentwise does not guarantee they still sum to one
    for o in OUTCOMES:
        d[f"blend_{o}"] = (d[f"ship_{o}"] + d[f"elo_clf_{o}"]) / 2
    tot = sum(d[f"blend_{o}"] for o in OUTCOMES)
    for o in OUTCOMES:
        d[f"blend_{o}"] = d[f"blend_{o}"] / tot

    # THE LAYER, once the arms are known: the best TRIPLET carrying the best
    # DRAW. This is `unified_probs` written out over columns — P(draw) is
    # taken whole and home/away keep their ratio and rescale into the rest.
    # It is worth its own arm because "which model prices a match" and
    # "which model ranks a draw" came back with different winners, and the
    # product needs both at once.
    d["layer_D"] = d["elo_clf_D"]
    rest = 1.0 - d["layer_D"]
    s = (d["blend_H"] + d["blend_A"]).replace(0, 1.0)
    d["layer_H"] = d["blend_H"] / s * rest
    d["layer_A"] = d["blend_A"] / s * rest

    for a in ARMS:
        d[a] = d[f"{a}_D"]
    return d


def main() -> int:
    elo_params = json.loads((ROOT / "data" / "config" / "elo_params.json")
                            .read_text(encoding="utf-8"))
    ship_params = json.loads((ROOT / "data" / "config" / "model_params.json")
                             .read_text(encoding="utf-8"))
    draw_model = DrawModel.load()
    if draw_model is None:
        print("no draw classifier on disk")
        return 1

    zb_path = ROOT / "data" / "config" / "zone_blend.json"
    zone_blend = None
    if zb_path.exists():
        zb = json.loads(zb_path.read_text(encoding="utf-8"))
        if zb.get("mode") == "channels":
            zone_blend = zb
    print(f"zone channels: {'on (walk-forward)' if zone_blend else 'OFF'}")

    leagues = [lg for lg in ship_params["leagues"] if lg in elo_params]
    print(f"test season {TEST}; {len(leagues)} leagues\n")

    frames, per_league = [], {}
    for league in leagues:
        d = league_rows(league, elo_params, ship_params, draw_model, zone_blend)
        if d.empty:
            print(f"  {league}: no rows")
            continue
        frames.append(d)
        is_draw = d["is_draw"].values.astype(float)
        per_league[league] = {
            "n": len(d),
            "actual_draw_rate": round(float(is_draw.mean()), 4),
            "arms": {a: {**prob_stats(d[a].values, is_draw),
                         **pick_stats(d[a].values, is_draw, PER_LEAGUE_PICKS)}
                     for a in ARMS},
        }
        line = "  ".join(
            f"{a} {per_league[league]['arms'][a]['hit_rate'] * 100:.1f}%"
            for a in ARMS)
        print(f"  {league:<20} n={len(d):4d}  top{PER_LEAGUE_PICKS}: {line}")

    if not frames:
        print("nothing to compare")
        return 1

    d = pd.concat(frames, ignore_index=True)
    d.to_csv(ROWS, index=False, encoding="utf-8")
    is_draw = d["is_draw"].values.astype(float)

    pooled = {a: {**prob_stats(d[a].values, is_draw),
                  **pick_stats(d[a].values, is_draw, POOLED_PICKS)}
              for a in ARMS}

    # top-40 per league, added up — the number comparable with the old run
    summed = {}
    for a in ARMS:
        hits = sum(per_league[lg]["arms"][a]["hits"] for lg in per_league)
        picks = sum(per_league[lg]["arms"][a]["picks"] for lg in per_league)
        base = float(np.mean([per_league[lg]["actual_draw_rate"]
                              for lg in per_league]))
        summed[a] = {
            "picks": picks, "hits": hits,
            "hit_rate": round(hits / picks, 4),
            "base_rate": round(base, 4),
            "lift": round(hits / picks - base, 4),
            "p_better": round(stats.binomtest(
                hits, picks, base, alternative="greater").pvalue, 4),
            "p_worse": round(stats.binomtest(
                hits, picks, base, alternative="less").pvalue, 4),
        }

    print(f"\nPOOLED — {len(d):,} fixtures, actual draw rate "
          f"{is_draw.mean() * 100:.1f}%\n")
    print(f"{'arm':<10}{'mean P':>8}{'gap':>7}{'binary LL':>11}"
          f"{'top200 hit':>12}{'said':>7}{'lift':>8}{'p':>8}")
    for a in ARMS:
        s = pooled[a]
        print(f"{a:<10}{s['mean_p'] * 100:>7.1f}%{s['calibration_gap'] * 100:>+7.1f}"
              f"{s['binary_log_loss']:>11.4f}{s['hit_rate'] * 100:>11.1f}%"
              f"{s['said'] * 100:>6.1f}%{s['lift'] * 100:>+7.1f}"
              f"{min(s['p_better'], s['p_worse']):>8.4f}")

    print(f"\ntop-{PER_LEAGUE_PICKS} per league, summed "
          f"({summed[ARMS[0]]['picks']} picks)\n")
    print(f"{'arm':<10}{'hits':>6}{'hit rate':>10}{'base':>8}{'lift':>8}"
          f"{'p better':>10}{'p worse':>9}")
    for a in ARMS:
        s = summed[a]
        print(f"{a:<10}{s['hits']:>6}{s['hit_rate'] * 100:>9.1f}%"
              f"{s['base_rate'] * 100:>7.1f}%{s['lift'] * 100:>+8.1f}"
              f"{s['p_better']:>10.4f}{s['p_worse']:>9.4f}")

    # ---- the other half of the decision: what gets PUBLISHED -------------
    lls = {a: triplet_ll(d, a) for a in ARMS}
    called = {a: d[[f"{a}_{o}" for o in OUTCOMES]].values.argmax(axis=1)
              for a in ARMS}
    truth = np.array([OUTCOMES.index(v) for v in d["y"]])
    prior = d["y"].value_counts(normalize=True)
    base_ll = float(np.mean([-np.log(max(prior.get(v, 1 / 3), 1e-9))
                             for v in d["y"]]))

    triplet = {a: {"log_loss": round(float(lls[a].mean()), 4),
                   "accuracy": round(float((called[a] == truth).mean()), 4)}
               for a in ARMS}

    print(f"\nFULL TRIPLET — what gets published "
          f"(base log-loss {base_ll:.4f})\n")
    print(f"{'arm':<10}{'log-loss':>10}{'vs base':>10}{'accuracy':>11}")
    for a in ARMS:
        t = triplet[a]
        print(f"{a:<10}{t['log_loss']:>10.4f}{base_ll - t['log_loss']:>+10.4f}"
              f"{t['accuracy'] * 100:>10.1f}%")

    head = {}
    for a in ARMS:
        if a == "ship":
            continue
        head[f"{a}_vs_ship"] = paired(lls[a], lls["ship"])
    print("\npaired bootstrap against ship (5,000 resamples of the pairs)\n")
    for k, v in head.items():
        print(f"  {k:<18} mean gain {v['mean_gain']:+.5f} nats   "
              f"P(better) {v['p_better']:.3f}")

    REPORT.write_text(json.dumps({
        "test_season": TEST,
        "n": int(len(d)),
        "actual_draw_rate": round(float(is_draw.mean()), 4),
        "base_log_loss": round(base_ll, 4),
        "triplet": triplet,
        "head_to_head_vs_ship": head,
        "pooled_top_picks": pooled,
        "per_league_top40_summed": summed,
        "per_league": per_league,
    }, indent=2), encoding="utf-8")
    print(f"\n-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
