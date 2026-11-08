# P102 — Real ASIO callback failure diagnostics (NOT a PASS)

P179 on an actual Windows PC with **Yamaha Steinberg USB ASIO** now gets
past buffer validation: `IASIO::getBufferSize` reports **512 / 512 / 512**
frames (granularity 0, only 512 accepted), and `canSampleRate` accepts
44.1 / 48 / 96 kHz. At 512 frames / 44.1 kHz, the local report rejected
the run with the aggregated failure
`Physical ASIO real callback timing or DSP errors observed`.
This is **real hardware acceptance FAIL/NOT VERIFIED**, not evidence that
the AWE DSP caused the failure. The previous error message did not reveal
whether the failed gate was driver messages, timing, sample-rate changes,
VST3 `process`, output conversion or another callback condition.

P102 adds an optional command-line argument to the existing Windows native
physical-ASIO host:

```powershell
--diagnostic-out C:/new-output/ASIO-CALLBACK-DIAGNOSTICS.json
```

This diagnostic is written only **after** an actual ASIO driver has been
instantiated, streaming has run, the driver has returned from `stop()`,
and the plugin has been deactivated. It is deliberately produced **before**
the strict original callback gate, so the next failure's raw counters
survive instead of being discarded.

### Recorded signals, independently inspectable

- Real ASIO callback count versus successfully completed VST3 callbacks.
- Audio-callback wall-duration deadline overruns, separately from
  inter-callback spacing gaps. Existing total deadline counter and gate
  are **unchanged**.
- Maximum observed callback execution and spacing, in nanoseconds.
- Native ASIO overload/resync/reset driver notifications.
- Unexpected sample-rate-change notifications.
- VST3 `process()` returned error, failed MIDI event insert,
  nonfinite plugin PCM, missing output buffer, sample writer failure,
  caught exceptions and total process failures.
- MIDI NoteOn/NoteOff counts, PCM nonzero sample count and peak value.
- Executable and plugin SHA-256, real driver name/CLSID, requested
  sample rate and hardware buffer size, and fresh session nonce.

The schema is `125a-asio-callback-diagnostic-v1`, with **mandatory**
`status=DIAGNOSTIC_ONLY_NOT_HARDWARE_PASS`,
`physical_asio_verified=false`, `commercial_daw_verified=false`,
and `release_approved=false`. It cannot be mistaken for the P56
or P100 positive attestation: successful ASIO/MIDI audio still needs
the **independent original** native proof files with all zero-fault gates.

The diagnostic file is never created for an unregistered physical ASIO
driver, a nonexistent VST3 module, or a path alias with a PASS proof.
CI compiles the actual native P58/P100 code, runs its sample-format and
buffer-selection selftests, and uses a real source-built test VST3 against
a deliberately missing driver to verify *no* false proof/diagnostic.

Only a user workstation's real callback run can populate this report.
Cloud Windows CI cannot run an ASIO interface or validate the private ROM/SF2.
This is **not** a MIDI sound-fidelity certification or a full audit.
