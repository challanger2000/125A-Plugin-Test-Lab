#!/usr/bin/env python3
"""P83 real source-built native VST3 positive/inert GUI exploration batch.

Opt-in never asserts product semantics or musical correctness.
"""
import argparse
import json
from pathlib import Path

from run_vst3_batch_qa import load_selection, run, SCHEMA


def locate(root, name):
    matches = [p for p in root.rglob(name) if
               p.is_dir() == name.endswith(".vst3")]
    if len(matches) != 1:
        raise ValueError("P83 ambiguous/missing native fixture " + name)
    return matches[0].resolve(strict=True)


def scenario(out, host, active, inert, *, opt_both):
    out.mkdir(parents=True, exist_ok=True)
    plugins = [
        {"id": "interactive", "bundle": str(active),
         "run_technical_baseline": False,
         "explore_unknown_gui": True,
         "exploration_points": "160,90", "exploration_max_points": 1},
        {"id": "inert", "bundle": str(inert),
         "run_technical_baseline": False}
    ]
    if opt_both:
        plugins[1].update(
            explore_unknown_gui=True, exploration_points="160,90",
            exploration_max_points=1)
    selection = out / "selection.json"
    selection.write_text(
        json.dumps({"schema": SCHEMA, "plugins": plugins}, indent=2) + "\n",
        encoding="utf-8")
    selected = load_selection(selection=selection)
    observed = run(selected, host, out / "results",
                   native_timeout=90, per_plugin_timeout=350)
    if (observed.get("status") != "BATCH_EXPLORATORY_OBSERVATIONS_COMPLETE" or
            observed.get("passed_plugins") != 2 or
            observed.get("failed_plugins") != 0 or
            observed.get("release_approved") is not False):
        raise ValueError("P83 real native unknown GUI batch rejected")
    for idx, row in enumerate(observed["plugins"]):
        expected = ("INVENTORY_WITH_EXPLORATORY_OBSERVATIONS" if idx == 0 or opt_both
                    else "INVENTORY_COMPLETE")
        expected_clicks = 1 if idx == 0 or opt_both else 0
        if (row.get("status") != "PASS" or
                row.get("verified_stage") != expected or
                row.get("exploratory_clicks_performed") != expected_clicks):
            raise ValueError("P83 native GUI probe evidence count/identity incorrect")
        if idx == 0 or opt_both:
            folder = out / "results" / ("%02d-%s" % (idx+1, row["id"]))
            report_file = folder / "UNIVERSAL-QA-RESULT.json"
            source = json.loads(report_file.read_text(encoding="utf-8"))
            expected_candidates = 1 if idx == 0 else 0
            if (source.get("unknown_gui_exploration") != "OBSERVATIONS_COMPLETE" or
                    source.get("exploratory_candidates_observed") != expected_candidates or
                    source.get("unknown_gui_semantics") != "UNAPPROVED OBSERVATIONS ONLY" or
                    source.get("release_approved") is not False):
                raise ValueError("P83 interactive and inert VST3 were misclassified")
    return {"status": "NATIVE_OBSERVATIONS_CONFIRMED",
            "opt_in_both": opt_both,
            "interactive_candidates": 1,
            "inert_candidates": 0 if opt_both else "NOT PROBED",
            "release_approved": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    a = parser.parse_args()
    build = a.build.resolve(strict=True)
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    host = locate(build, "125A_Test_Lab_GUI.exe")
    good = locate(build, "125A_QA_GUI_Click.vst3")
    inert = locate(build, "125A_QA_GUI_Inert.vst3")
    results = [
        scenario(out / "selected-only", host, good, inert, opt_both=False),
        scenario(out / "positive-and-negative", host, good, inert, opt_both=True)
    ]
    summary = {
        "schema": "125a-p83-native-batch-probes-v1",
        "status": "PASS",
        "real_source_built_vst3_controls_probed": True,
        "scenarios": results,
        "unknown_plugin_control_semantics_verified": False,
        "real_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False
    }
    (out / "P83-RESULT.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
