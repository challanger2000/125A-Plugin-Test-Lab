#!/usr/bin/env python3
"""Acceptance gate mutation tests: no fake green from missing or stale evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location("accept", Path(__file__).with_name("verify_product_acceptance.py"))
accept = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accept)
sha = "b" * 64

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    m = {"schema": "125a-product-acceptance-v1",
         "product": {"name": "Synthetic", "version": "0.1", "binary_sha256": sha},
         "checks": {}}
    result = accept.evaluate(m, root)
    assert result["status"] == "NO-GO" and result["covered"] == 0
    assert len(result["checks"]) == len(accept.REQUIREMENTS)

    # Even correctly signed single-domain evidence must never release the plugin.
    r = root / "audio.json"
    r.write_text(json.dumps({"status": "PASS", "product_sha256": sha,
                            "requirement": "audio_output_correctness",
                            "oracle": "independent", "negative_control": "DETECTED"}), encoding="utf-8")
    m["checks"]["audio_output_correctness"] = {
        "plugin_sha256": sha, "source": "real-vst3",
        "report": "audio.json",
        "report_sha256": hashlib.sha256(r.read_bytes()).hexdigest()}
    result = accept.evaluate(m, root)
    assert result["status"] == "NO-GO" and result["covered"] == 1

    # Fake fixture claims are explicitly rejected even when report says PASS.
    m["checks"]["audio_output_correctness"]["source"] = "synthetic-fixture"
    assert accept.evaluate(m, root)["covered"] == 0
    m["checks"]["audio_output_correctness"]["source"] = "real-vst3"

    # Corruption, missing negative control, path traversal, and wrong plugin hash fail.
    r.write_text(r.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert accept.evaluate(m, root)["covered"] == 0
    m["checks"]["audio_output_correctness"]["report_sha256"] = hashlib.sha256(r.read_bytes()).hexdigest()
    r.write_text(json.dumps({"status": "PASS", "product_sha256": sha,
                            "requirement": "audio_output_correctness",
                            "oracle": "independent"}), encoding="utf-8")
    m["checks"]["audio_output_correctness"]["report_sha256"] = hashlib.sha256(r.read_bytes()).hexdigest()
    assert accept.evaluate(m, root)["covered"] == 0
    m["checks"]["audio_output_correctness"]["report"] = "../outside.json"
    assert accept.evaluate(m, root)["covered"] == 0
    m["checks"]["audio_output_correctness"]["plugin_sha256"] = "c" * 64
    assert accept.evaluate(m, root)["covered"] == 0

    # Unknown acceptance check must not be silently disregarded.
    m["checks"]["unrecognized"] = {}
    try:
        accept.evaluate(m, root)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown requirement accepted")
    # Fully populated independent evidence index is an explicit acceptance of
    # report coverage (not cryptographic validation of its producing host).
    m["checks"].clear()
    for requirement in accept.REQUIREMENTS:
        file = root / (requirement + ".json")
        file.write_text(json.dumps({"status": "PASS", "product_sha256": sha,
                                   "requirement": requirement, "oracle": "independent",
                                   "negative_control": "DETECTED"}), encoding="utf-8")
        m["checks"][requirement] = {
            "plugin_sha256": sha, "source": "real-vst3",
            "report": file.name,
            "report_sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    assert accept.evaluate(m, root)["status"] == "PASS", "complete evidence index refused"
    m["checks"].pop("gui_all_controls")
    assert accept.evaluate(m, root)["status"] == "NO-GO", "one missing GUI domain accepted"
print("[PASS] production acceptance gate rejects missing, stale, synthetic and counterfeit evidence")
