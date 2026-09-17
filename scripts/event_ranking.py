"""Player ranking from event data — built ONLY from metrics that repeat.

Every metric here cleared the persistence test for that position
(scripts/experiment_persistence_by_position.py). Anything that failed to
repeat is excluded by rule, however good it sounds: a rating built on a
number that cannot reproduce itself is decoration.

That means this is an INTENT AND COMPETING ranking, not yet a pressure one.
It answers "how much does he go at people, and does he keep the ball", per
position, against his own kind. It does not yet answer "does he change when
losing" — that measurement is still too noisy to publish (see the reports).

Scores are percentiles within position, so a centre-back is only ever
compared with centre-backs.

Usage:
    .venv/Scripts/python.exe scripts/event_ranking.py --season 2526
    .venv/Scripts/python.exe scripts/event_ranking.py --season 2526 --pos WIDE
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import scripts.experiment_persistence as E
from scripts.experiment_persistence_by_position import position_map

ROOT = Path(__file__).resolve().parent.parent

# metric -> (weight, higher_is_better). Only metrics with cross-season
# persistence >= 0.6 FOR THAT POSITION are allowed in.
RECIPES = {
    "WIDE": {"takeon_90": (35, True), "duel_90": (25, True),
             "pass_pct": (20, True), "dispossessed_90": (20, False)},
    "AM":   {"takeon_90": (30, True), "duel_90": (25, True),
             "pass_pct": (30, True), "recovery_90": (15, True)},
    "ST":   {"takeon_90": (25, True), "duel_90": (30, True),
             "aerial_pct": (25, True), "dispossessed_90": (20, False)},
    "CM":   {"duel_90": (30, True), "pass_pct": (25, True),
             "recovery_90": (25, True), "pass_90": (20, True)},
    "FB":   {"duel_90": (30, True), "takeon_90": (20, True),
             "pass_pct": (25, True), "recovery_90": (25, True)},
    "CB":   {"duel_90": (30, True), "recovery_90": (25, True),
             "pass_pct": (20, True), "foul_90": (15, False),
             "aerial_pct": (10, True)},
}
LABEL = {
    "takeon_90": "runs at his man", "duel_90": "duels",
    "pass_pct": "keeps it", "dispossessed_90": "loses it",
    "recovery_90": "wins it back", "aerial_pct": "aerials",
    "pass_90": "on the ball", "foul_90": "fouls",
}
GROUP_NAME = {"WIDE": "Wide attackers", "AM": "Attacking midfield",
              "ST": "Strikers", "CM": "Central midfield",
              "FB": "Full-backs", "CB": "Centre-backs"}


def build(league: str, season: str, min_minutes: int = 900) -> pd.DataFrame:
    E.MIN_MINUTES = min_minutes
    path = ROOT / "data" / "whoscored" / league / f"{season}_stamped.parquet"
    t = E.season_table(path)
    t["grp"] = t.index.map(position_map(league, season))
    out = []
    for grp, recipe in RECIPES.items():
        sub = t[t["grp"] == grp].copy()
        if len(sub) < 8:
            continue
        total = 0.0
        score = pd.Series(0.0, index=sub.index)
        for metric, (weight, higher) in recipe.items():
            if metric not in sub.columns:
                continue
            # percentile within position; ties averaged, missing left out
            pct = sub[metric].rank(pct=True, na_option="keep") * 100
            if not higher:
                pct = 100 - pct
            score = score.add(pct.fillna(50) * weight, fill_value=0)
            total += weight
            sub[f"p_{metric}"] = pct.round(0)
        sub["score"] = (score / total).round(1)
        out.append(sub)
    return pd.concat(out) if out else pd.DataFrame()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default="2526")
    ap.add_argument("--pos", default=None, help="WIDE / AM / ST / CM / FB / CB")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--min-minutes", type=int, default=900)
    args = ap.parse_args()

    df = build(args.league, args.season, args.min_minutes)
    if df.empty:
        print("no data — has the season been stamped?")
        return 1

    groups = [args.pos] if args.pos else list(RECIPES)
    for grp in groups:
        sub = df[df["grp"] == grp].sort_values("score", ascending=False)
        if sub.empty:
            continue
        recipe = RECIPES[grp]
        cols = list(recipe)
        print(f"\n{GROUP_NAME.get(grp, grp)} — {args.season[:2]}/{args.season[2:]}"
              f"  ({len(sub)} players, {args.min_minutes}+ min)")
        head = f"{'#':<3}{'player':<24}{'score':>6}  " + "".join(
            f"{LABEL.get(c, c):>17}" for c in cols)
        print(head)
        print("-" * len(head))
        for i, (name, r) in enumerate(sub.head(args.top).iterrows(), 1):
            cells = ""
            for c in cols:
                raw = r.get(c)
                pct = r.get(f"p_{c}")
                cells += f"{'' if pd.isna(raw) else f'{raw:.2f}'} ({'' if pd.isna(pct) else int(pct)}){'':>3}".rjust(17)
            print(f"{i:<3}{name:<24}{r['score']:>6.1f}  {cells}")

    out = ROOT / "data" / "reports" / f"event_ranking_{args.season}.json"
    keep = ["grp", "score", "minutes"] + [c for c in df.columns if c.startswith("p_")]
    out.write_text(df[keep].reset_index().to_json(orient="records", indent=1),
                   encoding="utf-8")
    print(f"\n-> {out}")
    print("Numbers are the raw per-90 (or %) with the player's percentile "
          "WITHIN HIS POSITION in brackets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
