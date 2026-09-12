"""Build per-match lineup rosters (slots + minutes) for every league.

Follows the shot-events build: reads the same cached match JSONs, so already
stored matches cost no network. Usage:
    .venv/Scripts/python scripts/build_rosters.py [--season 2627]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.understat.rosters_service import RostersService


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2627")
    ap.add_argument("--sleep", type=float, default=0.3,
                    help="pause between matches (use ~0.05 for cache-only backfills)")
    args = ap.parse_args()
    for league in LEAGUE_NAME_MAP:
        try:
            r = RostersService(league, args.season).build(sleep_s=args.sleep)
            print(f"OK   {league}: {r['stored_total']} stored (+{r['fetched_now']}, {r['errors']} errors)",
                  flush=True)
        except Exception as e:
            print(f"WARN {league}: {e}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
