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
        target = Path(cmd[cmd.index("--out") + 1])
        target.mkdir(parents=True, exist_ok=True)
        if cmd[1].endswith("run_product_qa.py"):
            (target / "PRODUCT-QA-RESULT.json").write_text(
                json.dumps({"status": "TECHNICAL_PASS", "release_approved": False,
                            "verified_vst3_sha256": sha}), encoding="utf-8")
            captured = target / "P34" / "captured-state.bin"
            captured.parent.mkdir(parents=True, exist_ok=True)
            captured.write_bytes(b"stored project state fixture")
            return subprocess.CompletedProcess(cmd, 0, "native smoke passed", "")
        if cmd[1].endswith("run_state_reload.py"):
            (target / "RECALL-RESULT.json").write_text(
                json.dumps({"status": "PASS", "verified_vst3_sha256": sha,
                            "new_process_instances": 2,
                            "fresh_process_recall": "PASS",
                            "audio_determinism": "NOT COVERED",
                            "musical_correctness": "NOT COVERED"}), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "two fresh native hosts", "")
        raise AssertionError("unexpected synthetic stage: " + repr(cmd))

    report = quick.run(bundle, host, stress, out, runner=synthetic_native)
    assert report["status"] == "TECHNICAL_PASS"
    assert report["release_approved"] is False
    assert report["verified_module_sha256"] == sha
    assert report["coverage"]["fresh_process_project_recall"] == "PASS"
    assert report["coverage"]["recall_audio_determinism"] == "NOT COVERED"
    assert report["coverage"]["product_gui_controls"] == "NOT COVERED"
    assert report["coverage"]["commercial_daw_integration"] == "NOT COVERED"

    def absent(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, "", "")

    bad = quick.run(bundle, host, stress, out, runner=absent)
    assert bad["status"] == "FAIL" and bad["release_approved"] is False
    assert not (out / "native" / "PRODUCT-QA-RESULT.json").exists(), (
        "stale native report survived a new invocation")

    # A native host that returns success but no new state-recall report must
    # never reuse old green evidence from an earlier quickcheck.
    def missing_recall(cmd, **kwargs):
        if cmd[1].endswith("run_state_reload.py"):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return synthetic_native(cmd, **kwargs)
    failed_recall = quick.run(bundle, host, stress, out, runner=missing_recall)
    assert failed_recall["status"] == "FAIL", "stale recall PASS reused"
    assert failed_recall["release_approved"] is False
    assert not (out / "fresh-recall" / "RECALL-RESULT.json").exists()

    def wrong_recall_identity(cmd, **kwargs):
        if cmd[1].endswith("run_state_reload.py"):
            target = Path(cmd[cmd.index("--out") + 1])
            target.mkdir(parents=True, exist_ok=True)
            (target / "RECALL-RESULT.json").write_text(json.dumps({
                "status": "PASS", "verified_vst3_sha256": "f" * 64,
                "new_process_instances": 2, "fresh_process_recall": "PASS"
            }), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "wrong plugin", "")
        return synthetic_native(cmd, **kwargs)
    assert quick.run(bundle, host, stress, out, runner=wrong_recall_identity)[
        "status"] == "FAIL", "recall for another plugin accepted"

    def mismatched(cmd, **kwargs):
        target = Path(cmd[cmd.index("--out") + 1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "PRODUCT-QA-RESULT.json").write_text(json.dumps({
            "status": "TECHNICAL_PASS", "release_approved": False,
            "verified_vst3_sha256": "0" * 64}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "fake other plugin", "")

    assert quick.run(bundle, host, stress, out, runner=mismatched)["status"] == "FAIL"
    # The same invocation can prove a real editor's two lifecycle cycles.
    gui = root / "gui.exe"
    gui.write_bytes(b"dummy native gui host")
    controls_file = root / "independent-controls.json"
    controls_file.write_text(json.dumps({"controls": [
        {"id": "switch", "param_id": 9001, "x": 120, "y": 80,
         "expected_normalized": 1.0}]}), encoding="utf-8")

    def all_native_gui(cmd, **kwargs):
        if cmd[1] == "--probe":
            return subprocess.CompletedProcess(
                cmd, 0, "two actual editor attach/message/input/detach cycles", "")
        if cmd[1].endswith("run_gui_control_matrix.py"):
            out_name = Path(cmd[cmd.index("--out") + 1])
            out_name.mkdir(parents=True, exist_ok=True)
            (out_name / "GUI-CONTROL-RESULT.json").write_text(json.dumps({
                "status": "TECHNICAL_PASS", "verified_module_sha256": sha,
                "tested_controls": 1}), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "real native matrix success", "")
        return synthetic_native(cmd, **kwargs)

    report = quick.run(bundle, host, stress, out, runner=all_native_gui,
                       gui_host=gui, gui_controls=controls_file)
    assert report["status"] == "TECHNICAL_PASS"
    assert report["coverage"]["native_gui_lifecycle"] == "PASS"
    assert report["coverage"]["declared_gui_controls"] == "PASS"
    assert report["coverage"]["product_gui_controls"] == "NOT COVERED"

    def gui_not_available(cmd, **kwargs):
        if cmd[1] == "--probe":
            return subprocess.CompletedProcess(cmd, 10, "", "[INCONCLUSIVE] no editor")
        return synthetic_native(cmd, **kwargs)

    result = quick.run(bundle, host, stress, out, runner=gui_not_available,
                       gui_host=gui)
    assert result["status"] == "TECHNICAL_PASS"
    assert result["coverage"]["native_gui_lifecycle"] == "NOT COVERED"
    result = quick.run(bundle, host, stress, out, runner=gui_not_available,
                       gui_host=gui, gui_controls=controls_file)
    assert result["status"] == "FAIL", "requested unexecutable GUI test approved"

    def absent_matrix(cmd, **kwargs):
        if cmd[1].endswith("run_gui_control_matrix.py"):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return all_native_gui(cmd, **kwargs)

    result = quick.run(bundle, host, stress, out, runner=absent_matrix,
                       gui_host=gui, gui_controls=controls_file)
    assert result["status"] == "FAIL", "stale GUI evidence accepted"

    (bundle / "Contents" / "x86_64-win" / "Extra.vst3").write_bytes(b"extra")
    try:
        quick.run(bundle, host, stress, out, runner=synthetic_native)
    except ValueError as e:
        assert "exactly one" in str(e)
    else:
        raise AssertionError("ambiguous multi-module bundle accepted")
print("[PASS] one-command quickcheck rejects stale, wrong module and missing coverage")
