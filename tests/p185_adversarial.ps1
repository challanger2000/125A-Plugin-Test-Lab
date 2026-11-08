#requires -Version 5.1
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$Evidence)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../tools/p185/P185-ANALYZE.ps1')
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null
$dir=Join-Path $Evidence 'synthetic-never-hardware';New-Item -ItemType Directory -Force $dir | Out-Null
$nonce='0123456789abcdef0123456789abcdef0123456789abcdef';$sha='a'*64;$product='b'*64;$source='c'*40;$clsid='{00000000-0000-0000-0000-000000000001}'
$trace=@{start=0;stop=0;open=0;process=0;events_lost=0;buffers_lost=0;session_events_lost=0;session_buffers_lost=0;frequency=1000000;clock=1}
$baselineCapture=@{schema='125a-p185-native-etw-v1';source_sha=$source;nonce=$nonce;child_pid=70;child_exit=0;timeout=$false;marker_enable=0;decode_errors=0;cswitches=1;kernel=$trace;user=$trace;providers=@()}
$callbacks=@();for($i=0;$i -lt 100;$i++){$callbacks+=@{index=$i;tid=42;buffer=$i%2;start=100000+$i*12000;end=100100+$i*12000;ok=$true;gap=$false}}
$baselineAsio=@{schema='125a-p185-asio-observation-v1';source_sha=$source;nonce=$nonce;pid=70;qpc_frequency=1000000;executor_sha256=$sha;product_sha256=$product;driver_clsid=$clsid;binary_identity_after=$true;sample_rate=44100;frames=512;requested=100;actual=100;complete=$true;gap_count=0;execution_overruns=0;xrun_messages=0;process_failures=0;rate_changes=0;markers=@(@{sequence=1;before=10;after=30;result=0;tid=40},@{sequence=2;before=2000010;after=2000030;result=0;tid=40});lifecycle=@{create_before=100;create_after=200;active=300;processing=400;armed=500;start_before=600;start_after=20000;stop_before=1900000;stop_after=1950000};callbacks=$callbacks}
$baseC=$baselineCapture | ConvertTo-Json -Depth 15;$baseA=$baselineAsio | ConvertTo-Json -Depth 15
function Reset-Fixture {
  $baseC | Set-Content (Join-Path $dir 'capture.json');$baseA | Set-Content (Join-Path $dir 'asio.json')
  "qpc,pid,tid,nonce,sequence`n20,70,40,$nonce,1`n2000020,70,40,$nonce,2" | Set-Content (Join-Path $dir 'markers.csv')
  "qpc,cpu,old_tid,new_tid,old_state,wait_reason`n1000,0,0,42,1,0" | Set-Content (Join-Path $dir 'cswitch.csv')
  "qpc,opcode,pid,tid`n900,1,70,42`n2100000,2,70,42" | Set-Content (Join-Path $dir 'threads.csv')
  'qpc,tid,cpu' | Set-Content (Join-Path $dir 'ready.csv')
  'qpc,cpu,provider,event_id,opcode,initial_time_valid,initial_time' | Set-Content (Join-Path $dir 'activity.csv')
}
function Analyze { Get-P185Analysis $dir $nonce $sha $product $clsid $source }
$tests=[Collections.Generic.List[object]]::new()
Reset-Fixture
$good=Analyze
Assert-P185 ($good.strict_full_run -ceq 'CLEAN_IN_THIS_RUN' -and $good.cause -ceq 'INCONCLUSIVE' -and $good.awe_realtime -ceq 'NOT_RUN' -and -not $good.release_approved -and $good.callback_wall.median_us -eq 100 -and $good.start_spacing.p99_us -eq 12000) 'POSITIVE_ORACLE_FAILED'
Assert-P185 ($good.lifecycle_observation.iasio_start_wall_us -eq 19400 -and $good.lifecycle_observation.first_callback_after_start_call_us -eq 99400 -and -not $good.lifecycle_observation.first_callback_before_start_return -and $good.lifecycle_observation.calibration_max_bracket_us -eq 20) 'LIFECYCLE_NUMERIC_ORACLE_FAILED'
$tests.Add(@{case='independent numeric positive';status='PASS';hardware='NOT_RUN'})
function Reject([string]$Name,[scriptblock]$Mutate,[string]$Expected) {
  Reset-Fixture
  $c=Read-P185Json (Join-Path $dir 'capture.json');$a=Read-P185Json (Join-Path $dir 'asio.json')
  & $Mutate
  $c | ConvertTo-Json -Depth 15 | Set-Content (Join-Path $dir 'capture.json')
  $a | ConvertTo-Json -Depth 15 | Set-Content (Join-Path $dir 'asio.json')
  $errorCode='';try{$null=Analyze}catch{$errorCode=$_.Exception.Message}
  Assert-P185 ($errorCode -ceq $Expected) ('NEGATIVE_DID_NOT_KILL_'+$Name+'_'+$errorCode)
  $tests.Add(@{case=$Name;status='PASS';rejected=$errorCode;hardware='NOT_RUN'})
}
Reject 'source sha' {$a.source_sha='d'*40} 'SOURCE_SHA_MISMATCH'
Reject 'nonce' {$a.nonce='f'*48} 'NONCE_MISMATCH'
Reject 'sha' {$a.product_sha256='c'*64} 'SHA_MISMATCH'
Reject 'binary changed during audio' {$a.binary_identity_after=$false} 'SHA_MISMATCH'
Reject 'driver' {$a.driver_clsid='wrong'} 'DRIVER_MISMATCH'
Reject 'pid' {$c.child_pid=71} 'PID_MISMATCH_OR_TIMEOUT'
Reject 'timeout' {$c.timeout=$true} 'PID_MISMATCH_OR_TIMEOUT'
Reject 'truncated kernel tail' {"qpc,opcode,pid,tid`n900,1,70,42" | Set-Content (Join-Path $dir 'threads.csv')} 'KERNEL_END_COVERAGE_MISSING'
Reject 'wrong tid' {$a.callbacks[0].tid=99} 'TID_OWNERSHIP_MISMATCH'
Reject 'wrong owner' {"qpc,opcode,pid,tid`n900,1,71,42`n2100000,2,70,42" | Set-Content (Join-Path $dir 'threads.csv')} 'TID_OWNERSHIP_MISMATCH'
Reject 'thread terminated' {Add-Content (Join-Path $dir 'threads.csv') '99000,2,70,42'} 'TID_OWNERSHIP_MISMATCH'
Reject 'thread reused' {Add-Content (Join-Path $dir 'threads.csv') '100050,1,71,42'} 'TID_REUSE_DURING_CALLBACK'
Reject 'qpc frequency' {$c.kernel.frequency=1000001} 'QPC_CLOCK_MISMATCH'
Reject 'qpc wrong clock' {$c.user.clock=2} 'QPC_CLOCK_MISMATCH'
Reject 'qpc offset' {$a.markers[0].before=100;$a.markers[0].after=120} 'QPC_CALIBRATION_MISMATCH'
Reject 'qpc uncertainty' {$a.markers[0].after=50000} 'QPC_CALIBRATION_MISMATCH'
Reject 'marker missing' {"qpc,pid,tid,nonce,sequence`n20,70,40,$nonce,1" | Set-Content (Join-Path $dir 'markers.csv')} 'MISSING_CALIBRATION'
Reject 'marker nonce' {(Get-Content (Join-Path $dir 'markers.csv')) -replace $nonce,('f'*48) | Set-Content (Join-Path $dir 'markers.csv')} 'MARKER_IDENTITY_MISMATCH'
Reject 'marker pid' {(Get-Content (Join-Path $dir 'markers.csv')) -replace ',70,40,',',71,40,' | Set-Content (Join-Path $dir 'markers.csv')} 'MARKER_IDENTITY_MISMATCH'
Reject 'permission denied' {$c.kernel.start=5} 'ETW_NOT_AVAILABLE'
Reject 'provider absent' {$c.marker_enable=1168} 'ETW_MARKER_ENABLE_FAILED'
Reject 'events lost' {$c.kernel.events_lost=1} 'ETW_LOSS'
Reject 'buffers lost' {$c.user.buffers_lost=1} 'ETW_LOSS'
Reject 'live loss' {$c.kernel.session_events_lost=1} 'ETW_LOSS'
Reject 'undecodable schema' {$c.decode_errors=1} 'ETW_DECODE_ERRORS'
Reject 'callback overflow' {$a.complete=$false} 'CALLBACK_LOSS'
Reject 'truncated switch CSV' {$c.cswitches=2} 'SWITCH_COUNT_MISMATCH'
Reject 'lifecycle reversed' {$a.lifecycle.stop_before=100} 'LIFECYCLE_ORDER'
Reject 'overlapping callbacks' {$a.callbacks[1].start=$a.callbacks[0].end-1} 'OVERLAPPING_CALLBACKS'
Reject 'false strict clean' {$c.child_exit=1} 'EXIT_GATE_MISMATCH'
Reject 'gap count altered' {$a.gap_count=1} 'STRICT_COUNTER_MISMATCH'
# A conspicuous USB name/timestamp must never turn coincidence into a causal verdict.
Reset-Fixture
'100050,0,Microsoft-Windows-USB-FalseCause,999,1,0,0' | Add-Content (Join-Path $dir 'activity.csv')
$r=Analyze;Assert-P185 ($r.cause -ceq 'INCONCLUSIVE' -and -not $r.release_approved) 'FALSE_USB_ATTRIBUTION'
$tests.Add(@{case='false USB attribution';status='PASS';hardware='NOT_RUN'})
# Golden scheduler intervals: 100100..150000 ready (49,900 ticks), no actual DSP overload.
$a=Read-P185Json (Join-Path $dir 'asio.json');$c=Read-P185Json (Join-Path $dir 'capture.json')
for($i=1;$i -lt 100;$i++){$a.callbacks[$i].start+=50000;$a.callbacks[$i].end+=50000}
$a.callbacks[1].gap=$true;$a.gap_count=1;$c.child_exit=1;$c.cswitches=3
$a | ConvertTo-Json -Depth 15 | Set-Content (Join-Path $dir 'asio.json');$c | ConvertTo-Json -Depth 15 | Set-Content (Join-Path $dir 'capture.json')
Add-Content (Join-Path $dir 'cswitch.csv') "100100,0,42,0,1,0`n150000,0,0,42,1,0"
$r=Analyze
Assert-P185 ($r.strict_full_run -ceq 'NO_GO' -and $r.gaps.Count -eq 1 -and $r.gaps[0].ready_not_scheduled_us -eq 49900 -and $r.gaps[0].previous_start_to_start_us -eq 62000 -and $r.gaps[0].previous_end_to_start_us -eq 61900 -and $r.cause -ceq 'INCONCLUSIVE') 'SCHEDULER_INTERVAL_ORACLE_FAILED'
$tests.Add(@{case='ready interval and strict startup gap retained';status='PASS';hardware='NOT_RUN'})
# Same delay, waiting instead of ready: cannot be scheduler starvation proof.
(Get-Content (Join-Path $dir 'cswitch.csv')) -replace '42,0,1,0','42,0,5,0' | Set-Content (Join-Path $dir 'cswitch.csv')
$r=Analyze
Assert-P185 ($r.gaps[0].ready_not_scheduled_us -eq 0 -and $r.gaps[0].waiting_us -eq 49900 -and $r.cause -ceq 'INCONCLUSIVE') 'FALSE_SCHEDULER_ATTRIBUTION'
$tests.Add(@{case='wait is not ready starvation';status='PASS';hardware='NOT_RUN'})
# ReadyThread splits a documented wait into 10ms wait and 39.9ms ready.
Add-Content (Join-Path $dir 'ready.csv') '110100,42,0'
$r=Analyze
Assert-P185 ($r.gaps[0].ready_not_scheduled_us -eq 39900 -and $r.gaps[0].waiting_us -eq 10000) 'READY_SPLIT_ORACLE_FAILED'
$tests.Add(@{case='ready-thread transition';status='PASS';hardware='NOT_RUN'})
$tests | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $Evidence 'P185-ADVERSARIAL.json')
Write-Host ('[PASS] P185 '+$tests.Count+' adversarial/positive tests; synthetic fixtures, physical ASIO NOT RUN')
