#!/usr/bin/env python3
"""Quickcheck fail-closed release, stale-report and wrong-product tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("quickcheck", Path(__file__).with_name("run_plugin_quickcheck.py"))
quick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quick)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    bundle = root / "A.vst3"
    binary = bundle / "Contents" / "x86_64-win" / "A.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"fixed test plugin module")
    sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    host = root / "host.exe"
    stress = root / "stress.exe"
    host.write_bytes(b"host")
    stress.write_bytes(b"stress")
    out = root / "result"

    def synthetic_native(cmd, **kwargs):
        assert cmd[1].endswith("run_product_qa.py")
        target = Path(cmd[cmd.index("--out") + 1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "PRODUCT-QA-RESULT.json").write_text(
            json.dumps({"status": "TECHNICAL_PASS", "release_approved": False,
                        "verified_vst3_sha256": sha}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "native smoke passed", "")

    report = quick.run(bundle, host, stress, out, runner=synthetic_native)
    assert report["status"] == "TECHNICAL_PASS"
    assert report["release_approved"] is False
    assert report["verified_module_sha256"] == sha
    assert report["coverage"]["product_gui_controls"] == "NOT COVERED"
    assert report["coverage"]["commercial_daw_integration"] == "NOT COVERED"

    def absent(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, "", "")

    bad = quick.run(bundle, host, stress, out, runner=absent)
    assert bad["status"] == "FAIL" and bad["release_approved"] is False
    assert not (out / "native" / "PRODUCT-QA-RESULT.json").exists(), (
        "stale native report survived a new invocation")

    def mismatched(cmd, **kwargs):
        target = Path(cmd[cmd.index("--out") + 1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "PRODUCT-QA-RESULT.json").write_text(json.dumps({
            "status": "TECHNICAL_PASS", "release_approved": False,
            "verified_vst3_sha256": "0" * 64}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "fake other plugin", "")

    assert quick.run(bundle, host, stress, out, runner=mismatched)["status"] == "FAIL"
    (bundle / "Contents" / "x86_64-win" / "Extra.vst3").write_bytes(b"extra")
    try:
        quick.run(bundle, host, stress, out, runner=synthetic_native)
    except ValueError as e:
        assert "exactly one" in str(e)
    else:
        raise AssertionError("ambiguous multi-module bundle accepted")
print("[PASS] one-command quickcheck rejects stale, wrong module and missing coverage")
