#requires -Version 5.1
[CmdletBinding()]param([string]$ExistingRun='', [switch]$CheckOnly,[switch]$Cancel)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=$PSScriptRoot;$out=$null;$report=$null
try {
  if(-not [Environment]::Is64BitProcess){throw 'WINDOWS_X64_REQUIRED'}
  $manifest=Get-Content -LiteralPath (Join-Path $root 'P186-PACKAGE.json') -Raw | ConvertFrom-Json
  if($manifest.schema -cne '125a-p186-offline-package-v1' -or $manifest.testlab_source -cnotmatch '^[0-9a-f]{40}$'){throw 'PACKAGE_MANIFEST_INVALID'}
  foreach($entry in $manifest.files.PSObject.Properties){
    if($entry.Name -match '(^[\\/]|\.\.|:)' -or $entry.Value -cnotmatch '^[0-9a-f]{64}$'){throw 'PACKAGE_ENTRY_INVALID'}
    $path=Join-Path $root $entry.Name
    if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value){throw 'PACKAGE_HASH_MISMATCH'}
  }
  foreach($required in @('P186-REANALYZE.ps1','P186-EXISTING-RUN.bat','P185-ANALYZE.ps1','P185-DIAGNOSTICS.ps1','P186-SOURCE-PROFILES.json')){
    if(-not $manifest.files.PSObject.Properties[$required]){throw 'PACKAGE_ENTRY_MISSING'}
  }
  . (Join-Path $root 'P185-ANALYZE.ps1')
  $profiles=Read-P185Json (Join-Path $root 'P186-SOURCE-PROFILES.json')
  Assert-P185 ($profiles.schema -ceq '125a-p186-source-profiles-v1' -and @($profiles.profiles).Count -gt 0 -and @($profiles.profiles).Count -le 32) 'SOURCE_PROFILE_INVALID'
  foreach($p in $profiles.profiles){
    Assert-P185 ($p.source_sha -cmatch '^[0-9a-f]{40}$' -and $p.executor_sha256 -cmatch '^[0-9a-f]{64}$' -and $p.product_sha256 -cmatch '^[0-9a-f]{64}$' -and $p.driver_clsid -match '^\{[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\}$') 'SOURCE_PROFILE_INVALID'
  }
  if($CheckOnly){Write-Host 'P186 Paketintegritaet geprueft. Kein Audio, kein ETW, kein Geraetestart.';exit 0}
  if($Cancel){Write-Host 'P186 abgebrochen. Keine Messung gestartet.';exit 2}
  if(-not $ExistingRun){
    Write-Host 'P186 liest den BEREITS GESPEICHERTEN P185-Lauf. Es wird nichts neu gemessen.'
    $ExistingRun=(Read-Host 'Vorhandener P185-LOCAL-Ordner oder RAW-LOCAL-ONLY-Ordner').Trim().Trim([char]34)
  }
  Assert-P185 (Test-Path -LiteralPath $ExistingRun -PathType Container) 'EXISTING_RUN_DIRECTORY_MISSING'
  $raw=$ExistingRun
  if(Test-Path -LiteralPath (Join-Path $raw 'RAW-LOCAL-ONLY') -PathType Container){$raw=Join-Path $raw 'RAW-LOCAL-ONLY'}
  $out=Join-Path $root ('P186-RESULT-'+[Guid]::NewGuid().ToString('N'));New-Item -ItemType Directory -Path $out | Out-Null
  # Select only among profiles pinned by the package, never invent pins from raw claims.
  $claimed=''
  foreach($name in @('capture.json','asio.json')){
    try{$limit=if($name -ceq 'capture.json'){4194304}else{8388608};$candidate=Read-P186Json (Join-Path $raw $name) $limit;$v=Get-P186Property $candidate 'source_sha';if($v -is [string] -and $v -cmatch '^[0-9a-f]{40}$'){$claimed=$v;break}}catch{}
  }
  $profile=$profiles.profiles[0]
  foreach($p in $profiles.profiles){if($p.source_sha -ceq $claimed){$profile=$p;break}}
  $inputHashes=[ordered]@{}
  foreach($name in @('capture.json','asio.json')){if(Test-Path -LiteralPath (Join-Path $raw $name) -PathType Leaf){$inputHashes[$name]=(Get-FileHash -LiteralPath (Join-Path $raw $name) -Algorithm SHA256).Hash.ToLowerInvariant()}}
  $assessment=Get-P186Assessment -Directory $raw -Profile $profile -Correlate
  $report=$assessment.report;$report.analyzer_source=$manifest.testlab_source;$report.input_sha256=$inputHashes
  foreach($name in $inputHashes.Keys){Assert-P185 ((Get-FileHash -LiteralPath (Join-Path $raw $name) -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $inputHashes[$name]) 'RAW_INPUT_CHANGED_DURING_ANALYSIS'}
  $report | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $out 'P186-ACCEPTANCE.json') -Encoding UTF8
  if($null -ne $assessment.analysis){$assessment.analysis | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $out 'P186-AGGREGATE-LOCAL.json') -Encoding UTF8}
  Write-Host ('P186: '+$report.physical_asio+'; Diagnose '+$report.error_code+'; Ursache INCONCLUSIVE, Release NO-GO.')
  Write-Host ('Ergebnis: '+(Join-Path $out 'P186-ACCEPTANCE.json'))
  Write-Host 'Keine neue Hardwaremessung. Keine ETL-/ROM-/SF2-Dateien uebertragen.'
  exit 3 # Evaluation is diagnostic; never an audio/release success code.
} catch {
  $code=[string]$_.Exception.Message;if($code -cnotmatch '^[A-Z0-9_]+$'){$code='LOCAL_TOOL_ERROR'}
  # If an assessment exists, preserve its already established attempt/reference grade.
  if($out){
    if($null -eq $report){$report=[ordered]@{schema='125a-p186-acceptance-v1';physical_asio='NOT_RUN';status='INCONCLUSIVE';cause='INCONCLUSIVE';awe_realtime='NOT_RUN';strict_full_run='UNVERIFIED';release_approved=$false;full_audit=$false}}
    if($code -ceq 'RAW_INPUT_CHANGED_DURING_ANALYSIS'){
      $report.physical_asio='REFERENCE_ATTEMPTED_UNVERIFIED';$report.reference_identity_validated=$false;$report.strict_full_run='UNVERIFIED';$report.correlation='NOT_VERIFIED'
      foreach($k in @('callbacks','successful_callbacks','requested_callbacks','gap_count','execution_overruns','process_failures')){if($report.Contains($k)){$report.Remove($k)}}
    }
    $oldCodes=Get-P186Property $report 'error_codes';$report.error_codes=@($oldCodes | Where-Object {$_ -and $_ -cne $code})+@($code)
    $report.error_code=$code;$report | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $out 'P186-ACCEPTANCE.json') -Encoding UTF8
  }
  Write-Host ('P186: '+$code+'. Keine Freigabe.');exit 3
}
