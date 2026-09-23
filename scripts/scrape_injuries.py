"""Injured and suspended players, for the fixtures about to be played.

WhoScored publishes a team sheet of absentees on each match's PREVIEW page,
before kickoff — `/Matches/{id}/Preview`. That makes it one of the very few
genuinely pre-match inputs available to us: unlike a lineup, it is knowable
on Thursday for a Saturday game, so a model may use it without cheating.

UPCOMING FIXTURES ONLY, which is what makes this a daily job rather than a
scrape. A preview is one page fetch, and there are about ten fixtures per
league per round — fifty pages a day across five leagues, against the ~5,700
it would take to backfill every match ever played. The backfill is a separate
decision; this is the part that pays for itself immediately.

Run it daily. An injury list changes right up to kickoff, so the value is in
re-reading it often, and each run overwrites what it finds for the fixtures
still ahead while leaving everything already played untouched.

Writes data/injuries/{league}/{season}.json:

    {"<game_id>": {"date": "...", "home": "...", "away": "...",
                   "fetched": "...",
                   "missing": [{"team", "player", "player_id",
                                "reason", "status"}]}}

Usage:
    .venv/Scripts/python.exe scripts/scrape_injuries.py
    .venv/Scripts/python.exe scripts/scrape_injuries.py --days 3 --league "ENG-Premier League"
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import soccerdata as sd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "injuries"

# keep in sync with services/predictions/prediction_service.py
SEASON = "2627"
LEAGUES = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga",
           "GER-Bundesliga", "FRA-Ligue 1"]
# A week ahead by default. Far enough to catch a midweek round, near enough
# that the list is meaningful — an absentee named ten days out is a rumour.
DAYS = 7


def path_for(league: str, season: str) -> Path:
    return OUT / league.replace("/", "-") / f"{season}.json"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def upcoming(schedule: pd.DataFrame, days: int) -> pd.DataFrame:
    """Fixtures from today to `days` ahead that have not been played.

    Unplayed is judged on the date rather than on a score column, because a
    schedule row for a future match may carry no score field at all."""
    s = schedule.reset_index()
    col = next((c for c in ("date", "game_date", "datetime") if c in s.columns), None)
    if col is None:
        return s.iloc[0:0]
    when = pd.to_datetime(s[col], errors="coerce", utc=True)
    now = pd.Timestamp.now(tz=timezone.utc).normalize()
    keep = (when >= now) & (when <= now + pd.Timedelta(days=days))
    out = s[keep].copy()
    # NO leading underscore: itertuples renames such columns to _1, _2 …
    out["kick_when"] = when[keep]
    return out.sort_values("kick_when")


def run(league: str, season: str, days: int) -> dict:
    ws = sd.WhoScored(leagues=league, seasons=season)
    try:
        schedule = ws.read_schedule(force_cache=False)
    except Exception as e:
        print(f"  {league}: could not read the schedule — {e}")
        return {"league": league, "fixtures": 0, "missing": 0, "error": str(e)}

    soon = upcoming(schedule, days)
    ids = [int(g) for g in soon["game_id"].dropna().unique()]
    if not ids:
        print(f"  {league}: nothing in the next {days} days")
        return {"league": league, "fixtures": 0, "missing": 0}

    try:
        df = ws.read_missing_players(match_id=ids)
    except Exception as e:
        print(f"  {league}: preview fetch failed — {e}")
        return {"league": league, "fixtures": len(ids), "missing": 0,
                "error": str(e)}

    # game_id -> the absentees named for it
    rows = df.reset_index()
    per: dict = {}
    for r in rows.itertuples(index=False):
        gid = str(int(getattr(r, "game_id")))
        per.setdefault(gid, []).append({
            "team": getattr(r, "team", None),
            "player": getattr(r, "player", None),
            "player_id": int(getattr(r, "player_id"))
            if pd.notna(getattr(r, "player_id", None)) else None,
            "reason": getattr(r, "reason", None),
            "status": getattr(r, "status", None),
        })

    path = path_for(league, season)
    store = load(path)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for row in soon.itertuples(index=False):
        gid = str(int(getattr(row, "game_id")))
        store[gid] = {
            "date": str(getattr(row, "kick_when"))[:10],
            "home": getattr(row, "home_team", None),
            "away": getattr(row, "away_team", None),
            "fetched": stamp,
            # An empty list is a RESULT, not a gap: it means the preview was
            # read and nobody was named. Storing it stops a later reader
            # confusing "nobody out" with "never looked".
            "missing": per.get(gid, []),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    named = sum(len(v) for v in per.values())
    print(f"  {league}: {len(ids)} fixtures, {named} players named out")
    return {"league": league, "fixtures": len(ids), "missing": named}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", action="append", dest="leagues",
                    help="repeatable; defaults to all five")
    ap.add_argument("--season", default=SEASON)
    ap.add_argument("--days", type=int, default=DAYS)
    args = ap.parse_args()

    leagues = args.leagues or LEAGUES
    print(f"injuries for the next {args.days} days, season {args.season}")
    out = [run(lg, args.season, args.days) for lg in leagues]
    print()
    print(f"-> {OUT}   "
          f"{sum(r['fixtures'] for r in out)} fixtures, "
          f"{sum(r['missing'] for r in out)} players named out")
    bad = [r for r in out if r.get("error")]
    # A failed league is reported but never fatal: the weekly run calls this
    # and one league's preview page being unreachable must not stop the rest.
    return 1 if len(bad) == len(out) else 0


if __name__ == "__main__":
    raise SystemExit(main())
