@echo off
rem Monthly model upkeep: calibrate -> classifier -> frozen backtests -> zone
rem blend. Each stage ships only if its gate holds. Logs for the audit trail.
cd /d "C:\prog\projects\experimental\experimental-scraping-server"
".venv\Scripts\python.exe" "scripts\run_recal_chain.py" > "data\reports\recal_latest.log" 2> "data\reports\recal_latest.err.log"
