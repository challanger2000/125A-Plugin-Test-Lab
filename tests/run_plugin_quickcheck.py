#!/usr/bin/env python3
"""Single-command Windows real VST3 technical check, without release claims.

Builds the P32/P34 manifests from the *actual module bytes*, runs the two
existing native hosts and emits fail-closed coverage evidence. Never guesses
product-specific state, musical behavior, or DAW GUI expectations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def run(bundle, host, stress_host, out, timeout=120, runner=subprocess.run,
        gui_host=None, gui_controls=None, reference_wav=None, reference_tolerance=0,
        dual_host=None, dual_state_manifest=None, active_replay=False,
        gui_workflow=None, gui_explore=False, acknowledge_gui_explore=False):
    bundle = bundle.resolve(strict=True)
    host = host.resolve(strict=True)
    stress_host = stress_host.resolve(strict=True)
    if not bundle.is_dir() or bundle.suffix.lower() != ".vst3":
        raise ValueError("plugin must be a native .vst3 bundle directory")
    if not host.is_file() or not stress_host.is_file():
        raise ValueError("one or both native Windows test hosts missing")
    if not 5 <= timeout <= 300:
        raise ValueError("invalid timeout")
    if type(active_replay) is not bool:
        raise ValueError("active replay option must be a boolean")
    if type(gui_explore) is not bool or type(acknowledge_gui_explore) is not bool:
        raise ValueError("invalid GUI exploration options")
    if gui_explore and not acknowledge_gui_explore:
        raise ValueError("GUI exploration requires explicit acknowledgement of arbitrary UI clicks")
    binaries = [p for p in bundle.rglob("*.vst3") if p.is_file()]
    if len(binaries) != 1:
        raise ValueError("exactly one VST3 processor module expected in bundle")
    binary = binaries[0].resolve()
    sha = digest(binary)
    if dual_host is not None:
        dual_host = Path(dual_host).resolve(strict=True)
        if not dual_host.is_file():
            raise ValueError("native same-process dual-instance host missing")
    if (gui_controls is not None or gui_workflow is not None or gui_explore) and gui_host is None:
        raise ValueError("GUI controls, workflows and exploration require an actual native GUI host")
    if gui_host is not None:
        gui_host = Path(gui_host).resolve(strict=True)
        if not gui_host.is_file():
            raise ValueError("native GUI host missing")
    workflow_actions = 0
    visual_workflow_actions = 0
    if gui_workflow is not None:
        gui_workflow = Path(gui_workflow).resolve(strict=True)
        if not gui_workflow.is_file():
            raise ValueError("approved GUI workflow profile missing")
        from run_gui_workflow import validate as validate_workflow
        workflow_profile = json.loads(gui_workflow.read_text(encoding="utf-8"))
        workflow_host, workflow_bundle, workflow_binary, _, workflow_steps = (
            validate_workflow(workflow_profile))
        if (workflow_host != gui_host or workflow_bundle != bundle or
                workflow_binary != binary or
                workflow_profile["product"]["sha256"] != sha):
            raise ValueError("GUI workflow belongs to another VST3 module or native host")
        workflow_actions = len(workflow_steps)
        visual_workflow_actions = sum(
            "visual_oracle" in step for step in workflow_steps)
    pinned_states = []
    if dual_state_manifest is not None:
        if dual_host is None:
            raise ValueError("distinct A/B state oracle requires native dual host")
        dual_state_manifest = Path(dual_state_manifest).resolve(strict=True)
        if not dual_state_manifest.is_file():
            raise ValueError("distinct A/B reference manifest missing")
        from run_product_dual_state import validated_manifest
        dual_spec = validated_manifest(dual_state_manifest)
        if (Path(dual_spec["product"]["bundle"]) != bundle or
            Path(dual_spec["product"]["binary"]) != binary or
            dual_spec["product"]["sha256"] != sha or
            Path(dual_spec["host"]) != dual_host):
            raise ValueError("dual-state oracle belongs to another plugin or native host")
        pinned_states = [Path(dual_spec["initial_states"][label]["path"])
                         for label in ("A", "B")]
    # The default one-click QA performs several native test stages. Pin
    # *all* approved inputs across them, not just the initial module SHA.
    # Otherwise a rebuild or edited reference during testing can inherit
    # evidence that belongs to different bytes.
    approved_inputs = [(binary, sha), (host, digest(host)),
                       (stress_host, digest(stress_host))]
    for optional in (dual_host, gui_host, gui_controls, gui_workflow, reference_wav,
                     dual_state_manifest, *pinned_states):
        if optional is not None:
            path = Path(optional).resolve(strict=True)
            if not path.is_file():
                raise ValueError("approved test input is not a file")
            approved_inputs.append((path, digest(path)))

    def verify_immutable_inputs():
        for path, approved_hash in approved_inputs:
            if not path.is_file() or digest(path) != approved_hash:
                raise ValueError("approved plugin, host or reference changed during test: "
                                 + str(path))

    def checked_runner(command, **kwargs):
        verify_immutable_inputs()
        outcome = runner(command, **kwargs)
        verify_immutable_inputs()
        return outcome

    out.mkdir(parents=True, exist_ok=True)
    p32 = {
        "schema": "125a-p32-adapter-v1",
        "product": {
            "name": bundle.stem,
            "version": "UNVERIFIED",
            "commit_sha": "0" * 40,
            "binary": str(binary),
            "sha256": sha
        },
        "host": str(stress_host),
        "cases": [
            {
                "id": f"save_{rate}_{block}",
                "rate": rate,
                "block": block,
                "iterations": 2500,
                "mode": "save-only",
                "assertions": {
                    "result": {"eq": "PASS"},
                    "process_failures": {"eq": 0},
                    "save_failures": {"eq": 0},
                    "save_success": {"eq": 500},
                    "callbacks": {"eq": 2500},
                    "domain_correctness": {"eq": "NOT_COVERED"}
                }
            }
            for rate in (44100, 48000, 96000)
            for block in (64, 512)
        ]
    }
    p34 = {
        "schema": "125a-p34-capture-v1",
        "product": {"binary": str(binary), "sha256": sha},
        "host": str(host)
    }
    manifests = out / "manifests"
    manifests.mkdir(exist_ok=True)
    p32_path = manifests / "p32.json"
    p34_path = manifests / "p34.json"
    p32_path.write_text(json.dumps(p32, indent=2) + "\n", encoding="utf-8")
    p34_path.write_text(json.dumps(p34, indent=2) + "\n", encoding="utf-8")

    summary = {
        "schema": "125a-quickcheck-result-v1",
        "status": "FAIL",
        "release_approved": False,
        "verified_module_sha256": sha,
        "source_commit": "NOT VERIFIED",
        "product_version": "NOT VERIFIED",
        "product": bundle.stem,
        "coverage": {
            "api_playback_save": "NOT EXECUTED",
            "realtime_deadline_observation": "NOT COVERED",
            "sample_rate_buffer_matrix": "NOT EXECUTED",
            "native_audio_state_capture": "NOT EXECUTED",
            "fresh_process_project_recall": "NOT EXECUTED",
            "same_process_dual_instance_lifecycle": "NOT COVERED",
            "distinct_instance_state_isolation": "NOT COVERED",
            "reference_pcm_isolation": "NOT COVERED",
            "active_playback_state_replay": "NOT COVERED",
            "recall_audio_determinism": "NOT COVERED",
            "independent_musical_audio": "NOT COVERED",
            "externally_referenced_audio": "NOT COVERED",
            "product_gui_controls": "NOT COVERED",
            "native_gui_lifecycle": "NOT COVERED",
            "native_parameter_inventory": "NOT COVERED",
            "native_parameter_sweep": "NOT COVERED",
            "native_parameter_text_labels": "NOT COVERED",
            "native_parameter_text_reverse": "NOT COVERED",
            "native_gui_workflow": "NOT COVERED",
            "native_gui_visual_workflow": "NOT COVERED",
            "native_gui_exploration": "NOT COVERED",
            "midi_wav_export": "NOT COVERED",
            "preset_semantics": "NOT COVERED",
            "commercial_daw_integration": "NOT COVERED"
        }
    }
    report_path = out / "QUICKCHECK-RESULT.json"
    report_path.unlink(missing_ok=True)
    native_path = out / "native" / "PRODUCT-QA-RESULT.json"
    native_path.unlink(missing_ok=True)  # never reuse a previous fake PASS
    adapter_path = out / "native" / "P32" / "ADAPTER-RESULT.json"
    adapter_path.unlink(missing_ok=True)  # reject last run's old case matrix
    proc = checked_runner([sys.executable, str(Path(__file__).with_name("run_product_qa.py")),
                   "--p32", str(p32_path), "--p34", str(p34_path),
                   "--out", str(out / "native"), "--timeout", str(timeout)],
                  capture_output=True, text=True, timeout=timeout * 2 + 30,
                  check=False, errors="replace")
    (out / "quickcheck.log").write_text(
        (proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
    if not native_path.is_file():
        summary["reason"] = "missing native independent test report"
    else:
        native = json.loads(native_path.read_text(encoding="utf-8"))
        if proc.returncode != 0 or native.get("status") != "TECHNICAL_PASS":
            summary["reason"] = "native real-VST3 technical QA did not pass"
        elif native.get("verified_vst3_sha256") != sha:
            summary["reason"] = "native evidence did not match exact module SHA-256"
        elif native.get("release_approved") is not False:
            summary["reason"] = "native host improperly approved release"
        else:
            matrix_report = out / "native" / "P32" / "ADAPTER-RESULT.json"
            if not matrix_report.is_file():
                summary["reason"] = "six-case real playback/save matrix evidence missing"
            else:
                matrix = json.loads(matrix_report.read_text(encoding="utf-8"))
                expected_ids = {case["id"] for case in p32["cases"]}
                cases = matrix.get("cases")
                observed_ids = (
                    {item["id"] for item in cases
                     if isinstance(item, dict) and isinstance(item.get("id"), str)}
                    if isinstance(cases, list) else set()
                )
                if (matrix.get("status") != "PASS" or
                        matrix.get("verified_vst3_sha256") != sha or
                        not isinstance(cases, list) or len(cases) != len(expected_ids) or
                        observed_ids != expected_ids or
                        any(item.get("status") != "PASS" for item in cases)):
                    summary["reason"] = "six-case real playback/save matrix incomplete or failed"
                else:
                    summary["status"] = "TECHNICAL_PASS"
                    summary["coverage"]["api_playback_save"] = "PASS"
                    summary["coverage"]["sample_rate_buffer_matrix"] = "PASS"
                    summary["coverage"]["native_audio_state_capture"] = "PASS"
                    summary["sample_rate_buffer_matrix_cases"] = len(expected_ids)
                    # Audio callbacks can technically return success yet miss
                    # the buffer deadline; never silently call that realtime PASS.
                    timing = [case.get("realtime_certification") for case in cases]
                    measured = [case.get("timing") for case in cases]
                    if (all(t in ("PASS", "FAIL") for t in timing) and
                            all(isinstance(m, dict) and
                                type(m.get("callback_overruns")) is int and
                                m["callback_overruns"] >= 0 for m in measured)):
                        total_overruns = sum(m["callback_overruns"] for m in measured)
                        summary["measured_callback_overruns"] = total_overruns
                        summary["coverage"]["realtime_deadline_observation"] = (
                            "FAIL" if any(t == "FAIL" for t in timing) or total_overruns else "PASS")
                    else:
                        summary["coverage"]["realtime_deadline_observation"] = "NOT COVERED"
    if summary["status"] == "TECHNICAL_PASS" and reference_wav is not None:
        from verify_audio_reference import compare
        audio = out / "native" / "P34" / "captured.wav"
        if not audio.is_file():
            summary["status"] = "FAIL"
            summary["reason"] = "requested independent reference but no fresh real VST3 PCM"
        else:
            checked = compare(audio, Path(reference_wav), out / "reference-audio",
                              reference_tolerance)
            if checked.get("status") != "PASS":
                summary["status"] = "FAIL"
                summary["reason"] = "real VST3 PCM differs from independently supplied reference"
            else:
                summary["coverage"]["externally_referenced_audio"] = "REFERENCE_MATCH"
    # Reopen a captured project state in TWO independent native host processes.
    # Never equate successful IComponent::setState calls with musical correctness.
    if summary["status"] == "TECHNICAL_PASS":
        saved = out / "native" / "P34" / "captured-state.bin"
        if saved.is_file() and 0 < saved.stat().st_size < 128 * 1024 * 1024:
            recall_request = {
                "schema": "125a-state-reload-v1",
                "product": {"binary": str(binary), "sha256": sha},
                "host": str(host),
                "initial_state": str(saved.resolve()),
                "deterministic_audio": False
            }
            recall_manifest = manifests / "recall.json"
            recall_manifest.write_text(
                json.dumps(recall_request, indent=2) + "\n", encoding="utf-8")
            recall_folder = out / "fresh-recall"
            recall_result = recall_folder / "RECALL-RESULT.json"
            recall_result.unlink(missing_ok=True)
            recall_proc = checked_runner([
                sys.executable, str(Path(__file__).with_name("run_state_reload.py")),
                "--manifest", str(recall_manifest), "--out", str(recall_folder),
                "--timeout", str(timeout)
            ], capture_output=True, text=True, timeout=timeout * 2 + 30,
                check=False, errors="replace")
            (out / "fresh-recall.log").write_text(
                (recall_proc.stdout or "") + "\n" + (recall_proc.stderr or ""),
                encoding="utf-8")
            if not recall_result.is_file():
                summary["status"] = "FAIL"
                summary["reason"] = "two-session project recall produced no fresh report"
            else:
                evidence = json.loads(recall_result.read_text(encoding="utf-8"))
                if (recall_proc.returncode != 0 or evidence.get("status") != "PASS" or
                        evidence.get("verified_vst3_sha256") != sha or
                        evidence.get("new_process_instances") != 2 or
                        evidence.get("fresh_process_recall") != "PASS"):
                    summary["status"] = "FAIL"
                    summary["reason"] = "native VST3 state reload in two fresh host processes failed"
                else:
                    summary["coverage"]["fresh_process_project_recall"] = "PASS"
        else:
            summary["coverage"]["fresh_process_project_recall"] = "NOT COVERED"
            summary["recall_note"] = (
                "Captured state absent or outside current host 1-byte to 128-MB size range")
    if summary["status"] == "TECHNICAL_PASS" and dual_host is not None:
        from verify_multi_instance_smoke import audit as audit_instances
        saved = out / "native" / "P34" / "captured-state.bin"
        if not saved.is_file() or not 0 < saved.stat().st_size < 128 * 1024 * 1024:
            summary["coverage"]["same_process_dual_instance_lifecycle"] = "NOT COVERED"
        else:
            dual_dir = out / "same-process"
            dual_dir.mkdir(parents=True, exist_ok=True)
            for name in ("MULTI-INSTANCE.tsv", "A-after.bin", "B-after.bin"):
                (dual_dir / name).unlink(missing_ok=True)
            dual_proc = checked_runner([str(dual_host), "--dual-identical", str(bundle),
                                str(saved.resolve()), str(dual_dir.resolve())],
                               capture_output=True, text=True,
                               timeout=timeout, check=False, errors="replace")
            dual_log = (dual_proc.stdout or "") + "\n" + (dual_proc.stderr or "")
            (out / "same-process.log").write_text(dual_log, encoding="utf-8")
            if dual_proc.returncode == 10 and "[INCONCLUSIVE]" in dual_log:
                summary["coverage"]["same_process_dual_instance_lifecycle"] = "NOT COVERED"
            elif dual_proc.returncode != 0:
                summary["status"] = "FAIL"
                summary["reason"] = "two simultaneous VST3 instances failed native lifecycle/process/save"
            else:
                try:
                    evidence = audit_instances(dual_dir)
                    if (evidence["status"] != "PASS" or
                            "[PASS] two real VST3 instances processed in same host process"
                            not in dual_log):
                        raise ValueError("real native dual-instance proof incomplete")
                    summary["coverage"]["same_process_dual_instance_lifecycle"] = "PASS"
                except (ValueError, OSError, OverflowError, KeyError) as exc:
                    summary["status"] = "FAIL"
                    summary["reason"] = "actual same-process VST3 instance proof invalid: " + str(exc)
    if summary["status"] == "TECHNICAL_PASS" and gui_host is not None:
        gui_log = out / "gui-lifecycle.log"
        gui_log.unlink(missing_ok=True)
        gui_proc = checked_runner([str(gui_host), "--probe", str(bundle)],
                          capture_output=True, text=True, timeout=timeout,
                          check=False, errors="replace")
        gui_text = (gui_proc.stdout or "") + "\n" + (gui_proc.stderr or "")
        gui_log.write_text(gui_text, encoding="utf-8")
        if (gui_proc.returncode == 0 and
                "two actual editor attach/message/input/detach cycles" in gui_text):
            summary["coverage"]["native_gui_lifecycle"] = "PASS"
        elif gui_proc.returncode == 10 and "[INCONCLUSIVE]" in gui_text:
            summary["coverage"]["native_gui_lifecycle"] = "NOT COVERED"
        else:
            summary["status"] = "FAIL"
            summary["reason"] = "actual native editor attach/reopen/detach failed"
    if summary["status"] == "TECHNICAL_PASS" and gui_host is not None:
        from verify_parameter_inventory import audit as audit_parameters
        inventory_file = out / "native-parameters.tsv"
        inventory_file.unlink(missing_ok=True)
        inventory_proc = checked_runner([str(gui_host), "--inventory-parameters",
                                 str(bundle), str(inventory_file)],
                                capture_output=True, text=True, timeout=timeout,
                                check=False, errors="replace")
        inventory_log = (inventory_proc.stdout or "") + "\n" + (inventory_proc.stderr or "")
        (out / "native-parameters.log").write_text(inventory_log, encoding="utf-8")
        if inventory_proc.returncode == 10 and "[INCONCLUSIVE]" in inventory_log:
            summary["coverage"]["native_parameter_inventory"] = "NOT COVERED"
        elif inventory_proc.returncode != 0 or not inventory_file.is_file():
            summary["status"] = "FAIL"
            summary["reason"] = "native VST3 parameter enumeration failed or produced no new evidence"
        else:
            try:
                observed = audit_parameters(inventory_file)
                count = observed["advertised_parameters"]
                expected = "[PASS] VST3 parameter inventory verified %d unique parameters" % count
                if expected not in inventory_log:
                    raise ValueError("native VST3 parameter inventory count not independently observed")
                summary["coverage"]["native_parameter_inventory"] = "PASS"
                summary["advertised_vst3_parameters"] = count
            except (ValueError, OSError, OverflowError) as error:
                summary["status"] = "FAIL"
                summary["reason"] = "invalid native VST3 parameter inventory: " + str(error)
    # Exercise all VST3-controller-advertised writable parameters at
    # normalized boundary and quartile values. Unlike a scripted native
    # mouse click, this does NOT certify hidden product-only GUI controls.
    if summary["status"] == "TECHNICAL_PASS" and gui_host is not None:
        from verify_parameter_sweep import audit as audit_sweep
        sweep_file = out / "native-parameter-sweep.tsv"
        sweep_file.unlink(missing_ok=True)  # never accept old green evidence
        sweep_proc = checked_runner([str(gui_host), "--sweep-parameters",
                                     str(bundle), str(sweep_file)],
                                    capture_output=True, text=True, timeout=timeout,
                                    check=False, errors="replace")
        sweep_log = (sweep_proc.stdout or "") + "\n" + (sweep_proc.stderr or "")
        (out / "native-parameter-sweep.log").write_text(sweep_log, encoding="utf-8")
        if sweep_proc.returncode == 10 and "[INCONCLUSIVE]" in sweep_log:
            summary["coverage"]["native_parameter_sweep"] = "NOT COVERED"
        elif not sweep_file.is_file():
            summary["status"] = "FAIL"
            summary["coverage"]["native_parameter_sweep"] = "FAIL"
            summary["reason"] = "native controller sweep produced no fresh evidence"
        else:
            try:
                checked = audit_sweep(sweep_file)
                summary["writable_vst3_parameters_tested"] = checked["writable_parameters"]
                summary["parameter_values_verified"] = checked["independent_points_verified"]
                if (summary["coverage"]["native_parameter_inventory"] == "PASS" and
                    checked["advertised_parameters"] != summary["advertised_vst3_parameters"]):
                    raise ValueError("controller parameter count changed between inventory and sweep")
                if (checked["status"] != "PASS" or sweep_proc.returncode != 0 or
                    "[PASS] VST3 controller boundary sweep:" not in sweep_log):
                    raise ValueError("native VST3 normalized parameter roundtrip failed")
                summary["coverage"]["native_parameter_sweep"] = checked["controller_roundtrip"]
            except (ValueError, TypeError, OSError, OverflowError) as error:
                summary["status"] = "FAIL"
                summary["coverage"]["native_parameter_sweep"] = "FAIL"
                summary["reason"] = "native VST3 controller parameter sweep invalid: " + str(error)

    # A normalized VST3 value is not a readable value. Probe every
    # automatable parameter's displayed string and reverse text conversion.
    # Reverse text parsing is optional in third-party plugins; no support
    # is NOT COVERED rather than a silently fabricated PASS.
    if summary["status"] == "TECHNICAL_PASS" and gui_host is not None:
        from verify_parameter_text import audit as audit_text
        text_file = out / "native-parameter-text.tsv"
        text_file.unlink(missing_ok=True)
        text_proc = checked_runner([
            str(gui_host), "--verify-parameter-text", str(bundle), str(text_file)],
            capture_output=True, text=True, timeout=timeout,
            check=False, errors="replace")
        text_log = (text_proc.stdout or "") + "\n" + (text_proc.stderr or "")
        (out / "native-parameter-text.log").write_text(text_log, encoding="utf-8")
        if text_proc.returncode == 10 and "[INCONCLUSIVE]" in text_log:
            summary["coverage"]["native_parameter_text_labels"] = "NOT COVERED"
            summary["coverage"]["native_parameter_text_reverse"] = "NOT COVERED"
        elif not text_file.is_file():
            summary["status"] = "FAIL"
            summary["coverage"]["native_parameter_text_labels"] = "FAIL"
            summary["coverage"]["native_parameter_text_reverse"] = "FAIL"
            summary["reason"] = "native value text probe produced no fresh evidence"
        else:
            try:
                observed = audit_text(text_file)
                if (text_proc.returncode != 0 or
                    observed["status"] != "PASS" or
                    "[PASS] VST3 parameter text mapping:" not in text_log or
                    (summary["coverage"]["native_parameter_inventory"] == "PASS" and
                     observed["advertised_parameters"] != summary["advertised_vst3_parameters"])):
                    raise ValueError("VST3 value-to-text mapping failed or parameter count changed")
                summary["coverage"]["native_parameter_text_labels"] = observed["text_label_api"]
                summary["coverage"]["native_parameter_text_reverse"] = observed["reverse_text_api"]
                summary["parameter_labels_verified"] = observed["parameter_label_probes"]
                summary["reverse_text_values_verified"] = observed["parameter_reverse_probes"]
            except (ValueError, OSError, TypeError, OverflowError, UnicodeError) as error:
                summary["status"] = "FAIL"
                summary["coverage"]["native_parameter_text_labels"] = "FAIL"
                summary["coverage"]["native_parameter_text_reverse"] = "FAIL"
                summary["reason"] = "independent VST3 parameter text check failed: " + str(error)

    if summary["status"] == "TECHNICAL_PASS" and gui_controls is not None:
        control_spec = json.loads(Path(gui_controls).read_text(encoding="utf-8"))
        if not isinstance(control_spec, dict) or set(control_spec) != {"controls"}:
            raise ValueError("GUI mapping must contain exactly a controls array")
        if summary["coverage"]["native_gui_lifecycle"] != "PASS":
            summary["status"] = "FAIL"
            summary["reason"] = "requested GUI control assertions require a native editor"
        else:
            gui_manifest = {
                "schema": "125a-gui-controls-v1",
                "product": {"binary": str(binary), "sha256": sha},
                "gui_host": str(gui_host),
                "controls": control_spec["controls"]
            }
            gui_manifest_path = manifests / "gui.json"
            gui_manifest_path.write_text(json.dumps(gui_manifest, indent=2) + "\n",
                                         encoding="utf-8")
            gui_dir = out / "gui-controls"
            gui_result = gui_dir / "GUI-CONTROL-RESULT.json"
            gui_result.unlink(missing_ok=True)
            gui_proc = checked_runner([sys.executable, str(Path(__file__).with_name(
                               "run_gui_control_matrix.py")),
                               "--manifest", str(gui_manifest_path),
                               "--out", str(gui_dir), "--timeout", str(timeout)],
                              capture_output=True, text=True,
                              timeout=timeout * 128 + 30, check=False, errors="replace")
            (out / "gui-controls.log").write_text(
                (gui_proc.stdout or "") + "\n" + (gui_proc.stderr or ""),
                encoding="utf-8")
            if not gui_result.is_file():
                summary["status"] = "FAIL"
                summary["reason"] = "fresh GUI control evidence missing"
            else:
                gui_report = json.loads(gui_result.read_text(encoding="utf-8"))
                count = len(control_spec["controls"]) if isinstance(
                    control_spec["controls"], list) else 0
                if (gui_proc.returncode == 0 and
                        gui_report.get("status") == "TECHNICAL_PASS" and
                        gui_report.get("verified_module_sha256") == sha and
                        gui_report.get("tested_controls") == count and count > 0):
                    summary["coverage"]["declared_gui_controls"] = "PASS"
                    summary["declared_gui_controls_checked"] = count
                else:
                    summary["status"] = "FAIL"
                    summary["reason"] = "actual GUI control/pixel oracle failed"
    # Optional ordered click/drag user journey against one live HWND editor.
    # Every transition is independently declared, not inferred from the GUI.
    if gui_workflow is not None:
        summary["coverage"]["native_gui_workflow"] = "NOT EXECUTED"
        if visual_workflow_actions:
            summary["coverage"]["native_gui_visual_workflow"] = "NOT EXECUTED"
    if summary["status"] == "TECHNICAL_PASS" and gui_workflow is not None:
        journey_dir = out / "gui-workflow"
        journey_report = journey_dir / "GUI-WORKFLOW-RESULT.json"
        journey_report.unlink(missing_ok=True)
        journey_proc = checked_runner([
            sys.executable, str(Path(__file__).with_name("run_gui_workflow.py")),
            "--manifest", str(gui_workflow), "--out", str(journey_dir),
            "--timeout", str(timeout)
        ], capture_output=True, text=True, timeout=timeout + 30,
            check=False, errors="replace")
        (out / "gui-workflow.log").write_text(
            (journey_proc.stdout or "") + "\n" + (journey_proc.stderr or ""),
            encoding="utf-8")
        try:
            evidence = json.loads(journey_report.read_text(encoding="utf-8"))
            if (journey_proc.returncode != 0 or
                evidence.get("status") != "TECHNICAL_PASS" or
                evidence.get("verified_module_sha256") != sha or
                evidence.get("gui_host_sha256") != digest(gui_host) or
                evidence.get("declared_actions") != workflow_actions or
                evidence.get("verified_actions") != workflow_actions or
                evidence.get("verified_visual_only_actions", 0) != visual_workflow_actions or
                (visual_workflow_actions > 0 and
                 evidence.get("visual_only_controls") != "PASS") or
                evidence.get("controller_action_chain") != "PASS" or
                evidence.get("product_gui_complete") != "NOT COVERED"):
                raise ValueError("native ordered GUI workflow incomplete or invalid")
            summary["coverage"]["native_gui_workflow"] = "PASS"
            summary["native_gui_workflow_actions_verified"] = workflow_actions
            if visual_workflow_actions:
                summary["coverage"]["native_gui_visual_workflow"] = "PASS"
                summary["gui_only_painted_controls_verified"] = visual_workflow_actions
        except (OSError, ValueError, TypeError, KeyError) as error:
            summary["status"] = "FAIL"
            summary["coverage"]["native_gui_workflow"] = "FAIL"
            if visual_workflow_actions:
                summary["coverage"]["native_gui_visual_workflow"] = "FAIL"
            summary["reason"] = "optional real GUI workflow: " + str(error)

    # P41 opt-in. This deliberately never certifies arbitrary controls.
    # 9 fresh instances probe a deterministic grid. Real native Win32
    # clicks may activate dialogs or plugin actions: caller consent required.
    if gui_explore:
        summary["coverage"]["native_gui_exploration"] = "NOT EXECUTED"
    if gui_explore and summary["status"] == "TECHNICAL_PASS":
        survey_dir = out / "gui-exploration"
        survey_report = survey_dir / "GUI-EXPLORATION-RESULT.json"
        draft_path = survey_dir / "GUI-CONTROL-REVIEW-DRAFT.json"
        survey_report.unlink(missing_ok=True)
        draft_path.unlink(missing_ok=True)
        survey_proc = checked_runner([
            sys.executable, str(Path(__file__).with_name("run_gui_exploration.py")),
            "--plugin", str(bundle), "--gui-host", str(gui_host),
            "--out", str(survey_dir), "--acknowledge-ui-clicks", "--max-points", "9",
            "--timeout", str(min(timeout, 90))
        ], capture_output=True, text=True, timeout=timeout * 10 + 90,
            check=False, errors="replace")
        (out / "gui-exploration.log").write_text(
            (survey_proc.stdout or "") + "\n" + (survey_proc.stderr or ""),
            encoding="utf-8")
        try:
            outcome = json.loads(survey_report.read_text(encoding="utf-8"))
            if (survey_proc.returncode != 0 or
                outcome.get("status") != "OBSERVATIONS_COMPLETE" or
                outcome.get("verified_module_sha256") != sha or
                outcome.get("verified_gui_host_sha256") != digest(gui_host) or
                outcome.get("requested_points") != 9 or
                outcome.get("completed_points") != 9 or
                outcome.get("sham_verified_points") != 9 or
                outcome.get("sham_control") != "COMPLETE" or
                len(outcome.get("probes", [])) != 9 or
                outcome.get("product_gui_controls") != "NOT COVERED" or
                outcome.get("release_approved") is not False):
                raise ValueError("bounded GUI exploration omitted or forged actual probe evidence")
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            candidates = draft.get("candidates", [])
            if (draft.get("schema") != "125a-gui-control-review-draft-v1" or
                draft.get("status") != "REVIEW_REQUIRED" or
                draft.get("source_exploration_status") != "OBSERVATIONS_COMPLETE" or
                draft.get("verified_module_sha256") != sha or
                draft.get("verified_gui_host_sha256") != digest(gui_host) or
                draft.get("candidate_count") != len(candidates) or
                draft.get("candidate_count") > len(outcome["probes"]) or
                draft.get("automatically_approved_oracles") != 0 or
                draft.get("executable_workflow_manifest") != "NOT GENERATED" or
                draft.get("product_gui_controls") != "NOT COVERED" or
                draft.get("release_approved") is not False or
                any(item.get("approved_for_execution") is not False or
                    item.get("requires_independent_product_review") is not True
                    for item in candidates)):
                raise ValueError("P44 unapproved GUI review draft is missing, stale or falsely certified")
            summary["gui_review_candidates_generated"] = len(candidates)
            summary["coverage"]["native_gui_exploration"] = "OBSERVATIONS_ONLY"
            summary["observed_gui_probe_points"] = 9
            summary["sham_controlled_gui_probe_points"] = 9
            summary["gui_interaction_candidates"] = len(outcome["candidates"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            summary["status"] = "FAIL"
            summary["coverage"]["native_gui_exploration"] = "FAIL"
            summary["reason"] = "native opt-in GUI exploration failed: " + str(error)

    # An explicitly requested high-concurrency test uses the plugin's
    # genuine getState() bytes. It is not safe to require for every VST3:
    # some plugins only allow setState() with processing inactive.
    if active_replay:
        summary["coverage"]["active_playback_state_replay"] = "NOT EXECUTED"
    if summary["status"] == "TECHNICAL_PASS" and active_replay:
        live_dir = out / "live-replay"
        live_report = live_dir / "LIVE-STATE-REPLAY-RESULT.json"
        live_report.unlink(missing_ok=True)
        live_proc = checked_runner([
            sys.executable, str(Path(__file__).with_name("run_live_state_replay.py")),
            "--plugin", str(bundle), "--host", str(stress_host),
            "--out", str(live_dir), "--timeout", str(timeout)
        ], capture_output=True, text=True, timeout=timeout * 6 + 60,
            check=False, errors="replace")
        (out / "live-replay.log").write_text(
            (live_proc.stdout or "") + "\n" + (live_proc.stderr or ""),
            encoding="utf-8")
        try:
            evidence = json.loads(live_report.read_text(encoding="utf-8"))
            cases = evidence.get("cases", [])
            expected = {f"live-replay-{rate}-{block}" for rate in (44100, 48000, 96000)
                        for block in (64, 512)}
            if (live_proc.returncode != 0 or evidence.get("status") != "TECHNICAL_PASS" or
                evidence.get("release_approved") is not False or
                evidence.get("verified_module_sha256") != sha or
                evidence.get("native_host_sha256") != digest(stress_host) or
                not isinstance(cases, list) or len(cases) != 6 or
                {case.get("id") for case in cases if isinstance(case, dict)} != expected or
                any(case.get("status") != "PASS" or
                    case.get("sets_during_playback", 0) < 1 or
                    case.get("saves_during_playback", 0) < 1
                    for case in cases if isinstance(case, dict))):
                raise ValueError("genuine six-case live state replay incomplete or invalid")
            summary["coverage"]["active_playback_state_replay"] = "PASS"
        except (OSError, ValueError, TypeError, KeyError) as error:
            summary["status"] = "FAIL"
            summary["coverage"]["active_playback_state_replay"] = "FAIL"
            summary["reason"] = "optional active-playback state replay: " + str(error)

    # Optional independent product A/B state and PCM oracles extend the same
    # one-click report. Without a separately approved manifest the generic
    # same-state two-instance test must NOT imply distinct-bank correctness.
    if dual_state_manifest is not None:
        summary["coverage"]["distinct_instance_state_isolation"] = "NOT EXECUTED"
        summary["coverage"]["reference_pcm_isolation"] = "NOT EXECUTED"
    if summary["status"] == "TECHNICAL_PASS" and dual_state_manifest is not None:
        dual_dir = out / "distinct-state"
        dual_report = dual_dir / "PRODUCT-DUAL-STATE-RESULT.json"
        dual_report.unlink(missing_ok=True)
        dual_proc = checked_runner([
            sys.executable, str(Path(__file__).with_name("run_product_dual_state.py")),
            "--manifest", str(dual_state_manifest), "--out", str(dual_dir),
            "--timeout", str(timeout)
        ], capture_output=True, text=True, timeout=timeout + 30,
            check=False, errors="replace")
        (out / "distinct-state.log").write_text(
            (dual_proc.stdout or "") + "\n" + (dual_proc.stderr or ""),
            encoding="utf-8")
        try:
            evidence = json.loads(dual_report.read_text(encoding="utf-8"))
            if (dual_proc.returncode != 0 or evidence.get("status") != "TECHNICAL_PASS" or
                evidence.get("verified_module_sha256") != sha or
                evidence.get("release_approved") is not False or
                evidence.get("native_instances") != 2 or
                evidence.get("native_process_calls") != 4 or
                evidence.get("saved_state_isolation") != "PASS" or
                evidence.get("reference_pcm_isolation") != "PASS"):
                raise ValueError("real two-bank state or PCM differs from independent oracle")
            summary["coverage"]["distinct_instance_state_isolation"] = "PASS"
            summary["coverage"]["reference_pcm_isolation"] = "PASS"
        except (OSError, ValueError, TypeError, KeyError) as error:
            summary["status"] = "FAIL"
            summary["coverage"]["distinct_instance_state_isolation"] = "FAIL"
            summary["coverage"]["reference_pcm_isolation"] = "FAIL"
            summary["reason"] = "independently referenced A/B state test: " + str(error)

    # A successful VST3 API call is not an overall successful QA run when a
    # measured timing/GUI/audio domain test explicitly failed.
    if summary["status"] == "TECHNICAL_PASS" and any(
            value == "FAIL" for value in summary["coverage"].values()):
        summary["status"] = "FAIL"
        summary["reason"] = "one or more measured QA coverage checks failed"
    verify_immutable_inputs()
    report_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--stress-host", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--gui-host", type=Path)
    p.add_argument("--dual-host", type=Path)
    p.add_argument("--gui-controls", type=Path)
    p.add_argument("--gui-workflow", type=Path)
    p.add_argument("--gui-explore", action="store_true")
    p.add_argument("--acknowledge-gui-explore", action="store_true")
    p.add_argument("--reference-wav", type=Path)
    p.add_argument("--dual-state-manifest", type=Path)
    p.add_argument("--active-replay", action="store_true")
    p.add_argument("--reference-tolerance-lsb", type=int, default=0)
    a = p.parse_args()
    try:
        result = run(a.plugin, a.host, a.stress_host, a.out, a.timeout,
                     gui_host=a.gui_host, gui_controls=a.gui_controls,
                     reference_wav=a.reference_wav,
                     reference_tolerance=a.reference_tolerance_lsb,
                     dual_host=a.dual_host,
                     dual_state_manifest=a.dual_state_manifest,
                     active_replay=a.active_replay,
                     gui_workflow=a.gui_workflow,
                     gui_explore=a.gui_explore,
                     acknowledge_gui_explore=a.acknowledge_gui_explore)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired,
            json.JSONDecodeError) as error:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": "125a-quickcheck-result-v1",
                  "status": "FAIL", "release_approved": False, "error": str(error)}
        (a.out / "QUICKCHECK-RESULT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[%s] real VST3 one-command technical quickcheck; release approved: NO" % result["status"])
    return 0 if result["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
