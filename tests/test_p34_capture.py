#!/usr/bin/env python3
"""P34 negative controls: stale files, binary mismatch, missing capture."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("p34", Path(__file__).with_name("run_p34_capture.py"))
p34 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p34)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    binary = root / "Plugin.vst3" / "Contents" / "x86_64-win" / "Plugin.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"synthetic identity, not loaded")
    host = root / "host.exe"
    host.write_bytes(b"mock native process")
    manifest = root / "manifest.json"
    obj = {"schema": "125a-p34-capture-v1",
           "product": {"binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
           "host": str(host)}
    manifest.write_text(json.dumps(obj), encoding="utf-8")
    out = root / "results"
    out.mkdir()
    (out / "captured.wav").write_bytes(b"old wav")
    (out / "captured-state.bin").write_bytes(b"old state")
    called = []
    def no_artifacts(argv, **kwargs):
        called.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")
    result = p34.capture(manifest, out, runner=no_artifacts)
    assert called and called[0][1] == "--capture", "native capture not invoked"
    assert result["status"] == "FAIL", "stale captures accepted"
    assert result["capture"]["gui"] == "NOT COVERED", "GUI coverage overstated"
    assert not (out / "captured.wav").exists(), "old WAV survived"
    assert not (out / "captured-state.bin").exists(), "old state survived"
    obj["product"]["sha256"] = "f" * 64
    manifest.write_text(json.dumps(obj), encoding="utf-8")
    try:
        p34.capture(manifest, out, runner=no_artifacts)
    except ValueError as e:
        assert "SHA-256 mismatch" in str(e), e
    else:
        raise AssertionError("wrong pinned binary accepted")
print("[PASS] P34 stale artifact and wrong module fingerprint rejected")
