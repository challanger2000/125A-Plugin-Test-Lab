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
    # P57: even a green simulated/native VST3 quickcheck must never
    # silently inherit real hardware ASIO or commercial DAW certification.
    for field in ("physical_asio_driver_callbacks", "physical_asio_xruns_deadlines",
                  "physical_asio_hardware", "real_commercial_daw_session"):
        assert report["coverage"][field] == "NOT RUN", field
    assert report["release_approved"] is False
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
    assert measured["status"] == "FAIL", "measured realtime failure incorrectly certified"
    assert measured["coverage"]["realtime_deadline_observation"] == "FAIL"
    assert measured["measured_callback_overruns"] == 3
    assert measured["reason"] == "one or more measured QA coverage checks failed"
    assert measured["release_approved"] is False

    def mismatched(cmd, **kwargs):
        target = Path(cmd[cmd.index("--out") + 1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "PRODUCT-QA-RESULT.json").write_text(json.dumps({
            "status": "TECHNICAL_PASS", "release_approved": False,
            "verified_vst3_sha256": "0" * 64}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "fake other plugin", "")

    assert quick.run(bundle, host, stress, out, runner=mismatched)["status"] == "FAIL"
    # Two simultaneous instances in the same native Windows host are a
    # non-destructive default lifecycle check. No fabricated bank-isolation PASS.
    dual = root / "dual-host.exe"
    dual.write_bytes(b"native same-process runner")
    def same_process(cmd, **kwargs):
        if cmd[1] == "--dual-identical":
            folder = Path(cmd[4])
            folder.mkdir(parents=True, exist_ok=True)
            content = Path(cmd[3]).read_bytes()
            (folder / "A-after.bin").write_bytes(content)
            (folder / "B-after.bin").write_bytes(content)
            (folder / "MULTI-INSTANCE.tsv").write_text(
                "format\t125A-DUAL-INSTANCE-v1\n"
                "same_process_instances\t2\n"
                "process_callbacks\t4\n"
                "A_first_pcm\t0.25\n"
                "B_first_pcm\t0.25\n"
                "B_second_pcm\t0.25\n"
                "A_second_pcm\t0.25\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] two real VST3 instances processed in same host process", "")
        return synthetic_native(cmd, **kwargs)
    report = quick.run(bundle, host, stress, out, runner=same_process, dual_host=dual)
    assert report["status"] == "TECHNICAL_PASS"
    assert report["coverage"]["same_process_dual_instance_lifecycle"] == "PASS"
    assert report["coverage"]["distinct_instance_state_isolation"] == "NOT COVERED"

    def fake_dual(cmd, **kwargs):
        if cmd[1] == "--dual-identical":
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] two real VST3 instances processed in same host process", "")
        return synthetic_native(cmd, **kwargs)
    failed = quick.run(bundle, host, stress, out, runner=fake_dual, dual_host=dual)
    assert failed["status"] == "FAIL", "stale successful same-process report accepted"
    assert failed["release_approved"] is False

    def unsupported_dual(cmd, **kwargs):
        if cmd[1] == "--dual-identical":
            return subprocess.CompletedProcess(
                cmd, 10, "", "[INCONCLUSIVE] unsupported multi-bus topology")
        return synthetic_native(cmd, **kwargs)
    unsupported = quick.run(bundle, host, stress, out,
                            runner=unsupported_dual, dual_host=dual)
    assert unsupported["status"] == "TECHNICAL_PASS"
    assert unsupported["coverage"]["same_process_dual_instance_lifecycle"] == "NOT COVERED"

    # The same invocation can prove a real editor's two lifecycle cycles.
    gui = root / "gui.exe"
    gui.write_bytes(b"dummy native gui host")
    controls_file = root / "independent-controls.json"
    controls_file.write_text(json.dumps({"controls": [
        {"id": "switch", "param_id": 9001, "x": 120, "y": 80,
         "expected_normalized": 1.0}]}), encoding="utf-8")

    def all_native_gui(cmd, **kwargs):
        if cmd[1] == "--verify-parameter-text":
            Path(cmd[3]).write_text(
                "format\t125A-GUI-TEXT-v1\n"
                "param_count\t1\ntested\t1\nskipped\t0\nfailed\t0\n"
                "observations\t2\nreadable\t2\nreversible\t2\n"
                "param\t0\t9001\t1\t1\tPASS\n"
                "text\t0\t9001\t0\t004f00460046\tR\t0\t004f00460046\tPASS\n"
                "text\t0\t9001\t1\t004f004e\tR\t1\t004f004e\tPASS\n",
                encoding="utf-8")
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] VST3 parameter text mapping: 2 labels, 2 reverse values, 0 invalid controls", "")
        if cmd[1] == "--sweep-parameters":
            Path(cmd[3]).write_text(
                "format\t125A-GUI-SWEEP-v1\n"
                "param_count\t1\ntested\t1\nskipped\t0\nfailed\t0\n"
                "observations\t2\n"
                "param\t0\t9001\t1\t1\t0\tPASS\t1\n"
                "probe\t0\t9001\t0\t0\t1\n"
                "probe\t0\t9001\t1\t1\t1\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] VST3 controller boundary sweep: 1 writable parameters, 2 checked values, 0 failed", "")
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
    assert report["coverage"]["native_parameter_sweep"] == "PASS"
    assert report["coverage"]["native_parameter_text_labels"] == "PASS"
    assert report["coverage"]["native_parameter_text_reverse"] == "PASS"
    assert report["parameter_labels_verified"] == 2
    assert report["reverse_text_values_verified"] == 2
    assert report["writable_vst3_parameters_tested"] == 1
    assert report["parameter_values_verified"] == 2
    assert report["advertised_vst3_parameters"] == 1
    assert report["coverage"]["declared_gui_controls"] == "PASS"
    assert report["coverage"]["product_gui_controls"] == "NOT COVERED"

    # P121: a real native controller sweep process returning nonzero must
    # never count as PASS even if it left a syntactically correct TSV.
    def failing_sweep_process_with_valid_tsv(cmd, **kwargs):
        result = all_native_gui(cmd, **kwargs)
        if cmd[1] == "--sweep-parameters":
            return subprocess.CompletedProcess(
                cmd, 23, result.stdout, result.stderr)
        return result

    invalid_sweep_exit = quick.run(
        bundle, host, stress, out, runner=failing_sweep_process_with_valid_tsv,
        gui_host=gui)
    assert invalid_sweep_exit["status"] == "FAIL", (
        "P121 falsely accepted native sweep exit 23 with valid old TSV")
    assert invalid_sweep_exit["coverage"]["native_parameter_sweep"] == "FAIL"
    assert invalid_sweep_exit["release_approved"] is False

    # The native process must not be able to forge a green text mapping
    # when one parser silently returns a value for another displayed label.
    def falsified_text(cmd, **kwargs):
        if cmd[1] == "--verify-parameter-text":
            result = all_native_gui(cmd, **kwargs)
            path = Path(cmd[3])
            forged = path.read_text(encoding="utf-8").replace(
                "text\t0\t9001\t0\t004f00460046\tR\t0\t004f00460046\tPASS",
                "text\t0\t9001\t0\t004f00460046\tR\t1\t004f004e\tPASS")
            path.write_text(forged, encoding="utf-8")
            return result
        return all_native_gui(cmd, **kwargs)

    invalid_text = quick.run(bundle, host, stress, out,
                             runner=falsified_text, gui_host=gui)
    assert invalid_text["status"] == "FAIL"
    assert invalid_text["coverage"]["native_parameter_text_labels"] == "FAIL"
    assert invalid_text["release_approved"] is False

    def missing_text_evidence(cmd, **kwargs):
        if cmd[1] == "--verify-parameter-text":
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] VST3 parameter text mapping:", "")
        return all_native_gui(cmd, **kwargs)

    stale_text = quick.run(bundle, host, stress, out,
                           runner=missing_text_evidence, gui_host=gui)
    assert stale_text["status"] == "FAIL"
    assert stale_text["coverage"]["native_parameter_text_labels"] == "FAIL"
    assert not (out / "native-parameter-text.tsv").exists()

    # P41 bounded automatic GUI exploration is explicitly opt-in. It
    # records candidates without claiming a complete product GUI audit.
    try:
        quick.run(bundle, host, stress, out, runner=all_native_gui,
                  gui_host=gui, gui_explore=True)
    except ValueError as error:
        assert "acknowledgement" in str(error)
    else:
        raise AssertionError("unconsented blind plugin GUI click was permitted")

    exploratory_failure = {"mode": None}
    def explorer_native(cmd, **kwargs):
        if cmd[1].endswith("run_gui_exploration.py"):
            dest = Path(cmd[cmd.index("--out") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            if exploratory_failure["mode"] == "missing":
                return subprocess.CompletedProcess(cmd, 0, "fake green", "")
            overview = {
                "schema": "125a-gui-exploration-result-v1",
                "status": "OBSERVATIONS_COMPLETE",
                "verified_module_sha256": (
                    sha if exploratory_failure["mode"] != "wrong_module" else "f" * 64),
                "verified_gui_host_sha256": hashlib.sha256(gui.read_bytes()).hexdigest(),
                "requested_points": 9, "completed_points": (
                    8 if exploratory_failure["mode"] == "incomplete" else 9),
                "sham_verified_points": (8 if exploratory_failure["mode"] == "missing_sham" else 9),
                "sham_control": ("FAIL" if exploratory_failure["mode"] == "false_sham_pass" else "COMPLETE"),
                "probes": [{"x": 160, "y": 90}] * 9,
                "candidates": [{"x": 160, "y": 90}] * 2,
                "product_gui_controls": "NOT COVERED",
                "release_approved": False
            }
            (dest / "GUI-EXPLORATION-RESULT.json").write_text(
                json.dumps(overview), encoding="utf-8")
            if exploratory_failure["mode"] != "missing_draft":
                suggestions = [
                    {"probe_index": number,
                     "approved_for_execution": False,
                     "requires_independent_product_review": True}
                    for number in range(2)]
                draft = {
                    "schema": "125a-gui-control-review-draft-v1",
                    "status": "REVIEW_REQUIRED",
                    "verified_module_sha256": sha,
                    "verified_gui_host_sha256": hashlib.sha256(gui.read_bytes()).hexdigest(),
                    "source_exploration_status": "OBSERVATIONS_COMPLETE",
                    "candidate_count": (1 if exploratory_failure["mode"] == "wrong_count" else 2),
                    "candidates": suggestions,
                    "automatically_approved_oracles": 0,
                    "executable_workflow_manifest": "NOT GENERATED",
                    "product_gui_controls": "NOT COVERED",
                    "release_approved": exploratory_failure["mode"] == "fake_approval"}
                (dest / "GUI-CONTROL-REVIEW-DRAFT.json").write_text(
                    json.dumps(draft), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0,
                "[OBSERVATIONS_COMPLETE] real VST3 GUI exploration", "")
        return all_native_gui(cmd, **kwargs)

    explored = quick.run(bundle, host, stress, out, runner=explorer_native,
                         gui_host=gui, gui_explore=True,
                         acknowledge_gui_explore=True)
    assert explored["status"] == "TECHNICAL_PASS"
    assert explored["coverage"]["native_gui_exploration"] == "OBSERVATIONS_ONLY"
    assert explored["gui_interaction_candidates"] == 2
    assert explored["observed_gui_probe_points"] == 9
    assert explored["sham_controlled_gui_probe_points"] == 9
    assert explored["gui_review_candidates_generated"] == 2
    assert explored["coverage"]["product_gui_controls"] == "NOT COVERED"
    assert explored["release_approved"] is False
    for bad_mode in ("missing", "wrong_module", "incomplete",
                     "missing_sham", "false_sham_pass",
                     "missing_draft", "wrong_count", "fake_approval"):
        exploratory_failure["mode"] = bad_mode
        broken = quick.run(bundle, host, stress, out,
                           runner=explorer_native, gui_host=gui,
                           gui_explore=True, acknowledge_gui_explore=True)
        assert broken["status"] == "FAIL", (bad_mode, broken)
        assert broken["coverage"]["native_gui_exploration"] == "FAIL"
    exploratory_failure["mode"] = None

    # P45 must never run arbitrary double-clicks without *both* explicit
    # exploration and its existing user consent.
    try:
        quick.run(bundle, host, stress, out, runner=explorer_native,
                  gui_host=gui, gui_roundtrip=True)
    except ValueError as error:
        assert "opt-in" in str(error)
    else:
        raise AssertionError("P45 unconsented native GUI double-click accepted")

    roundtrip_failure = {"mode": None}

    def replay_native(cmd, **kwargs):
        if cmd[1].endswith("run_gui_roundtrip.py"):
            target = Path(cmd[cmd.index("--out") + 1])
            target.mkdir(parents=True, exist_ok=True)
            if roundtrip_failure["mode"] == "missing":
                return subprocess.CompletedProcess(cmd, 0, "fake green", "")
            r = {
                "schema": "125a-gui-roundtrip-observations-v1",
                "status": "OBSERVATIONS_COMPLETE",
                "verified_module_sha256": sha,
                "verified_gui_host_sha256": hashlib.sha256(gui.read_bytes()).hexdigest(),
                "tested_candidates": 2, "observed_reversible": 1,
                "observed_nonreversible": 1, "not_reproduced": 0,
                "cases": [{"classification": "OBSERVED_REVERSIBLE"},
                          {"classification": "OBSERVED_NONREVERSIBLE"}],
                "independent_product_semantics": "NOT COVERED",
                "product_gui_controls": "NOT COVERED",
                "release_approved": False
            }
            if roundtrip_failure["mode"] == "wrong_hash":
                r["verified_module_sha256"] = "f" * 64
            if roundtrip_failure["mode"] == "wrong_count":
                r["tested_candidates"] = 1
            if roundtrip_failure["mode"] == "fake_release":
                r["release_approved"] = True
            if roundtrip_failure["mode"] == "fake_semantics":
                r["independent_product_semantics"] = "PASS"
            (target / "GUI-ROUNDTRIP-RESULT.json").write_text(
                json.dumps(r), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "[OBSERVATIONS_COMPLETE]", "")
        return explorer_native(cmd, **kwargs)

    two_way = quick.run(bundle, host, stress, out, runner=replay_native,
                        gui_host=gui, gui_explore=True,
                        acknowledge_gui_explore=True, gui_roundtrip=True)
    assert two_way["status"] == "TECHNICAL_PASS"
    assert two_way["coverage"]["native_gui_bidirectional_observation"] == "OBSERVATIONS_ONLY"
    assert two_way["gui_observed_reversible"] == 1
    assert two_way["gui_observed_nonreversible"] == 1
    assert two_way["coverage"]["product_gui_controls"] == "NOT COVERED"
    assert two_way["release_approved"] is False
    for bad_mode in ("missing", "wrong_hash", "wrong_count",
                     "fake_release", "fake_semantics"):
        roundtrip_failure["mode"] = bad_mode
        fake = quick.run(bundle, host, stress, out, runner=replay_native,
                         gui_host=gui, gui_explore=True,
                         acknowledge_gui_explore=True, gui_roundtrip=True)
        assert fake["status"] == "FAIL", (bad_mode, fake)
        assert fake["coverage"]["native_gui_bidirectional_observation"] == "FAIL"
        assert fake["release_approved"] is False
    roundtrip_failure["mode"] = None

    # Product-independent click/drag sequences require a declared oracle;
    # a successful native host alone must never imply every button was tested.
    workflow_file = root / "approved-gui-workflow.json"
    workflow_steps = [
        {"id": "enable", "action": "click", "x": 100, "y": 90,
         "param_id": 9001, "before_normalized": 0.0, "expected_normalized": 1.0},
        {"id": "disable", "action": "click", "x": 100, "y": 90,
         "param_id": 9001, "before_normalized": 1.0, "expected_normalized": 0.0}]
    workflow_spec = {
        "schema": "125a-gui-workflow-v1",
        "product": {"binary": str(binary), "sha256": sha},
        "gui_host": str(gui),
        "initial": [{"param_id": 9001, "normalized": 0.0}],
        "steps": workflow_steps}
    workflow_file.write_text(json.dumps(workflow_spec), encoding="utf-8")
    workflow_failure = {"mode": None}

    def native_workflow(cmd, **kwargs):
        if cmd[1].endswith("run_gui_workflow.py"):
            target = Path(cmd[cmd.index("--out") + 1])
            target.mkdir(parents=True, exist_ok=True)
            mode = workflow_failure["mode"]
            if mode == "missing":
                return subprocess.CompletedProcess(cmd, 0, "fake native success", "")
            loaded_steps = json.loads(workflow_file.read_text(encoding="utf-8"))["steps"]
            visual_count = sum("visual_oracle" in item for item in loaded_steps)
            payload = {
                "status": "TECHNICAL_PASS",
                "verified_module_sha256": sha if mode != "wrong_identity" else "f" * 64,
                "gui_host_sha256": hashlib.sha256(gui.read_bytes()).hexdigest(),
                "declared_actions": len(loaded_steps),
                "verified_actions": len(loaded_steps) if mode != "missing_step" else 1,
                "verified_visual_only_actions": (visual_count if mode != "wrong_visual_count" else 0),
                "visual_only_controls": "PASS" if visual_count else "NOT COVERED",
                "controller_action_chain": "PASS",
                "product_gui_complete": "NOT COVERED"}
            (target / "GUI-WORKFLOW-RESULT.json").write_text(
                json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "native actions checked", "")
        return all_native_gui(cmd, **kwargs)

    tested = quick.run(bundle, host, stress, out, runner=native_workflow,
                       gui_host=gui, gui_workflow=workflow_file)
    assert tested["status"] == "TECHNICAL_PASS"
    assert tested["coverage"]["native_gui_workflow"] == "PASS"
    assert tested["native_gui_workflow_actions_verified"] == 2
    assert tested["coverage"]["product_gui_controls"] == "NOT COVERED"
    for bad_mode in ("missing", "wrong_identity", "missing_step"):
        workflow_failure["mode"] = bad_mode
        bad = quick.run(bundle, host, stress, out, runner=native_workflow,
                        gui_host=gui, gui_workflow=workflow_file)
        assert bad["status"] == "FAIL", bad_mode
        assert bad["coverage"]["native_gui_workflow"] == "FAIL", bad_mode
        assert bad["release_approved"] is False
    workflow_failure["mode"] = None

    try:
        quick.run(bundle, host, stress, out, runner=native_workflow,
                  gui_workflow=workflow_file)
    except ValueError as error:
        assert "native GUI host" in str(error)
    else:
        raise AssertionError("GUI journey silently omitted without native HWND host")
    wrong_spec = dict(workflow_spec)
    wrong_spec["product"] = dict(workflow_spec["product"])
    wrong_spec["product"]["sha256"] = "b" * 64
    workflow_file.write_text(json.dumps(wrong_spec), encoding="utf-8")
    try:
        quick.run(bundle, host, stress, out, runner=native_workflow,
                  gui_host=gui, gui_workflow=workflow_file)
    except ValueError as error:
        assert "missing/incorrect" in str(error) or "another VST3" in str(error)
    else:
        raise AssertionError("incorrect GUI workflow source fingerprints accepted")
    workflow_file.write_text(json.dumps(workflow_spec), encoding="utf-8")

    visual_spec = dict(workflow_spec)
    visual_spec["steps"] = [{
        "id": "hidden_led_toggle", "action": "click", "x": 100, "y": 90,
        "screenshot": True, "visual_oracle": {
            "x": 1, "y": 1, "before_rgb": [30, 36, 48],
            "after_rgb": [12, 142, 85]}}]
    workflow_file.write_text(json.dumps(visual_spec), encoding="utf-8")
    visually = quick.run(bundle, host, stress, out, runner=native_workflow,
                         gui_host=gui, gui_workflow=workflow_file)
    assert visually["status"] == "TECHNICAL_PASS"
    assert visually["coverage"]["native_gui_visual_workflow"] == "PASS"
    assert visually["gui_only_painted_controls_verified"] == 1
    assert visually["coverage"]["product_gui_controls"] == "NOT COVERED"
    workflow_failure["mode"] = "wrong_visual_count"
    visually_bad = quick.run(bundle, host, stress, out, runner=native_workflow,
                             gui_host=gui, gui_workflow=workflow_file)
    assert visually_bad["status"] == "FAIL"
    assert visually_bad["coverage"]["native_gui_visual_workflow"] == "FAIL"
    workflow_failure["mode"] = None
    workflow_file.write_text(json.dumps(workflow_spec), encoding="utf-8")

    def gui_not_available(cmd, **kwargs):
        if cmd[1] == "--verify-parameter-text":
            return subprocess.CompletedProcess(cmd, 10, "", "[INCONCLUSIVE] no controller")
        if cmd[1] == "--sweep-parameters":
            return subprocess.CompletedProcess(cmd, 10, "", "[INCONCLUSIVE] no controller")
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

    def wrong_controller_value(cmd, **kwargs):
        if cmd[1] == "--sweep-parameters":
            result = all_native_gui(cmd, **kwargs)
            path = Path(cmd[3])
            body = path.read_text(encoding="utf-8")
            body = body.replace("failed\t0\n", "failed\t1\n").replace(
                "param\t0\t9001\t1\t1\t0\tPASS\t1",
                "param\t0\t9001\t1\t1\t0\tFAIL\t1").replace(
                "probe\t0\t9001\t1\t1\t1",
                "probe\t0\t9001\t1\t0\t0")
            path.write_text(body, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 1,
                "[FAIL] VST3 controller boundary sweep", "")
        return all_native_gui(cmd, **kwargs)

    bad_sweep = quick.run(bundle, host, stress, out,
                          runner=wrong_controller_value, gui_host=gui)
    assert bad_sweep["status"] == "FAIL", "controller silently ignored automation"
    assert bad_sweep["coverage"]["native_parameter_sweep"] == "FAIL"

    def missing_parameter_sweep(cmd, **kwargs):
        if cmd[1] == "--sweep-parameters":
            return subprocess.CompletedProcess(
                cmd, 0, "[PASS] VST3 controller boundary sweep:", "")
        return all_native_gui(cmd, **kwargs)

    stale_sweep = quick.run(bundle, host, stress, out,
                            runner=missing_parameter_sweep, gui_host=gui)
    assert stale_sweep["status"] == "FAIL", "stale green controller sweep accepted"
    assert stale_sweep["coverage"]["native_parameter_sweep"] == "FAIL"
    assert not (out / "native-parameter-sweep.tsv").exists()

    def absent_matrix(cmd, **kwargs):
        if cmd[1].endswith("run_gui_control_matrix.py"):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return all_native_gui(cmd, **kwargs)

    result = quick.run(bundle, host, stress, out, runner=absent_matrix,
                       gui_host=gui, gui_controls=controls_file)
    assert result["status"] == "FAIL", "stale GUI evidence accepted"

    # A green wrapper report must not survive input mutations while the
    # native subprocess is running (including external reference edits).
    for name, input_path, original in (
            ("plugin", binary, binary.read_bytes()),
            ("host", host, host.read_bytes()),
            ("reference", reference, reference.read_bytes())):
        def mutate_input(cmd, **kwargs):
            answer = synthetic_native(cmd, **kwargs)
            if cmd[1].endswith("run_product_qa.py"):
                input_path.write_bytes(b"replaced approved " + name.encode("ascii"))
            return answer

        try:
            quick.run(bundle, host, stress, out, runner=mutate_input,
                      reference_wav=reference if name == "reference" else None)
        except ValueError as error:
            assert "changed during test" in str(error), name
        else:
            raise AssertionError(name + " mutation escaped immutable input gate")
        finally:
            input_path.write_bytes(original)
        assert not (out / "QUICKCHECK-RESULT.json").exists(), (
            name + " mutation reused stale successful report")

    # The advanced one-command runner must consume real independent A/B
    # references and genuinely overlapping state-reload evidence, rather
    # than upgrading generic dual-instance TECHNICAL_PASS to musical PASS.
    state_a = root / "approved-bank-A.bin"
    state_b = root / "approved-bank-B.bin"
    state_a.write_bytes(b"independent approved bank A")
    state_b.write_bytes(b"independent approved bank B")
    states = {"A": state_a, "B": state_b}
    dual_manifest = root / "approved-AB-oracle.json"
    independent = {
        "schema": "125a-product-dual-state-oracle-v1",
        "product": {"bundle": str(bundle), "binary": str(binary), "sha256": sha},
        "host": str(dual),
        "initial_states": {
            k: {"path": str(v), "sha256": hashlib.sha256(v.read_bytes()).hexdigest()}
            for k, v in states.items()},
        "reference": {
            "expected_saved_sha256": {"A": "a" * 64, "B": "b" * 64},
            "expected_pcm": {"A_first_pcm": 0.25, "B_first_pcm": 0.5,
                             "B_second_pcm": 0.5, "A_second_pcm": 0.25},
            "abs_tolerance": 0.0}}
    dual_manifest.write_text(json.dumps(independent), encoding="utf-8")
    deep_mode = {"broken": None}

    def deep_native(cmd, **kwargs):
        if cmd[1].endswith("run_live_state_replay.py"):
            target = Path(cmd[cmd.index("--out") + 1])
            target.mkdir(parents=True, exist_ok=True)
            cases = [
                {"id": f"live-replay-{rate}-{block}",
                 "status": "PASS", "sets_during_playback": 100,
                 "saves_during_playback": 100}
                for rate in (44100, 48000, 96000) for block in (64, 512)]
            if deep_mode["broken"] == "missing_replay_case":
                cases.pop()
            identity = sha if deep_mode["broken"] != "wrong_replay_plugin" else "e" * 64
            (target / "LIVE-STATE-REPLAY-RESULT.json").write_text(json.dumps({
                "status": "TECHNICAL_PASS", "release_approved": False,
                "verified_module_sha256": identity,
                "native_host_sha256": hashlib.sha256(stress.read_bytes()).hexdigest(),
                "cases": cases}), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "genuine replay observed", "")
        if cmd[1].endswith("run_product_dual_state.py"):
            target = Path(cmd[cmd.index("--out") + 1])
            target.mkdir(parents=True, exist_ok=True)
            (target / "PRODUCT-DUAL-STATE-RESULT.json").write_text(json.dumps({
                "status": "TECHNICAL_PASS", "release_approved": False,
                "verified_module_sha256": sha,
                "native_instances": 2, "native_process_calls": 4,
                "saved_state_isolation": "FAIL" if deep_mode["broken"] == "wrong_bank" else "PASS",
                "reference_pcm_isolation": "PASS"}), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "independent A/B observed", "")
        return same_process(cmd, **kwargs)

    deep_mode["broken"] = None
    deep = quick.run(bundle, host, stress, out, dual_host=dual,
                     active_replay=True, dual_state_manifest=dual_manifest,
                     runner=deep_native)
    assert deep["status"] == "TECHNICAL_PASS"
    assert deep["release_approved"] is False
    assert deep["coverage"]["active_playback_state_replay"] == "PASS"
    assert deep["coverage"]["distinct_instance_state_isolation"] == "PASS"
    assert deep["coverage"]["reference_pcm_isolation"] == "PASS"
    assert deep["coverage"]["independent_musical_audio"] == "NOT COVERED"
    assert deep["coverage"]["commercial_daw_integration"] == "NOT COVERED"
    assert deep["coverage"]["physical_asio_hardware"] == "NOT RUN"
    assert deep["coverage"]["real_commercial_daw_session"] == "NOT RUN"

    for broken in ("missing_replay_case", "wrong_replay_plugin", "wrong_bank"):
        deep_mode["broken"] = broken
        failed = quick.run(bundle, host, stress, out, dual_host=dual,
                           active_replay=True, dual_state_manifest=dual_manifest,
                           runner=deep_native)
        assert failed["status"] == "FAIL", broken
        assert failed["release_approved"] is False, broken
        if broken == "wrong_bank":
            assert failed["coverage"]["distinct_instance_state_isolation"] == "FAIL"
        else:
            assert failed["coverage"]["active_playback_state_replay"] == "FAIL"
            assert failed["coverage"]["distinct_instance_state_isolation"] == "NOT EXECUTED"
    deep_mode["broken"] = None

    # A reference approved for a different module or host must fail before
    # any real native process is launched.
    wrong = dict(independent)
    wrong["product"] = dict(independent["product"])
    wrong["product"]["sha256"] = "f" * 64
    dual_manifest.write_text(json.dumps(wrong), encoding="utf-8")
    try:
        quick.run(bundle, host, stress, out, dual_host=dual,
                  dual_state_manifest=dual_manifest, runner=deep_native)
    except ValueError as error:
        assert "fingerprint" in str(error) or "another plugin" in str(error)
    else:
        raise AssertionError("other module's A/B references accepted")
    dual_manifest.write_text(json.dumps(independent), encoding="utf-8")
    try:
        quick.run(bundle, host, stress, out,
                  dual_state_manifest=dual_manifest, runner=deep_native)
    except ValueError as error:
        assert "requires native dual host" in str(error)
    else:
        raise AssertionError("advanced A/B test without real host accepted")

    (bundle / "Contents" / "x86_64-win" / "Extra.vst3").write_bytes(b"extra")
    try:
        quick.run(bundle, host, stress, out, runner=synthetic_native)
    except ValueError as e:
        assert "exactly one" in str(e)
    else:
        raise AssertionError("ambiguous multi-module bundle accepted")
print("[PASS] one-command quickcheck rejects stale, wrong module and missing coverage")
