"""Backfill Understat shot events (with lastAction) per league/season.

Incremental + resumable: already-stored matches are skipped, and Understat's
per-match JSON cache means interrupted runs lose nothing.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\build_shot_events.py --seasons 2526
    .venv\\Scripts\\python.exe scripts\\build_shot_events.py --leagues "ENG-Premier League" --limit 5
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.understat.shot_events_service import ShotEventsService


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="*", default=["2526"])
    ap.add_argument("--leagues", nargs="*", default=list(LEAGUE_NAME_MAP.keys()))
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=None, help="max matches to fetch per league-season (testing)")
    args = ap.parse_args()

    failures = []
    for league in args.leagues:
        for season in args.seasons:
            try:
                r = ShotEventsService(league, season).build(sleep_s=args.sleep, limit=args.limit)
                print(f"OK   {league} {season}: {r['stored_total']} matches stored "
                      f"({r['fetched_now']} new, {r['errors']} errors)", flush=True)
            except Exception as e:
                failures.append((league, season, str(e)))
                print(f"FAIL {league} {season}: {e}", flush=True)

    print(f"done, {len(failures)} failures", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
