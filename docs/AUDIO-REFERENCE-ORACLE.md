# Independent PCM reference regression

The captured VST3 audio is compared sample by sample against a *separately
approved* stereo 24-bit, 44.1-kHz, four-bar WAV file. Neither the test host
nor the plugin generates or chooses the expected waveform during the test.

The comparison checks format, duration, non-silent reference and real output,
and every signed 24-bit PCM sample. Optional per-sample tolerance is an integer
0–128 LSB. Divergent samples, a silent plugin, a silent reference, incorrect
duration and corrupted audio all yield FAIL. Output evidence is
`AUDIO-REFERENCE-RESULT.json`.

```powershell
python verify_audio_reference.py --captured real-capture.wav --reference approved-golden.wav --out audio-proof --tolerance-lsb 2
```

The portable one-command QA accepts the optional argument
`--reference-wav approved-golden.wav`, optionally
`--reference-tolerance-lsb 2`, and performs this check against PCM
captured from the exact verified VST3 binary. If no independently approved
reference exists, the matching test is NOT COVERED, not PASS.

The Windows CI separately synthesizes the expected PCM from the
mathematically specified QA fixture (no reuse of observed capture), then
checks the actual source-built VST3 WAV. Its negative controls introduce an
altered sample, silence in the plugin output and silence in the reference,
and require failure. This establishes detection sensitivity for this known
fixture; it does not establish reference recordings for other products.

A passing reference comparison proves that particular audio test case
matches; it does **not** approve all presets, automation, product-specific
exports, or commercial DAW integration. Release approval remains false.
