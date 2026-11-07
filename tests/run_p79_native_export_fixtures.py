#!/usr/bin/env python3
"""P79 real Windows VST3 GUI export through P65/P67, with known-bad controls.

Fixtures are source-built in this repo. This does NOT demonstrate arbitrary
third-party exporters, a commercial DAW, or independent OS writer provenance.
"""
import argparse
import json
from pathlib import Path

from run_product_test_plan import execute, sha256

WAV_HASH = "3c548b8ac23f3be44063b4afce2609137a6e274e409af17f2397f0c95172741b"
MIDI_HASH = "7aa58ed767a3c5ec19ea0c33d0f104f37cfd82ce244c369a1a4f8abfd31e5244"
CASES = (
    ("wav-good", "125A_QA_GUI_ExportGood.vst3", "wav", True),
    ("wav-bad-pcm", "125A_QA_GUI_ExportBad.vst3", "wav", False),
    ("midi-good", "125A_QA_GUI_ExportMidiGood.vst3", "midi", True),
    ("midi-bad-note", "125A_QA_GUI_ExportMidiBad.vst3", "midi", False),
)


def plan_for(bundle, host, kind, case_id):
    modules = [p for p in bundle.rglob("*.vst3") if p.is_file()]
    if len(modules) != 1:
        raise ValueError("P79 VST3 fixture must have exactly one module")
    module = modules[0].resolve(strict=True)
    pinned = sha256(module)
    filename = "gui-export.wav" if kind == "wav" else "gui-export.mid"
    if kind == "wav":
        expected = {"filename": filename, "type": "wav",
                    "sha256": WAV_HASH, "channels": 1, "sample_rate": 44100,
                    "sample_width_bits": 16, "frames": 16}
    else:
        expected = {"filename": filename, "type": "midi",
                    "sha256": MIDI_HASH, "format": 0, "tracks": 1,
                    "ticks_per_quarter": 96, "note_on_count": 1}
    workflow = {
        "schema": "125a-gui-workflow-v1",
        "product": {"binary": str(module), "sha256": pinned},
        "gui_host": str(host),
        "initial": [{"param_id": 9001, "normalized": 0.0}],
        "steps": [{"id": "export_file", "action": "click", "x": 160, "y": 90,
                   "param_id": 9001, "before_normalized": 0.0,
                   "expected_normalized": 1.0}]
    }
    plan = {
        "schema": "125a-product-test-plan-v1",
        "product": {"id": case_id.replace("-", "_"), "module": str(module),
                    "sha256": pinned},
        "hosts": {"gui": {"path": str(host), "sha256": sha256(host)}},
        "cases": [{
            "id": "native_gui_export", "kind": "gui_export_contract",
            "contract": {"schema": "125a-gui-export-contract-v1",
                         "workflow": workflow, "expected_exports": [expected]}
        }]
    }
    matrix = {
        "schema": "125a-product-feature-matrix-v1",
        "product_id": plan["product"]["id"],
        "module_sha256": pinned,
        "features": [{
            "id": "explicit_export_control",
            "title": "Source-defined Win32 GUI-to-file test fixture",
            "criticality": "required",
            "case_ids": ["native_gui_export"],
            "waiver": None
        }]
    }
    return plan, matrix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    build = a.build.resolve(strict=True)
    a.out.mkdir(parents=True, exist_ok=True)
    hosts = list(build.rglob("125A_Test_Lab_GUI.exe"))
    if len(hosts) != 1:
        raise ValueError("P79 GUI test host missing/ambiguous")
    host = hosts[0].resolve(strict=True)
    results = []
    for name, folder, kind, positive in CASES:
        bundles = [p for p in build.rglob(folder) if p.is_dir()]
        if len(bundles) != 1:
            raise ValueError("P79 source-built VST3 fixture missing/ambiguous: " + name)
        plan, matrix = plan_for(bundles[0], host, kind, name)
        output = a.out / name
        output.mkdir(parents=True, exist_ok=True)
        (output / "approved-plan.json").write_text(json.dumps(plan, indent=2))
        (output / "approved-matrix.json").write_text(json.dumps(matrix, indent=2))
        report = execute(plan, output / "results", coverage_matrix=matrix)
        status = report["status"]
        if positive:
            if (status != "CONTRACT_PASS"
                    or report["required_feature_coverage"] != "REQUIRED_COVERAGE_COMPLETE"
                    or report["passed_cases"] != 1 or report["release_approved"] is not False):
                raise ValueError("P79 real native export fixture failed: " + name)
        else:
            if (status != "FAIL" or report["failed_cases"] != 1
                    or report["required_feature_coverage"] != "REQUIRED_COVERAGE_INCOMPLETE"
                    or report["release_approved"] is not False):
                raise ValueError("P79 native wrong-content exporter was not rejected: " + name)
        results.append({"fixture": name, "kind": kind, "expected_pass": positive,
                        "observed_status": status, "source_built_vst3": True})
    (a.out / "NATIVE-EXPORT-REGRESSION.json").write_text(json.dumps({
        "schema": "125a-p79-real-native-fixture-report-v1",
        "status": "POSITIVE_AND_NEGATIVE_CONFIRMED",
        "fixtures": results,
        "actual_native_vst3_gui_export_fixture_tested": True,
        "arbitrary_third_party_exporter_tested": False,
        "process_writer_provenance_verified": False,
        "physical_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False
    }, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
