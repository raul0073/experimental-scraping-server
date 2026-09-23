"""Fetch WhoScored (Opta) event streams and store them per league-season.

Each match is ~1,431 events with player, position, outcome and minute — the
substrate the mental benchmark and player-built zones need. At a MEASURED
~10.9s a match a full league-season is about seventy minutes and four
leagues is an overnight job, so it is built to be interrupted and resumed:

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

from services.scrape_log import banner, scrape

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "whoscored"
CURRENT_SEASON = "2627"
BATCH = 10           # matches per write — small so an interruption loses little
PAUSE_S = 3.0        # between batches, on top of the ~10.9s/match the fetch
                     # takes — 0.3s/match amortised, so plan from the 10.9


SCHED_DIR = OUT_DIR / "_schedules"


def out_path(league: str, season: str) -> Path:
    return OUT_DIR / league.replace("/", "-") / f"{season}.parquet"


def schedule_for(ws, league: str, season: str) -> pd.DataFrame:
    """The fixture list, fetched at most once per league-season per day.

    🐛 THIS WAS THE DOMINANT COST OF A DAILY RUN. read_schedule() fetches
    roughly ten month pages before a single match is requested, and the
    measured England run spent 251s to collect TEN matches — 25s each
    against a 10.9s baseline — because that fixed cost is paid up front
    every time. Across five leagues it is ten minutes a morning re-reading
    fixture lists that change a handful of times a season.

    A day is the right granularity: postponements and TV moves happen, so
    caching forever would eventually fetch a match that is no longer
    scheduled or miss one that now is, but they never happen twice in the
    same morning. Only the two columns played_ids needs are stored, so a
    stale or corrupt cache costs one refetch and nothing else.
    """
    day = datetime.now().strftime("%Y%m%d")
    path = SCHED_DIR / f"{league.replace('/', '-')}_{season}_{day}.parquet"
    if path.exists():
        try:
            df = pd.read_parquet(path)
            scrape("schedule from cache", league=league, season=season,
                   fixtures=len(df), cached=day)
            return df
        except Exception:
            pass                       # unreadable cache is not a failure

    scrape("reading schedule", league=league, season=season,
           note="~10 month pages, once per day")
    sched = ws.read_schedule().reset_index()
    keep = [c for c in ("game_id", "date") if c in sched.columns]
    out = sched[keep] if keep else sched
    try:
        SCHED_DIR.mkdir(parents=True, exist_ok=True)
        out.to_parquet(path, index=False)
        # yesterday's copies are dead weight the moment today's is written
        for old in SCHED_DIR.glob(f"{league.replace('/', '-')}_{season}_*.parquet"):
            if old != path:
                old.unlink(missing_ok=True)
    except Exception:
        pass
    return out


def played_ids(schedule: pd.DataFrame, until: str | None = None) -> list:
    """Game ids for matches that have actually been played.

    🐛 THIS USED TO BE EVERY ID THE SCHEDULE RETURNED. For a finished season
    that is the same thing — all 380 happened — but for a season in progress
    it means asking WhoScored for every fixture still to come. On 26/27 in
    September that is ~380 requests a league to collect the ~50 matches that
    exist, and a daily run across five leagues would spend its morning
    fetching nothing, every morning.

    Kickoff plus three hours is the test, rather than a score column, because
    the schedule's shape varies by competition but `date` is always there.
    If it somehow is not, fall back to the old behaviour rather than fetching
    nothing at all — too much is a waste, none is a silent outage."""
    if "date" not in schedule.columns:
        return [int(g) for g in schedule["game_id"].dropna().unique()]
    when = pd.to_datetime(schedule["date"], errors="coerce", utc=True)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=3)
    # `until` lets a caller fetch a season in controlled chunks — "bring
    # La Liga up to the end of October" — instead of committing to the whole
    # thing in one unattended run.
    if until:
        asked = pd.Timestamp(until, tz="UTC") + pd.Timedelta(days=1)
        cutoff = min(cutoff, asked)
    done = schedule[when.notna() & (when <= cutoff)]
    return [int(g) for g in done["game_id"].dropna().unique()]


def write_events(df: pd.DataFrame, path: Path) -> None:
    """Write the frame, surviving columns WhoScored types inconsistently.

    🐛 THIS KILLED TWO SEASONS EVERY NIGHT FOR DAYS. Some events have no
    player — a team-level action, or simply a gap in the feed — and pandas
    reads that cell as NaN, a float, in a column otherwise full of strings.
    Arrow cannot type a mixed str/float column and raises:

        ArrowTypeError: Expected bytes, got a 'float' object
        Conversion failed for column player with type object

    The write happens after every batch, so the season kept exactly the
    matches fetched before the first offending batch and then aborted:
    Serie A 24/25 stopped dead on 100 of 380, Ligue 1 25/26 on 220 of 306,
    and re-running produced the identical crash at the identical point. It
    read as throttling because the counts never moved.

    Coercing the offending column to a nullable string makes the NaN an
    explicit missing value instead of a float. Done only on the retry so the
    common path stays untouched and cheap.

    🐛 THE FIRST VERSION OF THIS FIX CORRUPTED TWO SEASONS. It coerced EVERY
    object column, which is far more than the broken one. `is_goal` and
    `is_shot` hold booleans, so they became the strings 'True' and pd.NA —
    and `bool(pd.NA)` raises, which killed the stamping step and left Serie A
    and Ligue 1 unable to become READY with complete data on disk. Worse,
    `qualifiers` holds an ARRAY OF DICTS and became a string repr of one, so
    every structured read of it (own goals, set pieces, pass length) was
    silently reduced to substring matching.

    Only genuine TEXT columns are coerced now. A column whose non-null values
    are strings is the one that can hold a stray NaN; a column of flags or
    arrays is not, and converting it destroys information that cannot be
    recovered without re-reading the source.
    """
    try:
        df.to_parquet(path, index=False)
        return
    except Exception as e:                                   # noqa: BLE001
        fixed = df.copy()
        touched = []
        for c in df.columns:
            if df[c].dtype != object:
                continue
            nn = df[c].dropna()
            if nn.empty:
                continue
            # A 1,000-row sample, not the whole column: this is the retry path
            # on a half-million-row frame, and a column that is text for its
            # first thousand non-null values is text.
            if all(isinstance(v, str) for v in nn.head(1000)):
                # 🐛 THIS USED TO BE astype("string"), WHICH BROKE A THIRD
                # SCRIPT. The nullable string dtype spells missing as pd.NA,
                # and .tolist() then hands pd.NA to code written for object
                # columns: services/mental/plots.py tests `a is None`, which
                # is False for pd.NA, so it falls through to `a == b` and
                # raises "boolean value of NA is ambiguous". Two leagues lost
                # their pass networks to that.
                #
                # Mapping to None instead keeps the column as OBJECT holding
                # str and None — byte-identical in shape to every season that
                # never hit this path. Arrow writes it as string-with-nulls
                # either way, so the fix costs nothing and no consumer
                # anywhere has to learn about a second spelling of missing.
                fixed[c] = df[c].map(lambda v: v if isinstance(v, str) else None)
                touched.append(c)
        print(f"WARN parquet write failed ({type(e).__name__}); coerced "
              f"{len(touched)} TEXT column(s) to string and retried: "
              f"{', '.join(touched) or 'none'}", flush=True)
        fixed.to_parquet(path, index=False)


def load_existing(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as e:                                  # corrupt part-file
        print(f"WARN could not read {path.name}: {e} — starting fresh")
        return None


def build(league: str, season: str, until: str | None = None) -> dict:
    path = out_path(league, season)
    path.parent.mkdir(parents=True, exist_ok=True)

    ws = sd.WhoScored(leagues=league, seasons=season)
    schedule = schedule_for(ws, league, season)
    all_ids = played_ids(schedule, until)

    done = load_existing(path)
    have = set(done["game_id"].unique().tolist()) if done is not None else set()
    todo = [g for g in all_ids if g not in have]

    print(f"\n=== {league} {season}: {len(all_ids)} played, "
          f"{len(have)} already stored, {len(todo)} to fetch", flush=True)
    if not todo:
        return {"league": league, "season": season, "fetched": 0,
                "stored": len(have), "failed": 0}

    frames = [done] if done is not None else []
    fetched = failed = 0
    t0 = time.time()

    for i in range(0, len(todo), BATCH):
        chunk = todo[i: i + BATCH]
        scrape("fetching events", league=league, season=season,
               batch=f"{i // BATCH + 1}/{(len(todo) + BATCH - 1) // BATCH}",
               matches=len(chunk), ids=",".join(str(c) for c in chunk[:4])
               + ("..." if len(chunk) > 4 else ""))
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
        write_events(pd.concat(frames, ignore_index=True), path)

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
    # 🐛 THE DEFAULT USED TO BE ["2425", "2526"], WHICH MADE THE DAILY RUN A
    # BACKFILL. run_daily calls this with --league only, so for any league
    # whose history is not on disk the "daily update" quietly began a
    # 2,744-match job. The default is now the season we are actually in;
    # fetching history is a deliberate act with an explicit --seasons.
    ap.add_argument("--seasons", nargs="+", default=[CURRENT_SEASON])
    ap.add_argument("--until", default=None,
                    help="only fetch matches played on or before "
                         "this date (YYYY-MM-DD), for controlled chunks")
    args = ap.parse_args()

    banner(f"events · {args.league} · seasons {' '.join(args.seasons)}"
           + (f" · until {args.until}" if args.until else ""))
    results = []
    for season in args.seasons:
        try:
            results.append(build(args.league, season, args.until))
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
