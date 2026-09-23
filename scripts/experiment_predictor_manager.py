"""Does knowing about the manager change make the predictor better?

THE CLAIM BEING TESTED. The shipped `FormModel` rates a side with a decayed
38-match window (DECAY = 0.985). That window does not know a club has changed
manager, so a side three games into a new tenure is still rated about ninety
per cent on the previous manager's football. We know the tenures exactly —
61 stitched spells, takeover dates checked against reality — and we know the
step change is real: Klopp to Slot moved PPDA 6.2 to 8.0, press height 36.9
to 33.9, shots 18.9 to 15.0, immediately.

So this is not a new signal competing with xG. It is a DEFECT in the existing
one, in a situation we can name.

Three ways of rating a side, identical in every other respect:

  naive    expanding mean over the club's season, seeded from last season.
           What the current harness does, and what FormModel does in spirit.
  spell    expanding mean over the CURRENT MANAGER'S matches only, seeded
           from the league average rather than from his predecessor's
           football. The hypothesis: when the manager changes, the old
           numbers are not evidence.
  feature  the naive rating, plus "how many matches into this tenure" handed
           to the model so it can shrink by itself.

Judged twice: over everything, and over the fixtures where at least one side
is NEW — under ten matches into a tenure. The second is the one that matters.
A fix for a situation that arises in nine per cent of matches cannot move the
overall number much, and if it moves the overall number without moving the
affected subset then it is not doing what it claims.

Writes data/reports/experiment_predictor_manager.json

Usage: .venv/Scripts/python.exe scripts/experiment_predictor_manager.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from services.mental.role_bank import seasons_on_disk
from services.mental.spells import build as build_spells

from experiment_predictor_epl import (           # noqa: E402
    ATTACK, CONCEDED, OUTCOMES, PRIOR, _composite, fixtures, log_loss,
)

LEAGUE = "ENG-Premier League"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_predictor_manager.json"
CACHE = ROOT / "data" / "reports" / "_manager_epl_rows.json"

# Under this many matches into a tenure, a side is "new" and its rating is
# the thing under test. Ten is about a third of a season: long enough that a
# manager has shown what he does, short enough that the old window still
# dominates a decayed average.
NEW = 10
PROC = ["f_att_h", "f_con_h", "f_att_a", "f_con_a"]


def build_rows(seasons: list) -> pd.DataFrame:
    fx = fixtures(LEAGUE, seasons)

    # per-team composites, z-scored on EARLIER seasons only (same rule as the
    # sibling experiment: scaling a season by its own spread peeks)
    for side in ("home", "away"):
        fx[f"att_{side}"] = [_composite(r, ATTACK) for r in fx[f"row_{side}"]]
        fx[f"con_{side}"] = [_composite(r, CONCEDED) for r in fx[f"row_{side}"]]
    order = sorted(fx["season"].unique())
    for col in ("att", "con"):
        both = pd.concat([fx[f"{col}_home"], fx[f"{col}_away"]], ignore_index=True)
        seas = pd.concat([fx["season"], fx["season"]], ignore_index=True)
        z = both.astype(float).copy()
        for i, season in enumerate(order):
            ref = order[:i] if i else [season]
            base = both[seas.isin(ref)]
            mu, sd = float(base.mean()), float(base.std()) or 1.0
            z[seas == season] = (both[seas == season] - mu) / sd
        fx[f"{col}_home"] = z.iloc[:len(fx)].values
        fx[f"{col}_away"] = z.iloc[len(fx):].values

    # (team, game_id) -> spell key, and how many matches into it
    spells = build_spells(LEAGUE, seasons)
    kick = dict(zip(fx["game_id"], fx["kick"]))
    spell_of, depth = {}, {}
    for sp in spells:
        games = sorted(sp.games, key=lambda g: kick.get(g, ""))
        for i, g in enumerate(games):
            spell_of[(sp.team, g)] = sp.key
            depth[(sp.team, g)] = i

    # last season's club mean, as the naive seed
    finals: dict = defaultdict(dict)
    for season, block in fx.groupby("season"):
        tot = defaultdict(lambda: defaultdict(list))
        for r in block.itertuples(index=False):
            for side, team in (("home", r.home), ("away", r.away)):
                tot[team]["att"].append(getattr(r, f"att_{side}"))
                tot[team]["con"].append(getattr(r, f"con_{side}"))
        for team, d in tot.items():
            finals[season][team] = {k: float(np.nanmean(v)) for k, v in d.items()}
    prev_of = {s: (order[i - 1] if i else None) for i, s in enumerate(order)}

    run_season: dict = defaultdict(lambda: defaultdict(list))
    # keyed by the (spell, metric) PAIR, so a flat list per key — nested the
    # way run_season is, `run_spell[(sp, key)]` hands back a dict to append to
    run_spell: dict = defaultdict(list)
    rows = []
    for r in fx.itertuples(index=False):
        prev = prev_of[r.season]

        def rate(team: str, key: str, how: str) -> float:
            club_seed = (finals.get(prev, {}).get(team, {}) or {}).get(key, 0.0)
            if how == "naive":
                seen = run_season[(r.season, team)][key]
                seed = club_seed
                prior = PRIOR
            elif how == "seed":
                # THE SURGICAL VERSION. Identical to naive in every respect
                # except one: under a new manager the seed is the league
                # average rather than his predecessor's football. The `spell`
                # arm below also swaps a within-season window for a
                # cross-season one, which is a second change and has nothing
                # to do with the hypothesis — if that arm loses, we cannot
                # say which of the two did it.
                seen = run_season[(r.season, team)][key]
                d = depth.get((team, r.game_id), 99)
                seed = 0.0 if d < NEW else club_seed
                prior = PRIOR
            else:
                sp = spell_of.get((team, r.game_id))
                seen = run_spell[(sp, key)] if sp else []
                d = depth.get((team, r.game_id), 99)
                # A NEW manager is seeded from the league average (0 in z
                # terms), not from what his predecessor's side did. Once the
                # tenure is established the club's own history is his too.
                seed = 0.0 if d < NEW else club_seed
                prior = PRIOR
            n = len(seen)
            now = float(np.nanmean(seen)) if n else 0.0
            return (prior * seed + n * now) / (prior + n)

        dh = depth.get((r.home, r.game_id), 99)
        da = depth.get((r.away, r.game_id), 99)
        rows.append({
            "season": r.season, "y": r.y, "kick": r.kick,
            "n_home": len(run_season[(r.season, r.home)]["att"]),
            "n_away": len(run_season[(r.season, r.away)]["att"]),
            "depth_home": dh, "depth_away": da,
            "new": int(dh < NEW or da < NEW),
            # naive
            "f_att_h": rate(r.home, "att", "naive"),
            "f_con_h": rate(r.home, "con", "naive"),
            "f_att_a": rate(r.away, "att", "naive"),
            "f_con_a": rate(r.away, "con", "naive"),
            # spell-scoped
            "m_att_h": rate(r.home, "att", "spell"),
            "m_con_h": rate(r.home, "con", "spell"),
            "m_att_a": rate(r.away, "att", "spell"),
            "m_con_a": rate(r.away, "con", "spell"),
            # seed-only: the one change, nothing else
            "s_att_h": rate(r.home, "att", "seed"),
            "s_con_h": rate(r.home, "con", "seed"),
            "s_att_a": rate(r.away, "att", "seed"),
            "s_con_a": rate(r.away, "con", "seed"),
            # how settled each side is, for the feature arm
            "settle_h": min(dh, 40) / 40,
            "settle_a": min(da, 40) / 40,
        })
        # only NOW do the running totals see this match
        for side, team in (("home", r.home), ("away", r.away)):
            for key in ("att", "con"):
                v = getattr(r, f"{key}_{side}")
                run_season[(r.season, team)][key].append(v)
                sp = spell_of.get((team, r.game_id))
                if sp:
                    run_spell[(sp, key)].append(v)
    return pd.DataFrame(rows)


def main() -> int:
    seasons = [s for s in seasons_on_disk(LEAGUE) if s != "2627"]
    if "--cached" in sys.argv and CACHE.exists():
        df = pd.read_json(CACHE, dtype={"season": str})
        df["season"] = df["season"].astype(str)
    else:
        df = build_rows(seasons)
        CACHE.write_text(df.to_json(orient="records"), encoding="utf-8")

    warm = df[(df["n_home"] >= 3) & (df["n_away"] >= 3)].copy()
    # Trained on the FIRST season, evaluated on the other two, so the
    # affected subset is twice the size it would be on one held-out year.
    train = warm[warm["season"] == seasons[0]]
    test = warm[warm["season"] != seasons[0]].copy()
    fresh = test[test["new"] == 1]
    print(f"train {len(train)} ({seasons[0]}), test {len(test)} "
          f"({', '.join(seasons[1:])})")
    print(f"of those, {len(fresh)} have a side under {NEW} matches into a "
          f"tenure ({100 * len(fresh) / max(len(test), 1):.0f}%)")

    ix = {o: i for i, o in enumerate(OUTCOMES)}
    losses = {}

    def fit(cols):
        sc = StandardScaler().fit(train[cols].values)
        clf = LogisticRegression(max_iter=2000, C=1.0)
        clf.fit(sc.transform(train[cols].values), list(train["y"]))
        raw = clf.predict_proba(sc.transform(test[cols].values))
        o = list(clf.classes_)
        p = np.column_stack([raw[:, o.index(k)] for k in OUTCOMES])
        mask = (test["new"] == 1).values
        # the PER-FIXTURE loss, kept so two arms can be compared pair by pair
        # rather than mean against mean
        per = np.array([-np.log(max(p[i, ix[v]], 1e-9))
                        for i, v in enumerate(test["y"])])
        return per, mask, {
            "log_loss": round(log_loss(p, list(test["y"])), 4),
            "log_loss_new": round(
                log_loss(p[mask], [v for v, k in zip(test["y"], mask) if k]), 4),
            "accuracy": round(float(np.mean(
                [OUTCOMES[i] == v for i, v in zip(p.argmax(axis=1), test["y"])])), 4),
        }

    def paired(a: str, b: str, only_new: bool) -> dict:
        """Is arm `a` really better than arm `b`, or did a few fixtures
        happen to fall the right way? The same match is scored by both, so
        the comparison is paired and the bootstrap resamples the PAIRS."""
        pa, mask = losses[a]
        pb, _ = losses[b]
        d = (pb - pa)[mask] if only_new else (pb - pa)
        if len(d) < 20:
            return {"n": len(d)}
        rng = np.random.default_rng(0)
        draws = np.array([
            rng.choice(d, size=len(d), replace=True).mean() for _ in range(5000)
        ])
        return {
            "n": int(len(d)),
            "mean_gain": round(float(d.mean()), 4),
            "p_better": round(float((draws > 0).mean()), 4),
            "ci95": [round(float(np.percentile(draws, 2.5)), 4),
                     round(float(np.percentile(draws, 97.5)), 4)],
        }

    MPROC = ["m_att_h", "m_con_h", "m_att_a", "m_con_a"]
    SPROC = ["s_att_h", "s_con_h", "s_att_a", "s_con_a"]
    arms = {
        "naive": PROC,
        "seed": SPROC,
        "spell": MPROC,
        "feature": PROC + ["settle_h", "settle_a"],
    }
    out = {}
    for k, v in arms.items():
        per, mask, stats = fit(v)
        losses[k] = (per, mask)
        out[k] = stats
    seed_vs_naive = {
        "all": paired("seed", "naive", False),
        "new_manager_only": paired("seed", "naive", True),
    }

    report = {
        "league": LEAGUE, "train_season": seasons[0],
        "test_seasons": seasons[1:], "new_within": NEW,
        "n_test": len(test), "n_new": len(fresh),
        "arms": out,
        "seed_vs_naive": seed_vs_naive,
        "gain_overall": round(out["naive"]["log_loss"] - out["seed"]["log_loss"], 4),
        "gain_on_new": round(
            out["naive"]["log_loss_new"] - out["seed"]["log_loss_new"], 4),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"{'arm':<10}{'log-loss':>10}{'on new mgr':>13}{'accuracy':>11}")
    for k, v in out.items():
        print(f"{k:<10}{v['log_loss']:>10.4f}{v['log_loss_new']:>13.4f}"
              f"{v['accuracy'] * 100:>10.1f}%")
    print()
    print(f"seeding a new manager from the league mean instead of his "
          f"predecessor moves log-loss")
    print(f"  {report['gain_overall']:+.4f} overall, "
          f"{report['gain_on_new']:+.4f} on the fixtures it targets "
          f"(positive = better)")
    print()
    print("paired bootstrap, seed against naive on the same fixtures:")
    for name, d in seed_vs_naive.items():
        if "mean_gain" not in d:
            continue
        print(f"  {name:<18}n={d['n']:<4} gain {d['mean_gain']:+.4f}  "
              f"95% CI [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]  "
              f"P(better) {d['p_better']:.3f}")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
