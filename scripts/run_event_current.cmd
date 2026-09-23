@echo off
REM THE CURRENT SEASON, RUN BY HAND, WITH SOMEBODY WATCHING.
REM
REM Deliberately not scheduled and deliberately not in run_event_leagues.cmd.
REM Two reasons to keep a person in front of this one:
REM
REM 1. build_whoscored_events fetches every game_id read_schedule returns,
REM    and for a season in progress most of those fixtures have not been
REM    played. Across the four leagues that is ~1,190 requests to collect the
REM    ~184 matches that actually exist. Until all_ids is filtered to played
REM    fixtures, this pass is mostly asking for nothing.
REM
REM 2. It is the pass whose output the site needs most — the predictor
REM    publishes thirty fixtures a round and only the six English ones have a
REM    match page with anything on it — so it is worth seeing it work rather
REM    than reading about it afterwards.
REM
REM Output goes to the console as well as the log, so progress is visible.
REM Ctrl-C is safe: matches are written after every batch of ten and already
REM fetched matches are skipped on the next run.

cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo ============================================ >> data\reports\event_pilot.log
echo CURRENT-SEASON run started %DATE% %TIME% >> data\reports\event_pilot.log

for %%L in ("ESP-La Liga" "ITA-Serie A" "GER-Bundesliga" "FRA-Ligue 1") do (
  echo.
  echo === %%~L 2627
  echo --- %%~L 2627 >> data\reports\event_pilot.log
  REM %%L not %%~L — the tilde strips the quotes and splits "ESP-La Liga"
  REM into two arguments, which argparse rejects before anything is fetched.
  .venv\Scripts\python.exe scripts\build_whoscored_events.py ^
    --league %%L --seasons 2627
)

echo CURRENT-SEASON run finished %DATE% %TIME% >> data\reports\event_pilot.log
echo.
echo done - now rebuild the payloads:  .venv\Scripts\python.exe scripts\run_daily.py --no-scrape
