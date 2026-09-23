"""The test run: the process Elo against the predictor we actually ship.

Both arms price the SAME Premier League fixtures of 25/26, and neither has
seen that season. The shipped model runs exactly as served — decayed xG
attack/defence into Dixon-Coles, then the draw classifier, then
`unified_probs`. The Elo runs off ratings that only ever saw earlier
matches, which is true by construction rather than by a filter.

Four arms:

  base      the league's own H/D/A frequencies from earlier seasons
  shipped   the live pipeline, untouched
  elo       the process Elo, fitted on 23/24 and 24/25 only
  blend     the two averaged, then renormalised

A blend is in because two models can both be right about different things,
and the cheapest way to find out is to ask. If the blend beats both, they
disagree usefully; if it lands between them, one is carrying the other.

Everything is compared PAIRED — the same match scored by both arms — and
the difference bootstrapped, because on 350 fixtures a gap of a few
thousandths is inside the noise and saying otherwise would be the third
false finding of the week.

Writes data/reports/experiment_elo_vs_shipped.json

Usage: .venv/Scripts/python.exe scripts/experiment_elo_vs_shipped.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from build_process_elo import CACHE, add_xg, outcome, walk    # noqa: E402
from experiment_predictor_stack_epl import align, shipped     # noqa: E402

LEAGUE = "ENG-Premier League"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "reports" / "experiment_elo_vs_shipped.json"
OUTCOMES = ["H", "D", "A"]
TEST = "2526"


def ll_of(p: np.ndarray, y: list) -> np.ndarray:
    ix = {o: i for i, o in enumerate(OUTCOMES)}
    return np.array([-math.log(max(p[i, ix[v]], 1e-9)) for i, v in enumerate(y)])


def paired(a: np.ndarray, b: np.ndarray, seed: int = 0) -> dict:
    """Is a really better than b? Resample the PAIRS, not the arms."""
    d = b - a
    rng = np.random.default_rng(seed)
    draws = np.array([rng.choice(d, size=len(d), replace=True).mean()
                      for _ in range(5000)])
    return {
        "mean_gain": round(float(d.mean()), 4),
        "p_better": round(float((draws > 0).mean()), 4),
        "ci95": [round(float(np.percentile(draws, 2.5)), 4),
                 round(float(np.percentile(draws, 97.5)), 4)],
    }


def main() -> int:
    params = json.loads(
        (ROOT / "data" / "web" / "team" / "eng-premier-league" / "elo.json")
        .read_text(encoding="utf-8"))["params"]

    print("running the Elo…", flush=True)
    df = pd.read_json(CACHE, dtype={"season": str})
    df["season"] = df["season"].astype(str)
    df = add_xg(df, LEAGUE)
    rows, _A, _D = walk(df, params["k"], params["home_adv"],
                        params["decay"], "xg")
    rows["date"] = [str(k)[:10] for k in rows["kick"]]
    elo = rows[rows["season"] == TEST]

    print("running the shipped pipeline…", flush=True)
    live = shipped(TEST, ["2425", TEST])
    us_names = {t for (_d, h, a) in live for t in (h, a)}
    name = align(us_names, set(df["home"]) | set(df["away"]))

    joined = []
    by_key = {(r.date, r.home, r.away): r for r in elo.itertuples(index=False)}
    for (date, h, a), got in live.items():
        r = by_key.get((date, name.get(h), name.get(a)))
        if r is None or got["low"]:
            continue
        lh = max(r.exp_hc * params["conv"], 1e-3)
        la = max(r.exp_ac * params["conv"], 1e-3)
        joined.append({
            "y": r.y,
            "ship": [got["p"]["home"], got["p"]["draw"], got["p"]["away"]],
            "elo": list(outcome(lh, la, params["rho"])),
        })
    if len(joined) < 100:
        print(f"only {len(joined)} fixtures matched — cannot judge")
        return 1

    y = [j["y"] for j in joined]
    ship = np.clip(np.array([j["ship"] for j in joined]), 1e-9, 1)
    eloP = np.clip(np.array([j["elo"] for j in joined]), 1e-9, 1)
    blend = (ship + eloP) / 2
    blend = blend / blend.sum(axis=1, keepdims=True)

    prior = df[df["season"] < TEST]["y"].value_counts(normalize=True)
    base = np.tile(np.array([prior.get(o, 1 / 3) for o in OUTCOMES]),
                   (len(y), 1))

    arms = {"base": base, "shipped": ship, "elo": eloP, "blend": blend}
    per = {k: ll_of(v, y) for k, v in arms.items()}
    acc = {k: float(np.mean([OUTCOMES[i] == t
                             for i, t in zip(v.argmax(axis=1), y)]))
           for k, v in arms.items()}

    print()
    print(f"TEST {TEST}, n={len(y)} fixtures priced by both")
    print(f"{'arm':<10}{'log-loss':>10}{'accuracy':>11}")
    for k in arms:
        print(f"{k:<10}{per[k].mean():>10.4f}{acc[k] * 100:>10.1f}%")

    tests = {
        "elo_vs_shipped": paired(per["elo"], per["shipped"]),
        "blend_vs_shipped": paired(per["blend"], per["shipped"]),
        "blend_vs_elo": paired(per["blend"], per["elo"]),
    }
    print()
    for k, d in tests.items():
        print(f"  {k:<18}gain {d['mean_gain']:+.4f}  "
              f"95% CI [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]  "
              f"P(better) {d['p_better']:.3f}")

    report = {
        "league": LEAGUE, "test_season": TEST, "n": len(y),
        "elo_params": params,
        "log_loss": {k: round(float(per[k].mean()), 4) for k in arms},
        "accuracy": {k: round(acc[k], 4) for k in arms},
        "paired": tests,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print()
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
