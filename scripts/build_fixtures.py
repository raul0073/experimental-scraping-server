"""Build fixtures + results files for all leagues/seasons.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\build_fixtures.py            # all leagues, default seasons
    .venv\\Scripts\\python.exe scripts\\build_fixtures.py --refresh  # bypass scrape cache (mid-season update)
    .venv\\Scripts\\python.exe scripts\\build_fixtures.py --seasons 2627
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService

DEFAULT_SEASONS = ["2425", "2526", "2627"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="*", default=DEFAULT_SEASONS)
    ap.add_argument("--leagues", nargs="*", default=list(LEAGUE_NAME_MAP.keys()))
    ap.add_argument("--refresh", action="store_true", help="bypass scrape cache")
    args = ap.parse_args()

    results, failures = [], []
    for league in args.leagues:
        for season in args.seasons:
            try:
                r = FixturesService(league, season, refresh=args.refresh).build()
                results.append(r)
                print(f"OK   {league} {season}: {r['match_count']} matches, {r['played_count']} played")
            except Exception as e:
                failures.append((league, season, str(e)))
                print(f"FAIL {league} {season}: {e}")

    print(f"\n{len(results)} built, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
