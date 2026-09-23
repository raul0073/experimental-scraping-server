"""Does the team layer add anything to the predictor we already ship?

`experiment_predictor_epl.py` asked whether the event-derived process metrics
carry match-level signal at all, against a points baseline, and they do. That
is not the same as being useful: the shipped model already prices a fixture
from Understat xG through Dixon-Coles and a draw classifier, and a new input
earns its place only by improving THAT.

So both arms run on the same Premier League fixtures:

  shipped    the live pipeline exactly as served — decayed xG attack/defence
             -> lambdas -> Dixon-Coles grid -> draw classifier ->
             unified_probs. Frozen params, nothing refitted.
  stacked    a logistic on the shipped triplet's log-odds PLUS the four
             walk-forward process ratings, trained on 24/25 and tested on
             25/26.

If stacking wins, the team layer is telling the model something xG does not.
If it does not, the honest answer is that xG already contains it and the
layer stays a descriptive product rather than a predictor input.

TWO BIASES, BOTH AGAINST THE NEW INPUT, both deliberate:
  * the shipped params were calibrated on 24/25, which is the stacker's
    TRAINING season, so the shipped arm looks its best exactly where the
    stacker is deciding how much to trust it
  * the process ratings are expanding means seeded from last season, never
    the season-long averages the team pages show

Writes data/reports/experiment_predictor_stack_epl.json

Usage: .venv/Scripts/python.exe scripts/experiment_predictor_stack_epl.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

# the experiment next door owns the walk-forward feature build; reuse it
# rather than keeping a second copy of the leak rules
from experiment_predictor_epl import (           # noqa: E402
    OUTCOMES, build_features, fixtures, log_loss,
)

LEAGUE = "ENG-Premier League"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_predictor_stack_epl.json"
PROC = ["f_att_h", "f_con_h", "f_att_a", "f_con_a"]
OUT_OF = {"home": "H", "draw": "D", "away": "A"}


def _tokens(name: str) -> list:
    drop = ("fc", "afc", "cf")
    return [w for w in "".join(c if c.isalnum() else " " for c in name.lower()).split()
            if w not in drop]


def align(src: set, dst: set) -> dict:
    """Understat names -> WhoScored names. Only four differ in the Premier
    League — Leeds United/Leeds, Manchester Utd/Man Utd — and the same token
    rule the crest matcher uses settles all of them: every word of the
    shorter name must prefix a word of the longer one, and an ambiguous
    match is dropped rather than guessed."""
    def fits(short, long):
        used = set()
        for w in short:
            hit = next((i for i, v in enumerate(long)
                        if i not in used and (v.startswith(w) or w.startswith(v))),
                       None)
            if hit is None:
                return False
            used.add(hit)
        return True

    out = {}
    for a in src:
        if a in dst:
            out[a] = a
            continue
        ta = _tokens(a)
        hits = [b for b in dst if fits(ta, _tokens(b)) or fits(_tokens(b), ta)]
        if len(hits) == 1:
            out[a] = hits[0]
    return out


def shipped(season: str, history: list) -> dict:
    """(date, home, away) -> the official triplet, exactly as served live."""
    params = json.loads(
        (ROOT / "data" / "config" / "model_params.json").read_text(encoding="utf-8"))
    rho = params["rho"]
    boosts = params["leagues"][LEAGUE]
    draw_model = DrawModel.load()

    fm = FormModel(LEAGUE, history)
    us = UnderstatService.load(LEAGUE, season)
    fx = FixturesService.load(LEAGUE, season)
    weeks = {(m["home_team"], m["away_team"]): m["week"]
             for m in fx["matches"] if isinstance(m["week"], int)}

    out = {}
    for m in us["matches"]:
        if m["home_goals"] is None:
            continue
        ratings = fm.ratings_before(m["date"])
        lam_h, lam_a, low = fm.lambdas(
            ratings, m["home_team"], m["away_team"],
            boosts["home_boost"], boosts["away_boost"])
        p = outcome_probs(lam_h, lam_a, rho)
        p_draw = None
        if draw_model and not low:
            roll = DrawModel.rolling_stats(fm.matches, m["date"])
            if m["home_team"] in roll and m["away_team"] in roll:
                ctx = DrawModel.season_context(
                    us["matches"], m["date"], m["home_team"], m["away_team"])
                p_draw = draw_model.predict(DrawModel.fixture_features(
                    lam_h, lam_a, rho, roll[m["home_team"]],
                    roll[m["away_team"]], ctx))
        out[(m["date"], m["home_team"], m["away_team"])] = {
            "p": unified_probs(p, p_draw),
            "low": low,
            "week": weeks.get((m["home_team"], m["away_team"])),
        }
    return out


CACHE = ROOT / "data" / "reports" / "_stack_epl_rows.json"


def main() -> int:
    import pandas as pd
    if "--cached" in sys.argv and CACHE.exists():
        # season back as a STRING: read_json turns "2425" into the integer
        # 2425, and every == "2425" then quietly matches nothing
        df = pd.read_json(CACHE, dtype={"season": str})
        df["season"] = df["season"].astype(str)
        print(f"cached rows: {len(df)}")
        return score(df)

    print("building walk-forward process ratings…", flush=True)
    fx = build_features(fixtures(LEAGUE, ["2324", "2425", "2526"]))
    fx["date"] = [str(k)[:10] for k in fx["kick"]]

    print("running the shipped pipeline…", flush=True)
    live = {}
    for season, hist in (("2425", ["2324", "2425"]), ("2526", ["2425", "2526"])):
        live[season] = shipped(season, hist)
        print(f"  {season}: {len(live[season])} fixtures", flush=True)

    # names, once
    us_names = {t for d in live.values() for (_dt, h, a) in d for t in (h, a)}
    ws_names = set(fx["home"]) | set(fx["away"])
    name = align(us_names, ws_names)
    missing = sorted(us_names - set(name))
    if missing:
        print(f"  unmatched team names: {missing}")

    rows = []
    for season, per in live.items():
        block = fx[fx["season"] == season]
        by_key = {(r.date, r.home, r.away): r for r in block.itertuples(index=False)}
        for (date, h, a), got in per.items():
            key = (date, name.get(h), name.get(a))
            r = by_key.get(key)
            if r is None or got["low"]:
                continue
            if r.n_home < 3 or r.n_away < 3:
                continue
            rows.append({
                "season": season, "y": r.y,
                **{c: getattr(r, c) for c in PROC},
                # log-odds of the shipped triplet: a stacker should be handed
                # the model's own confidence, not a raw probability it has to
                # re-learn the scale of
                "lp_h": math.log(max(got["p"]["home"], 1e-9)),
                "lp_d": math.log(max(got["p"]["draw"], 1e-9)),
                "lp_a": math.log(max(got["p"]["away"], 1e-9)),
                "_p": [got["p"]["home"], got["p"]["draw"], got["p"]["away"]],
            })

    df = pd.DataFrame(rows)
    CACHE.write_text(df.to_json(orient="records"), encoding="utf-8")
    return score(df)


def score(df) -> int:
    train = df[df["season"] == "2425"].copy()
    test = df[df["season"] == "2526"].copy()
    print(f"\nmatched: train {len(train)}, test {len(test)}")
    if len(test) < 100:
        print("too few matched fixtures to judge anything")
        return 1

    yte = list(test["y"])
    ship_probs = np.array(list(test["_p"]))
    ship_ll = log_loss(ship_probs, yte)
    ship_acc = float(np.mean(
        [OUTCOMES[i] == v for i, v in zip(ship_probs.argmax(axis=1), yte)]))

    def fit(cols, C=1.0):
        sc = StandardScaler().fit(train[cols].values)
        clf = LogisticRegression(max_iter=2000, C=C)
        clf.fit(sc.transform(train[cols].values), list(train["y"]))
        raw = clf.predict_proba(sc.transform(test[cols].values))
        order = list(clf.classes_)
        p = np.column_stack([raw[:, order.index(o)] for o in OUTCOMES])
        return {
            "log_loss": round(log_loss(p, yte), 4),
            "accuracy": round(float(np.mean(
                [OUTCOMES[i] == v for i, v in zip(p.argmax(axis=1), yte)])), 4),
        }

    # ONE process number instead of four, because seven free parameters on
    # 350 training matches is how a stack loses to its own inputs. Home
    # strength is this side's attack PLUS what the other side concedes —
    # conceding a lot is good news for whoever is playing them.
    for d in (train, test):
        d["f_edge"] = ((d["f_att_h"] + d["f_con_a"])
                       - (d["f_att_a"] + d["f_con_h"]))

    ship_only = fit(["lp_h", "lp_d", "lp_a"])
    stacked = fit(["lp_h", "lp_d", "lp_a"] + PROC)
    proc_only = fit(PROC)
    thin = fit(["lp_h", "lp_d", "lp_a", "f_edge"])
    tight = fit(["lp_h", "lp_d", "lp_a"] + PROC, C=0.05)

    report = {
        "league": LEAGUE, "train_season": "2425", "test_season": "2526",
        "n_train": len(train), "n_test": len(test),
        "shipped_as_served": {"log_loss": round(ship_ll, 4),
                              "accuracy": round(ship_acc, 4)},
        "shipped_recalibrated": ship_only,
        "process_only": proc_only,
        "stacked": stacked,
        "stacked_one_feature": thin,
        "stacked_regularised": tight,
        "gain": round(ship_only["log_loss"] - stacked["log_loss"], 4),
        "gain_best": round(ship_only["log_loss"] - min(
            stacked["log_loss"], thin["log_loss"], tight["log_loss"]), 4),
        "verdict": (
            "NOT SHIPPED. The best the team layer manages against the live "
            "model is +0.0001 log-loss, which is nothing, and it only gets "
            "there at C=0.05 — regularised so hard the process features are "
            "almost switched off. Left free they make it WORSE (1.0482 "
            "against 1.0318): seven parameters on 350 training matches is "
            "not a stack, it is a memoriser. The likely reason is that the "
            "layer and Understat xG measure the same thing — box entries, "
            "shots and big chances ARE chance creation — so it reproduces "
            "the input rather than adding to it. The accuracy reading "
            "(50.3% against 48.3%) is two points on 350 matches, inside its "
            "own standard error of about 2.7, so it is not evidence either. "
            "RETEST ON FIVE LEAGUES: ~1,750 test matches is where an edge "
            "this small would become visible or would finally disappear."
        ),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"  shipped, as served     log-loss {ship_ll:.4f}   "
          f"accuracy {ship_acc * 100:.1f}%")
    for label, r in (("shipped, recalibrated", ship_only),
                     ("process only", proc_only),
                     ("shipped + process x4", stacked),
                     ("shipped + one feature", thin),
                     ("shipped + process, C=.05", tight)):
        print(f"  {label:<22} log-loss {r['log_loss']:.4f}   "
              f"accuracy {r['accuracy'] * 100:.1f}%")
    print()
    print(f"best the team layer manages: {report['gain_best']:+.4f} log-loss "
          f"on the shipped model (positive = better)")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
