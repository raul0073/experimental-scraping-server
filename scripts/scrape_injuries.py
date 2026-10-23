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
import os
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

# WhoScored IS SCRAPED THROUGH A REAL BROWSER, AND soccerdata SHOWS IT.
#
# sd.WhoScored(..., headless=False) is the library default, so every events
# and injuries step opened a visible Chrome window and drove it. On a daily
# run that is ~50 match pages across five leagues, each popping a window on
# top of whatever the user is doing — which is exactly how this was
# reported: "i cant have u opening chrome windows while i work".
#
# Headless is the right default for an unattended job. It is an env var
# rather than a constant because WhoScored does fingerprint browsers and may
# start refusing headless sessions; WS_HEADLESS=0 restores the visible
# browser without a code change if that day comes.
WS_HEADLESS = os.environ.get("WS_HEADLESS", "1") not in ("0", "false", "False")

LEAGUES = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga",
           "GER-Bundesliga", "FRA-Ligue 1"]
# TWO DAYS, BECAUSE THAT IS WHEN THE PAGE EXISTS.
#
# 🐛 THIS WAS 7, AND ABOUT 60% OF EVERY PREVIEW REQUEST WAS A 404.
# The old reasoning was about meaningfulness — "an absentee named ten days
# out is a rumour" — which is true and is not the binding constraint.
# WhoScored does not PUBLISH a preview until roughly two days before
# kickoff; ask earlier and it serves a 676-byte "page you requested does not
# exist". Measured over the cached responses:
#
#     days ahead   0    1    2    3    4
#     result      real real real 404  404
#
# When every fixture in the window is 3+ days out, nothing comes back,
# soccerdata hands back its degenerate empty frame, and the run looks like a
# parser crash while quietly keeping a stale file. That is how four leagues
# carried a twenty-day-old absentee list while every step reported ok.
#
# A daily run with a 2-day window still covers every fixture: a match enters
# the window two days before kickoff and is refreshed each morning until it
# is played. Nothing is missed and roughly three in five requests are no
# longer thrown away.
DAYS = 2


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
    ws = sd.WhoScored(leagues=league, seasons=season,
                      headless=WS_HEADLESS)
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
    #
    # 🐛 "NO ABSENTEES" USED TO LOOK LIKE A CRASH, AND LEFT STALE DATA UP.
    # soccerdata returns a DEGENERATE frame when a preview names nobody:
    #
    #     if len(match_sheets) == 0:
    #         return pd.DataFrame(index=["league","season","game","team","player"])
    #
    # — those five strings become index VALUES, not names, so reset_index()
    # yields one `index` column and no game_id at all. The loop below then
    # raised "'Pandas' object has no attribute 'game_id'", the step logged a
    # WARN, and because the warning is non-fatal the PREVIOUS file stayed on
    # disk. build_injury_web then rebuilt from it and reported ok, so a
    # twenty-day-old absentee list was published as current for four leagues
    # while the summary said every step passed.
    #
    # An empty preview is a real and common answer — WhoScored does not fill
    # the absentee list until close to kickoff — so it is reported as the
    # fact it is, and the stale file is left ALONE rather than overwritten
    # with nothing.
    rows = df.reset_index()
    if "game_id" not in rows.columns:
        print(f"  {league}: previews carry no absentees yet "
              f"({len(ids)} fixtures asked) — keeping what is on disk")
        return {"league": league, "fixtures": len(ids), "missing": 0,
                "empty_preview": True}
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
