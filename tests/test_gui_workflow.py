#!/usr/bin/env python3
"""Adversarial independent sequence checks for reusable VST3 GUI workflows."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location(
    "workflow", Path(__file__).with_name("run_gui_workflow.py"))
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    binary = root / "Fixture.vst3" / "Contents" / "x86_64-win" / "Fixture.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"native test VST3 identity")
    host = root / "125A_Test_Lab_GUI.exe"
    host.write_bytes(b"pinned actual host identity")
    manifest = {
        "schema": "125a-gui-workflow-v1",
        "product": {"binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
        "gui_host": str(host),
        "initial": [{"param_id": 9001, "normalized": 0.0}],
        "steps": [
            {"id": "click_on", "action": "click", "x": 160, "y": 90,
             "param_id": 9001, "before_normalized": 0.0, "expected_normalized": 1.0},
            {"id": "click_off", "action": "click", "x": 160, "y": 90,
             "param_id": 9001, "before_normalized": 1.0, "expected_normalized": 0.0},
            {"id": "drag_on", "action": "drag", "x": 100, "y": 90,
             "end_x": 160, "end_y": 90, "param_id": 9001,
             "before_normalized": 0.0, "expected_normalized": 1.0},
            {"id": "drag_off", "action": "drag", "x": 100, "y": 90,
             "end_x": 160, "end_y": 90, "param_id": 9001,
             "before_normalized": 1.0, "expected_normalized": 0.0}]}
    out = root / "results"
    fail_mode = {"name": None}

    def native(argv, **_kwargs):
        assert argv[0] == str(host.resolve())
        assert argv[1] == "--gui-workflow", argv
        assert Path(argv[2]).samefile(binary.parents[2]), argv
        data = Path(argv[3]).read_text(encoding="utf-8")
        assert data.startswith("format\t125A-GUI-WORKFLOW-v1\n")
        assert data.count("\nstep\t") == 4, data
        if fail_mode["name"] == "changed_module":
            binary.write_bytes(b"other module silently swapped")
        if fail_mode["name"] == "changed_profile":
            Path(argv[3]).write_text("changed approved input", encoding="utf-8")
        if fail_mode["name"] == "missing":
            return subprocess.CompletedProcess(argv, 0, "native says PASS but no evidence", "")
        result = [
            "format\t125A-GUI-WORKFLOW-RESULT-v1", "step_count\t4"
        ]
        for index, item in enumerate(manifest["steps"]):
            before = item["before_normalized"]
            after = item["expected_normalized"]
            if fail_mode["name"] == "wrong_value" and index == 2:
                after = 0.0
            result.append("step\t%d\t%d\t%.17g\t%.17g\t%s" %
                          (index, item["param_id"], before, after,
                           "FAIL" if fail_mode["name"] == "wrong_value" and index == 2
                           else "PASS"))
        result.append("end\tPASS")
        if fail_mode["name"] == "truncated":
            result.pop()
        if fail_mode["name"] == "reordered":
            result[2], result[3] = result[3], result[2]
        Path(argv[4]).write_text("\n".join(result) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "native host processed actions", "")

    positive = workflow.run(manifest, out, runner=native)
    assert positive["status"] == "TECHNICAL_PASS", positive
    assert positive["verified_actions"] == 4
    assert positive["product_gui_complete"] == "NOT COVERED"
    assert positive["commercial_daw_integration"] == "NOT COVERED"
    unchanged = binary.read_bytes()

    for wrong in ("missing", "wrong_value", "truncated", "reordered",
                  "changed_module", "changed_profile"):
        fail_mode["name"] = wrong
        result = workflow.run(manifest, out, runner=native)
        assert result["status"] == "FAIL", (wrong, result)
        assert result["verified_actions"] == 0, (wrong, result)
        assert result["controller_action_chain"] == "FAIL", wrong
        assert result["faults"], wrong
        binary.write_bytes(unchanged)
        assert json.loads((out / "GUI-WORKFLOW-RESULT.json").read_text())["status"] == "FAIL"
    fail_mode["name"] = None

    invalid = [
        {"id": "bad", "action": "click", "x": -1, "y": 90},
        {"id": "bad", "action": "drag", "x": 0, "y": 0},
        {"id": "bad", "action": "delete", "x": 160, "y": 90},
        {"id": "bad", "expected_normalized": 0.0},
        {"id": "bad", "before_normalized": float("nan")},
        {"id": "bad", "before_normalized": 1.0},
        {"id": "bad", "screenshot": True, "expected_pixel": {"x": 0, "y": 0, "rgb": [0, 256, 0]}},
        {"id": "bad", "expected_pixel": {"x": 0, "y": 0, "rgb": [0, 0, 0]}},
        {"id": "bad", "screenshot": "yes"},
        {"id": "bad", "param_id": True},
    ]
    for change in invalid:
        candidate = dict(manifest)
        candidate["steps"] = [dict(manifest["steps"][0], **change)]
        try:
            workflow.validate(candidate)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError("invalid workflow profile unexpectedly accepted: " + str(change))

    no_state = dict(manifest)
    no_state["steps"] = []
    try:
        workflow.validate(no_state)
    except ValueError:
        pass
    else:
        raise AssertionError("empty GUI workflow accepted")
    assert workflow.validate(manifest)[3] == manifest["initial"]

print("[PASS] ordered real-GUI workflow oracle rejects stale/missing/false green actions")
