#requires -Version 5.1
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$WorkingRoot,
  [Parameter(Mandatory=$true)][string]$WixExecutable
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$adapter = Join-Path $PSScriptRoot 'Invoke-UniversalInstaller.ps1'
$wxs = Join-Path $PSScriptRoot 'p106_msi_fixture.wxs'
$input = Join-Path $PSScriptRoot 'p106-msi-marker.txt'
$path = Join-Path $WorkingRoot 'P106-Inert.msi'
$target = Join-Path $env:LOCALAPPDATA '125A-P106-MSI-Only-Test\p106-msi-marker.txt'
New-Item -ItemType Directory -Force -Path $WorkingRoot | Out-Null
if (Test-Path -LiteralPath $target) { throw 'P106 MSI target unexpectedly exists before install: test machine not clean' }
if (-not (Test-Path -LiteralPath $WixExecutable -PathType Leaf)) { throw 'WiX executable absent' }
& $WixExecutable build $wxs -bindpath $PSScriptRoot -o $path
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $path)) { throw 'P106 MSI fixture build failed' }
$sha = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
$markerHash = (Get-FileHash -LiteralPath $input -Algorithm SHA256).Hash.ToLowerInvariant()
function Execute-Case([string]$Case,[int]$Exit,[string]$Status,[string[]]$Extra) {
  $out = Join-Path $WorkingRoot $Case
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $adapter -Installer $path -ExpectedSha256 $sha -OutputFolder $out @Extra | Out-Null
  if ($LASTEXITCODE -ne $Exit) { throw "$Case wrong exit: $LASTEXITCODE vs $Exit" }
  $result = Get-Content -LiteralPath (Join-Path $out 'P106-INSTALLER-RESULT.json') -Raw | ConvertFrom-Json
  if ($result.status -ne $Status -or $result.release_approved -ne $false -or $result.vst3_qa_executed -ne $false) {
    throw "$Case invalid result: $($result | ConvertTo-Json -Depth 7)"
  }
  Write-Host "$Case : $Status"
  return $result
}
$inspect = Execute-Case '09-msi-inspect' 0 'INSPECTED_NOT_RUN' @('-AllowUnsigned')
if ($inspect.installer_executed -or (Test-Path -LiteralPath $target)) { throw 'MSI inspect had side effect' }
$deny = Execute-Case '10-msi-no-consent' 1 'FAIL' @('-Mode','Run','-AllowUnsigned','-ExpectedArtifact',$target,'-ExpectedArtifactSha256',$markerHash)
if ($deny.installer_executed -or (Test-Path -LiteralPath $target)) { throw 'Unapproved MSI launch' }
$installed = Execute-Case '11-msi-real-install' 0 'INSTALLATION_ARTIFACT_VERIFIED' @('-Mode','Run','-ApproveExecution','-AllowUnsigned','-ExpectedArtifact',$target,'-ExpectedArtifactSha256',$markerHash,'-TimeoutSeconds','120')
if (-not $installed.installer_executed -or $installed.installer_type -ne 'msi' -or
    -not $installed.expected_artifact_verified -or
    $installed.expected_artifact_sha256 -ne $markerHash -or
    -not (Test-Path -LiteralPath $target)) { throw 'MSI file installation evidence missing or corrupted' }
$stale = Execute-Case '12-msi-stale-artifact' 1 'FAIL' @('-Mode','Run','-ApproveExecution','-AllowUnsigned','-ExpectedArtifact',$target,'-ExpectedArtifactSha256',$markerHash)
if ($stale.installer_executed) { throw 'MSI stale artifact allowed launch' }
Write-Host 'P106 real MSI: 4/4 accepted/rejected fixture cases, exact marker bytes, Windows Installer process executed'
