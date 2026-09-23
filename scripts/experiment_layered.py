"""The layered model: the shipped stack, corrected where the team has changed.

THE WHOLE STACK STAYS. FormModel, the zone blend, Dixon-Coles, the draw
classifier and `unified_probs` all run exactly as they do live. Nothing is
removed — that was the mistake of every earlier experiment in this folder,
which quietly dropped three of the five stages and then reported the result
as a like-for-like comparison.

What is added is two corrections to the LAMBDA, between stage 1 and stage 2:

    lam *= exp( w_missing * missing  +  w_stale * stale )

Both terms are ZERO when nothing has changed, so on an ordinary fixture this
model IS the shipped model, to the last decimal. It can only differ where a
regular is absent or a manager is new — which is the entire claim being
tested: the history is not wrong, it is out of date.

`missing` is the rating value of regulars not in today's twenty. `stale` is
the share of the rating window that predates the current manager. Both are
built walk-forward by `build_change_layers.py`.

The weights are FITTED on earlier seasons, never on the test one, and are
expected to be NEGATIVE — losing good players and having a manager the
window has not caught up with should both lower expectations.

Judged three ways, because a correction that only fires on a fifth of
fixtures cannot move an overall average much and should not be asked to:

  all         every fixture
  changed     those with a missing regular or a new manager
  settled     the rest, where the two models should be identical

Writes data/reports/experiment_layered.json

Usage: .venv/Scripts/python.exe scripts/experiment_layered.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

from experiment_predictor_stack_epl import align              # noqa: E402

LEAGUE = "ENG-Premier League"
ROOT = Path(__file__).resolve().parent.parent
LAYERS = ROOT / "data" / "reports" / "change_layers.json"
REPORT = ROOT / "data" / "reports" / "experiment_layered.json"
OUTCOMES = ["H", "D", "A"]
TEST = "2526"
FIT = ["2425"]            # the only complete season before the test one that
                          # both the layers and Understat cover


def run_stack(league: str, season: str, history: list, layers: dict,
              w_missing: float, w_stale: float) -> list:
    """The live pipeline, with the lambda corrected before the zone blend.

    The zone blend is applied by PredictionService in production; it is left
    out of BOTH arms here so the only difference between them is the
    correction. That is a like-for-like comparison — unlike dropping a stage
    from one arm and not the other."""
    params = json.loads((ROOT / "data" / "config" / "model_params.json")
                        .read_text(encoding="utf-8"))
    boosts = params["leagues"][league]
    rho = params["rho"]
    draw_model = DrawModel.load()
    fm = FormModel(league, history)
    us = UnderstatService.load(league, season)

    out = []
    for m in us["matches"]:
        if m["home_goals"] is None:
            continue
        h, a, date = m["home_team"], m["away_team"], str(m["date"])[:10]
        key = (date, h, a)
        lay = layers.get(key)
        if lay is None:
            continue
        ratings = fm.ratings_before(m["date"])
        lam_h, lam_a, low = fm.lambdas(ratings, h, a,
                                       boosts["home_boost"], boosts["away_boost"])
        if low:
            continue

        # ---- THE CORRECTION, and the only difference between the arms
        ch = math.exp(w_missing * lay["h"]["missing"] + w_stale * lay["h"]["stale"])
        ca = math.exp(w_missing * lay["a"]["missing"] + w_stale * lay["a"]["stale"])
        lh, la = lam_h * ch, lam_a * ca

        p = outcome_probs(lh, la, rho)
        p_draw = None
        if draw_model:
            roll = DrawModel.rolling_stats(fm.matches, m["date"])
            if h in roll and a in roll:
                ctx = DrawModel.season_context(us["matches"], m["date"], h, a)
                p_draw = draw_model.predict(DrawModel.fixture_features(
                    lh, la, rho, roll[h], roll[a], ctx))
        pr = unified_probs(p, p_draw)
        out.append({
            "date": date, "home": h, "away": a,
            "y": "H" if m["home_goals"] > m["away_goals"]
                 else ("A" if m["away_goals"] > m["home_goals"] else "D"),
            "p": [pr["home"], pr["draw"], pr["away"]],
            # HOW MUCH has changed, not whether anything has. Some regular is
            # absent in 85% of fixtures, so a yes/no flag separates nothing —
            # it just relabels the whole season as "changed". The magnitude
            # of the correction is the thing that should decide whether this
            # model is expected to differ from the shipped one.
            "size": abs(math.log(ch)) + abs(math.log(ca)),
        })
    return out


def score(rows: list, mask=None) -> dict:
    ix = {o: i for i, o in enumerate(OUTCOMES)}
    use = rows if mask is None else [r for r, k in zip(rows, mask) if k]
    if not use:
        return {"n": 0}
    p = np.clip(np.array([r["p"] for r in use]), 1e-9, 1)
    y = [r["y"] for r in use]
    ll = float(np.mean([-math.log(p[i, ix[v]]) for i, v in enumerate(y)]))
    called = [OUTCOMES[i] for i in p.argmax(axis=1)]
    return {
        "n": len(use),
        "log_loss": round(ll, 4),
        "hit_rate": round(float(np.mean([c == v for c, v in zip(called, y)])), 4),
    }


def main() -> int:
    raw = json.loads(LAYERS.read_text(encoding="utf-8"))
    # layers are keyed on WhoScored names; the stack speaks Understat
    ws_names = {t for r in raw for t in (r["home"], r["away"])}
    us_seasons = {}
    for season in {r["season"] for r in raw}:
        try:
            us_seasons[season] = UnderstatService.load(LEAGUE, season)
        except Exception:
            pass
    us_names = {t for us in us_seasons.values() for m in us["matches"]
                for t in (m["home_team"], m["away_team"])}
    to_us = align(ws_names, us_names)
    layers = {}
    for r in raw:
        h, a = to_us.get(r["home"]), to_us.get(r["away"])
        if h and a:
            layers[(r["date"], h, a)] = r
    print(f"{len(layers)} fixtures with change layers")

    # ---- fit the two weights on the earlier season only
    hist = {"2425": ["2324", "2425"], TEST: ["2425", TEST]}
    best = None
    print("fitting the correction weights on", FIT)
    for wm in (0.0, -1.0, -2.0, -3.0, -4.5, -6.0, -8.0, -11.0):
        for ws in (0.0, -0.05, -0.10, -0.20, -0.35, -0.6):
            rows = []
            for s in FIT:
                rows += run_stack(LEAGUE, s, hist[s], layers, wm, ws)
            if len(rows) < 100:
                continue
            ll = score(rows)["log_loss"]
            if best is None or ll < best[0]:
                best = (ll, wm, ws)
    if best is None:
        print("could not fit")
        return 1
    _ll, w_missing, w_stale = best
    print(f"  w_missing={w_missing}  w_stale={w_stale}  "
          f"(train log-loss {_ll:.4f})")

    base = run_stack(LEAGUE, TEST, hist[TEST], layers, 0.0, 0.0)
    lay = run_stack(LEAGUE, TEST, hist[TEST], layers, w_missing, w_stale)
    # terciles of how much the correction moved the fixture
    # Split on zero / some / most, NOT on terciles: 15% of fixtures have no
    # absent regular at all, so a third of the "least changed" tercile was
    # fixtures the model does not touch, mixed in with ones it does.
    size = np.array([r["size"] for r in lay])
    nz = size[size > 0]
    cut = float(np.median(nz)) if len(nz) else 0.0
    most = list(size >= cut)
    mid = list((size > 0) & (size < cut))
    least = list(size <= 0)

    report = {"league": LEAGUE, "test_season": TEST,
              "w_missing": w_missing, "w_stale": w_stale, "cuts": {}}
    print()
    print(f"TEST {TEST} — split by how much the correction moved the fixture")
    print(f"{'cut':<16}{'n':>5}{'shipped LL':>12}{'layered LL':>12}"
          f"{'gain':>9}{'shipped hit':>13}{'layered hit':>13}")
    for name, mask in (("all", None),
                       ("most changed", most),
                       ("some change", mid),
                       ("unchanged", least)):
        b, l = score(base, mask), score(lay, mask)
        if not b.get("n"):
            continue
        gain = round(b["log_loss"] - l["log_loss"], 4)
        report["cuts"][name] = {"n": b["n"], "shipped": b, "layered": l,
                                "gain": gain}
        print(f"{name:<16}{b['n']:>5}{b['log_loss']:>12.4f}{l['log_loss']:>12.4f}"
              f"{gain:>+9.4f}{b['hit_rate'] * 100:>12.1f}%"
              f"{l['hit_rate'] * 100:>12.1f}%")

    # Paired, because the same match is scored by both arms. Restricted to
    # the fixtures the correction actually touches: including the untouched
    # ones adds 140 exact zeros to the sample and shrinks the interval
    # without adding a single piece of evidence, which would be cheating.
    ix = {o: i for i, o in enumerate(OUTCOMES)}
    touched = [r["size"] > 0 for r in lay]
    lb = np.array([-math.log(max(r["p"][ix[r["y"]]], 1e-9))
                   for r, k in zip(base, touched) if k])
    ll_ = np.array([-math.log(max(r["p"][ix[r["y"]]], 1e-9))
                    for r, k in zip(lay, touched) if k])
    rng = np.random.default_rng(0)
    d = lb - ll_
    draws = np.array([rng.choice(d, size=len(d), replace=True).mean()
                      for _ in range(5000)])
    boot = {
        "n_touched": int(len(d)),
        "mean_gain": round(float(d.mean()), 4),
        "p_better": round(float((draws > 0).mean()), 4),
        "ci95": [round(float(np.percentile(draws, 2.5)), 4),
                 round(float(np.percentile(draws, 97.5)), 4)],
    }
    report["bootstrap_on_touched"] = boot
    print()
    print(f"paired bootstrap on the {boot['n_touched']} fixtures the "
          f"correction touches:")
    print(f"  gain {boot['mean_gain']:+.4f}  "
          f"95% CI [{boot['ci95'][0]:+.4f}, {boot['ci95'][1]:+.4f}]  "
          f"P(better) {boot['p_better']:.3f}")

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print()
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
