#!/usr/bin/env python3
"""P87 reconcile native read-only VST3 ABI parameters with P86 GUI samples.

Observing a parameter transition at an arbitrary grid point does NOT establish
that every UI control is known, or that changing it produces correct audio.
"""
import argparse
import json
from pathlib import Path

from run_vst3_auto_discovery import (
    parse_capabilities, parse_parameters, digest as sha256
)

SCHEMA = "125a-abi-gui-observation-gap-v1"


def run(capability_file, parameter_file, dense_report, out):
    cap = Path(capability_file).resolve(strict=True)
    par = Path(parameter_file).resolve(strict=True)
    dense = Path(dense_report).resolve(strict=True)
    for path in (cap, par, dense):
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("P87 native read-only evidence missing or oversized")
    hashes = {str(p): sha256(p) for p in (cap, par, dense)}
    capabilities = parse_capabilities(cap.read_text(encoding="utf-8"))
    parameters = parse_parameters(par.read_text(encoding="utf-8"),
                                  capabilities["parameter_count"])
    observed = json.loads(dense.read_text(encoding="utf-8"))
    if (not isinstance(observed, dict) or
            observed.get("schema") != "125a-dense-gui-audit-v1" or
            observed.get("status") != "SAMPLED_GRID_COMPLETE" or
            observed.get("control_semantics") != "NOT ESTABLISHED" or
            observed.get("all_controls_discovered") is not False or
            observed.get("release_approved") is not False or
            observed.get("completed_points") != observed.get("planned_points") or
            type(observed.get("planned_points")) is not int or
            observed["planned_points"] not in (9, 25) or
            not isinstance(observed.get("observations"), list) or
            len(observed["observations"]) != observed["planned_points"] or
            not isinstance(observed.get("observed_parameter_ids"), list)):
        raise ValueError("P87 dense GUI observation evidence incomplete")
    all_ids = [p["param_id"] for p in parameters]
    observed_ids = observed["observed_parameter_ids"]
    if (any(type(i) is not int for i in observed_ids)
            or observed_ids != sorted(set(observed_ids))
            or not set(observed_ids) <= set(all_ids)):
        raise ValueError("P87 sample GUI observation references unknown/duplicate VST3 parameter")
    transitions = set()
    for item in observed["observations"]:
        if not isinstance(item, dict) or not isinstance(item.get("parameter_transitions"), list):
            raise ValueError("P87 no native GUI transition evidence")
        for t in item["parameter_transitions"]:
            if not isinstance(t, (tuple,list)) or len(t) != 3 or type(t[0]) is not int:
                raise ValueError("P87 invalid native GUI parameter transition")
            transitions.add(t[0])
    if transitions != set(observed_ids):
        raise ValueError("P87 P86 observed IDs and exact per-click transitions disagree")
    all_ids_set = set(all_ids)
    if len(all_ids_set) != len(all_ids):
        raise ValueError("P87 duplicate VST3 parameter identity")
    # VST3 ParameterInfo::kIsReadOnly flag == (1<<1). This is a
    # VST3 interface flag, NOT a GUI testability claim.
    editable = [p for p in parameters if not p["flags"] & 2]
    report = {
        "schema": SCHEMA, "status": "ABI_AND_SAMPLED_GUI_RECONCILED",
        "native_evidence_hashes": hashes,
        "verified_module_sha256": observed.get("verified_module_sha256"),
        "verified_gui_host_sha256": observed.get("verified_gui_host_sha256"),
        "native_parameter_count": len(parameters),
        "native_editable_parameter_count": len(editable),
        "sampled_grid_points": observed["completed_points"],
        "sampled_grid_observed_parameter_count": len(observed_ids),
        "sampled_grid_observed_parameter_ids": observed_ids,
        "abi_parameters_without_sampled_gui_transition": sorted(all_ids_set-set(observed_ids)),
        "editable_parameters_without_sampled_gui_transition": sorted(
            p["param_id"] for p in editable if p["param_id"] not in set(observed_ids)),
        "parameter_observation_ratio": (
            len(observed_ids) / len(parameters) if parameters else None),
        "unobserved_does_not_mean_broken": True,
        "abi_exposed_does_not_mean_gui_control_exists": True,
        "custom_functions_not_in_abi": "UNKNOWN",
        "complete_gui_control_inventory": False,
        "musical_correctness": "NOT ESTABLISHED",
        "release_approved": False
    }
    if any(sha256(path) != digest for path, digest in (
            (cap, hashes[str(cap)]), (par, hashes[str(par)]), (dense, hashes[str(dense)]))):
        raise ValueError("P87 source evidence mutated during ABI-to-GUI reconciliation")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ABI-GUI-COVERAGE-GAPS.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capabilities", type=Path, required=True)
    p.add_argument("--parameters", type=Path, required=True)
    p.add_argument("--dense-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        report = run(a.capabilities, a.parameters, a.dense_report, a.out)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        a.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": SCHEMA, "status": "FAIL", "faults": [str(e)],
                  "complete_gui_control_inventory": False, "release_approved": False}
        (a.out / "ABI-GUI-COVERAGE-GAPS.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ABI_AND_SAMPLED_GUI_RECONCILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
