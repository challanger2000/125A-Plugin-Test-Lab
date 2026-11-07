# P94 — ASIO4ALL with a virtual Windows soundcard (VB-CABLE)

**Scope:** Virtual Windows audio-driver integration, not physical ASIO hardware acceptance.

P58 already includes a native ASIO callback host and a separate SHA-256-pinned native VST3 processor. P94 reuses that executable with an independently verified real Windows **ASIO4ALL** COM registration and active **VB-CABLE Input/Output** WDM endpoint pair. It then performs bounded real driver callbacks and tests buffer-size/rate, process failures, dropouts, deadline misses and the native nonce/identity evidence. This does not modify any existing plugin repository.

The existing P58 binary still uses the CLI argument `--physical-asio-probe` for historical reasons. P94 deliberately wraps it in an independent virtual-only result **`VIRTUAL-ASIO4ALL-RESULT.json`**; it never calls this evidence a physical hardware test. A positive result is `VIRTUAL_ASIO_CALLBACK_PASS`, **not** a commercial DAW or physical ASIO pass.

## Driver prerequisites and one-time installation

A Windows 11 x64 **isolated, disposable VM or dedicated test machine**, installed and rebooted with:

1. [ASIO4ALL](https://asio4all.org/) from the official author (actual registered driver under `HKLM\SOFTWARE\ASIO\ASIO4ALL v2`, if that is the installed driver name).
2. [VB-Audio VB-CABLE](https://vb-audio.com/Cable/index.htm) installed as administrator, followed by a Windows reboot. The manufacturer explicitly requires a reboot. The WDM endpoint names should include **CABLE Input** (playback) and **CABLE Output** (recording).
3. ASIO4ALL configuration panel with the VB-CABLE WDM endpoint selected and enabled, and an actual supported sample rate/buffer size.
4. Visual Studio 2022 Build Tools, Git, CMake and Python 3.12 on the isolated test machine.

The framework deliberately **does not automatically download/install kernel audio drivers, bypass installation prompts, or restart the user workstation**. A GitHub-hosted Windows runner can lack interactive audio endpoints and a safe reboot/persistent device state; a green Linux CI test must never be interpreted as a successful audio driver session. Configure a dedicated private self-hosted Windows runner labelled `125A-VIRTUAL-ASIO` only after drivers are installed and rebooted, with repository variable `VIRTUAL_ASIO_RUNNER_ENABLED=YES_ISOLATED`. Do not attach a personal everyday PC to a public repository's self-hosted CI, and do not grant arbitrary unreviewed PRs access.

## Actual opt-in execution

Open **Actions → P94 virtual ASIO4ALL and VB-CABLE driver bridge → Run workflow**, select the *main* branch and provide the exact VST3 **module DLL** path on the dedicated Windows runner (not a VST3 bundle directory). Set the registered ASIO4ALL name, supported sample rate (44.1 or 48 kHz), buffer size (128/256/512/1024), and opt-in acknowledgment.

The workflow will:
- confirm the exact ASIO4ALL Windows registration and active VB-CABLE WDM playback/recording endpoints,
- build the P58 C++ native ASIO host against a pinned external ASIO SDK,
- SHA-256 pin the VST3 module and host and create a one-scenario native driver plan,
- invoke actual COM ASIO4ALL callbacks on the installed WDM driver and verify 500 successful callbacks with no missed deadlines, xruns, processor errors or changed module identities,
- publish a redacted report that explicitly says `physical_hardware_verified=false` and `daw_session_verified=false`.

The driver supports different buffer sizes; an unsupported rate or buffer size must fail rather than be silently substituted. To test several scenarios, dispatch several times. ASIO4ALL can require device configuration or exclusive access; if it cannot initialize VB-CABLE, the workflow fails instead of fabricating a PASS.

## Precisely what it does NOT prove

- The native P58 host currently creates **two ASIO output buffers**. It does not capture the VB-CABLE recording endpoint or measure actual roundtrip PCM/latency.
- Detecting the WDM Input and Output endpoints does **not** prove that ASIO4ALL has selected VB-CABLE rather than another device; the actual active WDM routing is still a separate acceptance gap. ASIO4ALL's own panel must be configured appropriately.
- Virtual ASIO callbacks prove the driver/host interface, not the reliability of a USB interface, speaker signal chain, licensed DAW or a physical ASIO device.
- Driver installation on a GitHub-hosted runner, independent virtual loopback PCM verification and hardware ASIO approval are **not complete** in this milestone.

**Public CI:** The lightweight Linux workflow runs fail-closed tests for fake driver names, wrong CLSIDs, absent WDM pairs, modified binaries, incorrect nonces, failing native executables and false physical/DAW labels, without touching Windows audio devices. Actual ASIO4ALL driver execution only takes place with an explicitly configured private Windows runner.

Sources: [ASIO4ALL official site](https://asio4all.org/), [VB-Audio driver and reboot instructions](https://vb-audio.com/Cable/index.htm), and [existing P58 native IASIO host](../src/physical_asio.cpp).
