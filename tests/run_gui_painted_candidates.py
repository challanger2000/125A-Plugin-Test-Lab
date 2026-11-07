#!/usr/bin/env python3
"""P70: visual candidate suggestions for *custom-painted* Win32 VST3 editors.

Read-only by default: find bounded foreground color islands in actual native
HWND BMP. They are visual regions, not proven controls. Opt-in execution
delegates to P42's sham-controlled, fresh-instance click explorer and cannot
claim semantic correctness or release approval.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import subprocess

from run_gui_exploration import read_bmp, run as explore_run
from run_gui_hwnd_guided import digest

SCHEMA = "125a-painted-gui-visual-candidates-v1"
TILE = 8
MAX_POINTS = 16


def pixel(image, x, y):
    w, h, data = image
    if not 0 <= x < w or not 0 <= y < h:
        raise ValueError("P70 sampled pixel outside editor")
    offset = (y * w + x) * 3
    return tuple(data[offset:offset+3])


def candidate_islands(image, *, max_points=9, tile=TILE):
    if (type(max_points) is not int or not 1 <= max_points <= MAX_POINTS or
            type(tile) is not int or not 4 <= tile <= 32):
        raise ValueError("P70 bounded tile/candidate budget required")
    if (not isinstance(image, tuple) or len(image) != 3 or
            type(image[0]) is not int or type(image[1]) is not int or
            not 16 <= image[0] <= 4096 or not 16 <= image[1] <= 4096 or
            image[0]*image[1] > 4194304 or not isinstance(image[2], bytes)
            or len(image[2]) != image[0]*image[1]*3):
        raise ValueError("P70 invalid real native Win32 editor frame")
    width, height, _ = image
    corners = (pixel(image, 0, 0), pixel(image, width-1, 0),
               pixel(image, 0, height-1), pixel(image, width-1, height-1))
    # A common corner color avoids pretending that busy/background artwork
    # can be unambiguously segmented as UI controls.
    background = max(set(corners), key=lambda p: (corners.count(p), p))
    if corners.count(background) < 3:
        return [], "BACKGROUND_AMBIGUOUS"
    bins = {}
    for y in range(height):
        for x in range(width):
            bgr = pixel(image, x, y)
            if max(abs(a-b) for a, b in zip(bgr, background)) < 18:
                continue
            key = (x//tile, y//tile)
            entry = bins.get(key)
            if entry is None:
                bins[key] = [x, y, x+1, y+1, 1]
            else:
                entry[0] = min(entry[0], x)
                entry[1] = min(entry[1], y)
                entry[2] = max(entry[2], x+1)
                entry[3] = max(entry[3], y+1)
                entry[4] += 1
    pending = set(bins)
    islands = []
    while pending:
        seed = min(pending, key=lambda p: (p[1], p[0]))
        pending.remove(seed)
        queue = deque([seed])
        left, top, right, bottom = width, height, 0, 0
        pixels = 0
        while queue:
            tx, ty = queue.popleft()
            x0, y0, x1, y1, n = bins[tx, ty]
            left, top = min(left, x0), min(top, y0)
            right, bottom = max(right, x1), max(bottom, y1)
            pixels += n
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbour = (tx + dx, ty + dy)
                    if neighbour in pending:
                        pending.remove(neighbour)
                        queue.append(neighbour)
        area = (right-left)*(bottom-top)
        if pixels < 24 or area < 64 or area > (width*height)//3:
            continue
        cx, cy = (left+right)//2, (top+bottom)//2
        if pixel(image, cx, cy) == background:
            # A painted outline may have an empty center; use a real
            # foreground pixel inside the detected island instead.
            candidate = None
            for y in range(top, bottom):
                for x in range(left, right):
                    if max(abs(a-b) for a, b in zip(pixel(image, x, y), background)) >= 18:
                        candidate = (x, y)
                        break
                if candidate is not None:
                    break
            if candidate is None:
                continue
            cx, cy = candidate
        islands.append({
            "x": cx, "y": cy, "bbox_xyxy": [left, top, right, bottom],
            "foreground_pixels": pixels, "origin": "NATIVE_STATIC_PIXEL_ISLAND",
            "control_semantics": "UNKNOWN", "approved_to_click": False
        })
    islands.sort(key=lambda p: (-p["foreground_pixels"], p["y"], p["x"]))
    return islands[:max_points], ("FOREGROUND_CANDIDATES" if islands else "NO_VISUAL_CANDIDATES")


def run(plugin, gui_host, out, *, acknowledge=False, max_points=9,
        timeout=40, runner=subprocess.run, explore=explore_run):
    if type(acknowledge) is not bool:
        raise ValueError("P70 explicit boolean acknowledgement required")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("P70 invalid bounded timeout")
    plugin = Path(plugin).resolve(strict=True)
    gui_host = Path(gui_host).resolve(strict=True)
    if not plugin.is_dir() or plugin.suffix.lower() != ".vst3" or not gui_host.is_file():
        raise ValueError("P70 actual VST3 bundle and host required")
    modules = [p for p in plugin.rglob("*.vst3") if p.is_file()]
    if len(modules) != 1:
        raise ValueError("P70 ambiguous native VST3 module")
    binary = modules[0]
    a, b = digest(binary), digest(gui_host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    frame_path = out / "untouched-editor.bmp"
    result_path = out / "PAINTED-CANDIDATES.json"
    for f in (frame_path, result_path):
        f.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": a, "verified_gui_host_sha256": b,
        "visual_candidates": [], "segmentation": "NOT RUN",
        "exploration": "NOT RUN", "gui_control_semantics": "NOT COVERED",
        "all_product_controls": "NOT COVERED", "release_approved": False,
        "faults": []
    }
    try:
        response = runner([str(gui_host), "--snapshot-editor",
                           str(plugin), str(frame_path)],
                          capture_output=True, text=True, check=False,
                          errors="replace", timeout=timeout)
        if response.returncode != 0 or not frame_path.is_file():
            raise ValueError("P70 cannot capture real native editor bitmap")
        image = read_bmp(frame_path)
        regions, finding = candidate_islands(image, max_points=max_points)
        report["visual_candidates"] = regions
        report["segmentation"] = finding
        if digest(binary) != a or digest(gui_host) != b:
            raise ValueError("P70 VST3/host identity changed during observation")
        if acknowledge and regions:
            points = ";".join(f"{region['x']},{region['y']}" for region in regions)
            observed = explore(plugin, gui_host, out / "sham-controlled-probes",
                               points=points, max_points=len(regions),
                               acknowledge=True, timeout=timeout)
            if (not isinstance(observed, dict) or
                    observed.get("status") != "OBSERVATIONS_COMPLETE" or
                    observed.get("verified_module_sha256") != a or
                    observed.get("verified_gui_host_sha256") != b or
                    observed.get("requested_points") != len(regions) or
                    observed.get("completed_points") != len(regions) or
                    observed.get("sham_verified_points") != len(regions) or
                    observed.get("release_approved") is not False):
                raise ValueError("P70 native sham-controlled painted click incomplete")
            if digest(binary) != a or digest(gui_host) != b:
                raise ValueError("P70 binary changed during opt-in native probes")
            report["exploration"] = "OBSERVATIONS_COMPLETE"
        report["status"] = "CANDIDATES_COMPLETE"
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        report["faults"].append(str(error))
        if acknowledge:
            report["exploration"] = "FAIL"
    result_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--gui-host", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-points", type=int, default=9)
    p.add_argument("--timeout", type=int, default=40)
    p.add_argument("--acknowledge-ui-clicks", action="store_true")
    a = p.parse_args()
    try:
        report = run(a.plugin, a.gui_host, a.out,
                     acknowledge=a.acknowledge_ui_clicks,
                     max_points=a.max_points, timeout=a.timeout)
    except (OSError, ValueError, TypeError) as e:
        a.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": SCHEMA, "status": "FAIL", "faults": [str(e)],
                  "all_product_controls": "NOT COVERED", "release_approved": False}
        (a.out / "PAINTED-CANDIDATES.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "CANDIDATES_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
