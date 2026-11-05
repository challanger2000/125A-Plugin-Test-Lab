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
        gui_host=None, gui_controls=None):
    bundle = bundle.resolve(strict=True)
    host = host.resolve(strict=True)
    stress_host = stress_host.resolve(strict=True)
    if not bundle.is_dir() or bundle.suffix.lower() != ".vst3":
        raise ValueError("plugin must be a native .vst3 bundle directory")
    if not host.is_file() or not stress_host.is_file():
        raise ValueError("one or both native Windows test hosts missing")
    if not 5 <= timeout <= 300:
        raise ValueError("invalid timeout")
    binaries = [p for p in bundle.rglob("*.vst3") if p.is_file()]
    if len(binaries) != 1:
        raise ValueError("exactly one VST3 processor module expected in bundle")
    binary = binaries[0].resolve()
    sha = digest(binary)
    if gui_controls is not None and gui_host is None:
        raise ValueError("GUI controls require an actual native GUI host")
    if gui_host is not None:
        gui_host = Path(gui_host).resolve(strict=True)
        if not gui_host.is_file():
            raise ValueError("native GUI host missing")
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
            "sample_rate_buffer_matrix": "NOT EXECUTED",
            "native_audio_state_capture": "NOT EXECUTED",
            "fresh_process_project_recall": "NOT EXECUTED",
            "recall_audio_determinism": "NOT COVERED",
            "independent_musical_audio": "NOT COVERED",
            "product_gui_controls": "NOT COVERED",
            "native_gui_lifecycle": "NOT COVERED",
            "midi_wav_export": "NOT COVERED",
            "preset_semantics": "NOT COVERED",
            "commercial_daw_integration": "NOT COVERED"
        }
    }
    report_path = out / "QUICKCHECK-RESULT.json"
    report_path.unlink(missing_ok=True)
    native_path = out / "native" / "PRODUCT-QA-RESULT.json"
    native_path.unlink(missing_ok=True)  # never reuse a previous fake PASS
    proc = runner([sys.executable, str(Path(__file__).with_name("run_product_qa.py")),
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
            recall_proc = runner([
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
    if summary["status"] == "TECHNICAL_PASS" and gui_host is not None:
        gui_log = out / "gui-lifecycle.log"
        gui_log.unlink(missing_ok=True)
        gui_proc = runner([str(gui_host), "--probe", str(bundle)],
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
            gui_proc = runner([sys.executable, str(Path(__file__).with_name(
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
    p.add_argument("--gui-controls", type=Path)
    a = p.parse_args()
    try:
        result = run(a.plugin, a.host, a.stress_host, a.out, a.timeout,
                     gui_host=a.gui_host, gui_controls=a.gui_controls)
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
