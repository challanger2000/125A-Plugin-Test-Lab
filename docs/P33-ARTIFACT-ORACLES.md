# P33 — Independent state/audio/GUI artifact oracle

P33 verifies **actual artifact bytes**, not self-reported VST3 API success.
It checks a saved processor-state binary's SHA-256, a PCM WAV file's
SHA-256 + channel/rate/bit-depth/frame count, and a *painted* pixel from
an uncompressed 24/32-bit Windows BMP. Expected values must come from
an independent, approved reference, not from the plugin under test.

## Invocation

```powershell
python tests/verify_p33_artifacts.py --manifest C:\QA\reference.json --out C:\QA\P33-RESULT.json
```

Manifest example (replace placeholder digests and paths):

```json
{
  "schema": "125a-p33-oracle-v1",
  "cases": [{
    "id": "preset_a_after_reconnect",
    "artifacts": {
      "state": "C:/QA/captured-state.bin",
      "audio": "C:/QA/captured-audio.wav",
      "gui_bmp": "C:/QA/captured-editor.bmp"
    },
    "expected": {
      "state_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "audio": {
        "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "channels": 2,
        "sample_rate": 44100,
        "bits": 24,
        "frames": 44100
      },
      "gui": {"x": 20, "y": 30, "rgb": [255, 90, 0]}
    }
  }]
}
```

All three domains are optional individually, but **at least one
independent expectation is mandatory**. Unspecified domains are
explicitly `not_covered`; a failed declared domain makes the result FAIL.
Missing or malformed files, invalid digests, corrupt WAV, unsupported
BMP and mismatched painted RGB are rejected. The runner emits JSON
and a nonzero exit code on failure.

## Validation and scope

The Windows P25 workflow runs `tests/test_p33_artifacts.py`: a synthetic
positive state/WAV/BMP fixture and deliberate state corruption, wrong
WAV hash, truncated WAV, stale-color pixel and missing-oracle controls.

**P33 is a semantic *verification building block*, not a native VST3
capture host.** The Windows regression proves the independent byte/pixel
comparison logic only. It does not prove an artifact came from a real
product, its exact build, a host playback-save scenario, or the DAW.
Provenance and capture automation are marked NOT VERIFIED until a
separate trusted, product-specific capture adapter supplies them.
Do not use fixture PASS as product certification.

To test real products, capture a VST3's state, audio and editor BMP
through an approved native host, pin the exact product binary/build,
record test parameters and independent expectations, and then run P33
on those files. Avoid committing commercial binaries or private sample content.
