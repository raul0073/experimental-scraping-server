# Wait for a running event scrape to finish, then fetch the next seasons.
#
# Two scrapers against the same site at once is impolite and risks a block,
# so this simply waits its turn. Detached and self-contained: launch it with
#   Start-Process powershell -ArgumentList '-File','scripts\chain_event_pilot.ps1' -WindowStyle Hidden
# and it survives whatever started it.

param(
    [string]$League = 'ENG-Premier League',
    [string[]]$Seasons = @('2627', '2324')
)

$repo = Split-Path $PSScriptRoot -Parent
$py   = Join-Path $repo '.venv\Scripts\python.exe'
$log  = Join-Path $repo 'data\reports\event_pilot.log'

function Test-ScrapeRunning {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        if ($p.CommandLine -and $p.CommandLine -like '*build_whoscored_events*') { return $true }
    }
    return $false
}

# wait for the current run (checked by command line, so it cannot be fooled
# by other python processes on the machine)
while (Test-ScrapeRunning) { Start-Sleep -Seconds 20 }
Start-Sleep -Seconds 15

Add-Content $log "============================================"
Add-Content $log "chained run started $(Get-Date -Format 'yyyy-MM-dd HH:mm') : $($Seasons -join ', ')"

$env:PYTHONIOENCODING = 'utf-8'
Set-Location $repo
& $py -u (Join-Path $repo 'scripts\build_whoscored_events.py') `
    --league $League --seasons $Seasons *>> $log

Add-Content $log "chained run finished $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
