#requires -Version 5.1
<#
P96: prepare, install (with explicit UAC), and validate ASIO4ALL + VB-CABLE
on an isolated Windows x64 test machine. No unattended driver installation,
no stealth elevation, no reboot without user action, no false hardware approval.

Examples:
  powershell -File tests/Prepare-VirtualASIO.ps1 -Mode Preflight
  powershell -File tests/Prepare-VirtualASIO.ps1 -Mode Install -ASIO4ALLInstaller C:\Temp\asio4all.exe -VBCableExtracted C:\Temp\VBCABLE -ApproveDriverInstallation
  # reboot Windows manually
  powershell -File tests/Prepare-VirtualASIO.ps1 -Mode Verify -OutputFolder C:\QA\P96
#>
[CmdletBinding()]
param(
    [ValidateSet('Preflight','Install','Verify')][string]$Mode = 'Preflight',
    [string]$ASIO4ALLInstaller = '',
    [string]$VBCableExtracted = '',
    [string]$OutputFolder = 'artifacts/P96',
    [switch]$ApproveDriverInstallation
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Get-AudioEndpoints {
    $devices = @(Get-PnpDevice -Class AudioEndpoint -ErrorAction Stop)
    $valid = @($devices | Where-Object { $_.Status -eq 'OK' })
    $playback = @($valid | Where-Object {
        $_.FriendlyName -match '(?i)CABLE Input' -and
        $_.FriendlyName -match '(?i)VB-Audio|VB-CABLE|Virtual Cable'
    })
    $recording = @($valid | Where-Object {
        $_.FriendlyName -match '(?i)CABLE Output' -and
        $_.FriendlyName -match '(?i)VB-Audio|VB-CABLE|Virtual Cable'
    })
    return @{
        playback_count = $playback.Count
        recording_count = $recording.Count
        playback_names = @($playback | ForEach-Object FriendlyName)
        recording_names = @($recording | ForEach-Object FriendlyName)
    }
}
function Get-ASIO4ALL {
    $keys = @(Get-ChildItem 'HKLM:\SOFTWARE\ASIO' -ErrorAction SilentlyContinue |
              Where-Object { $_.PSChildName -match '(?i)^ASIO4ALL' })
    $drivers = @()
    foreach ($key in $keys) {
        $properties = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction Stop
        $clsid = [string]$properties.CLSID
        if ($clsid -match '^\{[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}$') {
            $drivers += @{
                name = $key.PSChildName
                clsid = $clsid
            }
        }
    }
    return $drivers
}
function Get-BootFingerprint {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    return ([DateTime]$os.LastBootUpTime).ToUniversalTime().ToString('o')
}
function Get-Readiness {
    $endpointInfo = Get-AudioEndpoints
    $drivers = @(Get-ASIO4ALL)
    $service = Get-Service 'Audiosrv' -ErrorAction SilentlyContinue
    $running = $null -ne $service -and $service.Status -eq 'Running'
    return @{
        asio4all_registered = ($drivers.Count -gt 0)
        asio4all_drivers = $drivers
        vb_cable_playback = ($endpointInfo.playback_count -gt 0)
        vb_cable_recording = ($endpointInfo.recording_count -gt 0)
        enabled_playback_count = $endpointInfo.playback_count
        enabled_recording_count = $endpointInfo.recording_count
        playback_names = @($endpointInfo.playback_names)
        recording_names = @($endpointInfo.recording_names)
        windows_audio_service_running = $running
        reboot_fingerprint = Get-BootFingerprint
    }
}
function Resolve-InstallerFile([string]$File, [string]$Purpose) {
    if ([string]::IsNullOrWhiteSpace($File)) {
        throw "$Purpose installer path required"
    }
    $resolved = (Resolve-Path -LiteralPath $File -ErrorAction Stop).ProviderPath
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf) -or
        [IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne '.exe') {
        throw "$Purpose installer must be a real local EXE, not a URL"
    }
    $sig = Get-AuthenticodeSignature -LiteralPath $resolved
    if ($sig.Status -ne 'Valid') {
        throw "$Purpose installer signature is not valid. Verify publisher directly; refusing UAC."
    }
    $hash = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    return @{path = $resolved; sha256 = $hash; signer = [string]$sig.SignerCertificate.Subject}
}
function Write-Result($Report) {
    New-Item -ItemType Directory -Force -Path $OutputFolder | Out-Null
    $filename = Join-Path $OutputFolder 'P96-VIRTUAL-DRIVER-READINESS.json'
    $Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $filename -Encoding UTF8
    Write-Output ($Report | ConvertTo-Json -Depth 8)
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'P96 supports only x64 Windows with ASIO4ALL and VB-CABLE'
}
$report = @{
    schema = '125a-virtual-asio-machine-readiness-v1'
    mode = $Mode
    status = 'NOT_READY'
    real_asio4all_audio_callbacks = 'NOT_RUN'
    virtual_pcm_loopback = 'NOT_RUN'
    physical_hardware_verified = $false
    commercial_daw_verified = $false
    release_approved = $false
    safeguards = @('no_silent_kernel_driver_install','explicit_uac','no_auto_reboot',
                   'no_physical_asio_approval')
}
if ($Mode -eq 'Install') {
    if (-not $ApproveDriverInstallation) {
        throw 'P96 Install requires explicit -ApproveDriverInstallation'
    }
    if (-not (Test-IsAdministrator)) {
        throw 'P96 Install must be run in an administrator PowerShell session after UAC approval'
    }
    if ([string]::IsNullOrWhiteSpace($VBCableExtracted) -or
        -not (Test-Path -LiteralPath $VBCableExtracted -PathType Container)) {
        throw 'P96 extracted VB-CABLE driver directory required (not ZIP)'
    }
    $vb = Join-Path $VBCableExtracted 'VBCABLE_Setup_x64.exe'
    $asio = Resolve-InstallerFile $ASIO4ALLInstaller 'ASIO4ALL'
    $cable = Resolve-InstallerFile $vb 'VB-CABLE'
    $report.asio4all_installer_sha256 = $asio.sha256
    $report.vb_cable_installer_sha256 = $cable.sha256
    $report.asio4all_installer_signer = $asio.signer
    $report.vb_cable_installer_signer = $cable.signer
    $report.boot_before_install = Get-BootFingerprint
    $report.status = 'INSTALLERS_LAUNCHED_REBOOT_REQUIRED'
    Write-Result $report
    # Use only the vendor-supported *interactive* installer UI. Exit codes
    # cannot confirm driver load or selected ASIO4ALL channels.
    Start-Process -FilePath $asio.path -Wait
    Start-Process -FilePath $cable.path -Wait
    Write-Warning 'Installation is NOT verified. Restart Windows manually, then run -Mode Verify.'
    exit 0
}
$state = Get-Readiness
foreach ($key in $state.Keys) { $report[$key] = $state[$key] }
$ready = ($state.asio4all_registered -and $state.vb_cable_playback -and
          $state.vb_cable_recording -and $state.windows_audio_service_running)
if ($Mode -eq 'Verify') {
    # A prior install marker is meaningful only if it exists and its boot
    # fingerprint predates the current OS boot; otherwise report unknown.
    $installed = Join-Path $OutputFolder 'P96-VIRTUAL-DRIVER-READINESS.json'
    $prior = $null
    if (Test-Path -LiteralPath $installed) {
        try { $prior = Get-Content -LiteralPath $installed -Raw | ConvertFrom-Json }
        catch { $prior = $null }
    }
    $report.reboot_after_staged_install = (
        $null -ne $prior -and
        $prior.status -eq 'INSTALLERS_LAUNCHED_REBOOT_REQUIRED' -and
        $prior.boot_before_install -ne $state.reboot_fingerprint)
    $ready = $ready -and $report.reboot_after_staged_install
}
if ($ready) {
    $report.status = 'DRIVERS_AND_ENDPOINTS_READY'
} else {
    $report.status = 'NOT_READY'
}
$report.asio4all_selected_vb_cable_channels_verified = $false
$report.native_asio_callback_pass_verified = $false
Write-Result $report
if ($Mode -eq 'Verify' -and -not $ready) { exit 2 }
exit 0
