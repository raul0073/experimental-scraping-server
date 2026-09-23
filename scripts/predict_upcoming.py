"""This week's fixtures: the shipped model, and the shipped model corrected.

The layered arm is NOT a different predictor. It is the same five stages —
FormModel, Dixon-Coles, the draw classifier, `unified_probs` — with one
correction applied to the lambda for what the team's history does not yet
know: which regulars are unavailable.

The correction is zero when nobody is missing, so most fixtures come out
identical and the table says so. Where it fires, the two columns show
exactly what the injury news is worth in goals and in probability.

Backtested on 25/26 the correction gained +0.0023 log-loss overall and
+0.0000 on fixtures where nothing had changed — the architecture behaving as
designed — but only **P(better) = 0.633** on the fixtures it touches. It is
not established, and this table is here to be read against results, not
traded on.

Usage: .venv/Scripts/python.exe scripts/predict_upcoming.py
"""
import argparse
import json
import math
import sys
from datetime import date as _date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

from compare_upcoming import align                             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTCOMES = ["H", "D", "A"]
# fitted on 24/25 by experiment_layered.py; w_stale came out at exactly 0.0,
# so the manager-staleness term is carried but contributes nothing
W_MISSING = -4.5
W_STALE = 0.0


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default="2627")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    lk = slug(args.league)

    params = json.loads((ROOT / "data" / "config" / "model_params.json")
                        .read_text(encoding="utf-8"))
    boosts = params["leagues"][args.league]
    rho = params["rho"]
    draw_model = DrawModel.load()
    fm = FormModel(args.league, ["2526", args.season])
    us = UnderstatService.load(args.league, args.season)

    inj_path = ROOT / "data" / "web" / "team" / lk / "injuries.json"
    inj = (json.loads(inj_path.read_text(encoding="utf-8"))
           if inj_path.exists() else {"teams": {}})

    fx = json.loads((ROOT / "data" / "fixtures" / args.league /
                     f"{args.season}.json").read_text(encoding="utf-8"))
    today = _date.today().isoformat()
    todo = [m for m in fx["matches"]
            if not m.get("played") and str(m.get("date") or "") >= today]
    todo.sort(key=lambda m: (str(m["date"]), str(m.get("time") or "")))
    todo = todo[:args.limit]
    if not todo:
        print("no unplayed fixtures ahead of today")
        return 1

    fx_names = {t for m in todo for t in (m["home_team"], m["away_team"])}
    to_us = align(fx_names, {t for mm in us["matches"]
                             for t in (mm["home_team"], mm["away_team"])})
    to_ws = align(fx_names, set(inj["teams"]))

    def missing_of(team: str):
        """Same shape as build_change_layers: rating above replacement,
        weighted by how much of the football he was playing, over eleven."""
        d = inj["teams"].get(team or "", {})
        v, who = 0.0, []
        for p in d.get("out", []):
            if p.get("rating") is None:
                continue
            share = min(1.0, (p.get("minutes") or 0) / 3420)
            w = 1.0 if p.get("status") == "Out" else 0.4
            v += max(0.0, p["rating"] - 50) / 50 * share / 11 * w
            if p.get("status") == "Out":
                who.append(f"{p['player']} {p['rating']:.0f}")
        return v, who

    print(f"{args.league} — next {len(todo)} fixtures")
    print(f"correction: lam *= exp({W_MISSING} * missing)   "
          f"(fitted on 24/25; not significant, P=0.633)\n")
    print(f"{'fixture':<32}{'model':<10}{'goals':>12}{'H':>5}{'D':>5}{'A':>5}")
    print("-" * 80)

    for m in todo:
        h, a = m["home_team"], m["away_team"]
        date = str(m["date"])[:10]
        uh, ua = to_us.get(h), to_us.get(a)
        if not uh or not ua:
            print(f"{h + ' v ' + a:<32}no Understat name match")
            continue
        ratings = fm.ratings_before(date)
        lam_h, lam_a, low = fm.lambdas(ratings, uh, ua,
                                       boosts["home_boost"], boosts["away_boost"])
        mh, who_h = missing_of(to_ws.get(h))
        ma, who_a = missing_of(to_ws.get(a))
        ch, ca = math.exp(W_MISSING * mh), math.exp(W_MISSING * ma)

        rows = []
        for label, lh, la in (("shipped", lam_h, lam_a),
                              ("layered", lam_h * ch, lam_a * ca)):
            p = outcome_probs(lh, la, rho)
            p_draw = None
            if draw_model and not low:
                roll = DrawModel.rolling_stats(fm.matches, date)
                if uh in roll and ua in roll:
                    ctx = DrawModel.season_context(us["matches"], date, uh, ua)
                    p_draw = draw_model.predict(DrawModel.fixture_features(
                        lh, la, rho, roll[uh], roll[ua], ctx))
            pr = unified_probs(p, p_draw)
            rows.append((label, lh, la, [pr["home"], pr["draw"], pr["away"]]))

        same = abs(rows[0][3][0] - rows[1][3][0]) < 0.005
        print(f"{h + ' v ' + a:<32}{rows[0][0]:<10}{rows[0][1]:5.2f}-"
              f"{rows[0][2]:<5.2f}{rows[0][3][0] * 100:5.0f}"
              f"{rows[0][3][1] * 100:5.0f}{rows[0][3][2] * 100:5.0f}")
        if same:
            print(f"{'':<32}{'layered':<10}  — nobody rated is missing, "
                  f"identical")
        else:
            print(f"{'':<32}{rows[1][0]:<10}{rows[1][1]:5.2f}-"
                  f"{rows[1][2]:<5.2f}{rows[1][3][0] * 100:5.0f}"
                  f"{rows[1][3][1] * 100:5.0f}{rows[1][3][2] * 100:5.0f}")
            for side, who, v in ((h, who_h, mh), (a, who_a, ma)):
                if who:
                    print(f"{'':<32}out for {side}: {', '.join(who[:3])}"
                          f"   (−{(1 - math.exp(W_MISSING * v)) * 100:.0f}% on goals)")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
