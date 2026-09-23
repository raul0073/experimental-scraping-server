@echo off
REM THE BACKFILL: every event season the other four leagues are missing.
REM ESP / ITA / GER / FRA  x  23/24, 24/25, 25/26  (+ 26/27 as a safety net).
REM
REM WHAT IT IS FOR. The ratings table is built from the event stream —
REM build_team_web reads {season}_stamped.parquet — and its reliability gate
REM is a split-half correlation ACROSS team-seasons. One season gives n=20
REM and only 4 of 23 metrics survive; four seasons give n=60 and 20 of 23.
REM That is why La Liga rendered every cell as 50. Nothing else needs this:
REM the predictor, the projected tables and the track record all run off
REM Understat, which is complete for five leagues and thirteen seasons.
REM
REM ~4,116 matches at a measured 10.9s each = about 12h30m, which does not
REM fit a night. So this is scheduled NIGHTLY and capped at 7h30m: it runs
REM 01:00-08:30, stops well clear of the 09:00 daily, and picks up where it
REM left off the following night. Already-fetched matches are skipped, so a
REM resumed run costs nothing and a finished one is a fast no-op.
REM
REM NEWEST SEASON FIRST, ALL FOUR LEAGUES, THEN THE NEXT. An interruption
REM then leaves every league at the same depth rather than one league
REM complete and three untouched — two seasons across four leagues is a
REM usable rating; four seasons of one league and nothing else is not.
REM
REM 🐛 PASS %%L, NOT %%~L. The tilde strips the quotes, so "ESP-La Liga"
REM reaches argparse as `--league ESP-La` plus a stray `Liga` and the script
REM dies on "unrecognized arguments" before fetching anything. Every league
REM name with a space failed that way on 21 Sep — La Liga, Serie A, Ligue 1
REM — and GER-Bundesliga, the only one without a space, was the only one
REM that ran. Three quarters of the job vanished in under a second each
REM while the log looked busy. %%~L is still right in the echo lines.

cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo ============================================ >> data\reports\event_pilot.log
echo backfill run started %DATE% %TIME% >> data\reports\event_pilot.log

for %%S in (2627 2526 2425 2324) do (
  echo --- season %%S >> data\reports\event_pilot.log
  for %%L in ("ESP-La Liga" "ITA-Serie A" "GER-Bundesliga" "FRA-Ligue 1") do (
    echo --- %%~L %%S >> data\reports\event_pilot.log
    .venv\Scripts\python.exe scripts\build_whoscored_events.py ^
      --league %%L --seasons %%S >> data\reports\event_pilot.log 2>&1
  )
)

echo backfill run finished %DATE% %TIME% >> data\reports\event_pilot.log
