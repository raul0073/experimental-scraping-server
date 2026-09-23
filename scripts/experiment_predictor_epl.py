"""Does the team layer predict MATCHES? Premier League only, walk-forward.

The team layer was gated on whether its metrics predict POINTS over half a
season. That is a different question from whether they price Saturday's
fixture, and the second one is what the predictor needs.

THE WHOLE TEST IS THE WALK-FORWARD. Every rating used to price a match is
built only from matches that had already been played when it kicked off. A
season-long opponent-adjusted average — which is what the team pages show —
contains the result of the very match it would be predicting, and a model fed
that scores beautifully and knows nothing. So ratings here are EXPANDING
means, rebuilt before every round, seeded from last season's final standing
so that matchday one is not blind:

    rating = (PRIOR * last season's mean + n * this season's mean)
             / (PRIOR + n)

Four models, on the same fixtures, judged on log-loss:

  base      the league's own H/D/A frequencies. Beat this or go home.
  points    past points per game, home minus away. The honest baseline —
            the thing anyone would use without an event stream.
  process   the team layer: attack and defence built from the gated
            process metrics.
  both      points and process together.

Writes data/reports/experiment_predictor_epl.json

Usage: .venv/Scripts/python.exe scripts/experiment_predictor_epl.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from services.mental.positions import load_match
from services.mental.role_bank import RAW, seasons_on_disk
from services.mental.team_metrics import match_rows

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_predictor_epl.json"

# How many matches of last season's rating a team carries into this one.
# Six is about a month and a half: enough that matchday one is not a coin
# toss, little enough that a genuinely changed side is not held to its past
# for half a season.
PRIOR = 6.0

# Attack and defence, from the metrics that passed BOTH team gates. Weights
# are the shipped preset, rescaled inside each side of the ball — nothing
# tuned on the test season, because tuning on it is how a backtest lies.
ATTACK = {"box_entry_op_90": 14, "shot_op_90": 12, "bigchance_op_90": 10,
          "prog_pass_90": 8, "f3_entry_90": 6}
# CONCEDED, not "defensive quality" — every metric here counts what the
# opponent was allowed, so HIGHER IS WORSE. Naming it `def` and subtracting
# it from the other side's attack, as if it were a defensive rating, made a
# leaky back four look like a hard one: the process model then scored 1.0883
# against a base rate of 1.0880, which is not a null result, it is a sign
# error. The four ratings are now handed to the model separately and it
# works out the signs itself.
CONCEDED = {"box_entry_con_op_90": 15, "shot_con_op_90": 13,
            "bigchance_con_op_90": 12}
OUTCOMES = ["H", "D", "A"]


def fixtures(league: str, seasons: list) -> pd.DataFrame:
    """One row per match: who, when, what happened, and both teams' events."""
    out = []
    for season in seasons:
        df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
        for gid, match in df.groupby("game_id", sort=False):
            doc = load_match(league, season, gid)
            if doc is None:
                continue
            home = (doc.get("home") or {}).get("name")
            away = (doc.get("away") or {}).get("name")
            hg = ((doc.get("home") or {}).get("scores") or {}).get("fulltime")
            ag = ((doc.get("away") or {}).get("scores") or {}).get("fulltime")
            kick = doc.get("startTime") or doc.get("startDate") or ""
            if not home or not away or hg is None or ag is None or not kick:
                continue
            per = {r["team"]: r for r in match_rows(match)}
            if home not in per or away not in per:
                continue
            out.append({
                "season": season, "game_id": int(gid), "kick": kick,
                "home": home, "away": away, "hg": int(hg), "ag": int(ag),
                "y": "H" if hg > ag else ("A" if ag > hg else "D"),
                "row_home": per[home], "row_away": per[away],
            })
        print(f"  read {season}  ({len(out)} matches so far)", flush=True)
    return pd.DataFrame(out).sort_values("kick").reset_index(drop=True)


def _composite(row: dict, weights: dict) -> float:
    s = used = 0.0
    for k, w in weights.items():
        v = row.get(k)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        s += float(v) * w
        used += w
    return s / used if used else np.nan


def build_features(fx: pd.DataFrame) -> pd.DataFrame:
    """Ratings as they stood BEFORE each kickoff.

    Walked match by match in kickoff order. A team's rating going into a
    fixture is the mean of its own prior matches this season, blended with
    where it finished last season. Nothing from the match itself, and nothing
    from later in the season, ever touches it.
    """
    # z-scored per season so a rating means the same thing across seasons
    for side in ("home", "away"):
        fx[f"att_{side}"] = [
            _composite(r, ATTACK) for r in fx[f"row_{side}"]]
        fx[f"con_{side}"] = [
            _composite(r, CONCEDED) for r in fx[f"row_{side}"]]
        fx[f"pts_{side}"] = [
            float(r.get("pts", 0) or 0) for r in fx[f"row_{side}"]]
    # Normalised on EARLIER SEASONS ONLY. Scaling a season by its own mean
    # and spread uses matches that had not been played yet — a small leak,
    # because it only sets the scale rather than the order, but a backtest
    # that allows itself small leaks is a backtest nobody can argue from.
    # The first season has nothing before it and is normalised on itself; it
    # is only ever a training season, so nothing on the test set is flattered.
    order = sorted(fx["season"].unique())
    for col in ("att", "con", "pts"):
        both = pd.concat([fx[f"{col}_home"], fx[f"{col}_away"]], ignore_index=True)
        seas = pd.concat([fx["season"], fx["season"]], ignore_index=True)
        z = both.astype(float).copy()
        for i, season in enumerate(order):
            ref = order[:i] if i else [season]
            base = both[seas.isin(ref)]
            mu = float(base.mean())
            sd = float(base.std()) or 1.0
            z[seas == season] = (both[seas == season] - mu) / sd
        fx[f"{col}_home"] = z.iloc[:len(fx)].values
        fx[f"{col}_away"] = z.iloc[len(fx):].values

    # last season's final mean, per team, as the seed for the next one
    finals: dict = defaultdict(dict)
    for season, block in fx.groupby("season"):
        tot = defaultdict(lambda: defaultdict(list))
        for r in block.itertuples(index=False):
            for side, team in (("home", r.home), ("away", r.away)):
                tot[team]["att"].append(getattr(r, f"att_{side}"))
                tot[team]["con"].append(getattr(r, f"con_{side}"))
                tot[team]["pts"].append(getattr(r, f"pts_{side}"))
        for team, d in tot.items():
            finals[season][team] = {k: float(np.nanmean(v))
                                    for k, v in d.items()}

    order = sorted(fx["season"].unique())
    prev_of = {s: (order[i - 1] if i else None) for i, s in enumerate(order)}

    run: dict = defaultdict(lambda: defaultdict(list))
    feats = []
    for r in fx.itertuples(index=False):
        prev = prev_of[r.season]

        def rating(team: str, key: str) -> float:
            seen = run[(r.season, team)][key]
            seed = (finals.get(prev, {}).get(team, {}) or {}).get(key, 0.0)
            n = len(seen)
            now = float(np.nanmean(seen)) if n else 0.0
            return (PRIOR * seed + n * now) / (PRIOR + n)

        feats.append({
            "n_home": len(run[(r.season, r.home)]["att"]),
            "n_away": len(run[(r.season, r.away)]["att"]),
            # the four ratings, unopinionated. The model decides what a high
            # `con` means rather than being told by the sign I chose.
            "f_att_h": rating(r.home, "att"),
            "f_con_h": rating(r.home, "con"),
            "f_att_a": rating(r.away, "att"),
            "f_con_a": rating(r.away, "con"),
            "f_pts": rating(r.home, "pts") - rating(r.away, "pts"),
        })
        # only NOW does this match enter the running totals
        for side, team in (("home", r.home), ("away", r.away)):
            for key in ("att", "con", "pts"):
                run[(r.season, team)][key].append(
                    getattr(r, f"{key}_{side}"))
    return pd.concat([fx, pd.DataFrame(feats)], axis=1)


def log_loss(probs: np.ndarray, y: list) -> float:
    ix = {o: i for i, o in enumerate(OUTCOMES)}
    p = np.clip(probs, 1e-9, 1)
    return float(-np.mean([np.log(p[i, ix[v]]) for i, v in enumerate(y)]))


def run(train: pd.DataFrame, test: pd.DataFrame, cols: list) -> dict:
    ytr = list(train["y"])
    yte = list(test["y"])
    if not cols:                       # the base rate, from the TRAIN years
        freq = np.array([ytr.count(o) / len(ytr) for o in OUTCOMES])
        probs = np.tile(freq, (len(test), 1))
    else:
        sc = StandardScaler().fit(train[cols].values)
        clf = LogisticRegression(max_iter=2000, C=1.0)
        clf.fit(sc.transform(train[cols].values), ytr)
        raw = clf.predict_proba(sc.transform(test[cols].values))
        order = list(clf.classes_)
        probs = np.column_stack([raw[:, order.index(o)] for o in OUTCOMES])
    called = [OUTCOMES[i] for i in probs.argmax(axis=1)]
    return {
        "log_loss": round(log_loss(probs, yte), 4),
        "accuracy": round(float(np.mean([a == b for a, b in zip(called, yte)])), 4),
        "n": len(test),
        "_probs": probs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--test", default="2526", help="season held out")
    args = ap.parse_args()

    seasons = [s for s in seasons_on_disk(args.league) if s != "2627"]
    print(f"seasons: {', '.join(seasons)}  (26/27 excluded — 4 matches)")
    fx = build_features(fixtures(args.league, seasons))

    # Matchdays 1-3 are dropped from SCORING, not from the ratings: a side
    # three games in is still mostly last season, and judging a model on a
    # rating it has barely been given is judging the seed.
    warm = fx[(fx["n_home"] >= 3) & (fx["n_away"] >= 3)]
    train = warm[warm["season"] != args.test]
    test = warm[warm["season"] == args.test]
    print(f"train {len(train)} matches, test {len(test)} "
          f"({args.test}, after matchday 3)")

    PROC = ["f_att_h", "f_con_h", "f_att_a", "f_con_a"]
    models = {
        "base": [],
        "points": ["f_pts"],
        "process": PROC,
        "both": ["f_pts"] + PROC,
    }
    out = {}
    for name, cols in models.items():
        res = run(train, test, cols)
        probs = res.pop("_probs")
        if name == "both":
            # where the picks would land: the most likely outcome, and how
            # often the model was right when it was confident
            conf = probs.max(axis=1)
            for cut in (0.5, 0.6):
                pick = conf >= cut
                if pick.sum():
                    called = [OUTCOMES[i] for i in probs[pick].argmax(axis=1)]
                    truth = [v for v, k in zip(test["y"], pick) if k]
                    res[f"hit_over_{int(cut * 100)}"] = round(float(
                        np.mean([a == b for a, b in zip(called, truth)])), 4)
                    res[f"n_over_{int(cut * 100)}"] = int(pick.sum())
        out[name] = res
        print(f"  {name:<9}log-loss {res['log_loss']:.4f}   "
              f"accuracy {res['accuracy'] * 100:.1f}%")

    report = {
        "league": args.league,
        "test_season": args.test,
        "train_seasons": [s for s in seasons if s != args.test],
        "n_test": len(test),
        "prior_matches": PRIOR,
        "models": out,
        "gain_vs_points": round(
            out["points"]["log_loss"] - out["both"]["log_loss"], 4),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print()
    print(f"process adds {report['gain_vs_points']:+.4f} log-loss over points "
          f"alone (positive = better)")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
