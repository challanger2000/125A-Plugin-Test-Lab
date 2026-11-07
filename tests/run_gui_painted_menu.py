#!/usr/bin/env python3
"""P64 verify a custom-painted (one HWND) VST3 popup menu over ordered clicks.

This runner independently locates a painted visual change from native
before/after BMPs and confirms a subsequently selected VST3 parameter.
Approved fixture coordinates and semantic expectations are REQUIRED.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from run_gui_workflow import run as workflow_run
from run_gui_hwnd_tree import run as tree_run

SCHEMA = "125a-painted-popup-menu-result-v1"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def bmp_pixels(path):
    raw = Path(path).read_bytes()
    if len(raw) < 54 or raw[:2] != b"BM":
        raise ValueError("P64 invalid native BMP signature")
    file_size, off = struct.unpack_from("<IxxxxI", raw, 2)
    header, width, signed_height, planes, bits, compression = struct.unpack_from(
        "<IiiHHI", raw, 14)
    if (file_size != len(raw) or header != 40 or planes != 1 or bits != 32
            or compression != 0 or off != 54 or not 1 <= width <= 2048
            or not 1 <= abs(signed_height) <= 2048):
        raise ValueError("P64 native BMP geometry, format or file bounds invalid")
    height = abs(signed_height)
    if len(raw) != 54 + width * height * 4:
        raise ValueError("P64 truncated or padded native screenshot pixels")
    pixels = memoryview(raw)[54:]
    return width, height, signed_height < 0, pixels


def changed_bbox(before, after, *, threshold=0):
    a = bmp_pixels(before)
    b = bmp_pixels(after)
    if a[:3] != b[:3]:
        raise ValueError("P64 different HWND screenshot dimensions/direction")
    if type(threshold) is not int or not 0 <= threshold <= 60:
        raise ValueError("P64 invalid RGB difference threshold")
    width, height, top_down, source = a
    target = b[3]
    x_min, y_min = width, height
    x_max = y_max = -1
    changed = 0
    for y in range(height):
        row = y if top_down else height - 1 - y
        for x in range(width):
            offset = (row * width + x) * 4
            if max(abs(source[offset + c] - target[offset + c])
                   for c in (0, 1, 2)) > threshold:
                changed += 1
                x_min, y_min = min(x_min, x), min(y_min, y)
                x_max, y_max = max(x_max, x), max(y_max, y)
    return ([x_min, y_min, x_max + 1, y_max + 1] if changed else None), changed


def fixture_manifest(dll, host):
    return {
        "schema": "125a-gui-workflow-v1",
        "product": {"binary": str(dll), "sha256": digest(dll)},
        "gui_host": str(host),
        "initial": [{"param_id": 9001, "normalized": 0.0}],
        "steps": [
            {"id": "open_painted_menu", "action": "click",
             "x": 160, "y": 50, "screenshot": True,
             "visual_oracle": {"x": 110, "y": 100,
                               "before_rgb": [30, 36, 48],
                               "after_rgb": [210, 136, 44]}},
            {"id": "select_painted_menu", "action": "click",
             "x": 160, "y": 105, "param_id": 9001,
             "before_normalized": 0.0, "expected_normalized": 1.0,
             "screenshot": True,
             "expected_pixel": {"x": 40, "y": 140,
                                "rgb": [12, 142, 85]}},
            {"id": "reopen_painted_menu", "action": "click",
             "x": 160, "y": 50, "screenshot": True,
             "visual_oracle": {"x": 110, "y": 100,
                               "before_rgb": [12, 142, 85],
                               "after_rgb": [210, 136, 44]}}
        ]
    }


def run(plugin, host, out, *, workflow=workflow_run, inventory=tree_run):
    plugin, host, out = Path(plugin).resolve(strict=True), Path(host).resolve(strict=True), Path(out)
    binary = [x for x in plugin.rglob("*.vst3") if x.is_file()]
    if plugin.suffix.lower() != ".vst3" or len(binary) != 1 or not host.is_file():
        raise ValueError("P64 requires one actual Windows VST3 DLL and real GUI host")
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "PAINTED-MENU-RESULT.json"
    report_path.unlink(missing_ok=True)
    module_sha, host_sha = digest(binary[0]), digest(host)
    report = {
        "schema": SCHEMA, "status": "FAIL", "faults": [],
        "module_sha256": module_sha, "gui_host_sha256": host_sha,
        "detected_visual_popup_bounds": None, "observed_changed_pixels": 0,
        "verified_clicks": 0, "verified_visual_open_actions": 0,
        "native_child_controls": "NOT VERIFIED",
        "painted_menu_identity": "FIXTURE_ORACLE_ONLY",
        "arbitrary_commercial_painted_menus": "NOT COVERED",
        "product_gui_complete": "NOT COVERED",
        "commercial_daw_session": "NOT COVERED",
        "release_approved": False
    }
    try:
        observed = inventory(plugin, host, out / "hwnd-tree")
        if (observed.get("status") != "OBSERVATIONS_COMPLETE"
                or observed.get("verified_module_sha256") != module_sha
                or observed.get("verified_gui_host_sha256") != host_sha
                or observed.get("native_hwnd_count") != 1
                or len(observed.get("nodes", [])) != 1):
            raise ValueError("P64 expected actual custom-painted single HWND editor")
        report["native_child_controls"] = "ZERO_NATIVE_CHILD_HWND"
        if module_sha != digest(binary[0]) or host_sha != digest(host):
            raise ValueError("P64 actual binary changed after HWND inventory")
        manifest = fixture_manifest(binary[0], host)
        raw = workflow(manifest, out / "gui-workflow")
        if (raw.get("status") != "TECHNICAL_PASS"
                or raw.get("verified_actions") != 3
                or raw.get("verified_visual_only_actions") != 2
                or raw.get("controller_action_chain") != "PASS"
                or raw.get("verified_module_sha256") != module_sha
                or raw.get("gui_host_sha256") != host_sha):
            raise ValueError("P64 native visual popup action chain failed")
        shots = out / "gui-workflow" / "snapshots"
        bounds, count = changed_bbox(shots / "0.before.bmp", shots / "0.bmp")
        if bounds != [90, 82, 230, 135] or count < 7000:
            raise ValueError("P64 native popup differs from approved visual bounds")
        if changed_bbox(shots / "2.before.bmp", shots / "2.bmp")[0] != bounds:
            raise ValueError("P64 reopening painted popup changed unexpected region")
        if module_sha != digest(binary[0]) or host_sha != digest(host):
            raise ValueError("P64 plugin or host changed during real GUI workflow")
        report["detected_visual_popup_bounds"] = bounds
        report["observed_changed_pixels"] = count
        report["verified_clicks"] = 3
        report["verified_visual_open_actions"] = 2
        report["status"] = "CONTRACT_PASS"
    except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
        report["faults"].append(str(error))
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--gui-host", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.plugin, args.gui_host, args.out)
    except (OSError, ValueError, TypeError) as error:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": SCHEMA, "status": "FAIL",
                  "faults": [str(error)], "release_approved": False}
        (args.out / "PAINTED-MENU-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "CONTRACT_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
