"""Fetch WhoScored (Opta) event streams and store them per league-season.

Each match is ~1,431 events with player, position, outcome and minute — the
substrate the mental benchmark and player-built zones need. At ~29s a match
this is an overnight job, so it is built to be interrupted and resumed:

  * already-stored matches are skipped, so re-running costs nothing
  * events are written after EVERY batch, never only at the end
  * a failed batch is logged and skipped, not fatal
  * soccerdata caches each match, so even a lost batch re-reads from disk

Politeness: small batches with a pause between them, run off-peak. We fetch
each match exactly once and never re-request it.

Storage: data/whoscored/{league}/{season}.parquet — gitignored (hundreds of
MB). Published output is always DERIVED metrics, never this raw stream.

Usage:
    .venv/Scripts/python.exe scripts/build_whoscored_events.py \
        --league "ENG-Premier League" --seasons 2425 2526
"""
import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import soccerdata as sd

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "whoscored"
BATCH = 10           # matches per write — small so an interruption loses little
PAUSE_S = 3.0        # between batches, on top of the ~29s/match the fetch takes


def out_path(league: str, season: str) -> Path:
    return OUT_DIR / league.replace("/", "-") / f"{season}.parquet"


def load_existing(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as e:                                  # corrupt part-file
        print(f"WARN could not read {path.name}: {e} — starting fresh")
        return None


def build(league: str, season: str) -> dict:
    path = out_path(league, season)
    path.parent.mkdir(parents=True, exist_ok=True)

    ws = sd.WhoScored(leagues=league, seasons=season)
    schedule = ws.read_schedule()
    all_ids = [int(g) for g in schedule["game_id"].dropna().unique()]

    done = load_existing(path)
    have = set(done["game_id"].unique().tolist()) if done is not None else set()
    todo = [g for g in all_ids if g not in have]

    print(f"\n=== {league} {season}: {len(all_ids)} matches, "
          f"{len(have)} already stored, {len(todo)} to fetch", flush=True)
    if not todo:
        return {"league": league, "season": season, "fetched": 0,
                "stored": len(have), "failed": 0}

    frames = [done] if done is not None else []
    fetched = failed = 0
    t0 = time.time()

    for i in range(0, len(todo), BATCH):
        chunk = todo[i: i + BATCH]
        try:
            ev = ws.read_events(match_id=chunk)
        except Exception as e:
            failed += len(chunk)
            print(f"WARN batch {i // BATCH + 1} failed ({len(chunk)} matches): "
                  f"{type(e).__name__}: {str(e)[:120]}", flush=True)
            continue

        frames.append(ev.reset_index())
        fetched += len(chunk)
        # write after every batch: an overnight job must never lose hours
        pd.concat(frames, ignore_index=True).to_parquet(path, index=False)

        elapsed = time.time() - t0
        rate = elapsed / max(fetched, 1)
        left = timedelta(seconds=int(rate * (len(todo) - fetched)))
        print(f"  {fetched}/{len(todo)} matches · {rate:.1f}s each · "
              f"ETA {left} · {path.stat().st_size / 1e6:.0f} MB", flush=True)
        time.sleep(PAUSE_S)

    final = pd.read_parquet(path)
    return {"league": league, "season": season, "fetched": fetched,
            "stored": int(final["game_id"].nunique()), "failed": failed,
            "events": len(final), "mb": round(path.stat().st_size / 1e6, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--seasons", nargs="+", default=["2425", "2526"])
    args = ap.parse_args()

    print(f"started {datetime.now():%Y-%m-%d %H:%M}", flush=True)
    results = []
    for season in args.seasons:
        try:
            results.append(build(args.league, season))
        except Exception as e:
            print(f"FAIL {args.league} {season}: {type(e).__name__}: {e}", flush=True)

    print(f"\nfinished {datetime.now():%Y-%m-%d %H:%M}")
    for r in results:
        print(f"  {r['league']} {r['season']}: {r.get('stored')} matches, "
              f"{r.get('events', '?')} events, {r.get('mb', '?')} MB"
              f"{f' — {r['failed']} FAILED' if r.get('failed') else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
