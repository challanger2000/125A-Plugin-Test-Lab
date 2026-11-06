#!/usr/bin/env python3
"""P45: fail-closed A/B/A regression of sham-supported GUI controls."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import struct


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


explorer = load("run_gui_exploration")
roundtrip = load("run_gui_roundtrip")


def bmp(path, color=(30, 36, 48), painted=(70, 80, 90)):
    width, height = 320, 180
    pix = bytearray(bytes((color[2], color[1], color[0], 255)) * (width * height))
    for y in range(65, 115):
        for x in range(120, 200):
            i = (y * width + x) * 4
            pix[i:i + 4] = bytes((painted[2], painted[1], painted[0], 255))
    header = struct.pack("<HIHHI", 0x4D42, 54 + len(pix), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32,
                      0, len(pix), 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + dib + pix)


with tempfile.TemporaryDirectory() as work:
    root = Path(work)
    bundle = root / "Fake.vst3"
    module = bundle / "Contents" / "x86_64-win" / "Fake.vst3"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"p45-original-real-module-hash")
    host = root / "GUI.exe"
    host.write_bytes(b"p45-native-test-host")
    phase = {"mode": "reversible"}

    def fake_native(command, **_):
        op = command[1]
        if op == "--snapshot-editor":
            bmp(Path(command[3]))
            return subprocess.CompletedProcess(command, 0, "", "")
        x, y = int(command[3]), int(command[4])
        if op in ("--explore-gui-click", "--explore-gui-sham"):
            mode = "click" if op.endswith("click") else "sham"
            rows = [
                "format\t125A-GUI-EXPLORE-v3",
                "mode\t" + mode, f"coordinate\t{x}\t{y}",
                "canvas\t320\t180", "target_depth\t0", "param_count\t1",
                "param\t0\t9001\t0\t0", "end\tCOMPLETE", ""
            ]
            Path(command[5]).write_text("\n".join(rows), encoding="utf-8")
            bmp(Path(command[6]))
            bmp(Path(command[7]))
            bmp(Path(command[8]), painted=(
                (12, 142, 85) if mode == "click" else (70, 80, 90)))
            return subprocess.CompletedProcess(command, 0, "", "")
        assert op == "--gui-observe-roundtrip", command
        behavior = phase["mode"]
        if behavior == "native_crash":
            return subprocess.CompletedProcess(command, 1, "", "crash")
        rows = [
            "format\t125A-GUI-ROUNDTRIP-v1", "mode\troundtrip",
            f"coordinate\t{x}\t{y}", "canvas\t320\t180",
            "target_depth\t0", "param_count\t1",
            "param\t0\t9001\t0\t0\t0", "end\tCOMPLETE", ""
        ]
        if behavior == "bad_target":
            rows[4] = "target_depth\t2"
        if behavior == "bad_pid":
            rows[6] = "param\t0\t9002\t0\t0\t0"
        if behavior == "bad_double":
            rows[6] = "param\t0\t9001\t0\t1\t0"
        if behavior == "bad_coordinate":
            rows[2] = "coordinate\t161\t90"
        Path(command[5]).write_text("\n".join(rows), encoding="utf-8")
        bmp(Path(command[6]))
        bmp(Path(command[7]))
        bmp(Path(command[8]), painted=(
            (70, 80, 90) if behavior == "not_reproduced" else (12, 142, 85)))
        if behavior != "missing_second":
            bmp(Path(command[9]), painted=(
                (12, 142, 85) if behavior == "nonreversible"
                else (70, 80, 90)))
        return subprocess.CompletedProcess(command, 0, "", "")

    scan = explorer.run(
        bundle, host, root / "exploration", points="160,90",
        acknowledge=True, runner=fake_native)
    assert scan["status"] == "OBSERVATIONS_COMPLETE", scan
    assert scan["candidates"][0]["observation"] == "VISUAL_CHANGE"
    assert (root / "exploration" / "GUI-CONTROL-REVIEW-DRAFT.json").exists()

    try:
        roundtrip.run(bundle, host, root / "exploration", root / "result",
                      runner=fake_native)
    except ValueError as exc:
        assert "explicit" in str(exc)
    else:
        raise AssertionError("unconsented double click went through")

    def check(mode):
        phase["mode"] = mode
        return roundtrip.run(
            bundle, host, root / "exploration", root / "result",
            acknowledge=True, runner=fake_native)

    ok = check("reversible")
    assert ok["status"] == "OBSERVATIONS_COMPLETE", ok
    assert ok["observed_reversible"] == 1
    assert ok["tested_candidates"] == 1
    assert ok["cases"][0]["classification"] == "OBSERVED_REVERSIBLE"
    assert ok["cases"][0]["controller_after_first_click"] == []
    assert ok["cases"][0]["painted_pixels_changed_after_first"] == 4000
    assert ok["cases"][0]["painted_pixels_remaining_after_second"] == 0
    assert ok["independent_product_semantics"] == "NOT COVERED"
    assert ok["release_approved"] is False

    nonreversible = check("nonreversible")
    assert nonreversible["status"] == "OBSERVATIONS_COMPLETE"
    assert nonreversible["observed_nonreversible"] == 1
    assert nonreversible["cases"][0]["classification"] == "OBSERVED_NONREVERSIBLE"
    assert nonreversible["release_approved"] is False

    no_repeat = check("not_reproduced")
    assert no_repeat["status"] == "OBSERVATIONS_COMPLETE"
    assert no_repeat["not_reproduced"] == 1
    assert no_repeat["cases"][0]["classification"] == "NOT_REPRODUCED"

    for bad in ("native_crash", "missing_second", "bad_target",
                "bad_pid", "bad_double", "bad_coordinate"):
        fail = check(bad)
        assert fail["status"] == "FAIL", (bad, fail)
        assert fail["faults"] and fail["release_approved"] is False, bad

    # A review draft is NOT an independently approved executable test.
    review = root / "exploration" / "GUI-CONTROL-REVIEW-DRAFT.json"
    before = review.read_text(encoding="utf-8")
    review.write_text(before.replace('"approved_for_execution": false',
                                     '"approved_for_execution": true'), encoding="utf-8")
    assert check("reversible")["status"] == "FAIL"
    review.write_text(before, encoding="utf-8")

    report = root / "exploration" / "GUI-EXPLORATION-RESULT.json"
    original = report.read_text(encoding="utf-8")
    report.write_text(original.replace('"sham_control": "COMPLETE"',
                                       '"sham_control": "FAIL"'), encoding="utf-8")
    assert check("reversible")["status"] == "FAIL"
    report.write_text(original, encoding="utf-8")

    # Previously observed RGB samples are not automatically trusted merely
    # because their JSON says the sham was complete.
    import json
    original_data = json.loads(original)
    original_data["probes"][0]["pixel_localization"]["regions"][0]["sample"][
        "after_rgb"] = [9, 9, 9]
    report.write_text(json.dumps(original_data), encoding="utf-8")
    assert check("reversible")["status"] == "FAIL"
    report.write_text(original, encoding="utf-8")

    screenshot = root / "exploration" / "probe-00" / "click-after.bmp"
    image_bytes = screenshot.read_bytes()
    screenshot.write_bytes(image_bytes[:80])
    assert check("reversible")["status"] == "FAIL"
    screenshot.write_bytes(image_bytes)

print("[PASS] P45 native A/B/A observes real two-way transitions, false success rejected")
