#requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$WorkingRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'Invoke-UniversalInstaller.ps1'
$fixture = Join-Path $PSScriptRoot 'p106_installer_fixture.cs'
New-Item -ItemType Directory -Path $WorkingRoot -Force | Out-Null
$installer = Join-Path $WorkingRoot 'P106-Harmless-Installer.exe'
Add-Type -Path $fixture -OutputAssembly $installer -OutputType ConsoleApplication -ErrorAction Stop
$sha = (Get-FileHash $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$marker = Join-Path $WorkingRoot 'installed-marker.txt'
$markerBytes = [Text.UTF8Encoding]::new($false).GetBytes("125A-P106-INSTALLED`n")
$expectedMarkerSha = [BitConverter]::ToString(
  [Security.Cryptography.SHA256]::Create().ComputeHash($markerBytes)).Replace('-','').ToLowerInvariant()
function Invoke-Case([string]$Name,[int]$ExpectedExit,[string]$ExpectedStatus,[string[]]$Extra) {
  $output = Join-Path $WorkingRoot $Name
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $script -Installer $installer -ExpectedSha256 $sha -OutputFolder $output @Extra | Out-Null
  if ($LASTEXITCODE -ne $ExpectedExit) { throw "$Name wrong process exit code: $LASTEXITCODE" }
  $report = Get-Content -LiteralPath (Join-Path $output 'P106-INSTALLER-RESULT.json') -Raw | ConvertFrom-Json
  if ($report.status -ne $ExpectedStatus -or $report.release_approved -ne $false -or $report.vst3_qa_executed -ne $false) {
    throw "$Name false evidence: $($report | ConvertTo-Json -Depth 7)"
  }
  Write-Host "$Name : $ExpectedStatus"
  return $report
}
$arg = '"' + $marker + '"'
$before = Invoke-Case '01-inspect' 0 'INSPECTED_NOT_RUN' @('-AllowUnsigned')
if ($before.installer_executed -ne $false -or (Test-Path $marker)) { throw 'Inspection executed installer' }
$wrong = '0' * 64
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $script -Installer $installer -ExpectedSha256 $wrong -OutputFolder (Join-Path $WorkingRoot '02-bad-hash') -AllowUnsigned | Out-Null
if ($LASTEXITCODE -eq 0 -or (Test-Path $marker)) { throw 'Bad installer SHA accepted or fixture executed' }
$unsigned = Invoke-Case '03-no-signature-optin' 1 'FAIL' @()
if ($unsigned.installer_executed -ne $false) { throw 'Unsigned fixture executed without approval' }
$denied = Invoke-Case '04-no-consent' 1 'FAIL' @('-Mode','Run','-AllowUnsigned','-ExpectedArtifact',$marker,'-ExpectedArtifactSha256',$expectedMarkerSha,'-InstallerArguments',$arg)
if ($denied.installer_executed -ne $false -or (Test-Path $marker)) { throw 'Unapproved execution occurred' }
$success = Invoke-Case '05-actual-exe' 0 'INSTALLATION_ARTIFACT_VERIFIED' @('-Mode','Run','-ApproveExecution','-AllowUnsigned','-ExpectedArtifact',$marker,'-ExpectedArtifactSha256',$expectedMarkerSha,'-InstallerArguments',$arg)
if (-not $success.installer_executed -or -not $success.expected_artifact_verified -or
    $success.expected_artifact_sha256 -ne $expectedMarkerSha -or
    -not (Test-Path $marker)) { throw 'No real installed artifact proof' }
$stale = Invoke-Case '06-stale-artifact' 1 'FAIL' @('-Mode','Run','-ApproveExecution','-AllowUnsigned','-ExpectedArtifact',$marker,'-ExpectedArtifactSha256',$expectedMarkerSha,'-InstallerArguments',$arg)
if ($stale.installer_executed) { throw 'Stale artifact permitted executable launch' }
Remove-Item -LiteralPath $marker
$noOutput = Invoke-Case '07-false-zero-exit' 1 'FAIL' @('-Mode','Run','-ApproveExecution','-AllowUnsigned','-ExpectedArtifact',$marker,'-ExpectedArtifactSha256',$expectedMarkerSha,'-InstallerArguments',($arg + ' omit'))
if (-not $noOutput.installer_executed -or $noOutput.expected_artifact_verified -or (Test-Path $marker)) {
  throw 'Zero-exit without artifact was accepted'
}
$failing = Invoke-Case '08-real-nonzero-exit' 1 'FAIL' @('-Mode','Run','-ApproveExecution','-AllowUnsigned','-ExpectedArtifact',$marker,'-ExpectedArtifactSha256',$expectedMarkerSha,'-InstallerArguments',($arg + ' fail'))
if (-not $failing.installer_executed -or $failing.exit_code -ne 42) { throw 'Nonzero exit missing from evidence' }
Write-Output 'P106: all 8 synthetic fixture and negative contract cases PASS; no third-party installers run'
