#requires -Version 5.1
[CmdletBinding()]param([string]$Build,[string]$Evidence)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../tools/p185/P185-ANALYZE.ps1')
$exe=(Get-ChildItem $Build -Recurse -File -Filter '125A_Test_Lab_ETW.exe').FullName
$hostExe=(Get-ChildItem $Build -Recurse -File -Filter '125A_Test_Lab_Physical_ASIO.exe').FullName
$reference=(Get-ChildItem $Build -Recurse -File -Filter '125A_QA_ASIO_Reference_MIDI.vst3').FullName
$broken=(Get-ChildItem $Build -Recurse -File -Filter '125A_QA_ASIO_Reference_MIDI_Broken.vst3').FullName
Assert-P185 ($exe -is [string] -and $hostExe -is [string] -and $reference -is [string] -and $broken -is [string]) 'EXACT_BINARY_INVENTORY'
New-Item -ItemType Directory -Force $Evidence | Out-Null
$nonce='0123456789abcdef0123456789abcdef0123456789abcdef'
foreach($mode in @('--sample-format-selftest','--buffer-choice-selftest','--timing-trace-selftest')){
  & $hostExe $mode;Assert-P185 ($LASTEXITCODE -eq 0) 'EXISTING_ASIO_SELFTEST_FAILED'
}
& $hostExe --vst3-reference-lifecycle-selftest --plugin $reference
Assert-P185 ($LASTEXITCODE -eq 0) 'REAL_REFERENCE_LIFECYCLE_FAILED'
$old=$ErrorActionPreference;$ErrorActionPreference='Continue'
$log=& $hostExe --vst3-reference-lifecycle-selftest --plugin $broken 2>&1;$badCode=$LASTEXITCODE;$ErrorActionPreference=$old
Assert-P185 ($badCode -ne 0 -and ($log -join "`n") -match 'setProcessing\(true\) failed') 'BROKEN_REFERENCE_DID_NOT_FAIL'
$missing=Join-Path $Evidence 'must-not-exist.json';$obs=Join-Path $Evidence 'no-observation.json'
& $hostExe --physical-asio-probe --plugin $reference --driver-name 'P185 unregistered negative' --driver-clsid '{00000000-0000-0000-0000-000000000000}' --rate 44100 --frames 512 --callbacks 1000 --nonce $nonce --out $missing --diagnostic-out (Join-Path $Evidence 'no-diagnostic.json') --timing-trace-out (Join-Path $Evidence 'no-p181.json') --p185-out $obs
Assert-P185 ($LASTEXITCODE -ne 0 -and -not (Test-Path $missing) -and -not (Test-Path $obs)) 'MISSING_DRIVER_FALSE_HARDWARE_PROOF'
& $exe --decoder-selftest (Join-Path $Evidence 'decoder-negative')
Assert-P185 ($LASTEXITCODE -eq 0) 'UNKNOWN_OPCODE_FALSE_DPC_ATTRIBUTION'
$native=Join-Path $Evidence 'native-etw-local'
& $exe --selftest $native $nonce
Assert-P185 ($LASTEXITCODE -eq 0) 'ACTUAL_NATIVE_ETW_CONTROL_FAILED'
$c=Read-P185Json (Join-Path $native 'capture.json');$w=Read-P185Json (Join-Path $native 'control.json')
# P189: actual offline re-decoding of the ETLs produced by the real Windows ETW control.
# No recording/ASIO/driver is started during this replay.
$replay=Join-Path $Evidence 'native-offline-etw-replay'
& $exe --decode-existing $native $replay $w.pid
Assert-P185 ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $replay 'P189-DECODE.json'))) 'P189_REAL_ETL_REPLAY_FAILED'
$again=Read-P185Json (Join-Path $replay 'P189-DECODE.json')
Assert-P185 ($again.schema -ceq '125a-p189-offline-etw-v1' -and
  $again.events -eq $c.events -and $again.cswitches -eq $c.cswitches -and
  $again.cswitch_events_seen -eq $c.cswitch_events_seen -and
  $again.cswitch_events_decoded -eq $c.cswitch_events_decoded -and
  $again.decode_errors -eq $c.decode_errors -and
  $again.target_pid_unverified -eq $w.pid -and
  $again.physical_asio -ceq 'NOT_VERIFIED_OFFLINE' -and
  -not $again.release_approved) 'P189_REPLAY_UNVERIFIED_OR_NONDETERMINISTIC'

foreach($t in @($c.kernel,$c.user)){
  Assert-P185 ($t.start -eq 0 -and $t.stop -eq 0 -and $t.open -eq 0 -and $t.process -eq 0 -and $t.frequency -eq $w.frequency -and $t.clock -eq 1 -and $t.events_lost -eq 0 -and $t.buffers_lost -eq 0 -and $t.session_events_lost -eq 0 -and $t.session_buffers_lost -eq 0) 'ACTUAL_ETW_METADATA_INVALID'
}
Assert-P185 ($c.child_pid -eq $w.pid -and $c.decode_errors -eq 0 -and $c.cswitches -gt 0) 'ACTUAL_ETW_PID_OR_SCHEMA_FAILED'
Assert-P185 ($c.cswitch_events_seen -gt 0 -and $c.cswitch_events_decoded -ge $c.cswitches -and
  $c.cswitch_events_seen -ge $c.cswitch_events_decoded -and
  $c.thread_events_seen -ge $c.thread_events_decoded -and
  $c.target_thread_count -gt 0 -and @($c.decode_failure_kinds).Count -eq 0) 'P189_REAL_NATIVE_SCHEMA_DIAGNOSTICS_FAILED'
$marks=@(Import-Csv (Join-Path $native 'markers.csv'));Assert-P185 ($marks.Count -eq 2) 'ACTUAL_MARKERS_MISSING'
for($i=0;$i -lt 2;$i++){
  $m=$marks[$i];$b=$w.markers[$i]
  Assert-P185 ($b.result -eq 0 -and [long]$m.pid -eq $w.pid -and [long]$m.tid -eq $w.tid -and $m.nonce -ceq $nonce -and [long]$m.sequence -eq $i+1 -and [long]$m.qpc -ge $b.before -and [long]$m.qpc -le $b.after) 'ACTUAL_QPC_BRACKETS_FAILED'
}
$threadLife=@(Import-Csv (Join-Path $native 'threads.csv'))
Assert-P185 (@($threadLife | Where-Object {[long]$_.pid -eq $w.pid -and [int]$_.opcode -eq 2 -and [long]$_.qpc -ge $w.markers[1].after}).Count -gt 0) 'ACTUAL_KERNEL_END_COVERAGE_MISSING'
$switches=@(Import-Csv (Join-Path $native 'cswitch.csv'))
$sleeps=@($switches | Where-Object {[long]$_.old_tid -eq $w.tid -and [int]$_.old_state -eq 5 -and [int]$_.wait_reason -eq 4})
Assert-P185 ($sleeps.Count -gt 0) 'ACTUAL_SLEEP_WAIT_NOT_SEEN'
$denied=Join-Path $Evidence 'restricted.etl'
& $exe --denied-selftest $denied $nonce
Assert-P185 ($LASTEXITCODE -eq 0) 'ACTUAL_PRIVILEGE_NEGATIVE_FAILED'
# Refuse existing directory instead of reusing old ETL or replacing an owned trace.
& $exe --selftest $native $nonce
Assert-P185 ($LASTEXITCODE -eq 2) 'STALE_DIRECTORY_ACCEPTED'
@{unknown_opcode_negative='PASS';native_etw_control='PASS';qpc_brackets='PASS';real_sleep_cswitch='PASS';restricted_token_negative='PASS';missing_driver_negative='PASS';reference_lifecycle='PASS';broken_reference='REJECTED';physical_asio='NOT_RUN';release_approved=$false} | ConvertTo-Json | Set-Content (Join-Path $Evidence 'P185-WINDOWS-CONTROLS.json')
Write-Host '[PASS] actual Windows ETW control/negative tests; physical ASIO NOT RUN'

exit 0 # Clear the deliberately rejected stale-directory native exit.
