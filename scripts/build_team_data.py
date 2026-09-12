"""Build team-stat aggregates (fbref, for+against, snapshot-archived) and
Understat per-match xG files for all leagues/seasons.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\build_team_data.py                      # everything, default seasons
    .venv\\Scripts\\python.exe scripts\\build_team_data.py --source understat   # one source only
    .venv\\Scripts\\python.exe scripts\\build_team_data.py --seasons 2627 --refresh
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP

DEFAULT_SEASONS = ["2425", "2526"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="*", default=DEFAULT_SEASONS)
    ap.add_argument("--leagues", nargs="*", default=list(LEAGUE_NAME_MAP.keys()))
    ap.add_argument("--source", choices=["fbref", "understat", "all"], default="all")
    ap.add_argument("--refresh", action="store_true", help="bypass fbref scrape cache")
    args = ap.parse_args()

    failures = []

    if args.source in ("understat", "all"):
        from services.understat.understat_service import UnderstatService
        for league in args.leagues:
            for season in args.seasons:
                try:
                    svc = UnderstatService(league, season)
                    try:
                        learned = svc.learn_name_map()
                    except RuntimeError:
                        learned = {}  # no fbref fixtures for this season — keep existing map
                    r = svc.build()
                    print(f"OK   understat {league} {season}: {r['match_count']} matches "
                          f"({len(learned)} name mappings learned)")
                except Exception as e:
                    failures.append(("understat", league, season, str(e)))
                    print(f"FAIL understat {league} {season}: {e}")

    if args.source in ("fbref", "all"):
        from services.fbref.team_stats.team_stats_service import TeamStatsService
        for league in args.leagues:
            for season in args.seasons:
                try:
                    r = TeamStatsService(league, season, refresh=args.refresh).build()
                    print(f"OK   team_stats {league} {season}: {r['team_count']} teams "
                          f"(snapshot {r['snapshot_date']})")
                except Exception as e:
                    failures.append(("team_stats", league, season, str(e)))
                    print(f"FAIL team_stats {league} {season}: {e}")

    print(f"\ndone, {len(failures)} failures")
    for f in failures:
        print("  FAIL:", f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
