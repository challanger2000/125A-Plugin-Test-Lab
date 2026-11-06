#!/usr/bin/env python3
"""Adversarial P41 GUI exploration tests. No product-specific click mapping."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location(
    "explorer", Path(__file__).with_name("run_gui_exploration.py"))
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def bmp(path, color, width=320, height=180):
    pixels = bytes((color[2], color[1], color[0], 255)) * (width * height)
    file_hdr = struct.pack("<HIHHI", 0x4D42, 54 + len(pixels), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32,
                      0, len(pixels), 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_hdr + dib + pixels)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    bundle = root / "Example.vst3"
    binary = bundle / "Contents" / "x86_64-win" / "Example.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"real-module-identity")
    host = root / "GUI.exe"
    host.write_bytes(b"real-native-exploration-host-identity")
    base_binary = binary.read_bytes()
    scenario = {"mode": "working"}

    def fake_native(argv, **kwargs):
        assert argv[0] == str(host.resolve())
        if argv[1] == "--snapshot-editor":
            bmp(Path(argv[3]), (30, 36, 48))
            return subprocess.CompletedProcess(argv, 0, "[PASS] snapshot", "")
        assert argv[1] in ("--explore-gui-click", "--explore-gui-sham"), argv
        assert len(argv) == 9, argv
        actual_click = argv[1] == "--explore-gui-click"
        x, y = int(argv[3]), int(argv[4])
        mode = scenario["mode"]
        if mode == "timeout":
            raise subprocess.TimeoutExpired(argv, 5)
        if mode == "crash":
            return subprocess.CompletedProcess(argv, 1, "", "crash")
        if mode == "missing_evidence":
            return subprocess.CompletedProcess(argv, 0, "[PASS] forged", "")
        if mode == "tamper_binary":
            binary.write_bytes(b"modified mid-test module")
        params = [(9001, 0.0, 1.0)] if (
            actual_click and mode not in ("inert", "visual_only", "spontaneous", "hover_only")
            or mode == "sham_parameter") else [(9001, 0.0, 0.0)]
        text = ["format\t125A-GUI-EXPLORE-v3",
                "mode\t" + ("click" if actual_click else "sham"),
                f"coordinate\t{x}\t{y}",
                "canvas\t320\t180",
                "target_depth\t" + ("1" if mode in ("nested", "wrong_hit") and
                                     (actual_click or mode == "nested") else "0"),
                "param_count\t1"]
        text.extend(f"param\t{i}\t{pid}\t{a}\t{b}"
                    for i, (pid, a, b) in enumerate(params))
        text.append("end\tCOMPLETE")
        report = "\n".join(text) + "\n"
        if mode == "wrong_coordinate":
            report = report.replace(f"coordinate\t{x}\t{y}",
                                    f"coordinate\t{x+1}\t{y}")
        if mode == "wrong_control_mode" and not actual_click:
            report = report.replace("mode\tsham", "mode\tclick")
        if mode == "bad_target_depth":
            report = report.replace("target_depth\t0", "target_depth\t19")
        if mode == "duplicate_param":
            report = report.replace("param_count\t1", "param_count\t2").replace(
                "end\tCOMPLETE", "param\t1\t9001\t0\t1\nend\tCOMPLETE")
        if mode == "missing_end":
            report = report.replace("end\tCOMPLETE\n", "")
        Path(argv[5]).write_text(report, encoding="utf-8")
        base = (40, 36, 48) if mode == "cross_baseline" and not actual_click else (30, 36, 48)
        bmp(Path(argv[6]), base)
        bmp(Path(argv[7]), base if mode != "baseline_drift" else (42, 36, 48))
        post = ((12, 142, 85)
                if (mode in ("spontaneous", "baseline_drift", "hover_only")
                    or (actual_click and mode not in ("stale_paint", "inert", "sham_parameter")))
                else base)
        bmp(Path(argv[8]), post)
        if mode == "bad_bmp":
            Path(argv[8]).write_bytes(b"bad bmp")
        return subprocess.CompletedProcess(argv, 0, "[OBSERVED] actual native click", "")

    try:
        e.run(bundle, host, root / "out", points="160,90", runner=fake_native)
    except ValueError as exc:
        assert "explicit opt-in" in str(exc)
    else:
        raise AssertionError("surprise plugin GUI click without consent")
    for invalid in ("", "160,90;", "-1,90", "160,9000", "160,90;160,90",
                    "900,90", "160 90", "160,90;0,0;160,90"):
        try:
            e.parse_points(invalid, 320, 180)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe GUI exploration coordinates accepted: " + invalid)
    assert len(e.grid_points(320, 180, 9)) == 9
    assert (160, 90) in e.grid_points(320, 180, 9)
    assert len(e.grid_points(320, 180, 16)) == 16

    def inspect(mode, *, points="160,90"):
        scenario["mode"] = mode
        return e.run(bundle, host, root / "out", points=points,
                     acknowledge=True, runner=fake_native)

    good = inspect("working")
    assert good["status"] == "OBSERVATIONS_COMPLETE", good
    assert good["completed_points"] == 1
    assert good["sham_verified_points"] == 1
    assert good["sham_control"] == "COMPLETE"
    assert good["probes"][0]["sham_control_attribution"] == "SUPPORTED"
    assert good["probes"][0]["sham_pixels_changed"] == 0
    assert good["probes"][0]["native_child_depth"] == 0
    assert good["probes"][0]["routed_to_descendant_hwnd"] is False
    assert good["candidates"][0]["parameter_ids_changed"] == [9001]
    assert good["probes"][0]["classification"] == "PARAMETER_AND_VISUAL_CHANGE"
    assert good["gui_control_discovery"] == "OBSERVATIONS_ONLY"
    assert good["product_gui_controls"] == "NOT COVERED"
    assert good["release_approved"] is False

    # Source-agnostic test: a real nested native HWND has depth >= 1,
    # while sham and click must identify the SAME descendant window depth.
    nested = inspect("nested")
    assert nested["status"] == "OBSERVATIONS_COMPLETE"
    assert nested["probes"][0]["native_child_depth"] == 1
    assert nested["probes"][0]["routed_to_descendant_hwnd"] is True
    assert nested["candidates"][0]["native_child_depth"] == 1
    wrong_hit = inspect("wrong_hit")
    assert wrong_hit["status"] == "FAIL"
    assert wrong_hit["gui_control_discovery"] == "NOT COVERED"

    stale = inspect("stale_paint")
    assert stale["status"] == "OBSERVATIONS_COMPLETE"
    assert stale["probes"][0]["classification"] == "PARAMETER_CHANGE"
    assert stale["probes"][0]["painted_pixels_changed"] == 0

    inert = inspect("inert")
    assert inert["status"] == "OBSERVATIONS_COMPLETE"
    assert inert["candidates"] == [], "inert plugin falsely discovered as interactive"
    assert inert["probes"][0]["classification"] == "NO_OBSERVED_CHANGE"

    visual = inspect("visual_only")
    assert visual["status"] == "OBSERVATIONS_COMPLETE"
    assert visual["probes"][0]["classification"] == "VISUAL_CHANGE"
    assert visual["candidates"][0]["parameter_ids_changed"] == []

    drifting = inspect("baseline_drift")
    assert drifting["status"] == "OBSERVATIONS_COMPLETE"
    assert drifting["probes"][0]["classification"] == "UNSTABLE_CONTROL"
    assert drifting["probes"][0]["painted_visual_observation"] == "UNSTABLE"
    assert drifting["candidates"] == [], "unstable baseline was misattributed to click"

    # The vital negative: motion that occurs even without clicking must NOT
    # become a discovered UI button. A click-only detector would report
    # a completely fictional visual control here.
    spontaneous = inspect("spontaneous")
    assert spontaneous["status"] == "OBSERVATIONS_COMPLETE"
    assert spontaneous["probes"][0]["sham_pixels_changed"] > 0
    assert spontaneous["probes"][0]["classification"] == "UNSTABLE_CONTROL"
    assert spontaneous["candidates"] == [], "spontaneous animation falsely discovered as button"

    hover = inspect("hover_only")
    assert hover["status"] == "OBSERVATIONS_COMPLETE"
    assert hover["probes"][0]["sham_pixels_changed"] > 0
    assert hover["probes"][0]["classification"] == "UNSTABLE_CONTROL"
    assert hover["candidates"] == [], "hover painted without any actual click change"

    sham_parameter = inspect("sham_parameter")
    assert sham_parameter["status"] == "OBSERVATIONS_COMPLETE"
    assert sham_parameter["probes"][0]["sham_parameter_changes"]
    assert sham_parameter["probes"][0]["classification"] == "UNSTABLE_CONTROL"
    assert sham_parameter["candidates"] == [], "background parameter automation falsely attributed"

    cross_baseline = inspect("cross_baseline")
    assert cross_baseline["status"] == "OBSERVATIONS_COMPLETE"
    assert cross_baseline["probes"][0]["cross_process_baseline_mismatch"] > 0
    assert cross_baseline["probes"][0]["classification"] == "UNSTABLE_CONTROL"
    assert cross_baseline["candidates"] == []

    for mode in ("crash", "timeout", "missing_evidence", "wrong_coordinate",
                 "duplicate_param", "missing_end", "bad_bmp", "tamper_binary",
                 "wrong_control_mode", "bad_target_depth"):
        broken = inspect(mode)
        assert broken["status"] == "FAIL", (mode, broken)
        assert broken["gui_control_discovery"] == "NOT COVERED"
        assert broken["release_approved"] is False
        assert broken["faults"], mode
        binary.write_bytes(base_binary)

    # Default grid works without author-supplied coordinates. It still does
    # not pretend to know product semantics or certify undiscovered controls.
    scenario["mode"] = "working"
    grid = e.run(bundle, host, root / "grid", acknowledge=True,
                 max_points=3, runner=fake_native)
    assert grid["status"] == "OBSERVATIONS_COMPLETE", grid
    assert grid["requested_points"] == 3
    assert grid["completed_points"] == 3
    assert grid["sham_verified_points"] == 3
    assert grid["sham_control"] == "COMPLETE"
    assert len(grid["candidates"]) == 3
    assert grid["product_gui_controls"] == "NOT COVERED"
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == grid["verified_module_sha256"]

print("[PASS] sham-controlled GUI discovery rejects spontaneous animation and unrelated parameter changes")
