"""Backfill fbref per-player counting stats (misc/shooting/keeper) —
the tables that survived the Opta loss. Usage:
    .venv/Scripts/python scripts/build_fbref_players.py --seasons 2526 2627
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.player_stats_service import FbrefPlayerStatsService


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=["2627"])
    args = ap.parse_args()
    for season in args.seasons:
        for league in LEAGUE_NAME_MAP:
            try:
                r = FbrefPlayerStatsService(league, season).build()
                print(f"OK   {league} {season}: {r['players']} players", flush=True)
            except Exception as e:
                print(f"WARN {league} {season}: {e}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
