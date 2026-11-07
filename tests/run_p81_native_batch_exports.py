#!/usr/bin/env python3
"""P81: native, end-to-end P75/P80 batch -> P74 -> P65/P67 -> P46.

Runs four *real* source-built Windows VST3 modules. Valid WAV/MIDI file
bytes are independently specified in P79. This is not proof that a
previously unseen third-party VST3 can be operated automatically.
"""
import argparse
import json
from pathlib import Path

from run_p79_native_export_fixtures import plan_for, CASES, WAV_HASH, MIDI_HASH
from run_vst3_batch_qa import load_selection, run, SCHEMA
from run_export_artifact_oracle import digest


def require(value, detail):
    if not value:
        raise ValueError("P81 " + detail)


def setup(build, gui, out):
    options = []
    for name, bundle_name, kind, positive in CASES:
        bundles = [p for p in build.rglob(bundle_name) if p.is_dir()]
        require(len(bundles) == 1, "native fixture missing/ambiguous: " + name)
        plan, matrix = plan_for(bundles[0], gui, kind, name)
        folder = out / "approved" / name
        folder.mkdir(parents=True, exist_ok=True)
        plan_path, matrix_path = folder / "plan.json", folder / "features.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        matrix_path.write_text(json.dumps(matrix, indent=2), encoding="utf-8")
        options.append({
            "id": name.replace("-", "_"),
            "bundle": str(bundles[0]),
            "run_technical_baseline": False,
            "approved_plan": str(plan_path),
            "feature_matrix": str(matrix_path)
        })
    return options


def verify_positive_artifact(root, case_name, kind):
    # P75 child directory holds P74's verified P65/P46 nested evidence.
    case_root = root / "approved-cases" / "01-native_gui_export"
    p46 = case_root / "GUI-EXPORT-CONTRACT-RESULT.json"
    require(p46.is_file(), case_name + " missing native P46 report")
    evidence = json.loads(p46.read_text(encoding="utf-8"))
    filename = "gui-export.wav" if kind == "wav" else "gui-export.mid"
    expected = WAV_HASH if kind == "wav" else MIDI_HASH
    require(evidence.get("status") == "CONTRACT_PASS", case_name + " P46 failed")
    require(evidence.get("verified_export_count") == 1,
            case_name + " incorrect verified output count")
    observed = evidence.get("verified_exports", {}).get(filename, {})
    require(observed.get("sha256") == expected,
            case_name + " independent expected bytes mismatch")
    folder = evidence.get("saved_evidence_directory")
    require(isinstance(folder, str) and folder.startswith("verified-"),
            case_name + " retained evidence path missing")
    actual = case_root / folder / filename
    require(actual.is_file() and digest(actual) == expected,
            case_name + " retained native export bytes differ from golden reference")


def run_scenario(options, gui, out, *, all_good):
    chosen = [p for p in options if (
        p["id"] in ("wav_good", "midi_good") if all_good else True)]
    # Negative exporters first, then working ones, to prove batch continues.
    if not all_good:
        order = ("wav_bad_pcm", "midi_bad_note", "wav_good", "midi_good")
        chosen = sorted(chosen, key=lambda p: order.index(p["id"]))
    else:
        chosen = sorted(chosen, key=lambda p: p["id"])
    out.mkdir(parents=True, exist_ok=True)
    selection = out / "selection.json"
    selection.write_text(json.dumps({"schema": SCHEMA, "plugins": chosen}, indent=2),
                         encoding="utf-8")
    entries = load_selection(selection=selection)
    report = run(entries, gui, out / "results", per_plugin_timeout=400,
                 native_timeout=110)
    assert_expected = ("BATCH_DECLARED_COVERAGE_PASS" if all_good else "FAIL")
    require(report.get("status") == assert_expected,
            "unexpected real native batch result: " + str(report.get("status")))
    require(report.get("declared_plugins") == len(chosen) and
            report.get("release_approved") is False,
            "missing complete bounded batch evidence")
    for index, (plugin, row) in enumerate(zip(chosen, report["plugins"]), start=1):
        name = plugin["id"]
        positive = name in ("wav_good", "midi_good")
        expected_status = "PASS" if positive else "FAIL"
        require(row["id"] == name and row["status"] == expected_status,
                name + " unexpected native outcome")
        child = out / "results" / (f"{index:02d}-" + name)
        top = child / "UNIVERSAL-QA-RESULT.json"
        require(top.is_file(), name + " missing P74 child evidence")
        found = json.loads(top.read_text(encoding="utf-8"))
        require(found.get("discovery") == "PASS",
                name + " native discovery failed before functional testing")
        require(found.get("release_approved") is False,
                name + " falsely granted product release")
        if positive:
            require(found.get("status") == "DECLARED_COVERAGE_PASS" and
                    found.get("required_feature_coverage") ==
                    "REQUIRED_COVERAGE_COMPLETE", name + " P74/P67 not passed")
            kind = "wav" if name.startswith("wav_") else "midi"
            verify_positive_artifact(child, name, kind)
        else:
            require(found.get("status") == "FAIL" and
                    found.get("required_feature_coverage") ==
                    "REQUIRED_COVERAGE_INCOMPLETE",
                    name + " incorrectly passed wrong-content export")
    summary = {
        "schema": "125a-p81-real-native-batch-v1",
        "status": "EXPECTED_GOOD_AND_BAD_PROVED",
        "scenario": "ALL_GOOD" if all_good else "BAD_FIRST_GOOD_LATER",
        "tested_real_source_built_vst3": len(chosen),
        "passed_plugins": report["passed_plugins"],
        "failed_plugins": report["failed_plugins"],
        "actual_gui_triggered_export_bytes_checked": True,
        "unknown_third_party_controls_tested": False,
        "commercial_daw_session": "NOT RUN",
        "physical_asio_hardware": "NOT RUN",
        "release_approved": False
    }
    (out / "P81-BATCH-ACCEPTANCE.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve(strict=True)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    hosts = list(build.rglob("125A_Test_Lab_GUI.exe"))
    require(len(hosts) == 1, "native GUI host missing/ambiguous")
    options = setup(build, hosts[0].resolve(strict=True), out)
    scenarios = [
        run_scenario(options, hosts[0].resolve(strict=True), out / "bad-first", all_good=False),
        run_scenario(options, hosts[0].resolve(strict=True), out / "all-good", all_good=True)
    ]
    (out / "P81-SUMMARY.json").write_text(json.dumps({
        "schema": "125a-p81-native-batch-summary-v1",
        "status": "PASS",
        "scenarios": scenarios,
        "release_approved": False
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
