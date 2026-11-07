# P97 — One-command local ASIO4ALL/VB-CABLE acceptance (no GitHub self-hosted runner)

**Why this exists:** P94/P95 built a real Windows native VST3-to-ASIO4ALL bridge, and a stereo PCM return oracle, but the GitHub-hosted Windows machines have no persistent rebooted WDM audio endpoints. The vendor installation procedure for VB-CABLE explicitly requires an administrator-launched setup and reboot. Normal hosted CI cannot substitute for a driver-equipped Windows machine.

**P97 is the shortest safe path to final live evidence, without registering your everyday computer as a self-hosted GitHub runner.** It runs locally once on a dedicated isolated Windows 11 x64 installation after an attended setup. It does not require a real USB audio interface.

## One-time installation

1. Install official [ASIO4ALL](https://asio4all.org/) and [VB-CABLE](https://vb-audio.com/Cable/index.htm) on an isolated Windows test installation. A preflight and vendor installation helper already exist: [P96 installation and reboot procedure](P96-VIRTUAL-AUDIO-PROVISIONING.md).
2. Reboot Windows after VB-CABLE installation, as required by its vendor.
3. Enable **VB-CABLE playback and recording devices, exclusively**, in the ASIO4ALL configuration panel, at a supported matching rate/buffer. Other physical outputs should be disabled/muted for the test.
4. Install Visual Studio 2022 C++ Build Tools, Git, CMake and Python 3.10+ on this isolated machine. The original repo uses C++23 and the Windows VST3 SDK; nothing is bundled with the installers.

## One command after setup

From a checked-out copy of this repository, in Windows PowerShell:

```powershell
# Safe read-only readiness check; does not open or install a sound device:
powershell -NoProfile -File tests/Invoke-VirtualASIOAcceptance.ps1 -CheckOnly -OutputFolder C:\QA\P97-check

# Actual driver callback and returning audio capture (separate new output):
powershell -NoProfile -File tests/Invoke-VirtualASIOAcceptance.ps1 -ApproveVirtualAudioTesting -OutputFolder C:\QA\P97-live
```

The live command verifies real Windows HKLM ASIO4ALL registration, Windows Audio service, and active VB-CABLE Input/Output PnP endpoints; downloads **only the previously pinned external Steinberg ASIO SDK Git reference**; compiles the preexisting dedicated C++ 2-input/2-output host and its unique stereo VST3 pattern generator; builds a SHA-256-pinned driver plan; executes 500 real ASIO4ALL callbacks; independently compares output and captured input for signal integrity, channel swaps and approximate delay; then writes a local machine-readable `P97-ACCEPTANCE.json`.

The entire native trace stays inside the chosen local output folder, never automatically uploaded to GitHub. Every fresh run requires a **different empty/nonexistent** `-OutputFolder`, preventing stale recordings from being accidentally reused.

The command fails closed if drivers are missing, the ASIO4ALL mapping is incorrect, sample rate/buffer unsupported, a plugin or native host fails to compile, or PCM is absent, silent, swapped, truncated or lacks a sufficient correlation. Nothing in this command silently installs or reboots Windows, creates a GitHub Actions runner, or requires a physical soundcard.

Optional live command options: `-SampleRate 48000 -BufferFrames 256 -Callbacks 500 -ASIODriverName 'ASIO4ALL v2'`, provided the actual driver configuration supports them.

## Evidence statuses (do not confuse them)

- `DRIVERS_NOT_READY_LIVE_AUDIO_NOT_RUN`: Windows cannot see the full installed VB-CABLE and ASIO4ALL setup.
- `DRIVERS_READY_LIVE_AUDIO_NOT_RUN`: registry/endpoints are visible, **no** real callback or audio measurement was performed.
- `NOT_RUN_OR_FAILED`: a required prerequisite, actual driver test, or PCM comparison failed; examine the explicit error in JSON.
- `REAL_VIRTUAL_ASIO_PCM_LOOPBACK_PASS`: an explicitly approved *real* ASIO4ALL session produced source-defined VST3 audio, received its corresponding stereo PCM through a virtual audio return, and passed the independent validator. This status is emitted only from an actual live run.

**Physical ASIO hardware, external audio analog loopback, licensed DAW and product release approval remain false in every report.** Source-built VST3 fixtures are not evidence that every product plugin has been tested.

## CI coverage

The P97 Windows-2022 cloud workflow tests a read-only Windows preflight and the **no-consent rejection**. It never installs audio kernel drivers or claims that it has executed a real ASIO4ALL device. The real REAPER suite P91/P92 and the P95 native C++ compilation are preserved in their separate workflows. A ready machine is the only missing external prerequisite for a live P97 run.

Official manufacturer installation guidance: [VB-CABLE manual](https://vb-audio.com/Cable/VBCABLE_ReferenceManual.pdf) and [ASIO4ALL site](https://asio4all.org/).
