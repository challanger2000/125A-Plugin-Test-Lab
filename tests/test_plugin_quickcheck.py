#!/usr/bin/env python3
"""Quickcheck fail-closed release, stale-report and wrong-product tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import wave

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
            p32_manifest = Path(cmd[cmd.index("--p32") + 1])
            fixture = json.loads(p32_manifest.read_text(encoding="utf-8"))
            cases = fixture["cases"]
            assert {(x["rate"], x["block"]) for x in cases} == {
                (44100, 64), (44100, 512),
                (48000, 64), (48000, 512),
                (96000, 64), (96000, 512)}
            assert all(x["assertions"]["save_success"] == {"eq": 500}
                       and x["assertions"]["process_failures"] == {"eq": 0}
                       for x in cases)
            adapter_path = target / "P32" / "ADAPTER-RESULT.json"
            adapter_path.parent.mkdir(parents=True, exist_ok=True)
            adapter_path.write_text(json.dumps({
                "status": "PASS", "verified_vst3_sha256": sha,
                "cases": [{"id": c["id"], "status": "PASS",
                           "realtime_certification": "PASS",
                           "timing": {"callback_overruns": 0}} for c in cases]
            }), encoding="utf-8")
            captured = target / "P34" / "captured-state.bin"
            captured.parent.mkdir(parents=True, exist_ok=True)
            captured.write_bytes(b"stored project state fixture")
            # Independent known PCM with audible content for the optional
            # per-product reference comparison. This only simulates the wrapper.
            audio = target / "P34" / "captured.wav"
            with wave.open(str(audio), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(3)
                wav.setframerate(44100)
                wav.writeframes(b"\x00\x00\x20" * (352800 * 2))
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
    assert report["coverage"]["sample_rate_buffer_matrix"] == "PASS"
    assert report["sample_rate_buffer_matrix_cases"] == 6
    assert report["coverage"]["realtime_deadline_observation"] == "PASS"
    assert report["measured_callback_overruns"] == 0
    assert report["coverage"]["fresh_process_project_recall"] == "PASS"
    assert report["coverage"]["recall_audio_determinism"] == "NOT COVERED"
    assert report["coverage"]["product_gui_controls"] == "NOT COVERED"
    assert report["coverage"]["commercial_daw_integration"] == "NOT COVERED"

    original_capture = out / "native" / "P34" / "captured.wav"
    reference = root / "approved-independent-audio.wav"
    reference.write_bytes(original_capture.read_bytes())
    assert quick.run(bundle, host, stress, out, runner=synthetic_native,
                     reference_wav=reference)["coverage"][
                         "externally_referenced_audio"] == "REFERENCE_MATCH"
    altered = root / "wrong-golden.wav"
    corrupted = bytearray(reference.read_bytes())
    corrupted[-300] ^= 0x1f
    altered.write_bytes(corrupted)
    rejected = quick.run(bundle, host, stress, out, runner=synthetic_native,
                         reference_wav=altered)
    assert rejected["status"] == "FAIL", "incorrect golden PCM accepted"
    assert rejected["release_approved"] is False
    assert rejected["reason"] == (
        "real VST3 PCM differs from independently supplied reference")

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

    # A fabricated top-level green report cannot hide one silently missing
    # save run, even if the wrapper executed without an exception.
    def incomplete_matrix(cmd, **kwargs):
        if cmd[1].endswith("run_product_qa.py"):
            result = synthetic_native(cmd, **kwargs)
            target = Path(cmd[cmd.index("--out") + 1])
            path = target / "P32" / "ADAPTER-RESULT.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cases"].pop()
            path.write_text(json.dumps(data), encoding="utf-8")
            return result
        return synthetic_native(cmd, **kwargs)

    result = quick.run(bundle, host, stress, out, runner=incomplete_matrix)
    assert result["status"] == "FAIL", "five of six save matrix cases were accepted"
    assert result["release_approved"] is False
    assert result.get("reason") == "six-case real playback/save matrix incomplete or failed"

    # A successful VST3 process() may still miss its real-time deadline.
    # Show the violation prominently rather than converting it to a PASS.
    def slow_audio_callback(cmd, **kwargs):
        if cmd[1].endswith("run_product_qa.py"):
            result = synthetic_native(cmd, **kwargs)
            target = Path(cmd[cmd.index("--out") + 1])
            path = target / "P32" / "ADAPTER-RESULT.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cases"][0]["timing"]["callback_overruns"] = 3
            data["cases"][0]["realtime_certification"] = "FAIL"
            path.write_text(json.dumps(data), encoding="utf-8")
            return result
        return synthetic_native(cmd, **kwargs)

    measured = quick.run(bundle, host, stress, out, runner=slow_audio_callback)
    assert measured["status"] == "TECHNICAL_PASS"
    assert measured["coverage"]["realtime_deadline_observation"] == "FAIL"
    assert measured["measured_callback_overruns"] == 3
    assert measured["release_approved"] is False

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
        if cmd[1] == "--inventory-parameters":
            Path(cmd[3]).write_text(
                "format\t125A-GUI-PARAMS-v1\nparam_count\t1\n"
                "param\t0\t9001\t1\t0\t0\t1\n",
                encoding="utf-8")
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] VST3 parameter inventory verified 1 unique parameters", "")
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
    assert report["coverage"]["native_parameter_inventory"] == "PASS"
    assert report["advertised_vst3_parameters"] == 1
    assert report["coverage"]["declared_gui_controls"] == "PASS"
    assert report["coverage"]["product_gui_controls"] == "NOT COVERED"

    def gui_not_available(cmd, **kwargs):
        if cmd[1] == "--inventory-parameters":
            return subprocess.CompletedProcess(cmd, 10, "", "[INCONCLUSIVE] no controller")
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

    def broken_inventory(cmd, **kwargs):
        if cmd[1] == "--inventory-parameters":
            Path(cmd[3]).write_text(
                "format\\t125A-GUI-PARAMS-v1\\nparam_count\\t2\\n"
                "param\\t0\\t9001\\t1\\t0\\t0\\t1\\n"
                "param\\t1\\t9001\\t1\\t0\\t0\\t1\\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] VST3 parameter inventory verified 2 unique parameters", "")
        return all_native_gui(cmd, **kwargs)

    bad_inventory = quick.run(bundle, host, stress, out,
                              runner=broken_inventory, gui_host=gui)
    assert bad_inventory["status"] == "FAIL", "duplicate parameter ID went unreported"

    def missing_inventory(cmd, **kwargs):
        if cmd[1] == "--inventory-parameters":
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] VST3 parameter inventory verified 1 unique parameters", "")
        return all_native_gui(cmd, **kwargs)

    stale_inventory = quick.run(bundle, host, stress, out,
                                runner=missing_inventory, gui_host=gui)
    assert stale_inventory["status"] == "FAIL", "stale parameter inventory reused"

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
