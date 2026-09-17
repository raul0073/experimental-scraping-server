# Development launcher: FastAPI server + Next.js client, side by side.
#
#   scripts\dev.ps1            both, each in its own window (logs visible)
#   scripts\dev.ps1 -Server    only the Python app  (127.0.0.1:8080)
#   scripts\dev.ps1 -Client    only the web client  (localhost:3000)
#   scripts\dev.ps1 -Quiet     both hidden, logging to data\reports\
#   scripts\dev.ps1 -Stop      stop whatever is on those ports and exit
#
# NOTE: always launch Python through .venv\Scripts\python.exe. The `py`
# launcher ignores an activated virtualenv, which is why `py main.py` fails
# with ModuleNotFoundError even when the venv looks active.

[CmdletBinding()]
param(
    [switch]$Server,
    [switch]$Client,
    [switch]$Quiet,
    [switch]$Stop,
    [switch]$NoBrowser
)

$repo = Split-Path $PSScriptRoot -Parent
$py   = Join-Path $repo '.venv\Scripts\python.exe'
$web  = Join-Path $repo 'web'
$logs = Join-Path $repo 'data\reports'
New-Item -ItemType Directory -Force $logs | Out-Null

$SERVER_PORT = 8080
$CLIENT_PORT = 3000

function Stop-Port([int]$port, [string]$label) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return $false }
    $conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        try { Stop-Process -Id $_ -Force -Confirm:$false } catch {}
    }
    Write-Host "  stopped $label on port $port" -ForegroundColor DarkYellow
    Start-Sleep -Milliseconds 600
    return $true
}

function Test-Port([int]$port) {
    [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Port([int]$port, [int]$seconds = 45) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

# --- stop mode -------------------------------------------------------------
if ($Stop) {
    Write-Host 'stopping...' -ForegroundColor Cyan
    $a = Stop-Port $SERVER_PORT 'server'
    $b = Stop-Port $CLIENT_PORT 'client'
    if (-not ($a -or $b)) { Write-Host '  nothing was running' -ForegroundColor DarkGray }
    return
}

$doServer = $Server -or -not ($Server -or $Client)
$doClient = $Client -or -not ($Server -or $Client)

if (-not (Test-Path $py)) {
    Write-Host "venv python not found at $py" -ForegroundColor Red
    Write-Host '  create it:  py -m venv .venv'
    Write-Host '  then:       .venv\Scripts\python.exe -m pip install -r requirements.txt'
    return
}

Write-Host ''
Write-Host 'Predictorous dev' -ForegroundColor Cyan

# --- server ----------------------------------------------------------------
if ($doServer) {
    if (Test-Port $SERVER_PORT) {
        Write-Host '  server   already running' -ForegroundColor DarkGray
    }
    else {
        $uviArgs = @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1',
                     '--port', "$SERVER_PORT", '--reload')
        if ($Quiet) {
            $env:PYTHONIOENCODING = 'utf-8'
            Start-Process -FilePath $py -ArgumentList $uviArgs -WorkingDirectory $repo `
                -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $logs 'server.out.log') `
                -RedirectStandardError  (Join-Path $logs 'server.err.log')
        }
        else {
            # own window so uvicorn's reload log stays readable
            $inner = '$host.UI.RawUI.WindowTitle = "Predictorous server"; '
            $inner += '$env:PYTHONIOENCODING = "utf-8"; '
            $inner += 'Set-Location "' + $repo + '"; '
            $inner += '& "' + $py + '" ' + ($uviArgs -join ' ')
            Start-Process -FilePath 'powershell.exe' `
                -ArgumentList '-NoExit', '-NoProfile', '-Command', $inner
        }
        if (Wait-Port $SERVER_PORT) {
            Write-Host "  server   http://127.0.0.1:$SERVER_PORT/dashboard" -ForegroundColor Green
        }
        else {
            Write-Host "  server   did not start - see $logs\server.err.log" -ForegroundColor Red
        }
    }
}

# --- client ----------------------------------------------------------------
if ($doClient) {
    if (Test-Port $CLIENT_PORT) {
        Write-Host '  client   already running' -ForegroundColor DarkGray
    }
    elseif (-not (Test-Path (Join-Path $web 'node_modules'))) {
        Write-Host '  client   node_modules missing - run:  cd web ; pnpm install' -ForegroundColor Red
    }
    else {
        if ($Quiet) {
            Start-Process -FilePath 'pnpm.cmd' -ArgumentList 'dev' -WorkingDirectory $web `
                -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $logs 'client.out.log') `
                -RedirectStandardError  (Join-Path $logs 'client.err.log')
        }
        else {
            $inner = '$host.UI.RawUI.WindowTitle = "Predictorous client"; '
            $inner += 'Set-Location "' + $web + '"; '
            $inner += 'pnpm dev'
            Start-Process -FilePath 'powershell.exe' `
                -ArgumentList '-NoExit', '-NoProfile', '-Command', $inner
        }
        if (Wait-Port $CLIENT_PORT) {
            Write-Host "  client   http://localhost:$CLIENT_PORT" -ForegroundColor Green
        }
        else {
            Write-Host '  client   did not start - try:  cd web ; pnpm dev' -ForegroundColor Red
        }
    }
}

if ($doClient -and -not $NoBrowser -and (Test-Port $CLIENT_PORT)) {
    Start-Process "http://localhost:$CLIENT_PORT"
}

Write-Host ''
Write-Host '  stop both:  dev.cmd -Stop' -ForegroundColor DarkGray
Write-Host ''
