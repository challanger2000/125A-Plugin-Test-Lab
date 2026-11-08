#requires -Version 5.1
[CmdletBinding()]param([string]$Package,[string]$Raw,[string]$Evidence)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$env:CI='true'
# Use the actual Windows cmd/BAT entry, not a mocked summary function.
$bat=(Resolve-Path (Join-Path $Package 'P186-EXISTING-RUN.bat')).Path
function Invoke-P186Bat([string]$Arguments) {
  & cmd.exe /d /s /c ('""'+$bat+'" '+$Arguments+'"') | Out-Host
  return [int]$LASTEXITCODE
}
$rc=Invoke-P186Bat '-CheckOnly';if($rc -ne 0){throw 'P186 actual BAT CheckOnly failed'}
$rc=Invoke-P186Bat '-Cancel';if($rc -ne 2){throw 'P186 cancel lost errorlevel'}
$beforeCapture=(Get-FileHash (Join-Path $Raw 'capture.json')).Hash
$beforeAsio=(Get-FileHash (Join-Path $Raw 'asio.json')).Hash
$rc=Invoke-P186Bat ('-ExistingRun "'+(Resolve-Path $Raw).Path+'"')
if($rc -ne 3){throw 'Diagnostic BAT reported success'}
$r=@(Get-ChildItem $Package -Recurse -File -Filter P186-ACCEPTANCE.json | ForEach-Object {Get-Content $_.FullName -Raw | ConvertFrom-Json})
if($r.Count -ne 1 -or $r[0].error_code -cne 'ETW_DECODE_ERRORS' -or $r[0].physical_asio -cne 'REFERENCE_OBSERVED_BUT_ETW_INCONCLUSIVE' -or $r[0].diagnostic_summary.capture.decode_errors -ne 1 -or $r[0].callbacks -ne 100 -or $r[0].release_approved){throw 'Actual BAT did not preserve precise decoder/attempt evidence'}
if((Get-FileHash (Join-Path $Raw 'capture.json')).Hash -cne $beforeCapture -or (Get-FileHash (Join-Path $Raw 'asio.json')).Hash -cne $beforeAsio){throw 'Reanalysis changed original files'}
# No new physical test executables or launcher in the user-facing root.
if(@(Get-ChildItem $Package -File -Filter '*.exe').Count -or (Test-Path (Join-Path $Package 'P185-ETW-ASIO.bat'))){throw 'Offline package exposes a new hardware run'}
# Tamper the real dependency. Integrity failure must happen before source reads.
Add-Content -LiteralPath (Join-Path $Package 'P185-DIAGNOSTICS.ps1') '# intentional integrity mutation'
$rc=Invoke-P186Bat '-CheckOnly';if($rc -ne 3){throw 'P186 actual tamper accepted'}
New-Item -ItemType Directory -Force $Evidence | Out-Null
@{actual_bat='PASS';check_only='PASS';cancel_exit=2;inconclusive_exit=3;decoded_error=1;original_files_unchanged=$true;tamper='REJECTED';new_hardware_test='NOT_RUN';release_approved=$false} | ConvertTo-Json | Set-Content (Join-Path $Evidence 'P186-PACKAGE-TESTS.json')
exit 0 # Clear expected negative exits only after checking them.
