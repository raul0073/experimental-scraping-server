@echo off
rem Scheduled entry point: refresh data, grade everything, commit the new
rem window's picks + slip. Logs to data\reports\run_weekly_latest.log
cd /d "C:\prog\projects\experimental\experimental-scraping-server"
".venv\Scripts\python.exe" "scripts\run_weekly.py" > "data\reports\run_weekly_latest.log" 2> "data\reports\run_weekly_latest.err.log"
