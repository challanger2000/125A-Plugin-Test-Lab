#!/usr/bin/env python3
"""P88 deterministic GUI review queue from native ABI and sampled GUI evidence.

This is intentionally NON-EXECUTABLE. A sham-controlled transition is a
measurement, not independently approved functional correctness or a label.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from run_vst3_auto_discovery import parse_capabilities, parse_parameters, digest
from run_gui_parameter_coverage import run as reconcile

SCHEMA = "125a-gui-owner-review-package-v1"
MAX_BYTES = 2_000_000


def _source(path):
    p = Path(path).resolve(strict=True)
    if not p.is_file() or p.stat().st_size < 1 or p.stat().st_size > MAX_BYTES:
        raise ValueError("P88 source evidence missing or oversized")
    return p


def _transition(t):
    if (not isinstance(t, (tuple, list)) or len(t) != 3
            or type(t[0]) is not int or type(t[1]) not in (int, float)
            or type(t[2]) not in (int, float)
            or not 0 <= t[1] <= 1 or not 0 <= t[2] <= 1):
        raise ValueError("P88 malformed observed parameter transition")
    return t


def generate(capabilities, parameters, dense_report, out,
             *, reconciler=reconcile):
    cap, par, dense_path = map(_source, (capabilities, parameters, dense_report))
    caps = parse_capabilities(cap.read_text(encoding="utf-8"))
    params = parse_parameters(par.read_text(encoding="utf-8"),
                              caps["parameter_count"])
    evidence = json.loads(dense_path.read_text(encoding="utf-8"))
    if (not isinstance(evidence, dict) or
            evidence.get("schema") != "125a-dense-gui-audit-v1" or
            evidence.get("status") != "SAMPLED_GRID_COMPLETE" or
            evidence.get("control_semantics") != "NOT ESTABLISHED" or
            evidence.get("release_approved") is not False or
            evidence.get("all_controls_discovered") is not False or
            not isinstance(evidence.get("observations"), list)):
        raise ValueError("P88 not a complete source-defined native sampled GUI audit")

    hashes = {str(p): digest(p) for p in (cap, par, dense_path)}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    gap = reconciler(cap, par, dense_path, out / "verified-gaps")
    if (not isinstance(gap, dict) or
            gap.get("schema") != "125a-abi-gui-observation-gap-v1" or
            gap.get("status") != "ABI_AND_SAMPLED_GUI_RECONCILED" or
            gap.get("verified_module_sha256") != evidence.get("verified_module_sha256") or
            gap.get("verified_gui_host_sha256") != evidence.get("verified_gui_host_sha256") or
            gap.get("sampled_grid_points") != len(evidence["observations"]) or
            gap.get("complete_gui_control_inventory") is not False or
            gap.get("release_approved") is not False):
        raise ValueError("P88 independent ABI/GUI gap reconciliation failed")

    by_id = {p["param_id"]: p for p in params}
    observed_by_parameter = defaultdict(list)
    visual_candidates = []
    inert_count = 0
    for index, row in enumerate(evidence["observations"]):
        if (not isinstance(row, dict) or type(row.get("x")) is not int
                or type(row.get("y")) is not int or
                not 0 <= row["x"] <= 4095 or not 0 <= row["y"] <= 4095 or
                row.get("classification") not in (
                    "PARAMETER_CHANGE", "PARAMETER_AND_VISUAL_CHANGE",
                    "VISUAL_CHANGE", "NO_OBSERVED_CHANGE") or
                not isinstance(row.get("parameter_transitions"), list)):
            raise ValueError("P88 malformed native sampled editor coordinate")
        changes = row["parameter_transitions"]
        if row["classification"] == "NO_OBSERVED_CHANGE":
            inert_count += 1
            if changes:
                raise ValueError("P88 inert coordinate contains unexpected parameter effect")
        if row["classification"] == "VISUAL_CHANGE":
            if changes:
                raise ValueError("P88 visual-only click spuriously includes parameters")
            visual_candidates.append({
                "observation_id": "sample_%02d" % (index+1),
                "position": {"x": row["x"], "y": row["y"]},
                "observed_visual_change": True,
                "proposed_function": None,
                "expected_visual_reference": None,
                "status": "REQUIRES_INDEPENDENT_PRODUCT_ORACLE"
            })
        if row["classification"] in ("PARAMETER_CHANGE",
                                     "PARAMETER_AND_VISUAL_CHANGE") and not changes:
            raise ValueError("P88 controller change observed without actual transition")
        for t in changes:
            pid, before, after = _transition(t)
            if pid not in by_id:
                raise ValueError("P88 unknown VST3 ParameterID in sampled GUI evidence")
            observed_by_parameter[pid].append({
                "observation_id": "sample_%02d" % (index+1),
                "position": {"x": row["x"], "y": row["y"]},
                "before_normalized": before,
                "after_normalized": after,
                "visual_change_observed":
                    row["classification"] == "PARAMETER_AND_VISUAL_CHANGE"
            })

    if (set(observed_by_parameter) != set(gap.get("sampled_grid_observed_parameter_ids", []))
            or set(by_id) - set(observed_by_parameter) !=
               set(gap.get("abi_parameters_without_sampled_gui_transition", []))):
        raise ValueError("P88 source observations conflict with independently reconciled gaps")

    queue = []
    for p in sorted(params, key=lambda e: e["param_id"]):
        pid = p["param_id"]
        obs = observed_by_parameter[pid]
        queue.append({
            "param_id": pid,
            "native_step_count": p["step_count"],
            "native_default_normalized": p["default_normalized"],
            "native_current_normalized": p["current_normalized"],
            "native_read_only": bool(p["flags"] & 2),
            "observations": obs,
            "observed_at_grid_sample": bool(obs),
            "ambiguous_positions": len(obs) > 1,
            "proposed_product_control_name": None,
            "required_expected_state_values": None,
            "required_audio_reference": None,
            "requires_owner_approval": True,
            "approved_to_execute": False,
            "semantic_correctness": "NOT ESTABLISHED"
        })

    report = {
        "schema": SCHEMA, "status": "REVIEW_PACKAGE_COMPLETE",
        "native_module_sha256": evidence["verified_module_sha256"],
        "native_gui_host_sha256": evidence["verified_gui_host_sha256"],
        "source_evidence_sha256": hashes,
        "native_parameter_count": len(queue),
        "observed_parameter_count": len(observed_by_parameter),
        "unobserved_parameter_count": len(queue) - len(observed_by_parameter),
        "native_gui_sample_points": len(evidence["observations"]),
        "sample_points_without_observed_change": inert_count,
        "visual_only_review_candidates": visual_candidates,
        "parameter_review_queue": queue,
        "unobserved_does_not_mean_nonfunctional": True,
        "complete_ui_inventory": False,
        "executable_p65_plan_generated": False,
        "independent_product_oracles": "NOT PROVIDED",
        "physical_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False
    }
    if any(digest(p) != hashes[str(p)] for p in (cap, par, dense_path)):
        raise ValueError("P88 input files changed during review generation")
    (out / "OWNER-GUI-REVIEW-QUEUE.json").write_text(
        json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capabilities", type=Path, required=True)
    p.add_argument("--parameters", type=Path, required=True)
    p.add_argument("--dense-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        report = generate(a.capabilities, a.parameters, a.dense_report, a.out)
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            json.JSONDecodeError) as exc:
        a.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": SCHEMA, "status": "FAIL", "faults": [str(exc)],
                  "executable_p65_plan_generated": False,
                  "release_approved": False}
        (a.out / "OWNER-GUI-REVIEW-QUEUE.json").write_text(
            json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "REVIEW_PACKAGE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
