# P95 — actual ASIO4ALL/VB-CABLE 2-in / 2-out PCM loopback

P94 can verify genuine registered ASIO4ALL driver callbacks but cannot prove that VB-CABLE actually carries the emitted signal. **P95 adds that missing audio-path oracle.**

The P95 native Windows executable is built from the already-audited P58 ASIO host source with a **separate compile-time opt-in mode**. It refuses any request other than `--virtual-asio-loopback`, creates two output plus two input buffers through the registered ASIO4ALL COM driver, and records both the emitted VST3 PCM and returning actual ASIO input PCM into a bounded preallocated float32 trace. A separate source-built VST3 fixture generates different, low-level 317 Hz and 557 Hz amplitude-coded patterns in left and right channels. No samples, device or external DAW required for the source-built fixture itself.

The independent Python P95 analyzer requires:
- the real native driver's SHA-256 and fresh nonce evidence (no deadlines, xruns or DSP errors),
- consistent sample rate, buffer size and exact PCM frame count from each ASIO callback,
- **independent** emitted source PCM specification (phase-locked 317/557 Hz, exact per-channel gate/level pattern, bounded sample/RMS error) before accepting any return,
- non-silent output **and** non-silent captured input on both channels,
- positive correlation after bounded latency alignment **including zero-delay boundary**,
- return gain constrained to +/-3 dB per channel (the virtual cable path must not silently hide a 4x increase); this is a provisional QA threshold, not a hardware calibration,
- P102 signed-sample DC-to-RMS sanity: full-wave-rectified audio may preserve identical RMS envelopes and gain yet be audibly wrong; captured DC/RMS above 12% is rejected on either channel. This is only a bounded distortion detector, not a complete waveform-fidelity guarantee.
- consistent L/R latency and no swapped/crosstalk-dominated channels.

Result `VIRTUAL_ASIO_LOOPBACK_PASS` is virtual driver evidence **only**. It does **not** approve physical ASIO hardware, a commercial DAW, actual external USB hardware, or any product release. No cloud mock test produces this result legitimately. The Linux unit tests explicitly fabricate PCM only to verify the oracle accepts the correct 317/557 Hz stimulus and rejects silent, swapped, truncated, wrong-rate, wrong-source-frequency and +12.041 dB return-gain traces. A separate 0-sample delay boundary must report 0, not 256. These tests do NOT run a Windows audio driver or authorize product release.

## P101: PCM content is not proof of driver execution

The standalone `verify_virtual_asio_loopback.py` can evaluate deliberately fabricated PCM and JSON callback metadata. Its successful status `VIRTUAL_ASIO_PCM_LOOPBACK_PASS` means **PCM content agrees with the P95 stimulus/return contract only**. The standalone report deliberately sets `pcm_content_verified=true`, `driver_execution_verified=false` and `virtual_loopback_verified=false`, even if the content is correct. Never treat this report, even with plausible driver metadata, as proof of a running ASIO driver.

Only `run_virtual_asio_loopback.py` may report `VIRTUAL_ASIO_LOOPBACK_PASS`, after the separately consented native executable returns successfully, the fresh nonce, exact native/module hashes, real callback counts and PCM evidence are checked, and the content-only verifier passes. That top-level report alone records `driver_execution_verified=true` for the **virtual** driver session; this is not physical hardware, a commercial DAW or release certification. Synthetic regression fixtures must always leave driver execution false.

## Real Windows run

A dedicated isolated Windows 11 runner must have ASIO4ALL and VB-CABLE installed, rebooted, with both VB-CABLE playback and recording channels enabled **in the ASIO4ALL device selection panel**. This is a kernel driver requirement, not a Python dependency. The ASIO4ALL driver must expose at least two ASIO inputs and two ASIO outputs. Configure repository variable `VIRTUAL_ASIO_RUNNER_ENABLED=YES_ISOLATED`, and dedicate a private Windows x64 self-hosted runner with label `125A-VIRTUAL-ASIO` (never a personal daily-use PC attached to a public repository).

Use GitHub Actions → **P95 real virtual ASIO input-output PCM loopback oracle** → Run workflow, select **main**, enable the explicit virtual-driver acknowledgment, and specify supported rate (44.1 / 48 kHz) and buffer (256 / 512). The workflow builds and hashes the native ASIO loopback host and sound fixture, executes **500 actual ASIO4ALL callbacks**, independently compares the captured PCM trace and emits a small public report without revealing local paths or binaries.

The public GitHub-hosted Windows job compiles the full VST3 and IASIO C++ loopback code, but **does not execute real virtual sound drivers**. This remains a required follow-up until an actual driver-equipped isolated machine has been configured and a real P95 live run is green.

## Isolation and known gaps

- This version requires the same ASIO4ALL instance to expose both halves of VB-CABLE as input and output; do not claim working capture if ASIO4ALL exposes only one side.
- Analysis reports an estimated virtual loop delay at 256-frame resolution; it is not a physical analog roundtrip measurement.
- WDM endpoint discovery and returned PCM agreement establish a functional virtual return, but not unique PnP device identity cryptographically. Verify device selection in the ASIO4ALL panel.
- Native PCM trace is kept **locally** on the private runner; only redacted timing/audio metrics are uploaded.
- Live test requires installed Windows drivers; Actions cannot guarantee a Windows audio kernel environment after a reboot on an ephemeral hosted runner.
