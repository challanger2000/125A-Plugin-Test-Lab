#requires -Version 5.1
# P189: independently challenge bounded, path-free ETW decoder diagnostics.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../tools/p185/P185-ANALYZE.ps1')
function Require([bool]$ok,[string]$why){ if(-not $ok){throw $why} }
$meta=@{start=0;stop=0;open=0;process=0;frequency=10000000;clock=1;events_lost=0;buffers_lost=0;session_events_lost=0;session_buffers_lost=0}
$c=[pscustomobject]@{
  events=125671;cswitches=0;decode_errors=43425;child_pid=23164;child_exit=1;marker_enable=0;
  timeout=$false;provider_inventory_result=0;kernel=[pscustomobject]$meta;user=[pscustomobject]$meta;
  providers=@();cswitch_events_seen=43000;cswitch_events_decoded=0;
  thread_events_seen=425;thread_events_decoded=410;ready_events_seen=0;target_thread_count=4;
  decode_failure_kinds=@(
    [pscustomobject]@{kind='CSWITCH.NewThreadId.1168';count=43000},
    [pscustomobject]@{kind='THREAD.TThreadId.1168';count=425})
}
$errors=[Collections.Generic.List[string]]::new()
$summary=Get-P186DiagnosticSummary $c $null $errors
Require ($summary.capture.cswitch_events_seen -eq 43000 -and
  $summary.capture.thread_events_decoded -eq 410 -and
  $summary.capture.decode_failure_kinds.Count -eq 2 -and
  $summary.capture.decode_failure_kinds[0].kind -ceq 'CSWITCH.NewThreadId.1168' -and
  $summary.capture.decode_failure_kinds[1].count -eq 425 -and $errors.Count -eq 0) 'P189_OBSERVABILITY_POSITIVE_FAILED'
# Never export user-controlled/private fields or paths; inject an apparent error key.
$c.decode_failure_kinds=@([pscustomobject]@{kind='C:\\Users\\private\\account.sf2';count=12})
$errors.Clear()
$negative=Get-P186DiagnosticSummary $c $null $errors
Require (($errors -contains 'ETW_DIAGNOSTIC_KIND_INVALID') -and
  $negative.capture.decode_failure_kinds.Count -eq 0 -and
  ($negative|ConvertTo-Json -Depth 12) -notmatch 'private|account.sf2') 'P189_UNSAFE_DIAGNOSTIC_KEY_ACCEPTED'
# Prevent exporting unbounded parser signatures; keep only 32 metadata records.
$c.decode_failure_kinds=@(1..50 | ForEach-Object {[pscustomobject]@{kind=('THREAD.TThreadId.'+$_);count=$_}})
$errors.Clear()
$bounded=Get-P186DiagnosticSummary $c $null $errors
Require ($bounded.capture.decode_failure_kinds_truncated -and
  $bounded.capture.decode_failure_kinds.Count -eq 32 -and $errors.Count -eq 0) 'P189_UNBOUNDED_DIAGNOSTIC_SUMMARY'
# An invalid numeric counter must fail closed rather than be coerced to zero.
$c.cswitch_events_seen='12'
$errors.Clear()
$numeric=Get-P186DiagnosticSummary $c $null $errors
Require (($errors -contains 'ETW_DIAGNOSTIC_COUNTER_INVALID') -and
  $null -eq $numeric.capture.cswitch_events_seen) 'P189_NUMERIC_STRING_ACCEPTED'
Write-Host '[PASS] P189 metadata-only ETW decoder observations, malicious field rejection, bounded failure summary and typed counter negative; hardware NOT_RUN'
exit 0 # Clear stale native negative-control LASTEXITCODE; this script has passed all assertions.
