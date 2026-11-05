# Product acceptance release gate

A successful build or synthetic test is not a product release approval.

`tests/verify_product_acceptance.py` lists 18 user-facing behaviors, including real playback, preset and project recall, all GUI controls, MIDI/WAV exports, tempo and loops, undo/redo, multi-instance isolation and stress tests. Every requirement defaults to NOT COVERED. Overall result is NO-GO until evidence exists for all of them.

Run: `python tests/verify_product_acceptance.py --manifest evidence/product-acceptance.json --out evidence/ACCEPTANCE-RESULT.json`

Manifest schema `125a-product-acceptance-v1`: `product` requires name, version, binary_sha256; `checks` is a dictionary keyed by the exact requirement names in the verifier. Each check requires matching plugin_sha256, a source of real-vst3 / real-windows-gui / real-daw, relative report path, and report_sha256. Each report must include status PASS, matching product_sha256 and requirement, oracle independent, and negative_control DETECTED.

This is a coverage inventory and fails on missing, stale or altered evidence. It does not authenticate the capture system: independent native and DAW integrations are still required for functional certification. Synthetic fixtures are not product evidence. Feature applicability exceptions must be explicitly reviewed rather than silently treated as PASS.
