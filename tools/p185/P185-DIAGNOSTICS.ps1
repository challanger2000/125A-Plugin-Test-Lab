#requires -Version 5.1
# P186: evidence progress and correlation are independent. No hardware PASS.
Set-StrictMode -Version Latest
function Get-P186Property($Object,[string]$Name) {
  if($null -eq $Object){return $null}
  if($Object -is [Collections.IDictionary]){return $Object[$Name]}
  $p=$Object.PSObject.Properties[$Name];if($null -ne $p){return $p.Value};return $null
}
function Test-P186Integer($Value,[long]$Maximum=[long]::MaxValue) {
  if($null -eq $Value -or $Value -is [bool] -or $Value -is [string]){return $false}
  if($Value -isnot [int] -and $Value -isnot [long] -and $Value -isnot [uint32] -and $Value -isnot [uint64]){return $false}
  return $Value -ge 0 -and $Value -le $Maximum
}
function Add-P186Code($Codes,[string]$Code) { if(-not $Codes.Contains($Code)){$Codes.Add($Code)} }
function Read-P186Json([string]$Path,[int]$MaximumBytes) {
  Assert-P185 (Test-Path -LiteralPath $Path -PathType Leaf) 'RAW_JSON_MISSING'
  $file=Get-Item -LiteralPath $Path
  Assert-P185 ($file.Length -gt 0 -and $file.Length -le $MaximumBytes) 'RAW_JSON_SIZE_INVALID'
  try {return Read-P185Json $Path} catch {throw 'RAW_JSON_INVALID'}
}
function Get-P186DiagnosticSummary($Capture,$Asio,$Codes) {
  $s=[ordered]@{capture_present=($null -ne $Capture);asio_present=($null -ne $Asio);capture=[ordered]@{};kernel=[ordered]@{};user=[ordered]@{};asio_raw=[ordered]@{};providers=@();provider_count=0;providers_truncated=$false;reported_provider_enable_failures=0}
  if($null -ne $Capture){
    foreach($key in @('events','cswitches','decode_errors','child_pid','child_exit','marker_enable')){
      $value=Get-P186Property $Capture $key
      if(Test-P186Integer $value){$s.capture[$key]=[long]$value}else{$s.capture[$key]=$null;Add-P186Code $Codes 'CAPTURE_NUMERIC_INVALID'}
    }
    if($null -ne $s.capture.events -and (($null -ne $s.capture.cswitches -and $s.capture.cswitches -gt $s.capture.events) -or ($null -ne $s.capture.decode_errors -and $s.capture.decode_errors -gt $s.capture.events))){Add-P186Code $Codes 'ETW_EVENT_COUNTERS_INCONSISTENT'}
    $inventory=Get-P186Property $Capture 'provider_inventory_result'
    $s.capture.provider_inventory_result=if(Test-P186Integer $inventory){[long]$inventory}else{$null}
    $timeout=Get-P186Property $Capture 'timeout'
    if($timeout -is [bool]){$s.capture.timeout=$timeout}else{$s.capture.timeout=$null;Add-P186Code $Codes 'CAPTURE_TIMEOUT_INVALID'}
    foreach($session in @('kernel','user')){
      $raw=Get-P186Property $Capture $session
      foreach($key in @('start','stop','open','process','frequency','clock','events_lost','buffers_lost','session_events_lost','session_buffers_lost')){
        $v=Get-P186Property $raw $key
        if(Test-P186Integer $v){$s[$session][$key]=[long]$v}else{$s[$session][$key]=$null;Add-P186Code $Codes ('ETW_'+$session.ToUpperInvariant()+'_METADATA_INVALID')}
      }
    }
    $rawProviders=Get-P186Property $Capture 'providers'
    if($null -ne $rawProviders){
      $count=@($rawProviders).Count;$s.provider_count=$count;$s.providers_truncated=($count -gt 32)
      for($i=0;$i -lt [Math]::Min(32,$count);$i++){
        $p=$rawProviders[$i];$id=Get-P186Property $p 'guid';$rc=Get-P186Property $p 'enable'
        if($id -is [string] -and $id -match '^\{[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\}$' -and (Test-P186Integer $rc)){
          $s.providers+=@{guid=$id;enable=[long]$rc};if($rc -ne 0){$s.reported_provider_enable_failures++}
        }else{Add-P186Code $Codes 'ETW_PROVIDER_METADATA_INVALID'}
      }
    }
  }
  if($null -ne $Asio){
    foreach($key in @('pid','qpc_frequency','sample_rate','frames','requested','actual','gap_count','execution_overruns','xrun_messages','process_failures','rate_changes')){
      $v=Get-P186Property $Asio $key;$s.asio_raw[$key]=if(Test-P186Integer $v){[long]$v}else{$null}
    }
    $complete=Get-P186Property $Asio 'complete';$s.asio_raw.complete=if($complete -is [bool]){$complete}else{$null}
  }
  return $s
}
function Get-P186ReferenceEvidence($Capture,$Asio,$Profile,[string]$ExpectedNonce) {
  Assert-P185 ($Capture.schema -ceq '125a-p185-native-etw-v1' -and $Asio.schema -ceq '125a-p185-asio-observation-v1') 'WRONG_SCHEMA'
  Assert-P185 ($Profile.source_sha -cmatch '^[0-9a-f]{40}$' -and $Capture.source_sha -ceq $Profile.source_sha -and $Asio.source_sha -ceq $Profile.source_sha) 'SOURCE_SHA_MISMATCH'
  Assert-P185 ($ExpectedNonce -cmatch '^[0-9a-f]{48}$' -and $Capture.nonce -ceq $ExpectedNonce -and $Asio.nonce -ceq $ExpectedNonce) 'NONCE_MISMATCH'
  Assert-P185 ($Profile.executor_sha256 -cmatch '^[0-9a-f]{64}$' -and $Profile.product_sha256 -cmatch '^[0-9a-f]{64}$' -and $Asio.executor_sha256 -ceq $Profile.executor_sha256 -and $Asio.product_sha256 -ceq $Profile.product_sha256 -and $Asio.binary_identity_after -is [bool] -and $Asio.binary_identity_after) 'SHA_MISMATCH'
  Assert-P185 ($Profile.driver_clsid -match '^\{[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\}$' -and $Asio.driver_clsid -ceq $Profile.driver_clsid) 'DRIVER_MISMATCH'
  Assert-P185 ((Test-P186Integer $Capture.child_pid 4294967295) -and $Capture.child_pid -gt 0 -and (Test-P186Integer $Asio.pid 4294967295) -and $Asio.pid -eq $Capture.child_pid) 'PID_MISMATCH'
  Assert-P185 (Test-P186Integer $Capture.child_exit 4294967295) 'CAPTURE_EXIT_INVALID'
  Assert-P185 ($Capture.timeout -is [bool] -and -not $Capture.timeout) 'CHILD_TIMEOUT'
  Assert-P185 ($Capture.kernel.start -eq 0 -and $Capture.user.start -eq 0 -and $Capture.marker_enable -eq 0) 'CAPTURE_LAUNCH_INCONSISTENT'
  foreach($k in @('qpc_frequency','sample_rate','frames','requested','actual','gap_count','execution_overruns','xrun_messages','process_failures','rate_changes')){
    Assert-P185 (Test-P186Integer (Get-P186Property $Asio $k)) 'ASIO_NUMERIC_INVALID'
  }
  Assert-P185 ($Asio.qpc_frequency -gt 0 -and $Asio.sample_rate -eq 44100 -and $Asio.frames -ge 64 -and $Asio.frames -le 4096) 'BUFFER_CONFIGURATION'
  Assert-P185 ($Asio.requested -ge 100 -and $Asio.requested -le 4096 -and $Asio.actual -le 4160) 'ASIO_CALLBACK_COUNT_INVALID'
  Assert-P185 ($Asio.actual -gt 0) 'ASIO_NO_CALLBACKS'
  Assert-P185 ($Asio.complete -is [bool] -and $Asio.complete -and @($Asio.callbacks).Count -eq $Asio.actual) 'ASIO_CALLBACK_TRACE_INCOMPLETE'
  $l=$Asio.lifecycle;$last=0
  foreach($k in @('create_before','create_after','active','processing','armed','start_before','start_after','stop_before','stop_after')){
    $v=Get-P186Property $l $k
    Assert-P185 ((Test-P186Integer $v) -and $v -gt 0 -and $v -ge $last) 'LIFECYCLE_ORDER';$last=[long]$v
  }
  [long]$gaps=0;[long]$overruns=0;[long]$failed=0;$prior=$null
  for($i=0;$i -lt $Asio.actual;$i++){
    $b=$Asio.callbacks[$i]
    foreach($k in @('index','tid','buffer','start','end')){Assert-P185 (Test-P186Integer (Get-P186Property $b $k)) 'ASIO_CALLBACK_NUMERIC_INVALID'}
    Assert-P185 ($b.index -eq $i -and $b.tid -gt 0 -and $b.tid -le 4294967295 -and $b.buffer -in @(0,1) -and $b.start -ge $l.armed -and $b.end -ge $b.start -and $b.end -le $l.stop_after) 'CALLBACK_ORDER_OR_BOUNDS'
    Assert-P185 ($b.ok -is [bool] -and $b.gap -is [bool]) 'ASIO_CALLBACK_FLAG_INVALID'
    if(-not $b.ok){$failed++}
    if(($b.end-$b.start) -gt [Math]::Floor(1.0*$Asio.frames*$Asio.qpc_frequency/$Asio.sample_rate)){$overruns++}
    $gap=$false
    if($null -ne $prior){
      Assert-P185 ($b.start -ge $prior.end) 'OVERLAPPING_CALLBACKS'
      $gap=([Math]::Floor($b.start*1e9/$Asio.qpc_frequency)-[Math]::Floor($prior.start*1e9/$Asio.qpc_frequency)) -gt 2*[Math]::Floor(1e9*$Asio.frames/$Asio.sample_rate)
    }
    Assert-P185 ($b.gap -eq $gap) 'GAP_FLAG_MISMATCH';if($gap){$gaps++};$prior=$b
  }
  Assert-P185 ($gaps -eq $Asio.gap_count -and $overruns -eq $Asio.execution_overruns) 'STRICT_COUNTER_MISMATCH'
  Assert-P185 ($failed -eq $Asio.process_failures) 'DSP_COUNTER_MISMATCH'
  $partial=$Asio.actual -lt $Asio.requested
  $violation=$gaps -gt 0 -or $overruns -gt 0 -or $failed -gt 0 -or $Asio.xrun_messages -gt 0 -or $Asio.rate_changes -gt 0
  Assert-P185 (-not ($Capture.child_exit -eq 0 -and ($partial -or $violation))) 'EXIT_GATE_MISMATCH'
  $bad=$partial -or $gaps -gt 0 -or $overruns -gt 0 -or $failed -gt 0 -or $Asio.xrun_messages -gt 0 -or $Asio.rate_changes -gt 0 -or $Capture.child_exit -ne 0
  return @{valid=$true;callbacks=[long]$Asio.actual;successful_callbacks=([long]$Asio.actual-$failed);requested_callbacks=[long]$Asio.requested;partial=$partial;strict_violation=$violation;strict_full_run=if($bad){'NO_GO'}else{'UNVERIFIED_WITHOUT_ETW'};gap_count=$gaps;execution_overruns=$overruns;process_failures=$failed}
}
function Get-P186Assessment {
  param([string]$Directory,$Profile,[string]$ExpectedNonce='', [switch]$Correlate)
  $codes=[Collections.Generic.List[string]]::new()
  $report=[ordered]@{schema='125a-p186-acceptance-v1';status='NOT_RUN';physical_asio='NOT_RUN';cause='INCONCLUSIVE';awe_realtime='NOT_RUN';strict_full_run='NOT_RUN';correlation='NOT_VERIFIED';release_approved=$false;full_audit=$false;error_code='';error_codes=@();reference_identity_validated=$false;nonce='';diagnostic_summary=$null}
  $c=$null;$a=$null;$analysis=$null;$captureReadCode='';$asioReadCode=''
  try{$c=Read-P186Json (Join-Path $Directory 'capture.json') 4194304}catch{$captureReadCode=if($_.Exception.Message -eq 'RAW_JSON_MISSING'){'ETW_CAPTURE_MISSING'}else{'ETW_CAPTURE_JSON_INVALID'}}
  try{$a=Read-P186Json (Join-Path $Directory 'asio.json') 8388608}catch{$asioReadCode=if($_.Exception.Message -eq 'RAW_JSON_MISSING'){'ASIO_OBSERVATION_MISSING'}else{'ASIO_OBSERVATION_JSON_INVALID'}}
  # Existence/child claims are explicitly UNVERIFIED. They never certify callbacks.
  if(((Test-P186Integer (Get-P186Property $c 'child_pid') 4294967295) -and $c.child_pid -gt 0) -or ((Test-P186Integer (Get-P186Property $a 'pid') 4294967295) -and $a.pid -gt 0)){
    $report.physical_asio='REFERENCE_ATTEMPTED_UNVERIFIED';$report.status='INCONCLUSIVE';$report.strict_full_run='UNVERIFIED'
  }
  $summaryCodes=[Collections.Generic.List[string]]::new()
  $s=Get-P186DiagnosticSummary $c $a $summaryCodes;$report.diagnostic_summary=$s
  if($captureReadCode){Add-P186Code $codes $captureReadCode}
  foreach($v in $summaryCodes){Add-P186Code $codes $v}
  if($null -ne $c){
    if((Get-P186Property $c 'schema') -cne '125a-p185-native-etw-v1'){Add-P186Code $codes 'CAPTURE_SCHEMA_INVALID'}
    foreach($session in @('kernel','user')){
      if($null -ne $s[$session].start -and $s[$session].start -ne 0){Add-P186Code $codes ('ETW_'+$session.ToUpperInvariant()+'_START_FAILED')}
    }
    if($null -ne $s.capture.marker_enable -and $s.capture.marker_enable -ne 0){Add-P186Code $codes 'ETW_MARKER_ENABLE_FAILED'}
  }
  if($asioReadCode){Add-P186Code $codes $asioReadCode}
  $reference=$null;$asioCodes=[Collections.Generic.List[string]]::new()
  if($null -ne $c -and $null -ne $a -and $summaryCodes.Count -eq 0){
    try{
      if(-not $ExpectedNonce){$ExpectedNonce=[string](Get-P186Property $c 'nonce')}
      $reference=Get-P186ReferenceEvidence $c $a $Profile $ExpectedNonce
      $report.physical_asio='REFERENCE_OBSERVED_BUT_ETW_INCONCLUSIVE';$report.status='INCONCLUSIVE';$report.reference_identity_validated=$true
      $report.nonce=$ExpectedNonce;$report.testlab_source=$Profile.source_sha;$report.executor_sha256=$Profile.executor_sha256;$report.reference_sha256=$Profile.product_sha256;$report.driver_clsid=$Profile.driver_clsid
      foreach($k in @('callbacks','successful_callbacks','requested_callbacks','strict_full_run','gap_count','execution_overruns','process_failures')){$report[$k]=$reference[$k]}
      if($reference.partial){Add-P186Code $asioCodes 'ASIO_PARTIAL_CALLBACKS'}
      if($c.child_exit -ne 0){
        if(-not $reference.partial -and $reference.strict_violation -and $c.child_exit -eq 1){Add-P186Code $asioCodes 'ASIO_STRICT_FULL_RUN_NO_GO'}else{Add-P186Code $asioCodes 'ASIO_CHILD_FAILED'}
      }
    }catch{
      $code=[string]$_.Exception.Message
      if($code -cnotmatch '^[A-Z0-9_]+$'){$code='REFERENCE_METADATA_INVALID'}
      Add-P186Code $codes $code
    }
  }
  if($null -ne $c){
    if($null -ne $s.capture.decode_errors -and $s.capture.decode_errors -gt 0){Add-P186Code $codes 'ETW_DECODE_ERRORS'}
    if($null -ne $s.capture.cswitches -and $s.capture.cswitches -eq 0){Add-P186Code $codes 'ETW_ZERO_CONTEXT_SWITCHES'}
    foreach($session in @('kernel','user')){
      foreach($op in @('stop','open','process')){if($null -ne $s[$session][$op] -and $s[$session][$op] -ne 0){Add-P186Code $codes ('ETW_'+$session.ToUpperInvariant()+'_'+$op.ToUpperInvariant()+'_FAILED')}}
      foreach($loss in @('events_lost','buffers_lost','session_events_lost','session_buffers_lost')){if($null -ne $s[$session][$loss] -and $s[$session][$loss] -gt 0){Add-P186Code $codes 'ETW_LOSS'}}
      if($null -ne $a -and $s[$session].start -eq 0 -and $s[$session].open -eq 0 -and $s[$session].process -eq 0 -and ($s[$session].clock -ne 1 -or $s[$session].frequency -le 0 -or $s[$session].frequency -ne (Get-P186Property $a 'qpc_frequency'))){Add-P186Code $codes 'QPC_CLOCK_MISMATCH'}
    }
  }
  foreach($code in $asioCodes){Add-P186Code $codes $code}
  $blocking=@($codes | Where-Object {$_ -cne 'ASIO_STRICT_FULL_RUN_NO_GO'})
  if($null -ne $reference -and $blocking.Count -eq 0){
    if($Correlate){
      $complete=$true;foreach($name in @('markers.csv','cswitch.csv','threads.csv','ready.csv','activity.csv')){if(-not (Test-Path -LiteralPath (Join-Path $Directory $name) -PathType Leaf)){$complete=$false}}
      if(-not $complete){Add-P186Code $codes 'ETW_CORRELATION_INPUTS_MISSING'}else{
        try{
          $analysis=Get-P185Analysis $Directory $ExpectedNonce $Profile.executor_sha256 $Profile.product_sha256 $Profile.driver_clsid $Profile.source_sha
          $report.physical_asio='OBSERVED_REFERENCE_ONLY';$report.correlation=$analysis.correlation;$report.strict_full_run=$analysis.strict_full_run
        }catch{
          $code=[string]$_.Exception.Message;if($code -cnotmatch '^[A-Z0-9_]+$'){$code='ETW_CORRELATION_INPUT_INVALID'};Add-P186Code $codes $code
        }
      }
    }else{Add-P186Code $codes 'ETW_CORRELATION_NOT_EVALUATED'}
  }
  $report.error_codes=@($codes.ToArray());if($codes.Count){$report.error_code=$codes[0]}
  return @{report=$report;analysis=$analysis}
}
