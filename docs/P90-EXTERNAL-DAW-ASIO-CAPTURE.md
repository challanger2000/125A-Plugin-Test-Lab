# P90 — Independent comparison of an actual externally recorded DAW / ASIO WAV

This is the first bridge toward a **real DAW/ASIO acceptance**, not a replacement for one. The Test Lab cannot access your physical ASIO interface or DAW on a GitHub Actions Windows runner. P90 compares the PCM from a reference WAV (approved before recording) with a second WAV *supplied from the real recording session*, while refusing to claim that editable text metadata establishes its recording provenance.

A legitimate local hardware acceptance workflow must independently document the actual driver/interface and DAW session; P90 does **not** automate that capture. It is an objective audio-content regression test only.

## How to use with a real DAW

1. Supply an independent known reference signal in a mono or stereo uncompressed 16-, 24-, or 32-bit PCM WAV, between 0.25 and 10 seconds, at 44.1, 48, 88.2, 96, 176.4 or 192 kHz. Avoid silence and clipped signals.
2. In the real DAW, route the signal through the setup under test and **record** a second WAV from the interface, with the same sample rate and channel count. Use a low-noise, appropriately calibrated signal. There is no claim of real hardware proof unless the actual local capture session was independently observed and certified.
3. Record exact SHA-256 fingerprints of the plugin module, reference and captured WAV, along with descriptive DAW name/version, driver/interface, session timestamp and buffer setting in the contract.
4. Run the comparator. It aligns up to the declared maximum 0–1024 sample lag and tests signal correlation, amplitude/level drift, waveform residual and lost frames. It rejects empty, clipped, unrelated, truncated or mismatched audio.

Contract example (the paths and SHA-256 strings **must be replaced with the actual file hashes**):

```json
{
  "schema": "125a-external-daw-asio-capture-v1",
  "plugin": {"binary": "C:/QA/Plugin.vst3/Contents/x86_64-win/Plugin.vst3", "sha256": "<64-character real SHA256>"},
  "session": {
    "daw_name": "Your actual DAW name",
    "daw_version": "Installed version",
    "asio_driver": "Actual ASIO driver name",
    "audio_interface": "Actual interface model",
    "rate": 44100,
    "buffer_size": 128,
    "recorded_at_utc": "2026-11-07T15:00:00Z"
  },
  "reference": {"wav": "C:/QA/reference.wav", "sha256": "<actual reference WAV SHA256>"},
  "capture": {"wav": "C:/QA/recorded.wav", "sha256": "<actual capture WAV SHA256>"},
  "oracle": {"min_correlation": 0.98, "max_lag_frames": 256}
}
```

```powershell
python tests/run_external_daw_capture_check.py --contract C:\QA\capture-contract.json --out C:\QA\capture-comparison
```

The JSON output includes measured sample offset, gain, correlation, RMS error, file identities, sample rate and channel configuration. A passing content comparison is `AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED`. This deliberately leaves `hardware_asio_verified: false`, `daw_session_verified: false`, and `release_approved: false`, because the tool cannot verify which process/device really created the supplied file. The automated test compares **every channel** of mono/stereo PCM independently, applying one common sample alignment. A good left channel cannot conceal a broken right channel. It does not independently establish audio-interface channel wiring or capture provenance. It also does **not** test arbitrary synth behavior, editor interaction, parameter recall, DSP fidelity or latency metrics beyond waveform alignment.

**Security:** Run locally; do not upload sensitive audio or proprietary plugin binaries. Textual declarations are not independent driver provenance. External objective ASIO/DAW certification must be provided by an appropriately equipped Windows machine and its trusted capture adapter.

Windows CI deliberately uses generated WAV fixtures to exercise the comparison algorithm (including capture delay, different gain and deliberately bad PCM). No CI-generated audio is presented as a real hardware recording.

## Optional P89 consolidated QA integration

The same source-pinned external comparison can be checked automatically while
generating the multi-plugin P89 summary. Supply the **original** P90 manifest
for each selected plugin, not a manually edited result. The comparator runs
again and must match the selected module SHA-256.

```powershell
python tests/run_unified_qa_gaps.py --batch C:\QA\Batch --out C:\QA\Summary --external-capture reviewed_plugin=C:\QA\capture-contract.json
```

Each plugin's section reports `externally_supplied_audio_comparison` as
`NOT PROVIDED`, `FAIL` or `AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED`.
The report never drops the `PHYSICAL_ASIO_HARDWARE_NOT_TESTED` or
`COMMERCIAL_DAW_SESSION_NOT_TESTED` gaps: metadata and supplied WAVs do not
independently prove a particular DAW or driver generated them.
