@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0P186-REANALYZE.ps1" %*
set "P186_EXIT=%ERRORLEVEL%"
if not defined CI pause
exit /b %P186_EXIT%
