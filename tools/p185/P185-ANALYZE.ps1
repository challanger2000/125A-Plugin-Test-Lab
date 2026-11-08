#requires -Version 5.1
# Universal offline ETW/ASIO reconciliation. No fixture may become hardware proof.
Set-StrictMode -Version Latest
function Assert-P185([bool]$Condition,[string]$Code) { if(-not $Condition){throw $Code} }
function Read-P185Json([string]$Path) { Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
function Get-P185Statistics([double[]]$Values) {
  Assert-P185 ($Values.Count -gt 0) 'EMPTY_MEASUREMENT'
  $s=@($Values | Sort-Object)
  $mid=[int][Math]::Floor($s.Count/2)
  $median=if($s.Count%2){$s[$mid]}else{($s[$mid-1]+$s[$mid])/2}
  @{median_us=$median;p99_us=$s[[Math]::Ceiling(.99*$s.Count)-1];maximum_us=$s[-1];count=$s.Count}
}
function Get-P185Window([object[]]$Switches,[object[]]$Ready,[long]$Thread,[long]$Begin,[long]$End) {
  # State transitions are observations. Waiting is not scheduler starvation.
  $related=@($Switches | Where-Object {([long]$_.old_tid -eq $Thread -or [long]$_.new_tid -eq $Thread) -and [long]$_.qpc -lt $End} | Sort-Object {[long]$_.qpc})
  $known=$false;$running=$false;$state=-1;$cursor=$Begin
  [long]$off=0;[long]$readyTicks=0;[long]$waiting=0;[long]$unknown=0
  $consistent=$true
  foreach($s in $related) {
    $t=[long]$s.qpc
    if($t -gt $Begin -and $known -and -not $running) {
      $left=$cursor;$right=[Math]::Min($t,$End);$dt=$right-$left
      if($dt -gt 0) {
        $off+=$dt
        if($state -eq 1){$readyTicks+=$dt}
        elseif($state -eq 5) {
          $r=@($Ready | Where-Object {[long]$_.tid -eq $Thread -and [long]$_.qpc -ge $left -and [long]$_.qpc -lt $right} | Sort-Object {[long]$_.qpc})
          if($r.Count){$waiting+=[long]$r[0].qpc-$left;$readyTicks+=$right-[long]$r[0].qpc}else{$waiting+=$dt}
        }else{$unknown+=$dt}
      }
    }
    if($t -gt $Begin -and -not $known){$consistent=$false}
    if([long]$s.old_tid -eq $Thread) {
      if($known -and -not $running){$consistent=$false}
      $running=$false;$state=[int]$s.old_state
    }else{
      if($known -and $running){$consistent=$false}
      $running=$true;$state=2
    }
    $known=$true;if($t -ge $Begin){$cursor=$t}
  }
  if(-not $known){$consistent=$false}
  if($known -and -not $running -and $cursor -lt $End) {
    $dt=$End-$cursor;$off+=$dt
    if($state -eq 1){$readyTicks+=$dt}elseif($state -eq 5){$waiting+=$dt}else{$unknown+=$dt}
  }
  @{complete=$consistent;off_ticks=$off;ready_ticks=$readyTicks;waiting_ticks=$waiting;unknown_ticks=$unknown}
}
function Get-P185Analysis {
  param([string]$Directory,[string]$ExpectedNonce,[string]$ExpectedHostHash,[string]$ExpectedProductHash,[string]$ExpectedDriverClsid,[string]$ExpectedTestlabSource)
  $c=Read-P185Json (Join-Path $Directory 'capture.json')
  $a=Read-P185Json (Join-Path $Directory 'asio.json')
  Assert-P185 ($c.schema -ceq '125a-p185-native-etw-v1' -and $a.schema -ceq '125a-p185-asio-observation-v1') 'WRONG_SCHEMA'
  Assert-P185 ($ExpectedTestlabSource -cmatch '^[0-9a-f]{40}$' -and $c.source_sha -ceq $ExpectedTestlabSource -and $a.source_sha -ceq $ExpectedTestlabSource) 'SOURCE_SHA_MISMATCH'
  Assert-P185 ($ExpectedNonce -cmatch '^[0-9a-f]{48}$' -and $c.nonce -ceq $ExpectedNonce -and $a.nonce -ceq $ExpectedNonce) 'NONCE_MISMATCH'
  Assert-P185 ($ExpectedHostHash -cmatch '^[0-9a-f]{64}$' -and $ExpectedProductHash -cmatch '^[0-9a-f]{64}$' -and $a.executor_sha256 -ceq $ExpectedHostHash -and $a.product_sha256 -ceq $ExpectedProductHash -and $a.binary_identity_after -eq $true) 'SHA_MISMATCH'
  Assert-P185 ($a.driver_clsid -ceq $ExpectedDriverClsid) 'DRIVER_MISMATCH'
  Assert-P185 ($c.child_pid -gt 0 -and $c.child_pid -eq $a.pid -and -not $c.timeout) 'PID_MISMATCH_OR_TIMEOUT'
  Assert-P185 ($c.marker_enable -eq 0) 'ETW_MARKER_ENABLE_FAILED'
  Assert-P185 ($c.decode_errors -eq 0) 'ETW_DECODE_ERRORS'
  Assert-P185 ($c.cswitches -gt 0) 'ETW_ZERO_CONTEXT_SWITCHES'
  foreach($t in @($c.kernel,$c.user)) {
    Assert-P185 ($t.start -eq 0 -and $t.stop -eq 0 -and $t.open -eq 0 -and $t.process -eq 0) 'ETW_NOT_AVAILABLE'
    Assert-P185 ($t.events_lost -eq 0 -and $t.buffers_lost -eq 0 -and $t.session_events_lost -eq 0 -and $t.session_buffers_lost -eq 0) 'ETW_LOSS'
    Assert-P185 ($t.frequency -gt 0 -and $t.frequency -eq $a.qpc_frequency -and $t.clock -eq 1) 'QPC_CLOCK_MISMATCH'
  }
  $marks=@(Import-Csv -LiteralPath (Join-Path $Directory 'markers.csv'))
  Assert-P185 ($marks.Count -eq 2 -and @($a.markers).Count -eq 2) 'MISSING_CALIBRATION'
  $f=[long]$a.qpc_frequency
  for($i=0;$i -lt 2;$i++) {
    $m=$a.markers[$i];$e=$marks[$i]
    Assert-P185 ($m.result -eq 0 -and [int]$e.sequence -eq $i+1 -and $m.sequence -eq $i+1 -and $e.nonce -ceq $ExpectedNonce -and [long]$e.pid -eq $a.pid -and [long]$e.tid -eq $m.tid) 'MARKER_IDENTITY_MISMATCH'
    Assert-P185 ($m.before -gt 0 -and $m.after -ge $m.before -and [long]$e.qpc -ge $m.before -and [long]$e.qpc -le $m.after -and ($m.after-$m.before) -le $f/100) 'QPC_CALIBRATION_MISMATCH'
  }
  Assert-P185 ($a.markers[1].before -gt $a.markers[0].after) 'QPC_CALIBRATION_ORDER'
  Assert-P185 ($a.complete -eq $true -and $a.actual -ge $a.requested -and $a.actual -eq @($a.callbacks).Count -and $a.actual -ge 100 -and $a.actual -le 4160) 'CALLBACK_LOSS'
  Assert-P185 ($a.sample_rate -eq 44100 -and $a.frames -ge 64 -and $a.frames -le 4096) 'BUFFER_CONFIGURATION'
  $l=$a.lifecycle
  $order=@($a.markers[0].after,$l.create_before,$l.create_after,$l.active,$l.processing,$l.armed,$l.start_before,$l.start_after,$l.stop_before,$l.stop_after,$a.markers[1].before)
  for($i=1;$i -lt $order.Count;$i++){Assert-P185 ($order[$i] -ge $order[$i-1]) 'LIFECYCLE_ORDER'}
  $switches=@(Import-Csv -LiteralPath (Join-Path $Directory 'cswitch.csv'))
  Assert-P185 ($switches.Count -eq $c.cswitches) 'SWITCH_COUNT_MISMATCH'
  $threads=@(Import-Csv -LiteralPath (Join-Path $Directory 'threads.csv'))
  Assert-P185 (@($threads | Where-Object {[long]$_.pid -eq $a.pid -and [int]$_.opcode -eq 2 -and [long]$_.qpc -ge $a.markers[1].after}).Count -gt 0) 'KERNEL_END_COVERAGE_MISSING'
  $ready=@(Import-Csv -LiteralPath (Join-Path $Directory 'ready.csv'))
  $activity=@(Import-Csv -LiteralPath (Join-Path $Directory 'activity.csv'))
  $bySwitch=@{};$byThread=@{};$byReady=@{}
  foreach($v in $switches){foreach($t in @([long]$v.old_tid,[long]$v.new_tid)) {if(-not $bySwitch.ContainsKey($t)){$bySwitch[$t]=[Collections.Generic.List[object]]::new()};$bySwitch[$t].Add($v)}}
  foreach($v in $threads){$t=[long]$v.tid;if(-not $byThread.ContainsKey($t)){$byThread[$t]=[Collections.Generic.List[object]]::new()};$byThread[$t].Add($v)}
  foreach($v in $ready){$t=[long]$v.tid;if(-not $byReady.ContainsKey($t)){$byReady[$t]=[Collections.Generic.List[object]]::new()};$byReady[$t].Add($v)}
  $gaps=@();$durations=@();$spacings=@();$idle=@();$callbackRows=@();$overruns=0;$prior=$null
  $threshold=2.0*$a.frames*$f/$a.sample_rate # Unchanged entire-run strict gate, no warmup exclusion.
  for($i=0;$i -lt $a.actual;$i++) {
    $b=$a.callbacks[$i]
    Assert-P185 ($b.index -eq $i -and $b.tid -gt 0 -and $b.buffer -in @(0,1) -and $b.start -ge $l.armed -and $b.end -ge $b.start -and $b.end -le $l.stop_after) 'CALLBACK_ORDER_OR_BOUNDS'
    Assert-P185 ($b.start -ge $a.markers[0].after -and $b.end -le $a.markers[1].before) 'CALLBACK_OUTSIDE_CALIBRATION'
    $thread=[long]$b.tid
    Assert-P185 ($byThread.ContainsKey($thread) -and $bySwitch.ContainsKey($thread)) 'TID_OWNERSHIP_MISMATCH'
    $ts=@($byThread[$thread]);$sw=@($bySwitch[$thread]);$rd=@();if($byReady.ContainsKey($thread)){$rd=@($byReady[$thread])}
    $life=@($ts | Where-Object {[long]$_.tid -eq $b.tid -and [long]$_.qpc -le $b.start} | Sort-Object {[long]$_.qpc})
    Assert-P185 ($life.Count -gt 0 -and [long]$life[-1].pid -eq $a.pid -and [int]$life[-1].opcode -in @(1,3)) 'TID_OWNERSHIP_MISMATCH'
    Assert-P185 (@($ts | Where-Object {[long]$_.tid -eq $b.tid -and [long]$_.qpc -gt $b.start -and [long]$_.qpc -lt $b.end -and [int]$_.opcode -in @(1,2,4)}).Count -eq 0) 'TID_REUSE_DURING_CALLBACK'
    $duration=$b.end-$b.start;$durations+=($duration*1e6/$f)
    if($duration -gt [Math]::Floor(1.0*$a.frames*$f/$a.sample_rate)){$overruns++}
    $window=Get-P185Window $sw $rd $b.tid $b.start $b.end
    $callbackRows+=@{index=$i;tid=$b.tid;wall_us=$duration*1e6/$f;off_cpu_us=$window.off_ticks*1e6/$f;scheduled_upper_bound_us=($duration-$window.off_ticks)*1e6/$f;schedule_complete=$window.complete}
    if($null -ne $prior){
      Assert-P185 ($b.start -ge $prior.end) 'OVERLAPPING_CALLBACKS'
      $spacing=$b.start-$prior.start;$endToStart=$b.start-$prior.end
      $spacings+=($spacing*1e6/$f);$idle+=($endToStart*1e6/$f)
      $quantizedGap=([Math]::Floor($b.start*1e9/$f)-[Math]::Floor($prior.start*1e9/$f)) -gt 2*[Math]::Floor(1e9*$a.frames/$a.sample_rate)
      Assert-P185 ($b.gap -eq $quantizedGap) 'GAP_FLAG_MISMATCH'
      if($quantizedGap){
        $w=Get-P185Window $sw $rd $b.tid $prior.end $b.start
        $near=@($activity | Where-Object {[long]$_.qpc -ge $prior.end -and [long]$_.qpc -le $b.start})
        $gaps+=@{index=$i;tid=$b.tid;previous_start_to_start_us=$spacing*1e6/$f;previous_end_to_start_us=$endToStart*1e6/$f;previous_callback_wall_us=($prior.end-$prior.start)*1e6/$f;ready_not_scheduled_us=$w.ready_ticks*1e6/$f;waiting_us=$w.waiting_ticks*1e6/$f;unknown_us=$w.unknown_ticks*1e6/$f;schedule_complete=$w.complete;nearby_kernel_or_provider_events=$near.Count;causal_attribution='INCONCLUSIVE'}
      }
    }
    $prior=$b
  }
  Assert-P185 ($gaps.Count -eq $a.gap_count -and $overruns -eq $a.execution_overruns) 'STRICT_COUNTER_MISMATCH'
  $bad=@($a.callbacks | Where-Object {-not $_.ok}).Count
  Assert-P185 ($bad -eq $a.process_failures) 'DSP_COUNTER_MISMATCH'
  $clean=($gaps.Count -eq 0 -and $overruns -eq 0 -and $a.xrun_messages -eq 0 -and $bad -eq 0 -and $a.rate_changes -eq 0)
  Assert-P185 (($c.child_exit -eq 0) -eq $clean) 'EXIT_GATE_MISMATCH'
  @{
    correlation='VERIFIED_QPC_BRACKETS_PID_TID_NONCE_SHA';strict_full_run=if($clean){'CLEAN_IN_THIS_RUN'}else{'NO_GO'}
    cause='INCONCLUSIVE';physical_asio_run='OBSERVED_REFERENCE_ONLY';awe_realtime='NOT_RUN';release_approved=$false
    callbacks=$a.actual;sample_rate=$a.sample_rate;frames=$a.frames;pid=$a.pid
    lifecycle_observation=@{iasio_start_wall_us=($l.start_after-$l.start_before)*1e6/$f;first_callback_after_start_call_us=($a.callbacks[0].start-$l.start_before)*1e6/$f;first_callback_before_start_return=($a.callbacks[0].start -lt $l.start_after);iasio_stop_wall_us=($l.stop_after-$l.stop_before)*1e6/$f;calibration_max_bracket_us=[Math]::Max(($a.markers[0].after-$a.markers[0].before),($a.markers[1].after-$a.markers[1].before))*1e6/$f}
    callback_wall=Get-P185Statistics $durations;start_spacing=Get-P185Statistics $spacings;end_to_start=Get-P185Statistics $idle
    gaps=$gaps;callback_intervals=$callbackRows;providers=$c.providers
    limitation='Scheduled time includes host, driver and interrupt work; it is not isolated DSP CPU time. Provider proximity is not causation. Pre-armed callbacks are unobserved. No warmup exclusion.'
  }
}

. (Join-Path $PSScriptRoot 'P185-DIAGNOSTICS.ps1')
