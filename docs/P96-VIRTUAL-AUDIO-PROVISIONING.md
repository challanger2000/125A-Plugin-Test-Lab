# P96 — Prepare a dedicated Windows 11 virtual-audio machine

P95 already compiles a complete stereo 2-out/2-in ASIO4ALL PCM return analyzer. The remaining **real-world dependency** is a rebooted Windows machine on which both signed third-party kernel drivers are installed and ASIO4ALL is pointed at VB-CABLE. GitHub-hosted Windows-2022 runners cannot be assumed to retain a rebooted kernel driver or interactive selected audio endpoints.

P96 provides a reproducible Windows **read-only preflight**, an explicit, attended vendor installer sequence, and a post-reboot driver-state gate. This can be run without any audio interface.

## Official packages

Download the actual installer executables yourself from the vendors, review their publisher signatures, and keep them locally on an **isolated Windows test installation**:

- [ASIO4ALL official website](https://asio4all.org/) — save a local ASIO4ALL `.exe` installer. Do not rename a random executable to match this path.
- [VB-Audio VB-CABLE official download](https://vb-audio.com/Cable/index.htm) — download and **extract** the package to a folder on the system disk. Its x64 installer is `VBCABLE_Setup_x64.exe`.

The official [VB-Audio installation reference](https://vb-audio.com/Cable/VBCABLE_ReferenceManual.pdf) requires the VB-CABLE setup to run as Administrator, followed by a Windows restart. There is no verified, supported unattended kernel-driver install command here. The script deliberately does not silently install drivers, download from mirror sites, bypass UAC or reboot.

## One-time workflow

From an isolated Administrator Windows PowerShell session (and after approving installation):

```powershell
powershell -NoProfile -File tests/Prepare-VirtualASIO.ps1 -Mode Preflight -OutputFolder C:\QA\P96

powershell -NoProfile -File tests/Prepare-VirtualASIO.ps1 -Mode Install `
  -ASIO4ALLInstaller C:\QA\Installers\asio4all.exe `
  -VBCableExtracted C:\QA\Installers\VBCABLE_Driver_Pack45 `
  -OutputFolder C:\QA\P96 -ApproveDriverInstallation
```

The script rejects missing installers and invalid **Authenticode signatures** before launching the official, interactive vendor installers and records the previous boot fingerprint.

**Manually restart Windows**, then execute:

```powershell
powershell -NoProfile -File tests/Prepare-VirtualASIO.ps1 -Mode Verify -OutputFolder C:\QA\P96
```

The `Verify` command returns an error unless there is a valid ASIO4ALL registration, enabled VB-CABLE input/output PnP devices, the Windows Audio service is running, and Windows has rebooted since the recorded install stage. The report always retains `real_asio4all_audio_callbacks=NOT_RUN` and `virtual_pcm_loopback=NOT_RUN`: Windows driver readiness is **not** audio path acceptance.

Next open the ASIO4ALL control panel and enable the two VB-CABLE input and output channels with matching supported rates/buffers. This is a vendor UI configuration, **not yet automated or verified by the P96 preflight**.

Finally, on a **dedicated and protected** self-hosted Windows x64 runner labeled `125A-VIRTUAL-ASIO`, set `VIRTUAL_ASIO_RUNNER_ENABLED=YES_ISOLATED` and manually dispatch the [P95 live virtual loopback workflow](../.github/workflows/p95-virtual-loopback.yml) with the explicit acknowledgment. Only P95's **actual green driver callback + returned PCM evidence** establishes virtual audio-loopback acceptance.

Do **not** register an everyday personal Windows PC as an unrestricted self-hosted runner in a public GitHub repository: hostile or unreviewed workflows can run commands on that machine. Prefer a separate disposable machine and restrict runners/workflows appropriately.

## Validation in public CI

P96's Windows-2022 job runs the PowerShell script against the real Windows registry and WDM endpoint inventory, and checks that a non-opted-in `Install` invocation fails. That job installs no drivers. A successful P96 CI is only proof that the setup script works and labels its evidence safely, not that ASIO4ALL or VB-CABLE were installed or streamed audio.

The physical ASIO hardware check remains separate. Neither P96 nor P95 can certify actual hardware that is not physically present.
