#requires -Version 5.1
[CmdletBinding()]param([switch]$CheckOnly,[switch]$Cancel)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$out=$null
function Invoke-P185Native([string]$Exe,[string[]]$Arguments,[string]$Log) {
  $prior=$ErrorActionPreference
  try {
    $ErrorActionPreference='Continue'
    & $Exe @Arguments 2>&1 | ForEach-Object { [string]$_ } | Tee-Object -FilePath $Log | Out-Host
    return [int]$LASTEXITCODE
  } finally {$ErrorActionPreference=$prior}
}
function New-P185Nonce {
  $bytes=New-Object byte[] 24;$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
  try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}
  ([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()
}
$report=@{schema='125a-p185-acceptance-v1';status='NOT_RUN';cause='INCONCLUSIVE';physical_asio='NOT_RUN';awe_realtime='NOT_RUN';strict_full_run='NOT_RUN';full_audit=$false;release_approved=$false;error_code='';testlab_source='';awe_source='';nonce=''}
function Save-P185 { $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $out 'P185-ACCEPTANCE.json') -Encoding UTF8 }
try {
  if(-not [Environment]::Is64BitProcess){throw 'WINDOWS_X64_REQUIRED'}
  $manifest=Get-Content -LiteralPath (Join-Path $root 'P185-PACKAGE.json') -Raw | ConvertFrom-Json
  if($manifest.schema -cne '125a-p185-package-v1' -or $manifest.testlab_source -cnotmatch '^[0-9a-f]{40}$'){throw 'INVALID_PACKAGE_MANIFEST'}
  $report.testlab_source=$manifest.testlab_source;$report.awe_source=$manifest.awe_source
  foreach($entry in $manifest.files.PSObject.Properties) {
    if($entry.Name -match '(^[\\/]|\.\.|:)' -or $entry.Value -cnotmatch '^[0-9a-f]{64}$'){throw 'INVALID_PACKAGE_ENTRY'}
    $path=Join-Path $root $entry.Name
    if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value){throw 'PACKAGE_HASH_MISMATCH'}
  }
  foreach($required in @('125A_Test_Lab_ETW.exe','125A_Test_Lab_Physical_ASIO.exe','125A_QA_ASIO_Reference_MIDI.vst3','P185-ANALYZE.ps1','P185-RUN.ps1','P185-ETW-ASIO.bat')){
    if(-not $manifest.files.PSObject.Properties[$required]){throw 'PACKAGE_REQUIRED_ENTRY_MISSING'}
  }
  . (Join-Path $root 'P185-ANALYZE.ps1')
  $out=Join-Path $root ('P185-LOCAL-'+[Guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $out | Out-Null
  $nonce=New-P185Nonce;$report.nonce=$nonce
  $etw=Join-Path $root '125A_Test_Lab_ETW.exe'
  $hostExe=Join-Path $root '125A_Test_Lab_Physical_ASIO.exe'
  $plugin=Join-Path $root '125A_QA_ASIO_Reference_MIDI.vst3'
  $drivers=@()
  if(Test-Path 'HKLM:\SOFTWARE\ASIO') {
    $drivers=@(Get-ChildItem 'HKLM:\SOFTWARE\ASIO' | ForEach-Object {
      $p=Get-ItemProperty -LiteralPath $_.PSPath
      if($p.PSObject.Properties['CLSID'] -and [string]$p.CLSID -match '^\{[0-9a-fA-F-]{36}\}$'){
        [PSCustomObject]@{Name=$_.PSChildName;CLSID=[string]$p.CLSID}
      }
    })
  }
  $rc=Invoke-P185Native $etw @('--capabilities',(Join-Path $out 'capabilities.json')) (Join-Path $out 'preflight.log')
  if($rc -ne 0){throw 'ETW_CAPABILITY_QUERY_FAILED'}
  $etwCaps=Read-P185Json (Join-Path $out 'capabilities.json')
  if($etwCaps.source_sha -cne $manifest.testlab_source){throw 'SOURCE_SHA_MISMATCH'}
  if($CheckOnly) {
    $report.error_code='CHECK_ONLY_NO_AUDIO_OR_CAPTURE';Save-P185
    Write-Host 'P185 Paketintegritaet geprueft. Audio und ETW-Aufzeichnung: NOT RUN.'
    exit 0
  }
  if($Cancel){$report.error_code='USER_CANCELLED';Save-P185;exit 2}
  if($drivers.Count -eq 0){throw 'ASIO_DRIVER_NOT_AVAILABLE'}
  Write-Host 'P185: eine Referenz-ASIO-Messung, ca. 12 Sekunden, 44.1 kHz / 512 Samples.'
  Write-Host 'DAW schliessen. Lautstaerke am Interface stark reduzieren. Ein leiser Testton wird ausgegeben.'
  Write-Host 'ETW kann System-/Treiberinformationen enthalten. Rohdateien bleiben lokal; keine automatische Uebertragung.'
  Write-Host 'Keine ROM-/SoundFont-Dateien erforderlich. Keine Installation oder Treiberaenderung.'
  for($i=0;$i -lt $drivers.Count;$i++){Write-Host ('  '+($i+1)+': '+$drivers[$i].Name)}
  $index=0
  if($drivers.Count -gt 1){$choice=Read-Host 'Nummer des physischen Interface-Treibers';$parsed=0
    if(-not [int]::TryParse($choice,[ref]$parsed) -or $parsed -lt 1 -or $parsed -gt $drivers.Count){throw 'INVALID_DRIVER_SELECTION'};$index=$parsed-1}
  $selected=$drivers[$index]
  $consent=Read-Host 'Nur wenn DAW geschlossen und Lautstaerke niedrig: START eingeben (sonst Abbruch)'
  if($consent -cne 'START'){$report.error_code='USER_CANCELLED';Save-P185;exit 2}
  $cap=Join-Path $out 'driver-capabilities.json'
  $rc=Invoke-P185Native $hostExe @('--asio-buffer-capabilities','--driver-name',$selected.Name,'--driver-clsid',$selected.CLSID,'--nonce',$nonce,'--out',$cap) (Join-Path $out 'driver-preflight.log')
  if($rc -ne 0){throw 'ASIO_CAPABILITIES_FAILED'}
  $caps=Read-P185Json $cap
  # Keep the documented P184 configuration. Never silently choose another buffer/rate.
  if($caps.nonce -cne $nonce -or $caps.executor_sha256 -cne $manifest.files.'125A_Test_Lab_Physical_ASIO.exe' -or $caps.driver_clsid -cne $selected.CLSID){throw 'CAPABILITY_IDENTITY_MISMATCH'}
  if($caps.selected_rate -ne 44100 -or 512 -lt $caps.minimum_frames -or 512 -gt $caps.maximum_frames){throw 'P184_CONFIGURATION_NOT_SUPPORTED'}
  $gran=[int]$caps.granularity
  if(($gran -gt 0 -and (512-$caps.minimum_frames)%$gran -ne 0) -or ($gran -eq 0 -and $caps.preferred_frames -ne 512)){throw 'P184_BUFFER_GRANULARITY_NOT_SUPPORTED'}
  $raw=Join-Path $out 'RAW-LOCAL-ONLY'
  $argv=@('--physical-asio-probe','--plugin',$plugin,'--driver-name',$selected.Name,'--driver-clsid',$selected.CLSID,'--rate','44100','--frames','512','--callbacks','1000','--nonce',$nonce,'--out',(Join-Path $raw 'strict-proof.json'),'--midi-note','48','--midi-out',(Join-Path $raw 'midi.json'),'--diagnostic-out',(Join-Path $raw 'diagnostic.json'),'--timing-trace-out',(Join-Path $raw 'p181.json'),'--p185-out',(Join-Path $raw 'asio.json'))
  $rc=Invoke-P185Native $etw (@('--capture',$raw,$nonce,'--',$hostExe)+$argv) (Join-Path $out 'capture.log')
  if(-not (Test-Path (Join-Path $raw 'capture.json'))){throw 'ETW_CAPTURE_FAILED'}
  $capture=Read-P185Json (Join-Path $raw 'capture.json')
  if($capture.kernel.start -ne 0 -or $capture.user.start -ne 0 -or $capture.marker_enable -ne 0){throw 'ETW_NOT_AVAILABLE'}
  if(-not (Test-Path (Join-Path $raw 'asio.json'))){throw 'ASIO_OBSERVATION_NOT_AVAILABLE'}
  $analysis=Get-P185Analysis $raw $nonce $manifest.files.'125A_Test_Lab_Physical_ASIO.exe' $manifest.files.'125A_QA_ASIO_Reference_MIDI.vst3' $selected.CLSID $manifest.testlab_source
  $analysis | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $out 'P185-AGGREGATE-LOCAL.json') -Encoding UTF8
  $report.status='INCONCLUSIVE';$report.physical_asio='OBSERVED_REFERENCE_ONLY';$report.strict_full_run=$analysis.strict_full_run
  $report.correlation=$analysis.correlation;$report.callbacks=$analysis.callbacks;$report.sample_rate=$analysis.sample_rate;$report.frames=$analysis.frames
  $report.gap_count=@($analysis.gaps).Count;$report.callback_wall=$analysis.callback_wall;$report.start_spacing=$analysis.start_spacing;$report.end_to_start=$analysis.end_to_start
  $report.native_exit=$rc;Save-P185
  Write-Host ('P185: '+$report.strict_full_run+'; Ursache INCONCLUSIVE. Keine Releasefreigabe.')
  Write-Host ('Rueckgabe: '+(Join-Path $out 'P185-ACCEPTANCE.json')+'; ETL und Rohdaten bleiben lokal.')
  exit 1 # A clean reference run cannot grant AWE real-time or release approval.
} catch {
  $code=[string]$_.Exception.Message
  if($code -cnotmatch '^[A-Z0-9_]+$'){$code='LOCAL_TOOL_ERROR'} # No private paths in acceptance JSON.
  $report.error_code=$code
  if($out){$report.status=if($code -eq 'ASIO_DRIVER_NOT_AVAILABLE'){'NOT_RUN'}else{'INCONCLUSIVE'};Save-P185}
  Write-Host ('P185: '+$code+'. Keine Abnahme; Details nur lokal.')
  exit 3
}
