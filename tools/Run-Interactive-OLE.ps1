# P14 interactive Windows OLE acceptance harness.
# Runs the REAL built VST3 and an independent native COM IDropTarget.
# GUI Save As / drag-source tests were already independently audited in CI.
# Success here requires four real OLE Drop callbacks on an interactive desktop.
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$gui = Join-Path $base "125A_Test_Lab_GUI.exe"
$plugin = Join-Path $base "125A Drumator.vst3\Contents\x86_64-win\125A Drumator.vst3"
$state = Join-Path $base "A-REST-A.bin"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$result = Join-Path $base "results\$stamp"
New-Item -ItemType Directory -Path $result -Force | Out-Null
$logFile = Join-Path $result "OLE-TEST-LOG.txt"
$resultFile = Join-Path $result "RESULT.txt"
$files = Join-Path $result "received"
New-Item -ItemType Directory -Path $files -Force | Out-Null

function Save-Result([string]$status, [string]$reason) {
  @(
    "125A Plugin Test Lab - P14 native Windows OLE receiver",
    "Status: $status",
    "Reason: $reason",
    "Tested product SHA: $(if (Test-Path (Join-Path $base 'TESTED-PRODUCT-REVISION.txt')) { (Get-Content (Join-Path $base 'TESTED-PRODUCT-REVISION.txt') -Raw).Trim() } else { 'not recorded' })",
    "Execution: $(Get-Date -Format o)",
    "Native runner: $gui",
    "Output directory: $result"
  ) | Set-Content -LiteralPath $resultFile -Encoding UTF8
  Write-Host "P14 $status - $reason"
  Write-Host "Proof: $resultFile"
}

try {
  if (-not [Environment]::Is64BitOperatingSystem) {
    throw "Windows x64 is required."
  }
  foreach ($path in @($gui, $plugin, $state)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
      throw "Required test bundle file missing: $path"
    }
  }
  if (-not (Test-Path -LiteralPath (Join-Path $base "125A Drumator.vst3\Contents\Resources\Drumator.uidesc"))) {
    throw "Complete product VST3 Resources folder is required."
  }
  if ($env:GITHUB_ACTIONS -eq "true" -or $env:CI -eq "true") {
    Save-Result "INCONCLUSIVE" "Headless CI is not an interactive user desktop; use a logged-in Windows session."
    exit 3
  }

  # A Windows user desktop is necessary. Do not count remote CI pixel
  # simulation or successful exporter invocation as a completed OLE drop.
  $session = (Get-Process -Id $PID).SessionId
  if ($session -eq 0) {
    Save-Result "INCONCLUSIVE" "Session 0 (Windows service) cannot verify interactive OLE drag/drop."
    exit 3
  }

  Write-Host "P14: Starting genuine VST3 editor with independent COM/OLE receiver."
  Write-Host "Do not touch the mouse or switch windows during the automation."
  Write-Host "Product state is synthetic; no purchased samples or local DAW content."
  Write-Host "This does NOT certify a drop into Studio One or another proprietary DAW."

  # The native executable itself must receive four genuine CF_HDROP events.
  # It exits nonzero when no independent COM Drop callback accepted the file.
  $stderrFile = Join-Path $result "OLE-TEST-STDERR.txt"
  $native = Start-Process -FilePath $gui -ArgumentList @(
    "--drumator-ole-drag-drop",
    ('"{0}"' -f $plugin),
    ('"{0}"' -f $state),
    ('"{0}"' -f $files)
  ) -Wait -PassThru -RedirectStandardOutput $logFile -RedirectStandardError $stderrFile
  $exitCode = $native.ExitCode
  Get-Content -LiteralPath $logFile -Tail 45 | ForEach-Object { Write-Host $_ }
  Get-Content -LiteralPath $stderrFile -Tail 45 | ForEach-Object { Write-Host $_ }
  if ($exitCode -ne 0) {
    Save-Result "FAIL" "Real OLE acceptance did not complete (native exit $exitCode). Inspect OLE-TEST-LOG.txt."
    exit 1
  }
  $successMarker = "[PASS] P13 all 4 actual VSTGUI OLE CF_HDROP drops accepted by independent native Windows target"
  if (-not ((Get-Content -LiteralPath $logFile -Raw).Contains($successMarker))) {
    throw "Native process exited zero without its verified four-drop acceptance marker."
  }

  # Independent PowerShell file header / duration check; no plugin methods.
  $expected = @(
    @{ Name="pattern-midi.mid"; Kind="MIDI"; Length=435 },
    @{ Name="pattern-wav.wav";  Kind="WAV";  Length=576044; Frames=96000 },
    @{ Name="song-midi.mid";    Kind="MIDI"; Length=444 },
    @{ Name="song-wav.wav";     Kind="WAV";  Length=1728044; Frames=288000 }
  )
  $actual = @(Get-ChildItem -LiteralPath $files -File | Select-Object -ExpandProperty Name | Sort-Object)
  $names = @($expected | ForEach-Object { $_.Name } | Sort-Object)
  if (($actual -join "|") -cne ($names -join "|")) {
    throw "Unexpected or missing OLE-dropped files: $($actual -join ', ')"
  }
  foreach ($entry in $expected) {
    $path = Join-Path $files $entry.Name
    $bytes = [IO.File]::ReadAllBytes($path)
    if ($bytes.Length -ne $entry.Length) {
      throw "$($entry.Name): incorrect file size $($bytes.Length), expected $($entry.Length)"
    }
    if ($entry.Kind -eq "MIDI") {
      if ([Text.Encoding]::ASCII.GetString($bytes, 0, 4) -cne "MThd" -or
          [Text.Encoding]::ASCII.GetString($bytes, 14, 4) -cne "MTrk" -or
          [BitConverter]::ToUInt16([byte[]]@($bytes[13],$bytes[12]),0) -ne 960) {
        throw "$($entry.Name): invalid SMF header, track or 960 PPQ"
      }
    } else {
      if ([Text.Encoding]::ASCII.GetString($bytes, 0, 4) -cne "RIFF" -or
          [Text.Encoding]::ASCII.GetString($bytes, 8, 4) -cne "WAVE" -or
          [Text.Encoding]::ASCII.GetString($bytes, 36, 4) -cne "data" -or
          [BitConverter]::ToUInt16($bytes, 20) -ne 1 -or
          [BitConverter]::ToUInt16($bytes, 22) -ne 2 -or
          [BitConverter]::ToInt32($bytes, 24) -ne 48000 -or
          [BitConverter]::ToUInt16($bytes, 34) -ne 24) {
        throw "$($entry.Name): invalid stereo 48kHz PCM24 WAV"
      }
      if ([BitConverter]::ToUInt32($bytes, 40) -ne ($entry.Frames * 6)) {
        throw "$($entry.Name): invalid exact frame duration"
      }
    }
    Write-Host "[PASS] Received genuine OLE file $($entry.Name), $($bytes.Length) bytes."
  }
  Save-Result "PASS" "Four independent CF_HDROP Drop callbacks; all four received exports passed the file integrity checks."
  exit 0
} catch {
  Save-Result "FAIL" ([string]$_.Exception.Message)
  exit 1
}
