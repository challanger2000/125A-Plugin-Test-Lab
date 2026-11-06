#!/usr/bin/env python3
"""P51 independently expected multi-point GUI control gesture contracts.

Compiles a strictly bounded sequence of real native Win32 drag gestures and
independent expected normalized VST3 values into P37's persistent-window
workflow. Never generates expected values from observed plugin output.
"""
import argparse
import json
import math
from pathlib import Path

from run_gui_workflow import run as run_workflow

SCHEMA = "125a-gui-gesture-sweep-v1"
RESULT = "125a-gui-gesture-sweep-result-v1"


def strict_int(x, maximum):
    if type(x) is not int or not 0 <= x <= maximum:
        raise ValueError("invalid bounded sweep integer")
    return x


def strict_value(x):
    if type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError("nonfinite/out-of-range expected normalized value")
    return float(x)


def compile_contract(contract):
    if not isinstance(contract, dict) or set(contract) != {
            "schema", "product", "gui_host", "param_id", "initial_normalized",
            "checkpoints"} or contract["schema"] != SCHEMA:
        raise ValueError("invalid gesture-sweep contract")
    pid = strict_int(contract["param_id"], 4294967295)
    initial = strict_value(contract["initial_normalized"])
    points = contract["checkpoints"]
    if not isinstance(points, list) or not 2 <= len(points) <= 32:
        raise ValueError("gesture sweep requires 2..32 ordered checkpoints")
    prev = initial
    steps = []
    endpoint_set = set()
    values = [initial]
    for index, point in enumerate(points):
        if not isinstance(point, dict) or set(point) != {
                "start_x", "start_y", "end_x", "end_y", "expected_normalized"}:
            raise ValueError("invalid independent gesture checkpoint")
        a, b, c, d = (strict_int(point[k], 8191) for k in
                       ("start_x", "start_y", "end_x", "end_y"))
        final = strict_value(point["expected_normalized"])
        if (a, b) == (c, d):
            raise ValueError("zero-length drag cannot prove regulator sweep")
        if abs(prev - final) <= 0.00001:
            raise ValueError("checkpoint must change the expected parameter")
        endpoint_set.add((c, d))
        steps.append({
            "id": "sweep_%02d" % index, "action": "drag",
            "x": a, "y": b, "end_x": c, "end_y": d,
            "param_id": pid, "before_normalized": prev,
            "expected_normalized": final
        })
        values.append(final)
        prev = final
    if len(endpoint_set) < 2 or max(values) - min(values) < .25:
        raise ValueError("sweep lacks spatial and parameter range")
    differences = [b - a for a, b in zip(values, values[1:])]
    if not (any(v > 0 for v in differences) and any(v < 0 for v in differences)):
        raise ValueError("sweep must validate movement in both value directions")
    workflow = {
        "schema": "125a-gui-workflow-v1",
        "product": contract["product"], "gui_host": contract["gui_host"],
        "initial": [{"param_id": pid, "normalized": initial}],
        "steps": steps
    }
    return workflow


def run(contract, out, *, timeout=90, workflow_runner=run_workflow):
    workflow = compile_contract(contract)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "GUI-GESTURE-SWEEP-RESULT.json"
    report_path.unlink(missing_ok=True)
    report = {
        "schema": RESULT, "status": "FAIL",
        "declared_checkpoints": len(workflow["steps"]),
        "verified_checkpoints": 0, "faults": [],
        "complete_gui_inventory": "NOT COVERED",
        "independent_product_audio_semantics": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
        "release_approved": False
    }
    try:
        nested = workflow_runner(workflow, out / "native", timeout=timeout)
        if (nested.get("status") != "TECHNICAL_PASS" or
                nested.get("verified_actions") != len(workflow["steps"]) or
                nested.get("declared_actions") != len(workflow["steps"]) or
                nested.get("controller_action_chain") != "PASS"):
            raise ValueError("native repeated drag workflow failed independent VST3 value checks")
        report["verified_checkpoints"] = len(workflow["steps"])
        report["status"] = "CONTRACT_PASS"
    except (ValueError, OSError, TypeError, KeyError) as exc:
        report["faults"].append(str(exc))
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    try:
        contract = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = run(contract, args.out, timeout=args.timeout)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": RESULT, "status": "FAIL", "faults": [str(exc)],
                  "release_approved": False}
        (args.out / "GUI-GESTURE-SWEEP-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "CONTRACT_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
