@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Drag a trusted VST3 folder onto this file to run native Windows QA.
rem The runner never claims commercial DAW acceptance or release approval.
if "%~1"=="" goto :usage
if not exist "%~1\" (
  echo [FAIL] Provide a real .vst3 plugin bundle folder.
  exit /b 2
)
if /I not "%~x1"==".vst3" (
  echo [FAIL] The dropped folder must have the .vst3 extension.
  exit /b 2
)
set "LAB=%~dp0"
if not exist "%LAB%125A_Test_Lab_Host.exe" goto :missing
if not exist "%LAB%125A_Test_Lab_State_Stress.exe" goto :missing
if not exist "%LAB%125A_Test_Lab_GUI.exe" goto :missing
if not exist "%LAB%run_plugin_quickcheck.py" goto :missing
if not exist "%LAB%write_user_report.py" goto :missing
where py >nul 2>&1
if not errorlevel 1 (
  set "PYTHON=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [FAIL] Python 3 is required to run the native VST3 tests.
    exit /b 2
  )
  set "PYTHON=python"
)
%PYTHON% "%LAB%run_plugin_quickcheck.py" --plugin "%~1" --host "%LAB%125A_Test_Lab_Host.exe" --stress-host "%LAB%125A_Test_Lab_State_Stress.exe" --gui-host "%LAB%125A_Test_Lab_GUI.exe" --out "%LAB%RESULTS\%~n1"
set "CODE=%ERRORLEVEL%"
%PYTHON% "%LAB%write_user_report.py" --result "%LAB%RESULTS\%~n1\QUICKCHECK-RESULT.json" --out "%LAB%RESULTS\%~n1\TESTERGEBNIS.html"
if errorlevel 1 (
  echo [FAIL] Human-readable test report could not be created.
  exit /b 3
)
echo.
echo Testergebnis: "%LAB%RESULTS\%~n1\TESTERGEBNIS.html"
echo A technical PASS is not a complete product release approval.
if not defined CI (
  start "" "%LAB%RESULTS\%~n1\TESTERGEBNIS.html"
  pause
)
exit /b %CODE%
:missing
echo [FAIL] The complete portable Test Lab package is required.
exit /b 2
:usage
echo Drop a trusted Windows VST3 plugin bundle folder onto Run-VST3-Test.cmd.
echo No arguments: no test was performed.
exit /b 2
