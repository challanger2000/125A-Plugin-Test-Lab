# P58 — Native Windows ASIO callback-to-VST3 engine

The new `src/physical_asio.cpp` is a **real Windows ASIO host**, not a
simulated process-callback timer. On a workstation where the selected
ASIO driver is actually installed, it:

- independently checks driver registry name/CLSID and instantiates its
  actual `IASIO` COM object via `CoCreateInstance`
- checks physical output channels, exact sample rate, buffer limits and
  32-bit little-endian float/int output formats (unsupported devices fail)
- creates the hardware driver's real double buffers and callbacks, loads
  the exact native Windows VST3 and runs `IAudioProcessor::process()`
  in the driver callback (32-bit float, stereo output)
- generates a low-amplitude deterministic test signal for VST3 input
  effects, preallocates callback buffers and observes callback duration
  against the hardware block budget
- records actual callback counts, DSP failures, driver overload messages,
  and deadline observations. Failed/absent devices never emit a passing
  `native-asio-evidence.json` report.
- issues P56's nonce-bound exact module/executor SHA-256 report only
  after a successful real callback session and complete device shutdown.

P58 deliberately excludes MIDI-driven instrument coverage, arbitrary
ASIO sample representations, latency round-trip measurements, DAW project
reopen, and real concurrent state-save. Thus successful callback evidence
is **not** all-product functional correctness or a commercial DAW release.

## Build and licensing

Supply Steinberg's ASIO SDK separately (its contents are not vendored
into this repository):

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 "-DASIO_SDK_DIR=C:/SDK/ASIO"
cmake --build build --config Release --target TestLabPhysicalASIO
```

The P58 GitHub Windows build checks out the exact source reference
`audiosdk/asio@496a0765b8bb9c26f764f22f9a9712a937177db2` **for CI
compilation only**; no SDK binary or headers are repackaged. Steinberg
ASIO SDK carries a dual license (GPLv3 or proprietary agreement);
software distribution or closed-source use requires selecting and
complying with the applicable license. See Steinberg's own terms.

Use the P56 `tests/run_physical_asio.py` plan, supplying the actual
`125A_Test_Lab_Physical_ASIO.exe` and exact SHA-256 (not placeholder
hashes), on a machine containing a registered ASIO driver and VST3.
The P56 native call contract is exactly
`--physical-asio-probe --plugin <dll> --driver-name <name>
--driver-clsid <clsid> --rate <hz> --frames <n> --callbacks <count>
--nonce <nonce> --out <evidence.json>`.

**No real audio interface is available on ordinary GitHub Windows-2022
workers.** P58 CI demonstrates compilation and negative rejection only:
`physical_asio_driver_callbacks: NOT RUN`. Physical ASIO success
requires an actual external-device run, e.g. via the separately opted-in
self-hosted `125A-ASIO` GitHub Actions worker. This has not happened
merely by merging P58.
