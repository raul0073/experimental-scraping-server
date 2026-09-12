"""Measure the promoted-team profile: how do teams with NO prior-season data
actually perform (xG for/against per match vs league average)?

Feeds the promoted-prior constants in form_model — instead of pretending a
promoted side is a league-average team, give it the measured promoted
archetype until real matches accumulate.

Usage: .venv/Scripts/python scripts/measure_promoted_priors.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.understat.understat_service import UnderstatService

PAIRS = [("2324", "2425"), ("2425", "2526")]  # (prior season, season measured)


def main() -> int:
    ratios_att, ratios_def, names = [], [], []
    for prev, cur in PAIRS:
        for league in LEAGUE_NAME_MAP:
            dp = UnderstatService.load(league, prev)
            dc = UnderstatService.load(league, cur)
            if not dp or not dc:
                continue
            prev_teams = {m["home_team"] for m in dp["matches"]} | \
                         {m["away_team"] for m in dp["matches"]}
            stats: dict = {}
            pool = []
            for m in dc["matches"]:
                if m.get("home_xg") is None:
                    continue
                for pre, team in (("home", m["home_team"]), ("away", m["away_team"])):
                    opp = "away" if pre == "home" else "home"
                    s = stats.setdefault(team, {"xf": 0.0, "xa": 0.0, "n": 0})
                    s["xf"] += m[f"{pre}_xg"]
                    s["xa"] += m[f"{opp}_xg"]
                    s["n"] += 1
                    pool.append(m[f"{pre}_xg"])
            if not pool:
                continue
            mu = sum(pool) / len(pool)
            for team, s in stats.items():
                if team in prev_teams or s["n"] < 10:
                    continue
                ratios_att.append(s["xf"] / s["n"] / mu)
                ratios_def.append(s["xa"] / s["n"] / mu)
                names.append(f"{cur} {league.split('-')[1]}: {team} "
                             f"att {s['xf'] / s['n'] / mu:.2f} def {s['xa'] / s['n'] / mu:.2f}")
    for n in names:
        print(" ", n)
    n = len(ratios_att)
    if not n:
        print("no promoted teams found")
        return 1
    print(f"\npromoted teams: {n}")
    print(f"PROMOTED_ATT = {sum(ratios_att) / n:.3f}  (xG created vs league avg)")
    print(f"PROMOTED_DEF = {sum(ratios_def) / n:.3f}  (xG conceded vs league avg)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
