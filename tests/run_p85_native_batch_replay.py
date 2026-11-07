#!/usr/bin/env python3
"""P85: prove fresh-instance GUI replay via real isolated Windows VST3 batches.

Evidence is observational, not proof of musical function or commercial release.
"""
import argparse
import json
from pathlib import Path
from run_vst3_batch_qa import load_selection, run, SCHEMA


def locate(build, name, *, directory):
    matches = [p for p in build.rglob(name) if p.is_dir() == directory]
    if len(matches) != 1:
        raise ValueError("P85 native fixture missing/ambiguous: " + name)
    return matches[0].resolve(strict=True)


def scenario(root, gui, active, inert, *, repeat_inert):
    root.mkdir(parents=True, exist_ok=True)
    cases = [{
        "id": "active", "bundle": str(active), "run_technical_baseline": False,
        "explore_unknown_gui": True, "exploration_points": "160,90",
        "exploration_max_points": 1, "exploration_repeats": 2
    }, {
        "id": "inert", "bundle": str(inert), "run_technical_baseline": False
    }]
    if repeat_inert:
        cases[1].update(
            explore_unknown_gui=True, exploration_points="160,90",
            exploration_max_points=1, exploration_repeats=2)
    manifest = root / "selection.json"
    manifest.write_text(json.dumps({"schema": SCHEMA, "plugins": cases}, indent=2),
                        encoding="utf-8")
    selected = load_selection(selection=manifest)
    report = run(selected, gui, root / "batch", per_plugin_timeout=400,
                 native_timeout=110)
    if (report.get("status") != "BATCH_EXPLORATORY_OBSERVATIONS_COMPLETE"
            or report.get("passed_plugins") != 2
            or report.get("failed_plugins") != 0
            or report.get("release_approved") is not False):
        raise ValueError("P85 repeatable native multi-VST3 batch did not pass")
    for index, row in enumerate(report["plugins"], start=1):
        active_probe = index == 1
        opted_in = active_probe or repeat_inert
        expect_count = 2 if opted_in else 0
        expect_stage = ("INVENTORY_WITH_EXPLORATORY_OBSERVATIONS"
                        if opted_in else "INVENTORY_COMPLETE")
        if (row.get("status") != "PASS" or
                row.get("verified_stage") != expect_stage or
                row.get("exploratory_clicks_performed") != expect_count):
            raise ValueError("P85 batch replay-count or read-only isolation wrong")
        child = root / "batch" / (f"{index:02d}-" + row["id"])
        native_report = json.loads(
            (child / "UNIVERSAL-QA-RESULT.json").read_text(encoding="utf-8"))
        if (native_report.get("gui_clicks_automatically_authorized") != 0
                or native_report.get("release_approved") is not False):
            raise ValueError("P85 observations misrepresented as product tests")
        if not opted_in:
            if native_report.get("unknown_gui_exploration") != "NOT RUN":
                raise ValueError("P85 unapproved plugin unexpectedly explored")
            continue
        if (native_report.get("unknown_gui_repeatability") != "REPRODUCIBLE_OBSERVATIONS"
                or native_report.get("unknown_gui_completed_repetitions") != 2
                or native_report.get("exploratory_clicks_performed") != 2
                or native_report.get("unknown_gui_semantics") != "UNAPPROVED OBSERVATIONS ONLY"):
            raise ValueError("P85 real VST3 replay evidence missing")
        sub = child / "unknown-gui-probes" / "GUI-REPEATABILITY-RESULT.json"
        evidence = json.loads(sub.read_text(encoding="utf-8"))
        signatures = evidence.get("reproduced_control_signatures")
        if (evidence.get("status") != "REPRODUCIBLE_OBSERVATIONS"
                or evidence.get("completed_repetitions") != 2
                or evidence.get("semantic_correctness") != "NOT ESTABLISHED"
                or evidence.get("identical_fresh_instance_observations") is not True
                or not isinstance(signatures, list) or len(signatures) != 1):
            raise ValueError("P85 P84 source-built VST3 repeatability unverified")
        expected = ("NO_OBSERVED_CHANGE" if not active_probe else
                    "PARAMETER_AND_VISUAL_CHANGE")
        if signatures[0]["classification"] != expected:
            raise ValueError("P85 genuine VST3 active/inert signature wrong")
        for n in (1, 2):
            native = child / "unknown-gui-probes" / ("repeat-%02d" % n)
            if not (native / "GUI-EXPLORATION-RESULT.json").is_file():
                raise ValueError("P85 independent sham/click native artifacts missing")
    return {
        "status": "FRESH_NATIVE_INSTANCES_VERIFIED",
        "native_vst3_plugins": len(cases),
        "approved_exploratory_clicks": 2 * (1 + int(repeat_inert)),
        "inert_probed": repeat_inert,
        "all_product_features_tested": False,
        "physical_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    build = a.build.resolve(strict=True)
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    gui = locate(build, "125A_Test_Lab_GUI.exe", directory=False)
    active = locate(build, "125A_QA_GUI_Click.vst3", directory=True)
    inert = locate(build, "125A_QA_GUI_Inert.vst3", directory=True)
    reports = [
        scenario(out / "only-active-opted-in", gui, active, inert, repeat_inert=False),
        scenario(out / "active-and-inert-opted-in", gui, active, inert, repeat_inert=True)
    ]
    (out / "P85-ACCEPTANCE.json").write_text(json.dumps({
        "schema": "125a-p85-native-batch-replay-v1",
        "status": "PASS", "scenarios": reports,
        "native_sham_and_clicks_verified": True,
        "unknown_control_semantics": "NOT ESTABLISHED",
        "release_approved": False
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
