@echo off
REM THE DAILY, BY HAND. Double-click this; everything after that is automatic.
REM
REM WHY THERE IS NO SCHEDULED TASK ANY MORE. There were three, and between
REM them they did the wrong thing every day for a fortnight:
REM
REM   01:00  predictorous-backfill  fetched event seasons for the four
REM          non-English leagues. That finished on 2026-09-23. It kept
REM          running nightly, WOKE THE MACHINE to do it, re-scanned data it
REM          already had, and was killed at its 7h30m cap. Deleted.
REM   09:00  predictorous-daily     run_daily --league "ENG-Premier League".
REM          The --league was a deliberate phased rollout from 09-21 —
REM          England only until the backfill landed. It landed on the 23rd
REM          and nobody took the restriction off, so Spain, Italy, Germany
REM          and France went thirteen days without an update while the live
REM          site showed all five. Disabled.
REM   09:00  PredictorWeekly        fired at the same minute as the daily,
REM          and run_daily ALREADY calls run_weekly twice internally. Four
REM          processes writing the same payload files at once. Disabled.
REM
REM NO --league HERE, DELIBERATELY. run_daily asks services/data_ready.py
REM which leagues have the event history to be built and does those. That is
REM the whole point of deriving it from disk: the set grows by itself and
REM cannot be left pinned to one league by a flag somebody forgot.
REM
REM The run prints every step as it happens and appends one line to
REM data/reports/daily.log when it finishes. The window stays open at the
REM end so a failure is readable rather than a window that vanished.

setlocal
cd /d "%~dp0.."

echo.
echo   Predictorous — daily update
echo   ---------------------------
echo   Every league with enough event history. Ctrl-C to stop.
echo.

".venv\Scripts\python.exe" -u "scripts\run_daily.py"
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
  echo   Done. Every step ok.
) else (
  echo   Finished with failures ^(exit %RC%^) — see the summary above,
  echo   or data\reports\daily.log for the one-line record.
)
echo.
echo   The site is NOT deployed by this. To publish:
echo       cd web ^&^& pnpm build ^&^& npx wrangler pages deploy out --project-name predictorous
echo.
pause
endlocal
