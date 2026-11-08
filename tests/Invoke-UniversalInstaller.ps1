#requires -Version 5.1
<#
P106 universal EXE/MSI installer observation. Does NOT provide sandboxing.
Use ONLY on a disposable Windows machine with trusted, independently reviewed
installer bytes. Defaults to inspection; execution needs explicit opt-in.
#>
[CmdletBinding()]
param(
  [ValidateSet('Inspect','Run')][string]$Mode = 'Inspect',
  [Parameter(Mandatory=$true)][string]$Installer,
  [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{64}$')][string]$ExpectedSha256,
  [Parameter(Mandatory=$true)][string]$OutputFolder,
  [string]$InstallerArguments = '',
  [string]$ExpectedArtifact = '',
  [string]$ExpectedArtifactSha256 = '',
  [ValidateRange(5,900)][int]$TimeoutSeconds = 120,
  [switch]$ApproveExecution,
  [switch]$AllowUnsigned
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$report = @{
  schema = '125a-p106-installer-evidence-v1'
  status = 'FAIL'
  mode = $Mode
  installer_executed = $false
  installer_verified = $false
  expected_artifact_verified = $false
  vst3_qa_executed = $false
  commercial_daw_verified = $false
  release_approved = $false
  faults = @()
}
function Capture-Vst3 {
  $roots = @(
    (Join-Path $env:CommonProgramFiles 'VST3'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Common\VST3')
  )
  $out = @()
  foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    # Finite observation inventory: no executable is loaded or evaluated.
    $items = @(Get-ChildItem -LiteralPath $root -Recurse -ErrorAction Stop |
      Where-Object { $_.Name -like '*.vst3' } |
      Select-Object -First 200)
    foreach ($item in $items) { $out += [string]$item.FullName }
  }
  return @($out | Sort-Object -Unique)
}
function Capture-Uninstall {
  $paths = @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
             'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
             'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')
  $entries = @()
  foreach ($p in $paths) {
    if (-not (Test-Path -LiteralPath $p)) { continue }
    foreach ($key in @(Get-ChildItem -LiteralPath $p -ErrorAction Stop)) {
      $v = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction Stop
      if ($v.DisplayName) {
        $entries += ([string]$key.Name + '|' + [string]$v.DisplayName + '|' + [string]$v.DisplayVersion)
      }
    }
  }
  return @($entries | Sort-Object -Unique)
}
function Publish-Report {
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $target 'P106-INSTALLER-RESULT.json') -Encoding UTF8
  Write-Output ($report | ConvertTo-Json -Depth 8)
}
$target = [IO.Path]::GetFullPath($OutputFolder)
try {
  if (-not [Environment]::Is64BitOperatingSystem -or -not $env:WINDIR) {
    throw 'P106 requires Windows x64'
  }
  if (Test-Path -LiteralPath $target) {
    throw 'P106 requires a fresh output directory; existing evidence must not be overwritten'
  }
  New-Item -ItemType Directory -Path $target -Force | Out-Null
  $path = (Resolve-Path -LiteralPath $Installer -ErrorAction Stop).ProviderPath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Installer is not a file' }
  $extension = [IO.Path]::GetExtension($path).ToLowerInvariant()
  if ($extension -notin @('.exe','.msi')) { throw 'Only local EXE/MSI installers are supported' }
  $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  $report.installer_sha256 = $actual
  $report.installer_name = [IO.Path]::GetFileName($path)
  $report.installer_type = $extension.TrimStart('.')
  if ($actual -cne $ExpectedSha256.ToLowerInvariant()) {
    throw 'Installer SHA256 differs from independently approved hash'
  }
  $signature = Get-AuthenticodeSignature -LiteralPath $path
  $report.signature_status = [string]$signature.Status
  $report.signer = if ($signature.SignerCertificate) { [string]$signature.SignerCertificate.Subject } else { '' }
  if ($signature.Status -ne 'Valid' -and -not $AllowUnsigned) {
    throw 'Authenticode signature not valid; require explicit -AllowUnsigned for an independently reviewed fixture'
  }
  if ($InstallerArguments -match '[\r\n\x00]') { throw 'Multiline/NUL installer arguments rejected' }
  if ($ExpectedArtifactSha256 -and $ExpectedArtifactSha256 -notmatch '^[a-fA-F0-9]{64}$') {
    throw 'Invalid expected artifact SHA256'
  }
  $report.status = 'INSPECTED_NOT_RUN'
  if ($Mode -eq 'Inspect') { Publish-Report; exit 0 }
  if (-not $ApproveExecution) { throw 'Execution requires explicit -ApproveExecution' }
  if (-not $ExpectedArtifact) { throw 'Run mode requires independently named expected artifact' }
  $artifactPath = [IO.Path]::GetFullPath($ExpectedArtifact)
  if (Test-Path -LiteralPath $artifactPath) {
    throw 'Expected artifact already exists: refusing stale or replayed proof'
  }
  $report.vst3_before = @(Capture-Vst3)
  $uninstallBefore = @(Capture-Uninstall)
  $report.started_utc = [DateTime]::UtcNow.ToString('o')
  if ($extension -eq '.msi') {
    $program = Join-Path $env:WINDIR 'System32\msiexec.exe'
    $arguments = '/i "' + $path + '" /qn /norestart ' + $InstallerArguments
  } else {
    $program = $path
    $arguments = $InstallerArguments
  }
  $startOptions = @{ FilePath = $program; WorkingDirectory = [IO.Path]::GetDirectoryName($path); PassThru = $true; ErrorAction = 'Stop' }
  if ($arguments) { $startOptions.ArgumentList = $arguments }
  $process = Start-Process @startOptions
  $report.installer_executed = $true
  $report.process_id = $process.Id
  if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    try { $process.Kill() } catch {}
    throw 'Installer exceeded bounded timeout (child processes may remain)'
  }
  $report.exit_code = [int]$process.ExitCode
  $report.finished_utc = [DateTime]::UtcNow.ToString('o')
  if ($process.ExitCode -ne 0) { throw ('Installer exited with code ' + $process.ExitCode) }
  $report.installer_verified = $true # verified exit only, not functional installation
  $report.vst3_after = @(Capture-Vst3)
  $after = @(Capture-Uninstall)
  $report.vst3_added = @($report.vst3_after | Where-Object { $_ -notin $report.vst3_before })
  $report.uninstall_entries_added = @($after | Where-Object { $_ -notin $uninstallBefore })
  if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) {
    throw 'Installer returned zero but expected installed artifact is absent'
  }
  $report.expected_artifact_sha256 = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($ExpectedArtifactSha256 -and $report.expected_artifact_sha256 -cne $ExpectedArtifactSha256.ToLowerInvariant()) {
    throw 'Installed artifact exists but expected SHA256 does not match'
  }
  $report.expected_artifact_verified = [bool]$ExpectedArtifactSha256
  $report.status = if ($ExpectedArtifactSha256) { 'INSTALLATION_ARTIFACT_VERIFIED' } else { 'ARTIFACT_PRESENT_HASH_NOT_VERIFIED' }
  Publish-Report
  exit 0
} catch {
  $report.status = 'FAIL'
  $report.faults = @([string]$_.Exception.Message)
  if (Test-Path -LiteralPath $target -PathType Container) { Publish-Report }
  else { Write-Error ($report.faults -join '; ') }
  exit 1
}
