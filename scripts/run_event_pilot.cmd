@echo off
REM Overnight WhoScored event pilot: EPL 24/25 + 25/26.
REM Resumable — if it is interrupted, just run it again and it picks up where
REM it stopped. Already-fetched matches are never re-requested.
REM
REM Logs to data\reports\event_pilot.log (appends, so a resumed run keeps
REM the earlier history).

cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo ============================================ >> data\reports\event_pilot.log
echo run started %DATE% %TIME% >> data\reports\event_pilot.log

.venv\Scripts\python.exe scripts\build_whoscored_events.py ^
  --league "ENG-Premier League" --seasons 2425 2526 >> data\reports\event_pilot.log 2>&1

echo run finished %DATE% %TIME% >> data\reports\event_pilot.log
