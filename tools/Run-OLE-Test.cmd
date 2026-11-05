@echo off
setlocal
title 125A Plugin Test Lab - Interactive OLE Acceptance
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-Interactive-OLE.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo PASS - true native OLE receiver accepted four files.
) else (
  echo Test not passed. See results\...\RESULT.txt for details.
)
echo.
pause
exit /b %RC%
