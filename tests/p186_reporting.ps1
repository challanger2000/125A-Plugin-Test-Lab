#requires -Version 5.1
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$Evidence)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$p186Root=$Evidence
# Independent P185 arithmetic/clock/thread fixtures remain the baseline oracle.
. (Join-Path $PSScriptRoot 'p185_adversarial.ps1') -Evidence (Join-Path $p186Root 'legacy')
$p186Cases=[Collections.Generic.List[object]]::new()
$profile=[PSCustomObject]@{source_sha=$source;executor_sha256=$sha;product_sha256=$product;driver_clsid=$clsid}
# P185's earlier numeric fixture did not need a total-event field. Native capture does emit it.
$tmp=$baseC | ConvertFrom-Json;$tmp | Add-Member events 500;$tmp | Add-Member provider_inventory_result 0
$baseC=$tmp | ConvertTo-Json -Depth 15
function Test-P186Case([string]$Name,[scriptblock]$Mutate,[string]$ExpectedCode,[string]$ExpectedState,[string]$ExpectedStrict='UNVERIFIED', [switch]$WithoutAsio,[switch]$WithoutCapture,[int]$ExpectedCallbacks=-1,[string[]]$RequiredCodes=@()) {
  Reset-Fixture
  $c=Read-P185Json (Join-Path $dir 'capture.json');$a=Read-P185Json (Join-Path $dir 'asio.json')
  & $Mutate
  $c | ConvertTo-Json -Depth 15 | Set-Content (Join-Path $dir 'capture.json')
  $a | ConvertTo-Json -Depth 15 | Set-Content (Join-Path $dir 'asio.json')
  if($WithoutAsio){Remove-Item (Join-Path $dir 'asio.json')}
  if($WithoutCapture){Remove-Item (Join-Path $dir 'capture.json')}
  $out=Get-P186Assessment -Directory $dir -Profile $profile -ExpectedNonce $nonce -Correlate
  $r=$out.report
  Assert-P185 ($r.error_code -ceq $ExpectedCode) ('PRECISE_CODE_FAILED_'+$Name+'_'+$r.error_code)
  Assert-P185 ($r.physical_asio -ceq $ExpectedState -and $r.strict_full_run -ceq $ExpectedStrict) ('EVIDENCE_STATE_FAILED_'+$Name+'_'+$r.physical_asio+'_'+$r.strict_full_run)
  foreach($code in $RequiredCodes){Assert-P185 ($r.error_codes -contains $code) ('SECONDARY_CODE_MISSING_'+$Name+'_'+$code)}
  Assert-P185 ($r.awe_realtime -ceq 'NOT_RUN' -and $r.cause -ceq 'INCONCLUSIVE' -and -not $r.release_approved -and -not $r.full_audit) 'FORBIDDEN_HARDWARE_OR_RELEASE_PASS'
  if($ExpectedCallbacks -ge 0){Assert-P185 ($r.callbacks -eq $ExpectedCallbacks -and $r.reference_identity_validated) ('CALLBACK_COUNT_FAILED_'+$Name)}else{
    Assert-P185 (-not $r.Contains('callbacks') -and -not $r.reference_identity_validated) ('UNTRUSTED_CALLBACKS_PUBLISHED_'+$Name)
  }
  $encoded=$r | ConvertTo-Json -Depth 15
  Assert-P185 ($encoded -notmatch 'C:\\\\Users|secret\.sf2|private\.etl|DO_NOT_EXPORT') 'PRIVATE_DATA_EXPORTED'
  $p186Cases.Add(@{case=$Name;status='PASS';expected_code=$ExpectedCode;reference_state=$ExpectedState;fixture_kind='SYNTHETIC';hardware='NOT_RUN'})
  return $out
}
$observed='REFERENCE_OBSERVED_BUT_ETW_INCONCLUSIVE';$attempted='REFERENCE_ATTEMPTED_UNVERIFIED'
$null=Test-P186Case 'positive complete correlation' {} '' 'OBSERVED_REFERENCE_ONLY' 'CLEAN_IN_THIS_RUN' -ExpectedCallbacks 100
$r=Test-P186Case 'decode errors with switches' {$c.decode_errors=7} 'ETW_DECODE_ERRORS' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
Assert-P185 ($r.report.diagnostic_summary.capture.decode_errors -eq 7 -and $r.report.diagnostic_summary.capture.cswitches -eq 1 -and $r.report.diagnostic_summary.capture.events -eq 500) 'RAW_COUNTERS_LOST'
$null=Test-P186Case 'zero switches alone' {$c.cswitches=0} 'ETW_ZERO_CONTEXT_SWITCHES' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'decode errors and zero switches' {$c.decode_errors=9;$c.cswitches=0} 'ETW_DECODE_ERRORS' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100 -RequiredCodes @('ETW_ZERO_CONTEXT_SWITCHES')
$null=Test-P186Case 'kernel start denied no child' {$c.kernel.start=5;$c.child_pid=0;$c.child_exit=4294967295;$c.cswitches=0} 'ETW_KERNEL_START_FAILED' 'NOT_RUN' 'NOT_RUN' -WithoutAsio
$null=Test-P186Case 'user session start denied no child' {$c.user.start=5;$c.child_pid=0;$c.child_exit=4294967295} 'ETW_USER_START_FAILED' 'NOT_RUN' 'NOT_RUN' -WithoutAsio
$null=Test-P186Case 'marker enable failed no child' {$c.marker_enable=1168;$c.child_pid=0;$c.child_exit=4294967295} 'ETW_MARKER_ENABLE_FAILED' 'NOT_RUN' 'NOT_RUN' -WithoutAsio
$null=Test-P186Case 'marker and launch contradiction' {$c.marker_enable=5} 'ETW_MARKER_ENABLE_FAILED' $attempted -RequiredCodes @('CAPTURE_LAUNCH_INCONSISTENT')
$null=Test-P186Case 'missing ASIO after launch' {} 'ASIO_OBSERVATION_MISSING' $attempted -WithoutAsio
$null=Test-P186Case 'both raw files absent' {} 'ETW_CAPTURE_MISSING' 'NOT_RUN' 'NOT_RUN' -WithoutAsio -WithoutCapture
$null=Test-P186Case 'capture missing observation claim present' {} 'ETW_CAPTURE_MISSING' $attempted -WithoutCapture
$null=Test-P186Case 'partial actual callbacks not 100 of 100' {$a.actual=50;$a.callbacks=@($a.callbacks[0..49]);$c.child_exit=1} 'ASIO_PARTIAL_CALLBACKS' $observed 'NO_GO' -ExpectedCallbacks 50 -RequiredCodes @('ASIO_CHILD_FAILED')
$null=Test-P186Case 'actual process failure' {$a.callbacks[1].ok=$false;$a.process_failures=1;$c.child_exit=1} 'ASIO_STRICT_FULL_RUN_NO_GO' 'OBSERVED_REFERENCE_ONLY' 'NO_GO' -ExpectedCallbacks 100
$null=Test-P186Case 'strict failure plus bad ETW keeps specific ETW code' {$a.callbacks[1].ok=$false;$a.process_failures=1;$c.child_exit=1;$c.decode_errors=3} 'ETW_DECODE_ERRORS' $observed 'NO_GO' -ExpectedCallbacks 100 -RequiredCodes @('ASIO_STRICT_FULL_RUN_NO_GO')
$null=Test-P186Case 'forged zero exit with DSP failure' {$a.callbacks[1].ok=$false;$a.process_failures=1;$c.child_exit=0} 'EXIT_GATE_MISMATCH' $attempted
$null=Test-P186Case 'forged zero exit with partial stream' {$a.actual=50;$a.callbacks=@($a.callbacks[0..49]);$c.child_exit=0} 'EXIT_GATE_MISMATCH' $attempted
$null=Test-P186Case 'zero actual callbacks after launched child' {$a.actual=0;$a.callbacks=@();$c.child_exit=1} 'ASIO_NO_CALLBACKS' $attempted
$null=Test-P186Case 'pid mismatch' {$a.pid=71} 'PID_MISMATCH' $attempted
$null=Test-P186Case 'nonce mismatch' {$a.nonce='f'*48} 'NONCE_MISMATCH' $attempted
$null=Test-P186Case 'exit code outside Win32 range' {$c.child_exit=9223372036854775807} 'CAPTURE_EXIT_INVALID' $attempted
$null=Test-P186Case 'source sha mismatch' {$a.source_sha='d'*40} 'SOURCE_SHA_MISMATCH' $attempted
$null=Test-P186Case 'executor sha mismatch' {$a.executor_sha256='f'*64} 'SHA_MISMATCH' $attempted
$null=Test-P186Case 'product sha mismatch' {$a.product_sha256='f'*64} 'SHA_MISMATCH' $attempted
$null=Test-P186Case 'driver mismatch' {$a.driver_clsid='{00000000-0000-0000-0000-000000000002}'} 'DRIVER_MISMATCH' $attempted
$null=Test-P186Case 'child timeout' {$c.timeout=$true} 'CHILD_TIMEOUT' $attempted
$null=Test-P186Case 'callback slots incomplete' {$a.complete=$false} 'ASIO_CALLBACK_TRACE_INCOMPLETE' $attempted
$null=Test-P186Case 'callback count mismatch' {$a.actual=99} 'ASIO_CALLBACK_TRACE_INCOMPLETE' $attempted
$null=Test-P186Case 'wrong typed callback flag' {$a.callbacks[0].ok='true'} 'ASIO_CALLBACK_FLAG_INVALID' $attempted
$null=Test-P186Case 'overlap' {$a.callbacks[1].start=$a.callbacks[0].end-1} 'OVERLAPPING_CALLBACKS' $attempted
$null=Test-P186Case 'wrong gate counters' {$a.gap_count=1} 'STRICT_COUNTER_MISMATCH' $attempted
$null=Test-P186Case 'loss despite decoded context switches' {$c.kernel.events_lost=1} 'ETW_LOSS' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'user buffers lost' {$c.user.buffers_lost=1} 'ETW_LOSS' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'kernel stop failed' {$c.kernel.stop=5} 'ETW_KERNEL_STOP_FAILED' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'user open failed' {$c.user.open=5} 'ETW_USER_OPEN_FAILED' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'kernel process trace failed' {$c.kernel.process=13} 'ETW_KERNEL_PROCESS_FAILED' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'uncorrelated clock' {$c.kernel.frequency=1000001} 'QPC_CLOCK_MISMATCH' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'CSV absent does not mean no ASIO' {Remove-Item (Join-Path $dir 'markers.csv')} 'ETW_CORRELATION_INPUTS_MISSING' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$null=Test-P186Case 'contradictory event totals' {$c.events=0} 'ETW_EVENT_COUNTERS_INCONSISTENT' $attempted
$null=Test-P186Case 'malformed numeric metadata' {$c.decode_errors='C:\Users\DO_NOT_EXPORT\private.etl'} 'CAPTURE_NUMERIC_INVALID' $attempted
$null=Test-P186Case 'private provider names and extra data omitted' {$c | Add-Member ignored 'C:\Users\DO_NOT_EXPORT\secret.sf2';$c.providers=@(@{guid='{00000000-0000-0000-0000-000000000003}';enable=5;name='C:\Users\DO_NOT_EXPORT\private.etl'});$c.decode_errors=3} 'ETW_DECODE_ERRORS' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
$r=Test-P186Case 'bounded provider summary' {$c.providers=@(1..100 | ForEach-Object {@{guid='{00000000-0000-0000-0000-000000000003}';enable=5;name='DO_NOT_EXPORT'}});$c.decode_errors=2} 'ETW_DECODE_ERRORS' $observed 'UNVERIFIED_WITHOUT_ETW' -ExpectedCallbacks 100
Assert-P185 ($r.report.diagnostic_summary.providers.Count -eq 32 -and $r.report.diagnostic_summary.providers_truncated -and $r.report.diagnostic_summary.reported_provider_enable_failures -eq 32) 'UNBOUNDED_PROVIDER_EXPORT'
# Execute the original broken analyzer and its exact default-state control-flow defect.
Reset-Fixture;$c=Read-P185Json (Join-Path $dir 'capture.json');$c.decode_errors=1
$c | ConvertTo-Json -Depth 15 | Set-Content (Join-Path $dir 'capture.json')
$old=Join-Path $p186Root 'original-p185-analyze.ps1'
git -C (Join-Path $PSScriptRoot '..') show 59762ae67a5878f4bade2e000672497acde4f763:tools/p185/P185-ANALYZE.ps1 | Set-Content $old
Assert-P185 ($LASTEXITCODE -eq 0) 'ORIGINAL_BASELINE_NOT_AVAILABLE'
$oldResult=& { . $old; $default=@{physical_asio='NOT_RUN';error_code=''};try{$null=Get-P185Analysis $dir $nonce $sha $product $clsid $source;$default.physical_asio='OBSERVED_REFERENCE_ONLY'}catch{$default.error_code=$_.Exception.Message};$default }
Assert-P185 ($oldResult.error_code -ceq 'ETW_NOT_AVAILABLE_OR_UNDECODABLE' -and $oldResult.physical_asio -ceq 'NOT_RUN') 'ORIGINAL_REPORTING_BUG_NOT_REPRODUCED'
$new=Get-P186Assessment $dir $profile $nonce -Correlate
Assert-P185 ($new.report.error_code -ceq 'ETW_DECODE_ERRORS' -and $new.report.physical_asio -ceq $observed) 'NEW_REPORT_FAILED_ORIGINAL_REPRODUCTION'
$p186Cases.Add(@{case='original P185 source demonstrates misleading NOT_RUN; corrected source rejects regression';status='PASS';fixture_kind='SYNTHETIC';hardware='NOT_RUN'})
$p186Cases | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $p186Root 'P186-REPORTING-TESTS.json')
$profile | ConvertTo-Json | Set-Content (Join-Path $p186Root 'synthetic-profile.json')
Write-Host ('[PASS] P186 '+$p186Cases.Count+' evidence/reporting controls; synthetic fixtures, hardware NOT_RUN')
