#!/usr/bin/env python3
"""Bidirectional, profile-driven GUI click assertions and deliberate failures."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile


spec = importlib.util.spec_from_file_location(
    "matrix", Path(__file__).with_name("run_gui_control_matrix.py"))
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    bundle = root / "Test.vst3"
    binary = bundle / "Contents" / "x86_64-win" / "Test.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"real binary identity fixture")
    host = root / "gui.exe"
    host.write_bytes(b"gui host pinned in profile")
    manifest = {
        "schema": "125a-gui-controls-v1",
        "product": {
            "binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
        "gui_host": str(host),
        "controls": [
            {"id": "on", "param_id": 9001, "x": 100, "y": 90,
             "initial_normalized": 0.0, "expected_normalized": 1.0},
            {"id": "off", "param_id": 9001, "x": 100, "y": 90,
             "initial_normalized": 1.0, "expected_normalized": 0.0}]}
    seen = []

    def native(cmd, **_):
        seen.append(list(cmd))
        assert cmd[1] == "--prove-click-at-from", cmd
        assert Path(cmd[2]).samefile(bundle), (cmd, str(bundle))
        assert cmd[3:6] == ["9001", "100", "90"], cmd
        assert cmd[6:8] in (["0.0", "1.0"], ["1.0", "0.0"]), cmd
        before, after = cmd[6:8]
        return subprocess.CompletedProcess(cmd, 0,
            "[PASS] P04 cycle 1: native click changed VST3 parameter 9001 from " +
            before + " to " + after + "\n"
            "[PASS] P04 cycle 2: native click changed VST3 parameter 9001 from " +
            before + " to " + after + "\n"
            "[PASS] P04 two actual editor attach/message/input/detach cycles\n", "")

    report = matrix.run(manifest, root / "results", runner=native)
    assert report["status"] == "TECHNICAL_PASS", report
    assert report["tested_controls"] == 2
    assert all(x["status"] == "PASS" for x in report["cases"])
    assert report["all_product_controls"] == "NOT COVERED"
    assert len(seen) == 2

    def fail_native(cmd, **_):
        return subprocess.CompletedProcess(cmd, 0,
            "[PASS] P04 cycle 1: native click changed VST3 parameter 9001 from 1 to 0\n"
            "[PASS] P04 two actual editor attach/message/input/detach cycles\n", "")
    failed = matrix.run(manifest, root / "results", runner=fail_native)
    assert failed["status"] == "FAIL", "only one actual mouse click passed two-cycle gate"
    assert all(x["status"] == "FAIL" for x in failed["cases"])

    legacy = {**manifest, "controls": [
        {"id": "legacy", "param_id": 9001, "x": 100, "y": 90,
         "expected_normalized": 1.0}]}
    def old_native(cmd, **_):
        assert cmd[1] == "--prove-click-at" and len(cmd) == 7, cmd
        return subprocess.CompletedProcess(cmd, 0,
            "native click changed VST3 parameter 9001\n" * 2 +
            "two actual editor attach/message/input/detach cycles\n", "")
    assert matrix.run(legacy, root / "results", runner=old_native)["status"] == "TECHNICAL_PASS"

    failures = [
        {"initial_normalized": 1.0, "expected_normalized": 1.0},
        {"initial_normalized": 0.0, "expected_normalized": 0.0},
        {"initial_normalized": -0.01, "expected_normalized": 0.0},
        {"initial_normalized": 1.01, "expected_normalized": 0.0},
        {"initial_normalized": "1", "expected_normalized": 0.0},
        {"initial_normalized": 1.0, "expected_normalized": float("nan")},
    ]
    for change in failures:
        wrong = {**manifest, "controls": [
            {**manifest["controls"][1], **change}]}
        try:
            matrix.validate(wrong)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe GUI click accepted: " + repr(change))
print("[PASS] universal GUI profile verifies real on/off coordinates and rejects unproven clicks")
