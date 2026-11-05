# Product acceptance release gate

A successful build or synthetic test is not a product release approval.

`tests/verify_product_acceptance.py` lists 18 user-facing behaviors, including real playback, preset and project recall, all GUI controls, MIDI/WAV exports, tempo and loops, undo/redo, multi-instance isolation and stress tests. Every requirement defaults to NOT COVERED. Overall result is NO-GO until evidence exists for all of them.

Run: `python tests/verify_product_acceptance.py --manifest evidence/product-acceptance.json --out evidence/ACCEPTANCE-RESULT.json`

Manifest schema `125a-product-acceptance-v1`: `product` requires name, version, binary_sha256; `checks` is a dictionary keyed by the exact requirement names in the verifier. Each check requires matching plugin_sha256, a source of real-vst3 / real-windows-gui / real-daw, relative report path, and report_sha256. Each report must include status PASS, matching product_sha256 and requirement, oracle independent, and negative_control DETECTED.

This is a coverage inventory and fails on missing, stale or altered evidence. It does not authenticate the capture system: independent native and DAW integrations are still required for functional certification. Synthetic fixtures are not product evidence. Feature applicability exceptions must be explicitly reviewed rather than silently treated as PASS.

## First real-binary technical test command

With a pinned P32 playback-save manifest and a P34 native-capture manifest for the **same** .vst3 module, run:

```powershell
python tests/run_product_qa.py --p32 evidence/p32.json --p34 evidence/p34.json --out evidence/product-qa
```

This invokes native VST3 processing, in-playback state saves, PCM rendering and component-state capture, then records both results in `PRODUCT-QA-RESULT.json`. Incompatible binary digests or a failed test produce FAIL. Passing technical checks produce `TECHNICAL_PASS` but **release_approved remains false** until actual independent product GUI, audio, MIDI, preset and DAW assertions are implemented and proven. The Windows regression runs this command on a real, instrumented QA VST3 and rejects a wrong-product negative manifest.
