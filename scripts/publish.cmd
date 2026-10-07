@echo off
REM THE WHOLE THING, ONE CLICK: scrape, update, check, build, deploy, push.
REM
REM Double-click this. Everything after that is automatic, and it STOPS
REM rather than publishing something wrong — see scripts/publish.py for what
REM each gate refuses and why.
REM
REM There is also scripts\run_daily.cmd, which does only the first step. Use
REM that when you want the data refreshed without touching the live site.

setlocal
cd /d "%~dp0.."

echo.
echo   Predictorous — publish
echo   ----------------------
echo   update  -^>  check  -^>  build  -^>  deploy  -^>  push
echo   Every league with enough event history. Ctrl-C to stop.
echo.

".venv\Scripts\python.exe" -u "scripts\publish.py" %*
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
  echo   Published. https://predictorous.com
) else (
  echo   Stopped at exit %RC%. Read the stage above that failed — nothing
  echo   after it ran, so the live site is still serving the last good
  echo   publish rather than a half-finished one.
)
echo.
pause
endlocal
