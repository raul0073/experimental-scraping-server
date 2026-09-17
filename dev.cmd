@echo off
REM Double-click to start both the Python app (:8080) and the web client
REM (:3000). Pass -Stop to shut them down again:  dev.cmd -Stop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" %*
