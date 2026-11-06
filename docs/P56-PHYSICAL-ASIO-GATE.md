# P56 — Physical ASIO acceptance evidence gate

## What is actually implemented

The Test Lab now offers a **fail-closed** Windows hardware ASIO adapter contract
(`tests/run_physical_asio.py`). It verifies the exact SHA-256 of both the real
VST3 module and a separately approved native ASIO executor; confirms the
requested physical ASIO driver name/CLSID is installed in the Windows
`HKLM\\SOFTWARE\\ASIO` registry; and launches the pinned executor for
each independently declared sample-rate/buffer combination with a fresh,
unpredictable nonce.

For each scenario the native executor must emit genuine, session-specific
callback evidence:
- exact module/executor hashes, actual ASIO driver name/CLSID
- actual 44.1/48/96 kHz sample rate and 64–1024 frame hardware buffer size
- at least the requested number of real ASIO callbacks and process callbacks
- **zero** deadline misses, XRUNs and processing failures

Missing executor, absent ASIO driver, unsupported values, stale evidence,
replayed nonce, incomplete callbacks, nonzero failures, wrong DLL or a CI machine
without the device must **never** result in a PASS. The status is `NOT_RUN`
when hardware cannot be exercised. The JSON status `EVIDENCE_ACCEPTED` means
that a specifically pinned external executor reported all required metrics
and met the evidence contract — **not** that this Python harness independently
measured ASIO clock timing or certified a commercial DAW.

A vendor-neutral product contract (replace every example path, hash, driver
and test profile with real, approved ones; use a disposable test project):

```json
{
  "schema": "125a-physical-asio-plan-v1",
  "product": {
    "path": "C:/QA/Plugin.vst3/Contents/x86_64-win/Plugin.vst3",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "executor": {
    "path": "C:/QA/VerifiedAsioExecutor.exe",
    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  },
  "asio_driver": {
    "name": "Approved ASIO driver registry name",
    "clsid": "{12345678-1234-1234-1234-123456789abc}"
  },
  "scenarios": [
    {"sample_rate": 44100, "buffer_frames": 128, "callbacks": 12000},
    {"sample_rate": 48000, "buffer_frames": 256, "callbacks": 12000}
  ]
}
```

On an **opted-in, independently equipped Windows workstation**:

```powershell
python tests/run_physical_asio.py --plan C:\QA\asio-plan.json --out C:\QA\asio-evidence --acknowledge-physical-asio
```

A separate optional GitHub Actions workflow,
`.github/workflows/p56-physical-workstation.yml`, targets only runners
bearing `self-hosted, Windows, X64, 125A-ASIO`; it requires manual
`workflow_dispatch` and explicit physical-device confirmation. The normal
`windows-2022` cloud test **never** receives or fakes that label; CI checks
negative/replay/hardware-absent cases and publishes `NOT_RUN`.

## Critical remaining work and release gate

**An actual native ASIO-driver VST3 executor is not included in P56.**
The existing Test Lab C++ VST3 hosts process real PCM, but they do not
open hardware ASIO devices, receive their callbacks or measure their
device deadlines. Until such an independently audited ASIO backend is built
and successfully runs on a physical Windows PC with a compatible ASIO driver,
**P56 hardware qualification remains NOT RUN.** A simulated unit-test
`EVIDENCE_ACCEPTED` is *not* real device evidence.

Further separate gates are still required for background save/recall while
real audio runs, genuine physical-driver deadline timing, actual DAW session
save/reload and customer release. The adapter deliberately retains
`commercial_daw_session: NOT_RUN` and `release_approved: false`
even if its external hardware evidence is accepted.

No user-side Python installation is needed for **GitHub-hosted unit tests**.
The optional physical runner needs its own prerequisites and access to the
approved executor. No product repository source or DAW project was changed.
