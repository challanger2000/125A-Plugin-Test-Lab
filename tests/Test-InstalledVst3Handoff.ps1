#requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$WorkingRoot,
      [Parameter(Mandatory=$true)][string]$SourceBundle,
      [Parameter(Mandatory=$true)][string]$GuiHost,
      [Parameter(Mandatory=$true)][string]$AudioHost,
      [Parameter(Mandatory=$true)][string]$StressHost,
      [Parameter(Mandatory=$true)][string]$PythonExecutable)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$installerScript = Join-Path $PSScriptRoot 'Invoke-UniversalInstaller.ps1'
$postScript = Join-Path $PSScriptRoot 'Invoke-InstalledVst3QA.ps1'
$fixtureSource = Join-Path $PSScriptRoot 'p106_installer_fixture.cs'
New-Item -ItemType Directory -Path $WorkingRoot -Force | Out-Null
$fixture = Join-Path $WorkingRoot 'P106-Actual-Bundle-Install.exe'
Add-Type -Path $fixtureSource -OutputAssembly $fixture -OutputType ConsoleApplication -ErrorAction Stop
$bundle = (Resolve-Path -LiteralPath $SourceBundle).ProviderPath
$dest = Join-Path $WorkingRoot ([IO.Path]::GetFileName($bundle))
$sourceDll = Join-Path $bundle ('Contents\x86_64-win\' + [IO.Path]::GetFileName($bundle))
if (-not (Test-Path -LiteralPath $sourceDll -PathType Leaf)) { throw 'P106 actual source-built VST3 is missing its DLL' }
# One independent non-module resource is intentionally part of the
# source-built fixture. A DLL-only SHA must not be enough to prove it.
$sourceResource = Join-Path $bundle 'Contents\Resources\P109-fixture-resource.txt'
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($sourceResource)) -Force | Out-Null
$sourceBytes = [Text.Encoding]::ASCII.GetBytes('P109-approved-resource-content')
[IO.File]::WriteAllBytes($sourceResource, $sourceBytes)
$requiredEmptyDir = Join-Path $bundle 'Contents\Resources\P111-required-empty-directory'
New-Item -ItemType Directory -Path $requiredEmptyDir -Force | Out-Null
$sourceManifest = Join-Path $WorkingRoot 'P109-expected-source-manifest.json'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Get-Vst3BundleManifest.ps1') -Bundle $bundle -OutputFile $sourceManifest | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'P109 could not establish independent source bundle manifest' }
$manifestSha = (Get-FileHash -LiteralPath $sourceManifest -Algorithm SHA256).Hash.ToLowerInvariant()
$destModule = Join-Path $dest ('Contents\x86_64-win\' + [IO.Path]::GetFileName($bundle))
$moduleHash = (Get-FileHash -LiteralPath $sourceDll -Algorithm SHA256).Hash.ToLowerInvariant()
$installerHash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash.ToLowerInvariant()
$arguments = 'copydir "' + $bundle + '" "' + $dest + '"'
$installOut = Join-Path $WorkingRoot '09-real-vst3-bundle-installer'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installerScript -Mode Run -ApproveExecution -AllowUnsigned -Installer $fixture -ExpectedSha256 $installerHash -InstallerArguments $arguments -ExpectedArtifact $destModule -ExpectedArtifactSha256 $moduleHash -OutputFolder $installOut | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $destModule -PathType Leaf)) { throw 'P106 source-built VST3 bundle was not truly installed' }
$installedEmptyDir = Join-Path $dest 'Contents\Resources\P111-required-empty-directory'
if (-not (Test-Path -LiteralPath $installedEmptyDir -PathType Container)) {
  throw 'P111 discovered installer false PASS: required empty VST3 directory absent'
}
$report = Join-Path $installOut 'P106-INSTALLER-RESULT.json'
$qaOut = Join-Path $WorkingRoot '10-p74-actual-installed-vst3'
$baseArgs = @('-InstallationReport',$report,'-Vst3Bundle',$dest,
              '-InstalledModule',$destModule,'-ExpectedModuleSha256',$moduleHash,
              '-GuiHost',$GuiHost,'-PythonExecutable',$PythonExecutable,
              '-AudioHost',$AudioHost,'-StressHost',$StressHost,
              '-ExpectedBundleManifest',$sourceManifest,
              '-ExpectedBundleManifestSha256',$manifestSha,
              '-RunTechnicalBaseline')
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $postScript @baseArgs -OutputFolder $qaOut | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'P106 installed REAL VST3 did not pass P74 host and technical QA' }
$proof = Get-Content -LiteralPath (Join-Path $qaOut 'P106-POSTINSTALL-VST3-RESULT.json') -Raw | ConvertFrom-Json
if ($proof.status -ne 'INSTALL_AND_NATIVE_TECHNICAL_PASS' -or
    $proof.installed_module_sha256_verified -ne $true -or
    $proof.whole_bundle_integrity -ne 'VERIFIED' -or
    $proof.whole_bundle_file_count -lt 2 -or
    $proof.p74_executed -ne $true -or
    $proof.vst3_technical_baseline -ne 'PASS' -or
    $proof.release_approved -ne $false) { throw 'P106 bridge reported false-positive native technical evidence' }
Write-Host 'P106 installed actual source-built VST3 -> P74 actual native GUI, audio/state and API tests PASS'
$wrongSha = '0' * 64
$rejectOut = Join-Path $WorkingRoot '11-bad-installed-vst3-sha'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $postScript -InstallationReport $report -Vst3Bundle $dest -InstalledModule $destModule -ExpectedModuleSha256 $wrongSha -GuiHost $GuiHost -PythonExecutable $PythonExecutable -OutputFolder $rejectOut | Out-Null
if ($LASTEXITCODE -eq 0) { throw 'P106 bridge accepted wrong installed binary hash' }
$rejected = Get-Content -LiteralPath (Join-Path $rejectOut 'P106-POSTINSTALL-VST3-RESULT.json') -Raw | ConvertFrom-Json
if ($rejected.p74_executed -ne $false -or $rejected.status -ne 'FAIL') { throw 'P106 wrong installed hash incorrectly reached native host' }
Write-Host 'P106 independent wrong installed VST3 SHA rejected before P74 starts'

# P107: ordinary JSON is not cryptographic attestation. Refuse
# contradictory metadata *before* invoking native P74, even when
# the installed DLL itself has the right bytes.
$goodReport = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
$mutations = @(
  @{ id='bad-exit'; key='exit_code'; value=3010 },
  @{ id='false-audio'; key='vst3_qa_executed'; value=$true },
  @{ id='invented-daw'; key='commercial_daw_verified'; value=$true },
  @{ id='hidden-fault'; key='faults'; value=@('installer reported an error') },
  @{ id='installer-sha'; key='installer_sha256'; value=('0' * 64) },
  @{ id='artifact-sha'; key='expected_artifact_sha256'; value=('0' * 64) }
)
foreach ($mutation in $mutations) {
  $altered = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
  $altered.($mutation.key) = $mutation.value
  $fakePath = Join-Path $WorkingRoot ($mutation.id + '-tampered-install.json')
  $altered | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $fakePath -Encoding UTF8
  $negativeDir = Join-Path $WorkingRoot ('negative-' + $mutation.id)
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $postScript -InstallationReport $fakePath -Vst3Bundle $dest -InstalledModule $destModule -ExpectedModuleSha256 $moduleHash -GuiHost $GuiHost -PythonExecutable $PythonExecutable -OutputFolder $negativeDir | Out-Null
  if ($LASTEXITCODE -eq 0) { throw "P107 tampered $($mutation.id) wrongly passed" }
  $reject = Get-Content -LiteralPath (Join-Path $negativeDir 'P106-POSTINSTALL-VST3-RESULT.json') -Raw | ConvertFrom-Json
  if ($reject.status -ne 'FAIL' -or $reject.p74_executed -ne $false) {
    throw "P107 tampered $($mutation.id) reached native P74"
  }
  Write-Host "P107 tampered $($mutation.id) rejected before P74"
}

# P109 independently protect extra resources, not just executable bytes.
$installedResource = Join-Path $dest 'Contents\Resources\P109-fixture-resource.txt'
if (-not (Test-Path -LiteralPath $installedResource -PathType Leaf)) {
  throw 'P109 installer failed to include the expected resource file'
}
function Reject-Bundle([string]$case,[string]$manifestPath,[string]$manifestHash) {
  $testOut = Join-Path $WorkingRoot ('p109-' + $case)
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $postScript -InstallationReport $report -Vst3Bundle $dest -InstalledModule $destModule -ExpectedModuleSha256 $moduleHash -GuiHost $GuiHost -PythonExecutable $PythonExecutable -ExpectedBundleManifest $manifestPath -ExpectedBundleManifestSha256 $manifestHash -OutputFolder $testOut | Out-Null
  if ($LASTEXITCODE -eq 0) { throw "P109 modified $case falsely accepted" }
  $result = Get-Content -LiteralPath (Join-Path $testOut 'P106-POSTINSTALL-VST3-RESULT.json') -Raw | ConvertFrom-Json
  if ($result.status -ne 'FAIL' -or $result.p74_executed -ne $false -or
      $result.whole_bundle_integrity -eq 'VERIFIED') {
    throw "P109 modified $case reached native P74"
  }
  Write-Host "P109 $case rejected before native P74"
}
[IO.File]::WriteAllBytes($installedResource, [Text.Encoding]::ASCII.GetBytes('P109-corrupted'))
Reject-Bundle 'altered-resource' $sourceManifest $manifestSha
[IO.File]::WriteAllBytes($installedResource, $sourceBytes)
Remove-Item -LiteralPath $installedResource
Reject-Bundle 'missing-resource' $sourceManifest $manifestSha
[IO.File]::WriteAllBytes($installedResource, $sourceBytes)
$surprise = Join-Path $dest 'Contents\Resources\P109-unexpected-resource.txt'
[IO.File]::WriteAllBytes($surprise, [Text.Encoding]::ASCII.GetBytes('unapproved'))
Reject-Bundle 'extra-resource' $sourceManifest $manifestSha
Remove-Item -LiteralPath $surprise
Reject-Bundle 'wrong-manifest-hash' $sourceManifest ('0' * 64)
Write-Host 'P109 full bundle resources authenticated on positive and all four negative controls'
# P111: the required source directory contains NO files. It must still
# survive real EXE installation, and must be protected by the manifest.
if (-not (Test-Path -LiteralPath $installedEmptyDir -PathType Container)) {
  throw 'P111 approved empty directory missing after installation'
}
Remove-Item -LiteralPath $installedEmptyDir -Force
Reject-Bundle 'missing-required-empty-directory' $sourceManifest $manifestSha
New-Item -ItemType Directory -Path $installedEmptyDir -Force | Out-Null
$unexpectedEmpty = Join-Path $dest 'Contents\Resources\P111-unapproved-empty-directory'
New-Item -ItemType Directory -Path $unexpectedEmpty -Force | Out-Null
Reject-Bundle 'unexpected-empty-directory' $sourceManifest $manifestSha
Remove-Item -LiteralPath $unexpectedEmpty -Force
Write-Host 'P111 both missing and additional empty directories rejected before native P74'


# P110 hard links are invisible to reparse-point checks: same correct
# bytes, same relative path and file count, but another path outside the
# approved VST3 bundle addresses the same underlying NTFS file.
$externalResource = Join-Path $WorkingRoot 'P110-outside-bundle-hardlink-target.txt'
[IO.File]::WriteAllBytes($externalResource, $sourceBytes)
Remove-Item -LiteralPath $installedResource
New-Item -ItemType HardLink -Path $installedResource -Target $externalResource -ErrorAction Stop | Out-Null
if ((Get-FileHash -LiteralPath $installedResource -Algorithm SHA256).Hash -cne
    (Get-FileHash -LiteralPath $externalResource -Algorithm SHA256).Hash) {
  throw 'P110 hard-link test fixture bytes unexpectedly differ'
}
Reject-Bundle 'external-ntfs-hardlink' $sourceManifest $manifestSha
$badSourceManifest = Join-Path $WorkingRoot 'P110-should-not-create-manifest.json'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Get-Vst3BundleManifest.ps1') -Bundle $dest -OutputFile $badSourceManifest | Out-Null
if ($LASTEXITCODE -eq 0 -or (Test-Path -LiteralPath $badSourceManifest)) {
  throw 'P110 source manifest generator incorrectly accepted externally hardlinked resource'
}
Write-Host 'P110 NTFS hardlink rejected by both source manifest and installed-bundle verifier'
Remove-Item -LiteralPath $installedResource
[IO.File]::WriteAllBytes($installedResource, $sourceBytes)
# Even if the manifest bytes are legitimately hashed again, an untrusted
# manifest entry may not reference a parent path outside the bundle.
$maliciousManifest = Join-Path $WorkingRoot 'P110-parent-traversal-manifest.json'
$alteredManifest = Get-Content -LiteralPath $sourceManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$alteredManifest.files[0].path = '../outside-resource.txt'
$alteredManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $maliciousManifest -Encoding UTF8
$maliciousSha = (Get-FileHash -LiteralPath $maliciousManifest -Algorithm SHA256).Hash.ToLowerInvariant()
Reject-Bundle 'parent-traversal-path' $maliciousManifest $maliciousSha
Write-Host 'P110 traversal manifest rejected before native P74'

# P112 negative proof: NTFS Alternate Data Streams do not change the
# ordinary file content hash, yet may carry unapproved extra payloads.
$originalHash = (Get-FileHash -LiteralPath $installedResource -Algorithm SHA256).Hash
Set-Content -LiteralPath $installedResource -Stream 'P112Hidden' -Value 'P112-unapproved-side-content' -Encoding Ascii
if ((Get-FileHash -LiteralPath $installedResource -Algorithm SHA256).Hash -cne $originalHash) {
  throw 'P112 ADS fixture unexpectedly changed primary file bytes'
}
Reject-Bundle 'alternate-ntfs-stream' $sourceManifest $manifestSha
$adsSourceManifest = Join-Path $WorkingRoot 'P112-should-not-create-manifest.json'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Get-Vst3BundleManifest.ps1') -Bundle $dest -OutputFile $adsSourceManifest | Out-Null
if ($LASTEXITCODE -eq 0 -or (Test-Path -LiteralPath $adsSourceManifest)) {
  throw 'P112 source manifest generator accepted unapproved NTFS alternate stream'
}
Remove-Item -LiteralPath $installedResource -Stream 'P112Hidden' -ErrorAction Stop
Write-Host 'P112 NTFS ADS mutation rejected by manifest generator and installed-bundle oracle'
