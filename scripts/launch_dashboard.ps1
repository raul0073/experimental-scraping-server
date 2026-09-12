# Football Predictor — desktop launcher.
# Double-click flow (via the Desktop shortcut, which runs this hidden):
#   1. start the FastAPI server on 127.0.0.1:8080 if it isn't already running
#   2. kick a FULL data refresh in the background — skipped when the last
#      successful run is under 6h old (the daily 09:00 task usually covers it)
#   3. open the dashboard in an Edge app window (its own window + taskbar
#      icon, no browser chrome) — falls back to the default browser
# Everything logs to data\reports\ (server.*.log, launch_refresh.log).

$ErrorActionPreference = 'SilentlyContinue'
$repo = Split-Path $PSScriptRoot -Parent
$py   = Join-Path $repo '.venv\Scripts\python.exe'
$logs = Join-Path $repo 'data\reports'
New-Item -ItemType Directory -Force $logs | Out-Null
$env:PYTHONIOENCODING = 'utf-8'

# --- 1) server ---
$up = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if (-not $up) {
    Start-Process -FilePath $py `
        -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8080' `
        -WorkingDirectory $repo -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs 'server.out.log') `
        -RedirectStandardError  (Join-Path $logs 'server.err.log')
}
$deadline = (Get-Date).AddSeconds(40)
while ((Get-Date) -lt $deadline) {
    if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { break }
    Start-Sleep -Milliseconds 500
}

# --- 2) background freshen ("update on mount", staleness-guarded) ---
Start-Process -FilePath $py `
    -ArgumentList (Join-Path $repo 'scripts\run_weekly.py'),'--if-stale-hours','6' `
    -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs 'launch_refresh.log') `
    -RedirectStandardError  (Join-Path $logs 'launch_refresh.err.log')

# --- 3) open the dashboard as an app window ---
$url = 'http://127.0.0.1:8080/dashboard'
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if ($edge) { Start-Process $edge "--app=$url" } else { Start-Process $url }
