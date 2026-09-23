"""This weekend's fixtures, priced by both models side by side.

The shipped pipeline exactly as served — decayed xG attack/defence into a
Dixon-Coles grid, then the draw classifier, then `unified_probs` — against
the process Elo, which reaches a lambda pair from ratings that only ever saw
earlier matches.

Both are FAIR PRICES and nothing here is a bet. The point of putting them in
one table is that the head-to-head on last season came out level (1.0321
against 1.0326, P(better) 0.519) while a blend of the two beat both, which
means they disagree — and the only way to see what they disagree ABOUT is to
read the fixtures where they part company.

Usage: .venv/Scripts/python.exe scripts/compare_upcoming.py
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService

from build_process_elo import _tokens, outcome                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTCOMES = ["H", "D", "A"]


def align(src: set, dst: set) -> dict:
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
        hit = [b for b in dst if fits(ta, _tokens(b)) or fits(_tokens(b), ta)]
        if len(hit) == 1:
            out[a] = hit[0]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default="2627")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    lk = "".join(c if c.isalnum() else "-" for c in args.league.lower()).strip("-")

    elo = json.loads((ROOT / "data" / "web" / "team" / lk / "elo.json")
                     .read_text(encoding="utf-8"))
    P = elo["params"]
    R = {t["team"]: t for t in elo["table"]}

    inj_path = ROOT / "data" / "web" / "team" / lk / "injuries.json"
    inj = (json.loads(inj_path.read_text(encoding="utf-8"))["teams"]
           if inj_path.exists() else {})

    params = json.loads((ROOT / "data" / "config" / "model_params.json")
                        .read_text(encoding="utf-8"))
    boosts = params["leagues"][args.league]
    rho_ship = params["rho"]
    draw_model = DrawModel.load()
    fm = FormModel(args.league, ["2526", args.season])
    us = UnderstatService.load(args.league, args.season)

    # The fixture list comes from FixturesService, not from Understat:
    # Understat only ever stores matches that have been PLAYED, so asking it
    # for the next round returns nothing at all.
    from datetime import date as _date
    fx = json.loads((ROOT / "data" / "fixtures" / args.league /
                     f"{args.season}.json").read_text(encoding="utf-8"))
    today = _date.today().isoformat()
    todo = [m for m in fx["matches"]
            if not m.get("played") and str(m.get("date") or "") >= today]
    todo.sort(key=lambda m: (str(m["date"]), str(m.get("time") or "")))
    todo = todo[:args.limit]
    if not todo:
        print("no unplayed fixtures ahead of today — run the weekly refresh")
        return 1

    # fixture names are fbref's; both models want their own spelling
    fx_names = {t for m in todo for t in (m["home_team"], m["away_team"])}
    to_us = align(fx_names, {t for mm in us["matches"]
                             for t in (mm["home_team"], mm["away_team"])})

    names = align(fx_names, set(R))

    def lost(team: str) -> float:
        v = 0.0
        for p in inj.get(team, {}).get("out", []):
            if p.get("rating") is None:
                continue
            w = 1.0 if p.get("status") == "Out" else 0.4
            v += max(0.0, p["rating"] - 50) / 50 * 0.30 / 11 * w
        return v

    print(f"{args.league} — next {len(todo)} fixtures\n")
    print(f"{'fixture':<34}{'model':<9}{'goals':>12}"
          f"{'H':>6}{'D':>5}{'A':>5}   call")
    print("-" * 86)
    rows = []
    for m in todo:
        h, a = m["home_team"], m["away_team"]
        date = str(m["date"])[:10]
        uh, ua = to_us.get(h), to_us.get(a)
        if not uh or not ua:
            print(f"{h + ' v ' + a:<34}no Understat name match")
            continue

        # ---- shipped, exactly as served
        ratings = fm.ratings_before(date)
        lam_h, lam_a, low = fm.lambdas(ratings, uh, ua,
                                       boosts["home_boost"], boosts["away_boost"])
        p = outcome_probs(lam_h, lam_a, rho_ship)
        p_draw = None
        if draw_model and not low:
            roll = DrawModel.rolling_stats(fm.matches, date)
            if uh in roll and ua in roll:
                ctx = DrawModel.season_context(us["matches"], date, uh, ua)
                p_draw = draw_model.predict(DrawModel.fixture_features(
                    lam_h, lam_a, rho_ship, roll[uh], roll[ua], ctx))
        sp = unified_probs(p, p_draw)
        ship = [sp["home"], sp["draw"], sp["away"]]

        # ---- process Elo, with the absentees deducted
        eh, ea = names.get(h), names.get(a)
        if not eh or not ea or eh not in R or ea not in R:
            print(f"{h + ' v ' + a:<34}no Elo rating for one of these")
            continue
        lh = math.exp(R[eh]["attack"] - lost(eh) - R[ea]["defence"]
                      + P["home_adv"]) * P["conv"]
        la = math.exp(R[ea]["attack"] - lost(ea) - R[eh]["defence"]) * P["conv"]
        el = list(outcome(lh, la, P["rho"]))

        label = f"{h} v {a}"
        for name, pr, gh, ga in (("shipped", ship, lam_h, lam_a),
                                 ("elo", el, lh, la)):
            call = OUTCOMES[max(range(3), key=lambda i: pr[i])]
            call = {"H": h, "D": "draw", "A": a}[call]
            print(f"{label if name == 'shipped' else '':<34}{name:<9}"
                  f"{gh:5.2f}-{ga:<5.2f} {pr[0] * 100:5.0f}{pr[1] * 100:5.0f}"
                  f"{pr[2] * 100:5.0f}   {call}")
        gap = max(abs(ship[i] - el[i]) for i in range(3))
        out_h = len([x for x in inj.get(eh, {}).get('out', [])
                     if x.get('status') == 'Out'])
        out_a = len([x for x in inj.get(ea, {}).get('out', [])
                     if x.get('status') == 'Out'])
        extra = []
        if out_h or out_a:
            extra.append(f"out: {h} {out_h}, {a} {out_a}")
        if gap >= 0.08:
            extra.append(f"THEY DISAGREE by {gap * 100:.0f}pp")
        if extra:
            print(f"{'':<34}{' · '.join(extra)}")
        print()
        rows.append({"date": date, "home": h, "away": a,
                     "shipped": [round(x, 4) for x in ship],
                     "elo": [round(x, 4) for x in el],
                     "gap": round(gap, 4)})

    big = [r for r in rows if r["gap"] >= 0.08]
    print(f"{len(rows)} fixtures priced by both; "
          f"{len(big)} where they differ by 8 points or more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
