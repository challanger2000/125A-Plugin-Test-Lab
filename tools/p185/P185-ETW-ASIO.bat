@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0P185-RUN.ps1" %*
set "P185_EXIT=%ERRORLEVEL%"
if not defined CI pause
exit /b %P185_EXIT%
