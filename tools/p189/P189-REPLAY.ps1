#requires -Version 5.1
# P189 – decode existing P188 ETL locally; never start an ETW session, audio driver or ASIO.
[CmdletBinding()]param([string]$ExistingRun='', [switch]$CheckOnly, [switch]$Cancel)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=$PSScriptRoot;$out=$null;$report=$null
function Save-P189 {
  if($null -ne $out -and $null -ne $report) {
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $out 'P189-RESULT.json') -Encoding UTF8
  }
}
try {
  if(-not [Environment]::Is64BitProcess){throw 'WINDOWS_X64_REQUIRED'}
  $manifest=Get-Content -LiteralPath (Join-Path $root 'P185-PACKAGE.json') -Raw | ConvertFrom-Json
  if($manifest.schema -cne '125a-p185-package-v1'){throw 'P189_PACKAGE_SCHEMA_INVALID'}
  foreach($entry in $manifest.files.PSObject.Properties) {
    if($entry.Name -match '(^[\\/]|\.\.|:)' -or $entry.Value -cnotmatch '^[0-9a-f]{64}$'){throw 'P189_PACKAGE_ENTRY_INVALID'}
    $path=Join-Path $root $entry.Name
    if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or
       (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value){
      throw 'P189_PACKAGE_HASH_MISMATCH'
    }
  }
  foreach($required in @('125A_Test_Lab_ETW.exe','P189-REPLAY.ps1','P189-REPLAY.bat','P189-ETW-ASIO.bat')){
    if(-not $manifest.files.PSObject.Properties[$required]){throw 'P189_PACKAGE_REQUIRED_ENTRY_MISSING'}
  }
  if($CheckOnly){Write-Host 'P189 Offline-Paketintegritaet: PASS. Kein Audio, ETW oder ASIO gestartet.';exit 0}
  if($Cancel){Write-Host 'P189 Offline-Auswertung abgebrochen. Kein Audio gestartet.';exit 2}
  if(-not $ExistingRun){
    Write-Host 'P189 wertet nur BEREITS VORHANDENE ETL-Dateien aus; kein neuer Audiotest.'
    $ExistingRun=(Read-Host 'Ordner P185-LOCAL-... oder RAW-LOCAL-ONLY angeben').Trim().Trim([char]34)
  }
  if(-not (Test-Path -LiteralPath $ExistingRun -PathType Container)){throw 'P189_EXISTING_RUN_MISSING'}
  $raw=$ExistingRun
  if(Test-Path -LiteralPath (Join-Path $raw 'RAW-LOCAL-ONLY') -PathType Container){$raw=Join-Path $raw 'RAW-LOCAL-ONLY'}
  foreach($file in @('capture.json','kernel.etl','providers.etl')){
    if(-not (Test-Path -LiteralPath (Join-Path $raw $file) -PathType Leaf)){throw 'P189_EXISTING_ETL_INPUT_MISSING'}
  }
  $p=Join-Path $raw 'capture.json'
  $size=(Get-Item -LiteralPath $p).Length
  if($size -lt 2 -or $size -gt 4194304){throw 'P189_CAPTURE_JSON_SIZE_INVALID'}
  $capture=Get-Content -LiteralPath $p -Raw | ConvertFrom-Json
  if($capture.schema -cne '125a-p185-native-etw-v1' -or $capture.source_sha -cnotmatch '^[0-9a-f]{40}$' -or
     $capture.nonce -cnotmatch '^[0-9a-f]{48}$' -or
     $capture.child_pid -isnot [int] -and $capture.child_pid -isnot [long]){throw 'P189_CAPTURE_IDENTITY_INVALID'}
  $pid=[long]$capture.child_pid
  if($pid -lt 1 -or $pid -gt 4294967295){throw 'P189_CAPTURE_PID_INVALID'}
  if($capture.kernel.start -ne 0 -or $capture.user.start -ne 0 -or $capture.marker_enable -ne 0){throw 'P189_CAPTURE_ETW_NOT_STARTED'}
  $asioPresent=Test-Path -LiteralPath (Join-Path $raw 'asio.json') -PathType Leaf
  if($asioPresent){
    $asPath=Join-Path $raw 'asio.json'
    if((Get-Item -LiteralPath $asPath).Length -gt 8388608){throw 'P189_ASIO_METADATA_SIZE_INVALID'}
    $asio=Get-Content -LiteralPath $asPath -Raw | ConvertFrom-Json
    if($asio.schema -cne '125a-p185-asio-observation-v1' -or
       $asio.nonce -cne $capture.nonce -or $asio.source_sha -cne $capture.source_sha -or
       $asio.pid -ne $pid -or $asio.binary_identity_after -ne $true){throw 'P189_INPUT_CROSS_IDENTITY_MISMATCH'}
  }
  $oldHash=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
  $out=Join-Path $root ('P189-REPLAY-'+[Guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $out | Out-Null
  $report=[ordered]@{
    schema='125a-p189-offline-diagnostic-v1';status='INCONCLUSIVE';code='P189_REPLAY_NOT_STARTED';
    source_capture=$capture.source_sha;replay_decoder_source=$manifest.testlab_source;
    capture_sha256=$oldHash;original_events=[long]$capture.events;
    original_decode_errors=[long]$capture.decode_errors;original_cswitches=[long]$capture.cswitches;
    asio_json_present=$asioPresent;physical_asio='NOT_VERIFIED_OFFLINE';
    awe_realtime='NOT_RUN';causal_attribution='INCONCLUSIVE';release_approved=$false;full_audit=$false
  }
  $decodeOut=Join-Path $out 'ETW-ANALYSIS-LOCAL'
  $exe=Join-Path $root '125A_Test_Lab_ETW.exe'
  $prior=$ErrorActionPreference
  try{
    $ErrorActionPreference='Continue'
    & $exe --decode-existing $raw $decodeOut $pid 2>&1 | ForEach-Object {[string]$_} |
      Tee-Object -FilePath (Join-Path $out 'replay.log') | Out-Host
    $rc=[int]$LASTEXITCODE
  }finally{$ErrorActionPreference=$prior}
  $report.replay_native_exit=$rc
  if(-not (Test-Path -LiteralPath (Join-Path $decodeOut 'P189-DECODE.json'))){throw 'P189_DECODER_OUTPUT_MISSING'}
  $d=Get-Content -LiteralPath (Join-Path $decodeOut 'P189-DECODE.json') -Raw | ConvertFrom-Json
  if($d.schema -cne '125a-p189-offline-etw-v1' -or $d.source_sha -cne $manifest.testlab_source -or
     $d.target_pid_unverified -ne $pid -or $d.release_approved -ne $false){throw 'P189_DECODER_RESULT_IDENTITY_INVALID'}
  $report.events=[long]$d.events
  $report.decode_errors=[long]$d.decode_errors
  $report.cswitch_events_seen=[long]$d.cswitch_events_seen
  $report.cswitch_events_decoded=[long]$d.cswitch_events_decoded
  $report.target_cswitches=[long]$d.cswitches
  $report.thread_events_seen=[long]$d.thread_events_seen
  $report.thread_events_decoded=[long]$d.thread_events_decoded
  $report.target_thread_count=[long]$d.target_thread_count
  $report.decode_failure_kinds=@($d.decode_failure_kinds | Select-Object -First 32)
  $report.kernel=$d.kernel;$report.user=$d.user
  if($rc -ne 0 -or $d.kernel.open -ne 0 -or $d.kernel.process -ne 0 -or $d.user.open -ne 0 -or $d.user.process -ne 0){
    $report.code='P189_ETL_READ_OR_PROCESS_FAILED'
  }elseif($d.events -ne $capture.events){
    $report.code='P189_REPLAY_EVENT_COUNT_MISMATCH'
  }elseif($d.decode_errors -gt 0 -or $d.cswitch_events_decoded -eq 0){
    $report.code='P189_DECODER_FAILURE_CATEGORIZED'
  }else{
    $report.code='P189_REPLAY_DECODED_DIAGNOSTIC_ONLY'
  }
  if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -cne $oldHash){
    throw 'P189_INPUT_CHANGED_DURING_REPLAY'
  }
  Save-P189
  Write-Host ('P189: '+$report.code+'. Kein Audio/ASIO ausgefuehrt. Ursache INCONCLUSIVE.')
  Write-Host ('Nur diese Datei bereitstellen: '+(Join-Path $out 'P189-RESULT.json'))
  exit 3 # Diagnostic outcome cannot become a hardware/release PASS.
}catch{
  $code=[string]$_.Exception.Message
  if($code -cnotmatch '^P189_[A-Z0-9_]+$' -and $code -cnotmatch '^WINDOWS_X64_REQUIRED$'){$code='P189_LOCAL_INPUT_ERROR'}
  if($null -ne $report){$report.code=$code;Save-P189}
  Write-Host ('P189 Offline: '+$code+'. Kein Audio oder ASIO gestartet, keine Freigabe.')
  exit 3
}
