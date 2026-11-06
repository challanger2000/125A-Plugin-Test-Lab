#!/usr/bin/env python3
"""Adversarial independent sequence checks for reusable VST3 GUI workflows."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import struct
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

    # A real native VST3 can paint a control that is invisible to the
    # IEditController parameter inventory.  Independent before/after pixel
    # colors can still prove the actual action without a fabricated ParamID.
    visual_profile = dict(manifest)
    visual_profile["steps"] = [
        {"id": "visual_on", "action": "click", "x": 160, "y": 90,
         "screenshot": True, "visual_oracle": {
             "x": 1, "y": 1, "before_rgb": [30, 36, 48],
             "after_rgb": [12, 142, 85]}},
        {"id": "visual_off", "action": "click", "x": 160, "y": 90,
         "screenshot": True, "visual_oracle": {
             "x": 1, "y": 1, "before_rgb": [12, 142, 85],
             "after_rgb": [30, 36, 48]}}]
    visual_fail = {"mode": None}

    def colored_bmp(path, rgb):
        # Small 32-bit top-down native Win32 BMP, with a fixed pixel.
        width = height = 4
        stride = width * 4
        raw = bytes([rgb[2], rgb[1], rgb[0], 255]) * width * height
        file_hdr = struct.pack("<HIHHI", 0x4D42, 54 + len(raw), 0, 0, 54)
        dib = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32,
                          0, len(raw), 0, 0, 0, 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_hdr + dib + raw)

    def painted_native(argv, **_):
        assert argv[1] == "--gui-workflow"
        native_lines = Path(argv[3]).read_text(encoding="utf-8")
        assert native_lines.count("\t-\t-\t-\t1") == 2
        output = Path(argv[4])
        rows = ["format\t125A-GUI-WORKFLOW-RESULT-v1", "step_count\t2",
                "step\t0\t-\t-\t-\tPASS", "step\t1\t-\t-\t-\tPASS",
                "end\tPASS"]
        if visual_fail["mode"] == "forged_controller":
            rows[2] = "step\t0\t9001\t0\t1\tPASS"
        output.write_text("\n".join(rows) + "\n", encoding="utf-8")
        images = Path(argv[5])
        samples = [(30, 36, 48), (12, 142, 85), (12, 142, 85), (30, 36, 48)]
        if visual_fail["mode"] == "stale_paint":
            samples[1] = samples[0]
        for target, rgb in zip(("0.before.bmp", "0.bmp", "1.before.bmp", "1.bmp"), samples):
            if visual_fail["mode"] == "missing_before" and target == "1.before.bmp":
                continue
            colored_bmp(images / target, rgb)
        return subprocess.CompletedProcess(argv, 0, "native painting only", "")

    observed = workflow.run(visual_profile, out, runner=painted_native)
    assert observed["status"] == "TECHNICAL_PASS", observed
    assert observed["verified_actions"] == 2
    assert observed["verified_visual_only_actions"] == 2
    assert observed["visual_only_controls"] == "PASS"
    assert observed["product_gui_complete"] == "NOT COVERED"

    for visual_failure in ("stale_paint", "missing_before", "forged_controller"):
        visual_fail["mode"] = visual_failure
        rejected = workflow.run(visual_profile, out, runner=painted_native)
        assert rejected["status"] == "FAIL", (visual_failure, rejected)
        assert rejected["visual_only_controls"] == "FAIL"
        assert rejected["verified_visual_only_actions"] == 0
    visual_fail["mode"] = None

    forbidden = [
        {"visual_oracle": {"x": 1, "y": 1, "before_rgb": [0, 0, 0],
                           "after_rgb": [0, 0, 0]}},
        {"visual_oracle": {"x": 1, "y": 1, "before_rgb": [0, 0, 0],
                           "after_rgb": [256, 0, 0]}},
        {"visual_oracle": {"x": 1, "y": 1, "before_rgb": [0, 0, 0],
                           "after_rgb": [0, 0, 1]},
         "param_id": 9001},
        {"visual_oracle": {"x": 1, "y": 1, "before_rgb": [0, 0, 0],
                           "after_rgb": [0, 0, 1]},
         "screenshot": False},
    ]
    for addition in forbidden:
        check = dict(visual_profile)
        check["steps"] = [{**visual_profile["steps"][0], **addition}]
        try:
            workflow.validate(check)
        except ValueError:
            pass
        else:
            raise AssertionError("visual-only oracle accepted invalid/faked state: " +
                                 str(addition))

    # P39: keyboard shortcuts are sent to the real native HWND rather than
    # silently changing a VST3 controller value directly.
    keyboard_profile = dict(manifest)
    keyboard_profile["steps"] = [
        {"id": "space_on", "action": "key", "x": 160, "y": 90,
         "key_code": 32, "param_id": 9001,
         "before_normalized": 0.0, "expected_normalized": 1.0},
        {"id": "modified_enter_off", "action": "key", "x": 160, "y": 90,
         "key_code": 13, "modifiers": ["ctrl", "shift"], "param_id": 9001,
         "before_normalized": 1.0, "expected_normalized": 0.0}]
    expected_keyboard = workflow.make_native_manifest(
        keyboard_profile["initial"], keyboard_profile["steps"])
    assert "step\t0\tkey\t160\t90\t32\t0\t9001\t0\t1\t0" in expected_keyboard
    assert "step\t1\tkey\t160\t90\t13\t3\t9001\t1\t0\t0" in expected_keyboard
    keyboard_bad = {"mode": None}

    def native_keyboard(argv, **_):
        assert argv[1] == "--gui-workflow"
        assert Path(argv[3]).read_text(encoding="utf-8") == expected_keyboard
        rows = [
            "format\t125A-GUI-WORKFLOW-RESULT-v1", "step_count\t2",
            "step\t0\t9001\t0\t1\tPASS",
            "step\t1\t9001\t1\t0\tPASS", "end\tPASS"]
        if keyboard_bad["mode"] == "missing_first":
            rows.pop(2)
        if keyboard_bad["mode"] == "false_second":
            rows[3] = "step\t1\t9001\t1\t1\tPASS"
        Path(argv[4]).write_text("\n".join(rows) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "real keyboard messages observed", "")

    keyboard_ok = workflow.run(keyboard_profile, out, runner=native_keyboard)
    assert keyboard_ok["status"] == "TECHNICAL_PASS", keyboard_ok
    assert keyboard_ok["verified_actions"] == 2
    assert keyboard_ok["product_gui_complete"] == "NOT COVERED"
    for bad_key in ("missing_first", "false_second"):
        keyboard_bad["mode"] = bad_key
        keyboard_result = workflow.run(keyboard_profile, out, runner=native_keyboard)
        assert keyboard_result["status"] == "FAIL", (bad_key, keyboard_result)
        assert keyboard_result["verified_actions"] == 0
    keyboard_bad["mode"] = None

    disallowed_keyboard = [
        {"key_code": 0}, {"key_code": 7}, {"key_code": 256},
        {"key_code": 91}, {"key_code": 92}, {"key_code": True},
        {"key_code": "32"}, {"modifiers": ["ctrl", "ctrl"]},
        {"modifiers": ["super"]}, {"modifiers": "shift"},
        {"modifiers": [1]}, {"end_x": 160}, {"end_y": 90},
    ]
    for change in disallowed_keyboard:
        incorrect = dict(keyboard_profile)
        incorrect["steps"] = [dict(keyboard_profile["steps"][0], **change)]
        try:
            workflow.validate(incorrect)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe/incomplete keyboard action accepted: " + repr(change))

    # Keyboard messages must not be smuggled into mouse events.
    mouse_with_key = dict(manifest)
    mouse_with_key["steps"] = [dict(manifest["steps"][0], key_code=32)]
    try:
        workflow.validate(mouse_with_key)
    except ValueError:
        pass
    else:
        raise AssertionError("mouse action accepted silent keyboard payload")

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
