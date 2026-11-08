#requires -Version 5.1
<#
P106: independently verify the installed VST3 identity and hand it to the
existing P74 native VST3 inventory/audio-state test. No silent release GO.
The installer report must be from the just-run approved P106 installer.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$InstallationReport,
  [Parameter(Mandatory=$true)][string]$Vst3Bundle,
  [Parameter(Mandatory=$true)][string]$InstalledModule,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedModuleSha256,
  [Parameter(Mandatory=$true)][string]$GuiHost,
  [Parameter(Mandatory=$true)][string]$PythonExecutable,
  [Parameter(Mandatory=$true)][string]$OutputFolder,
  [string]$AudioHost = '',
  [string]$StressHost = '',
  [string]$ExpectedBundleManifest = '',
  [string]$ExpectedBundleManifestSha256 = '',
  [switch]$RunTechnicalBaseline
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$result = @{
  schema = '125a-p106-postinstall-vst3-qa-v1'
  status = 'FAIL'
  installation_evidence_checked = $false
  installed_module_sha256_verified = $false
  whole_bundle_integrity = 'NOT VERIFIED'
  whole_bundle_file_count = 0
  p74_executed = $false
  p74_result = 'NOT RUN'
  vst3_technical_baseline = 'NOT RUN'
  commercial_daw_verified = $false
  release_approved = $false
  faults = @()
}
$destination = [IO.Path]::GetFullPath($OutputFolder)
function Produce {
  $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $destination 'P106-POSTINSTALL-VST3-RESULT.json') -Encoding UTF8
  Write-Output ($result | ConvertTo-Json -Depth 6)
}
try {
  if (Test-Path -LiteralPath $destination) { throw 'OutputFolder must be fresh; cannot reuse prior QA evidence' }
  New-Item -ItemType Directory -Path $destination -Force | Out-Null
  $reportFile = (Resolve-Path -LiteralPath $InstallationReport -ErrorAction Stop).ProviderPath
  $install = Get-Content -LiteralPath $reportFile -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($install.schema -ne '125a-p106-installer-evidence-v1' -or
      $install.status -ne 'INSTALLATION_ARTIFACT_VERIFIED' -or
      $install.mode -ne 'Run' -or
      $install.installer_executed -ne $true -or
      $install.installer_verified -ne $true -or
      $install.expected_artifact_verified -ne $true -or
      $install.release_approved -ne $false -or
      $install.vst3_qa_executed -ne $false -or
      $install.commercial_daw_verified -ne $false -or
      $install.faults.Count -ne 0 -or
      $install.exit_code -ne 0 -or
      $install.installer_sha256 -notmatch '^[a-f0-9]{64}$' -or
      $install.expected_artifact_sha256 -notmatch '^[a-f0-9]{64}$') {
    throw 'P106 installation report is not verified genuine installation evidence'
  }
  $installerPath = (Resolve-Path -LiteralPath $install.installer_path -ErrorAction Stop).ProviderPath
  if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf) -or
      (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $install.installer_sha256) {
    throw 'Installer binary does not match the originally executed installer SHA256'
  }
  $bundle = (Resolve-Path -LiteralPath $Vst3Bundle -ErrorAction Stop).ProviderPath
  $module = (Resolve-Path -LiteralPath $InstalledModule -ErrorAction Stop).ProviderPath
  if (-not (Test-Path -LiteralPath $bundle -PathType Container) -or
      [IO.Path]::GetExtension($bundle).ToLowerInvariant() -ne '.vst3') {
    throw 'Installed VST3 must be an actual bundle directory'
  }
  if (-not (Test-Path -LiteralPath $module -PathType Leaf) -or
      [IO.Path]::GetExtension($module).ToLowerInvariant() -ne '.vst3') {
    throw 'Installed VST3 module binary missing'
  }
  $expectedModuleLocation = [IO.Path]::GetFullPath(
      (Join-Path $bundle ('Contents\x86_64-win\' + [IO.Path]::GetFileName($bundle))))
  if (-not [string]::Equals($module,$expectedModuleLocation,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Installed module does not match standard Windows VST3 bundle location/name'
  }
  if (-not [string]::Equals([IO.Path]::GetFullPath($install.expected_artifact),$module,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'P106 installation proof belongs to a different installed module path'
  }
  $actualHash = (Get-FileHash -LiteralPath $module -Algorithm SHA256).Hash.ToLowerInvariant()
  $wanted = $ExpectedModuleSha256.ToLowerInvariant()
  if ($actualHash -cne $wanted -or $install.expected_artifact_sha256 -cne $wanted) {
    throw 'Installed VST3 bytes differ from independently expected/P106 installed artifact SHA256'
  }
  # P109 complete bundle identity, not only the binary module. Require
  # a separately pinned source manifest to assert whole-bundle integrity.
  if ($ExpectedBundleManifest -or $ExpectedBundleManifestSha256) {
    if (-not $ExpectedBundleManifest -or
        $ExpectedBundleManifestSha256 -notmatch '^[a-fA-F0-9]{64}
  $result.installed_module_sha256_verified = $true
  $result.installed_module_sha256 = $actualHash
  $gui = (Resolve-Path -LiteralPath $GuiHost -ErrorAction Stop).ProviderPath
  $python = (Resolve-Path -LiteralPath $PythonExecutable -ErrorAction Stop).ProviderPath
  $runner = Join-Path $PSScriptRoot 'run_universal_qa.py'
  if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'P74 native VST3 QA runner missing' }
  $qaOut = Join-Path $destination 'P74-native'
  $arguments = @($runner,'--plugin',$bundle,'--gui-host',$gui,'--out',$qaOut)
  if ($RunTechnicalBaseline) {
    if (-not $AudioHost -or -not $StressHost) {
      throw 'Technical VST3 gate requires actual audio and stress hosts'
    }
    $audio = (Resolve-Path -LiteralPath $AudioHost -ErrorAction Stop).ProviderPath
    $stress = (Resolve-Path -LiteralPath $StressHost -ErrorAction Stop).ProviderPath
    $arguments += @('--audio-host',$audio,'--stress-host',$stress,'--run-technical-baseline')
  }
  $result.p74_executed = $true
  & $python @arguments | Out-Null
  $code = $LASTEXITCODE
  $qaFile = Join-Path $qaOut 'UNIVERSAL-QA-RESULT.json'
  if ($code -ne 0 -or -not (Test-Path -LiteralPath $qaFile -PathType Leaf)) {
    throw 'P74 subprocess failed or did not produce native VST3 evidence'
  }
  $qa = Get-Content -LiteralPath $qaFile -Raw -Encoding UTF8 | ConvertFrom-Json
  $acceptable = if ($RunTechnicalBaseline) { 'TECHNICAL_BASELINE_PASS' } else { 'INVENTORY_COMPLETE' }
  if ($qa.schema -ne '125a-universal-vst3-qa-pipeline-v1' -or
      $qa.status -ne $acceptable -or
      $qa.verified_module_sha256 -cne $actualHash -or
      $qa.verified_gui_host_sha256 -cne (Get-FileHash -LiteralPath $gui -Algorithm SHA256).Hash.ToLowerInvariant() -or
      $qa.discovery -ne 'PASS' -or
      $qa.faults.Count -ne 0 -or
      $qa.real_asio_hardware -ne 'NOT RUN' -or
      $qa.commercial_daw_session -ne 'NOT RUN' -or
      $qa.approved_product_cases -ne 'NOT DECLARED' -or
      $qa.required_feature_coverage -ne 'NOT DECLARED' -or
      $qa.release_approved -ne $false) {
    throw 'P74 independent native VST3 identity or acceptance disagrees'
  }
  if ($RunTechnicalBaseline -and $qa.native_technical -ne 'PASS') {
    throw 'P74 native technical VST3 checks not passed'
  }
  if ((Get-FileHash -LiteralPath $module -Algorithm SHA256).Hash.ToLowerInvariant() -cne $actualHash) {
    throw 'Installed VST3 changed while P74 inspected it'
  }
  # P109: preserve all-file proof across native P74 execution, not just
  # the main DLL. Re-run the independently pinned manifest comparison.
  if ($result.whole_bundle_integrity -eq 'VERIFIED') {
    $afterInventory = @(Get-ChildItem -LiteralPath $bundle -Recurse -Force -ErrorAction Stop)
    $afterFiles = @{}
    foreach ($entry in $afterInventory) {
      if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'P109 bundle changed to a reparse point during P74'
      }
      if ($entry.PSIsContainer) { continue }
      $relative = $entry.FullName.Substring($bundle.TrimEnd('\').Length + 1).Replace('\','/')
      $afterFiles[$relative.ToLowerInvariant()] = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($afterFiles.Count -ne $actualFiles.Count) { throw 'P109 bundle file set changed during P74' }
    foreach ($name in $actualFiles.Keys) {
      if (-not $afterFiles.ContainsKey($name) -or $afterFiles[$name] -cne $actualFiles[$name]) {
        throw 'P109 installed VST3 resource mutated during P74'
      }
    }
    if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $approvedManifestSha) {
      throw 'P109 expected source manifest changed during P74'
    }
  }
  $result.p74_result = $qa.status
  $result.vst3_technical_baseline = if ($RunTechnicalBaseline) { 'PASS' } else { 'NOT RUN' }
  $result.status = if ($RunTechnicalBaseline) { 'INSTALL_AND_NATIVE_TECHNICAL_PASS' } else { 'INSTALL_AND_NATIVE_INVENTORY_COMPLETE' }
  Produce
  exit 0
} catch {
  $result.faults = @([string]$_.Exception.Message)
  if (Test-Path -LiteralPath $destination -PathType Container) { Produce }
  exit 1
}
) {
      throw 'P109 whole-bundle proof needs both manifest path and independently expected SHA256'
    }
    $manifestPath = (Resolve-Path -LiteralPath $ExpectedBundleManifest -ErrorAction Stop).ProviderPath
    $approvedManifestSha = $ExpectedBundleManifestSha256.ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $approvedManifestSha) {
      throw 'P109 independently approved source manifest SHA256 mismatch'
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.schema -ne '125a-vst3-whole-bundle-sha256-v1' -or
        $null -eq $manifest.files -or @($manifest.files).Count -lt 1 -or
        @($manifest.files).Count -gt 3000) {
      throw 'P109 expected bundle manifest has invalid schema or count'
    }
    $base = Get-Item -LiteralPath $bundle -Force
    if (($base.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw 'P109 installed VST3 directory uses a reparse point'
    }
    $inventory = @(Get-ChildItem -LiteralPath $bundle -Recurse -Force -ErrorAction Stop)
    if ($inventory.Count -gt 3000) { throw 'P109 installed bundle exceeds 3000 entries' }
    $actualFiles = @{}
    foreach ($entry in $inventory) {
      if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'P109 installed bundle contains a reparse point/symlink'
      }
      if ($entry.PSIsContainer) { continue }
      $relative = $entry.FullName.Substring($bundle.TrimEnd('\').Length + 1).Replace('\','/')
      $key = $relative.ToLowerInvariant()
      if ($actualFiles.ContainsKey($key)) { throw 'P109 duplicate installed bundle resource paths' }
      $actualFiles[$key] = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($actualFiles.Count -ne @($manifest.files).Count) {
      throw 'P109 installed VST3 bundle has missing or extra resource files'
    }
    $seen = @{}
    foreach ($file in @($manifest.files)) {
      if ($null -eq $file.path -or $file.path -notmatch '^[^\\/].*' -or
          $file.path -match '(^|/)\.\.(/|$)' -or
          $file.sha256 -notmatch '^[a-f0-9]{64}
  $result.installed_module_sha256_verified = $true
  $result.installed_module_sha256 = $actualHash
  $gui = (Resolve-Path -LiteralPath $GuiHost -ErrorAction Stop).ProviderPath
  $python = (Resolve-Path -LiteralPath $PythonExecutable -ErrorAction Stop).ProviderPath
  $runner = Join-Path $PSScriptRoot 'run_universal_qa.py'
  if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'P74 native VST3 QA runner missing' }
  $qaOut = Join-Path $destination 'P74-native'
  $arguments = @($runner,'--plugin',$bundle,'--gui-host',$gui,'--out',$qaOut)
  if ($RunTechnicalBaseline) {
    if (-not $AudioHost -or -not $StressHost) {
      throw 'Technical VST3 gate requires actual audio and stress hosts'
    }
    $audio = (Resolve-Path -LiteralPath $AudioHost -ErrorAction Stop).ProviderPath
    $stress = (Resolve-Path -LiteralPath $StressHost -ErrorAction Stop).ProviderPath
    $arguments += @('--audio-host',$audio,'--stress-host',$stress,'--run-technical-baseline')
  }
  $result.p74_executed = $true
  & $python @arguments | Out-Null
  $code = $LASTEXITCODE
  $qaFile = Join-Path $qaOut 'UNIVERSAL-QA-RESULT.json'
  if ($code -ne 0 -or -not (Test-Path -LiteralPath $qaFile -PathType Leaf)) {
    throw 'P74 subprocess failed or did not produce native VST3 evidence'
  }
  $qa = Get-Content -LiteralPath $qaFile -Raw -Encoding UTF8 | ConvertFrom-Json
  $acceptable = if ($RunTechnicalBaseline) { 'TECHNICAL_BASELINE_PASS' } else { 'INVENTORY_COMPLETE' }
  if ($qa.schema -ne '125a-universal-vst3-qa-pipeline-v1' -or
      $qa.status -ne $acceptable -or
      $qa.verified_module_sha256 -cne $actualHash -or
      $qa.verified_gui_host_sha256 -cne (Get-FileHash -LiteralPath $gui -Algorithm SHA256).Hash.ToLowerInvariant() -or
      $qa.discovery -ne 'PASS' -or
      $qa.faults.Count -ne 0 -or
      $qa.real_asio_hardware -ne 'NOT RUN' -or
      $qa.commercial_daw_session -ne 'NOT RUN' -or
      $qa.approved_product_cases -ne 'NOT DECLARED' -or
      $qa.required_feature_coverage -ne 'NOT DECLARED' -or
      $qa.release_approved -ne $false) {
    throw 'P74 independent native VST3 identity or acceptance disagrees'
  }
  if ($RunTechnicalBaseline -and $qa.native_technical -ne 'PASS') {
    throw 'P74 native technical VST3 checks not passed'
  }
  if ((Get-FileHash -LiteralPath $module -Algorithm SHA256).Hash.ToLowerInvariant() -cne $actualHash) {
    throw 'Installed VST3 changed while P74 inspected it'
  }
  $result.p74_result = $qa.status
  $result.vst3_technical_baseline = if ($RunTechnicalBaseline) { 'PASS' } else { 'NOT RUN' }
  $result.status = if ($RunTechnicalBaseline) { 'INSTALL_AND_NATIVE_TECHNICAL_PASS' } else { 'INSTALL_AND_NATIVE_INVENTORY_COMPLETE' }
  Produce
  exit 0
} catch {
  $result.faults = @([string]$_.Exception.Message)
  if (Test-Path -LiteralPath $destination -PathType Container) { Produce }
  exit 1
}
) {
        throw 'P109 invalid path/hash within expected bundle manifest'
      }
      $key = ([string]$file.path).ToLowerInvariant()
      if ($seen.ContainsKey($key)) { throw 'P109 duplicate source manifest resource entry' }
      $seen[$key] = $true
      if (-not $actualFiles.ContainsKey($key) -or $actualFiles[$key] -cne $file.sha256) {
        throw 'P109 installed VST3 resource differs from approved source bundle'
      }
    }
    $result.whole_bundle_integrity = 'VERIFIED'
    $result.whole_bundle_file_count = $actualFiles.Count
    $result.whole_bundle_manifest_sha256 = $approvedManifestSha
  }
  $result.installation_evidence_checked = $true
  $result.installed_module_sha256_verified = $true
  $result.installed_module_sha256 = $actualHash
  $gui = (Resolve-Path -LiteralPath $GuiHost -ErrorAction Stop).ProviderPath
  $python = (Resolve-Path -LiteralPath $PythonExecutable -ErrorAction Stop).ProviderPath
  $runner = Join-Path $PSScriptRoot 'run_universal_qa.py'
  if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'P74 native VST3 QA runner missing' }
  $qaOut = Join-Path $destination 'P74-native'
  $arguments = @($runner,'--plugin',$bundle,'--gui-host',$gui,'--out',$qaOut)
  if ($RunTechnicalBaseline) {
    if (-not $AudioHost -or -not $StressHost) {
      throw 'Technical VST3 gate requires actual audio and stress hosts'
    }
    $audio = (Resolve-Path -LiteralPath $AudioHost -ErrorAction Stop).ProviderPath
    $stress = (Resolve-Path -LiteralPath $StressHost -ErrorAction Stop).ProviderPath
    $arguments += @('--audio-host',$audio,'--stress-host',$stress,'--run-technical-baseline')
  }
  $result.p74_executed = $true
  & $python @arguments | Out-Null
  $code = $LASTEXITCODE
  $qaFile = Join-Path $qaOut 'UNIVERSAL-QA-RESULT.json'
  if ($code -ne 0 -or -not (Test-Path -LiteralPath $qaFile -PathType Leaf)) {
    throw 'P74 subprocess failed or did not produce native VST3 evidence'
  }
  $qa = Get-Content -LiteralPath $qaFile -Raw -Encoding UTF8 | ConvertFrom-Json
  $acceptable = if ($RunTechnicalBaseline) { 'TECHNICAL_BASELINE_PASS' } else { 'INVENTORY_COMPLETE' }
  if ($qa.schema -ne '125a-universal-vst3-qa-pipeline-v1' -or
      $qa.status -ne $acceptable -or
      $qa.verified_module_sha256 -cne $actualHash -or
      $qa.verified_gui_host_sha256 -cne (Get-FileHash -LiteralPath $gui -Algorithm SHA256).Hash.ToLowerInvariant() -or
      $qa.discovery -ne 'PASS' -or
      $qa.faults.Count -ne 0 -or
      $qa.real_asio_hardware -ne 'NOT RUN' -or
      $qa.commercial_daw_session -ne 'NOT RUN' -or
      $qa.approved_product_cases -ne 'NOT DECLARED' -or
      $qa.required_feature_coverage -ne 'NOT DECLARED' -or
      $qa.release_approved -ne $false) {
    throw 'P74 independent native VST3 identity or acceptance disagrees'
  }
  if ($RunTechnicalBaseline -and $qa.native_technical -ne 'PASS') {
    throw 'P74 native technical VST3 checks not passed'
  }
  if ((Get-FileHash -LiteralPath $module -Algorithm SHA256).Hash.ToLowerInvariant() -cne $actualHash) {
    throw 'Installed VST3 changed while P74 inspected it'
  }
  $result.p74_result = $qa.status
  $result.vst3_technical_baseline = if ($RunTechnicalBaseline) { 'PASS' } else { 'NOT RUN' }
  $result.status = if ($RunTechnicalBaseline) { 'INSTALL_AND_NATIVE_TECHNICAL_PASS' } else { 'INSTALL_AND_NATIVE_INVENTORY_COMPLETE' }
  Produce
  exit 0
} catch {
  $result.faults = @([string]$_.Exception.Message)
  if (Test-Path -LiteralPath $destination -PathType Container) { Produce }
  exit 1
}
