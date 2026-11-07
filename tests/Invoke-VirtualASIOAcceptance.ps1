#requires -Version 5.1
<#
P97: one-command local *real* ASIO4ALL + VB-CABLE PCM acceptance after drivers
are installed/rebooted and ASIO4ALL is explicitly routed to VB-CABLE.
No self-hosted GitHub Actions runner, sound interface, or manual compilation.

Read-only:
  powershell -NoProfile -File tests/Invoke-VirtualASIOAcceptance.ps1 -CheckOnly

Actual opt-in on a DEDICATED isolated Windows installation:
  powershell -NoProfile -File tests/Invoke-VirtualASIOAcceptance.ps1 -ApproveVirtualAudioTesting -OutputFolder C:\QA\P97-live
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$ApproveVirtualAudioTesting,
    [ValidateSet(44100,48000)][int]$SampleRate = 44100,
    [ValidateSet(256,512)][int]$BufferFrames = 512,
    [ValidateRange(300,1000)][int]$Callbacks = 500,
    [ValidatePattern('(?i)^ASIO4ALL[^\\/\x00-\x1f]*$')][string]$ASIODriverName = 'ASIO4ALL v2',
    [string]$OutputFolder = 'artifacts/P97-local'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
$preflight = Join-Path $PSScriptRoot 'Prepare-VirtualASIO.ps1'
$planner = Join-Path $PSScriptRoot 'run_virtual_asio4all.py'
$runner = Join-Path $PSScriptRoot 'run_virtual_asio_loopback.py'
$target = [IO.Path]::GetFullPath($OutputFolder)
$reportPath = Join-Path $target 'P97-ACCEPTANCE.json'
$report = @{
    schema = '125a-p97-local-virtual-asio-acceptance-v1'
    status = 'NOT_RUN'
    native_virtual_asio_callbacks = 'NOT_RUN'
    virtual_pcm_loopback = 'NOT_RUN'
    physical_asio_hardware_verified = $false
    commercial_daw_verified = $false
    release_approved = $false
    faults = @()
}
function Publish-Report {
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        New-Item -Path $target -ItemType Directory -Force | Out-Null
    }
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Write-Output ($report | ConvertTo-Json -Depth 10)
}
function Invoke-Checked([string]$Program, [string[]]$CommandArgs, [string]$Label) {
    & $Program @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "P97 $Label failed (process exit code $LASTEXITCODE)"
    }
}
function Find-Unique([string]$Root, [string]$Name) {
    $found = @(Get-ChildItem -LiteralPath $Root -Filter $Name -File -Recurse -ErrorAction Stop)
    if ($found.Count -ne 1) {
        throw "P97 expected exactly one native binary $Name; found $($found.Count)"
    }
    return $found[0].FullName
}

try {
    if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
        throw 'P97 requires a real Windows host'
    }
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'P97 requires 64-bit Windows'
    }
    # Fresh evidence only. Never replace a previous live ASIO session.
    if (Test-Path -LiteralPath $target) {
        throw "P97 output path already exists; choose a fresh -OutputFolder"
    }
    New-Item -Path $target -ItemType Directory -Force | Out-Null
    $readinessFolder = Join-Path $target 'readiness'
    Invoke-Checked 'powershell.exe' @(
        '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
        '-File',$preflight,'-Mode','Preflight','-OutputFolder',$readinessFolder
    ) 'live Windows registry/WDM preflight'
    $readiness = Get-Content -LiteralPath (Join-Path $readinessFolder 'P96-VIRTUAL-DRIVER-READINESS.json') -Raw | ConvertFrom-Json
    $report.windows_audio_readiness = $readiness.status
    $report.asio4all_registered = [bool]$readiness.asio4all_registered
    $report.vb_cable_playback = [bool]$readiness.vb_cable_playback
    $report.vb_cable_recording = [bool]$readiness.vb_cable_recording
    if ($CheckOnly) {
        $report.status = if ($readiness.status -eq 'DRIVERS_AND_ENDPOINTS_READY') {
            'DRIVERS_READY_LIVE_AUDIO_NOT_RUN'
        } else {
            'DRIVERS_NOT_READY_LIVE_AUDIO_NOT_RUN'
        }
        Publish-Report
        exit 0
    }
    if (-not $ApproveVirtualAudioTesting) {
        throw 'P97 requires explicit -ApproveVirtualAudioTesting for actual ASIO4ALL/virtual audio execution'
    }
    if ($readiness.status -ne 'DRIVERS_AND_ENDPOINTS_READY') {
        throw 'P97 real ASIO4ALL and VB-CABLE endpoints are NOT_READY. Install both drivers, reboot, then rerun.'
    }
    # The real ASIO4ALL device selection must be reviewed manually first.
    # Registry and PnP cannot establish exclusive VB-CABLE routing.
    Write-Warning 'Ensure ASIO4ALL is configured to use VB-CABLE ONLY. Disconnect/mute any real speakers before continuing.'
    $git = (Get-Command git -ErrorAction Stop).Source
    $cmake = (Get-Command cmake -ErrorAction Stop).Source
    $python = (Get-Command python -ErrorAction Stop).Source
    Invoke-Checked $python @('-c','import sys; assert sys.version_info >= (3,10)') 'Python >=3.10 prerequisite'
    $sdk = Join-Path $target 'reference-asio-sdk'
    Invoke-Checked $git @('clone','--no-checkout','https://github.com/audiosdk/asio.git',$sdk) 'ASIO SDK checkout'
    $sdkCommit = '496a0765b8bb9c26f764f22f9a9712a937177db2'
    Invoke-Checked $git @('-C',$sdk,'checkout','--detach',$sdkCommit) 'ASIO SDK version pin'
    $pin = (& $git -C $sdk rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $pin -cne $sdkCommit) {
        throw 'P97 reference ASIO SDK does not match required exact revision'
    }
    $build = Join-Path $target 'build'
    Invoke-Checked $cmake @('-S',$projectRoot,'-B',$build,
        '-G','Visual Studio 17 2022','-A','x64',"-DASIO_SDK_DIR=$sdk") 'native project configure'
    Invoke-Checked $cmake @('--build',$build,'--config','Release',
        '--parallel','4','--target','TestLabVirtualASIOLoopback','QAVirtualASIOReturn') 'native VST3 and ASIO build'
    $exe = Find-Unique $build '125A_Test_Lab_Virtual_ASIO_Loopback.exe'
    $vst3 = Find-Unique $build '125A_QA_Virtual_ASIO_Return.vst3'
    $plan = Join-Path $target 'approved-plan.json'
    Invoke-Checked $python @($planner,'plan','--plugin',$vst3,
        '--executor',$exe,'--driver-name',$ASIODriverName,'--rate',
        [string]$SampleRate,'--frames',[string]$BufferFrames,'--callbacks',
        [string]$Callbacks,'--out',$plan) 'real Windows ASIO driver registration and binary plan'
    $measurement = Join-Path $target 'measurement'
    Invoke-Checked $python @($runner,'--plan',$plan,'--out',$measurement,
        '--timeout','180','--acknowledge-virtual-drivers') 'ACTUAL ASIO4ALL/VB-CABLE PCM return'
    $full = Get-Content -LiteralPath (Join-Path $measurement 'P95-VIRTUAL-LOOPBACK-RUN.json') -Raw | ConvertFrom-Json
    if ($full.status -ne 'VIRTUAL_ASIO_LOOPBACK_PASS' -or
        $full.physical_asio_hardware_verified -ne $false -or
        $full.commercial_daw_verified -ne $false -or
        $full.release_approved -ne $false -or
        $full.metrics.pass -ne $true) {
        throw 'P97 genuine ASIO loopback result is invalid or falsely asserts physical/DAW approval'
    }
    $report.status = 'REAL_VIRTUAL_ASIO_PCM_LOOPBACK_PASS'
    $report.native_virtual_asio_callbacks = $full.completed_asio_callbacks
    $report.virtual_pcm_loopback = 'VERIFIED'
    $report.metrics = $full.metrics
    $report.vst3_module_sha256 = $full.verified_module_sha256
    $report.native_executor_sha256 = $full.verified_executor_sha256
    Publish-Report
    exit 0
} catch {
    $report.status = 'NOT_RUN_OR_FAILED'
    $report.faults = @([string]$_.Exception.Message)
    Publish-Report
    exit 1
}
