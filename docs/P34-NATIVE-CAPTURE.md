# P34 — Native VST3 state and PCM capture (Windows x64)

P34 introduces `125A_Test_Lab_Host.exe --capture <bundle.vst3> <output.wav> <saved-state.bin>`. The real VST3 module is instantiated through Steinberg's hosting API. The existing host sends the fixed 120 BPM / 44.1 kHz / 4-bar transport and writes real 24-bit stereo WAV and real `IComponent::getState()` bytes. No product-specific synthetic `setState()` is injected.

The `tests/run_p34_capture.py` orchestration validates an explicitly pinned module-file SHA-256 before executing the native capture in a separate process, removes stale files before invocation, then validates the new WAV frame count, format, and state presence. It records the artifact digests and a machine-readable `CAPTURE-RESULT.json`.

## Invocation

```powershell
python tests/run_p34_capture.py --manifest C:\QA\capture.json --out C:\QA\P34
```

Example manifest:

```json
{
  "schema": "125a-p34-capture-v1",
  "product": {
    "binary": "C:/Trusted/MyPlugin.vst3/Contents/x86_64-win/MyPlugin.vst3",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "host": "C:/TestLab/125A_Test_Lab_Host.exe"
}
```

Replace the sample SHA with the actual binary's trusted SHA-256. The runner checks the binary content but cannot cryptographically prove its source commit or manufacturer. Keep the trusted binary and host in an isolated Windows runner.

## Scope and exclusions

P34 captures real API state and real native PCM; it does not independently prove musical correctness. A later independent, *externally approved* P33 reference can check the captured files. Even a successful capture can be silent for an instrument without loaded samples, and is not proof of the correct presets, polyphony, MIDI or DAW behavior.

**Native editor pixels are NOT COVERED by P34**: the P31 GUI harness is fixture-specific. Product GUI capture requires an editor-specific native adapter with a documented GUI geometry and independent visual oracle. P34 does not claim all three modalities.

The Windows P25 workflow uses an actual QA state VST3 fixture for a positive capture, a tampered module hash for an invalid manifest, and an empty fake host response over stale files for a negative artifact-provenance check. Only the Test Lab repository is changed.
