#!/usr/bin/env python3
"""P41: Bounded, opt-in real Win32 VST3 GUI control *exploration*.

Not a GUI release gate: a screenshot change is not proof of the effect's
semantics. Each probe starts in a fresh process and a fresh VST3 instance,
avoiding cross-click state contamination. All results are observations only.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys


NATIVE = "125A-GUI-EXPLORE-v1"
SCHEMA = "125a-gui-exploration-result-v1"
MAX_PIXELS = 4_194_304
MAX_POINTS = 16
COORD = re.compile(r"^[0-9]{1,4},[0-9]{1,4}$")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def positive_int(value, maximum):
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError("native exploration integer is invalid")
    number = int(value)
    if number > maximum:
        raise ValueError("native exploration integer exceeds permitted range")
    return number


def normalized(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError("native GUI observation has invalid parameter value")
    return number


def read_bmp(path):
    raw = Path(path).read_bytes()
    if len(raw) < 54 or raw[:2] != b"BM":
        raise ValueError("native Win32 GUI capture is not a BMP")
    size = struct.unpack_from("<I", raw, 2)[0]
    offset = struct.unpack_from("<I", raw, 10)[0]
    dib, width, signed_height, planes, bitcount, compression = (
        struct.unpack_from("<IiiHHI", raw, 14))
    if dib != 40 or not 0 < width <= 4096 or not -4096 <= signed_height < 0:
        raise ValueError("native snapshot has unsupported dimensions/orientation")
    height = -signed_height
    if width * height > MAX_PIXELS:
        raise ValueError("GUI snapshot is too large for bounded exploration")
    if planes != 1 or bitcount != 32 or compression != 0 or offset != 54:
        raise ValueError("GUI snapshot has unsupported pixel format")
    expected = width * height * 4 + offset
    if size != len(raw) or expected != len(raw):
        raise ValueError("truncated or extended native HWND screenshot")
    # Ignore alpha bytes: Win32 BitBlt does not promise meaningful alpha.
    pixels = raw[offset:]
    rgb = bytearray(width * height * 3)
    j = 0
    for i in range(0, len(pixels), 4):
        rgb[j:j + 3] = pixels[i:i + 3]
        j += 3
    return width, height, bytes(rgb)


def changed_pixels(a, b):
    if a[:2] != b[:2]:
        raise ValueError("native GUI screenshot geometry changed unexpectedly")
    return sum(a[2][i:i + 3] != b[2][i:i + 3]
               for i in range(0, len(a[2]), 3))


def native_evidence(path, x, y, width, height):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if len(lines) < 5 or lines[0] != "format\t" + NATIVE or (
            lines[1] != "coordinate\t%d\t%d" % (x, y)) or (
            lines[2] != "canvas\t%d\t%d" % (width, height)) or (
            lines[-1] != "end\tCOMPLETE"):
        raise ValueError("missing/stale/misattributed VST3 click observations")
    fields = lines[3].split("\t")
    if len(fields) != 2 or fields[0] != "param_count":
        raise ValueError("no declared native controller observation count")
    count = positive_int(fields[1], 8192)
    if len(lines) != count + 5:
        raise ValueError("missing or extra GUI parameter observations")
    ids = set()
    changed = []
    for index, line in enumerate(lines[4:-1]):
        parts = line.split("\t")
        if len(parts) != 5 or parts[0] != "param" or (
                positive_int(parts[1], 8192) != index):
            raise ValueError("bad native GUI parameter observation order")
        identifier = positive_int(parts[2], 4294967295)
        if identifier in ids:
            raise ValueError("duplicate native GUI parameter identifier")
        ids.add(identifier)
        before, after = normalized(parts[3]), normalized(parts[4])
        if abs(before - after) > 1e-5:
            changed.append({"param_id": identifier,
                            "before_normalized": before,
                            "after_normalized": after})
    return count, changed


def grid_points(width, height, count):
    # Deterministic 3x3 and optionally 4x4 positions. Never click window
    # borders; each point is in the actual GUI child client coordinates.
    columns = 3 if count <= 9 else 4
    rows = 3 if count <= 9 else 4
    return [(int(width * (col + .5) / columns),
             int(height * (row + .5) / rows))
            for row in range(rows) for col in range(columns)][:count]


def parse_points(raw, width, height):
    pieces = raw.split(";")
    if not 1 <= len(pieces) <= MAX_POINTS:
        raise ValueError("GUI discovery requires 1-16 bounded points")
    result = []
    for text in pieces:
        if not COORD.fullmatch(text):
            raise ValueError("invalid GUI exploratory click coordinate")
        x, y = map(int, text.split(","))
        if not 0 <= x < width or not 0 <= y < height or (x, y) in result:
            raise ValueError("out-of-editor or repeated GUI exploration click")
        result.append((x, y))
    return result


def run(bundle, gui_host, out, *, points=None, max_points=9,
        acknowledge=False, timeout=25, runner=subprocess.run):
    if acknowledge is not True:
        raise ValueError("GUI exploration requires explicit opt-in: clicks may activate plugin actions")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("invalid bounded GUI click timeout")
    if type(max_points) is not int or not 1 <= max_points <= MAX_POINTS:
        raise ValueError("GUI exploration supports 1-16 actual click probes")
    bundle = Path(bundle).resolve(strict=True)
    host = Path(gui_host).resolve(strict=True)
    if not bundle.is_dir() or bundle.suffix.lower() != ".vst3" or not host.is_file():
        raise ValueError("invalid native GUI exploration plugin or host")
    modules = [p.resolve() for p in bundle.rglob("*.vst3") if p.is_file()]
    if len(modules) != 1:
        raise ValueError("GUI exploration requires exactly one actual VST3 module")
    binary = modules[0]
    module_hash, host_hash = digest(binary), digest(host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_file = out / "GUI-EXPLORATION-RESULT.json"
    report_file.unlink(missing_ok=True)
    overview = out / "untouched-editor.bmp"
    overview.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_hash,
        "verified_gui_host_sha256": host_hash,
        "requested_points": 0, "completed_points": 0,
        "candidates": [], "probes": [],
        "gui_control_discovery": "NOT COVERED",
        "product_gui_controls": "NOT COVERED",
        "musical_or_audio_correctness": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
        "release_approved": False, "faults": [],
    }
    try:
        # Obtain actual HWND dimensions; no invented product layout.
        first = runner([str(host), "--snapshot-editor", str(bundle), str(overview)],
                       capture_output=True, text=True, check=False,
                       errors="replace", timeout=timeout)
        if first.returncode != 0 or not overview.is_file():
            raise ValueError("native plugin editor cannot be opened or captured")
        width, height, _ = read_bmp(overview)
        coordinates = (parse_points(points, width, height)
                       if points is not None else
                       grid_points(width, height, max_points))
        result["requested_points"] = len(coordinates)
        result["editor_dimensions"] = [width, height]
        for index, (x, y) in enumerate(coordinates):
            if module_hash != digest(binary) or host_hash != digest(host):
                raise ValueError("VST3 module or GUI host changed during exploration")
            run_dir = out / ("probe-%02d" % index)
            run_dir.mkdir(parents=True, exist_ok=True)
            report = run_dir / "native.tsv"
            first_bmp = run_dir / "before-a.bmp"
            second_bmp = run_dir / "before-b.bmp"
            after_bmp = run_dir / "after.bmp"
            for p in (report, first_bmp, second_bmp, after_bmp):
                p.unlink(missing_ok=True)
            proc = runner([str(host), "--explore-gui-click", str(bundle),
                           str(x), str(y), str(report), str(first_bmp),
                           str(second_bmp), str(after_bmp)],
                          capture_output=True, text=True, check=False,
                          errors="replace", timeout=timeout)
            (run_dir / "native.log").write_text(
                (proc.stdout or "") + "\n" + (proc.stderr or ""),
                encoding="utf-8")
            if proc.returncode != 0:
                raise ValueError("real Win32 GUI probe failed at %d,%d (exit %d)" %
                                 (x, y, proc.returncode))
            if any(not p.is_file() for p in (
                    report, first_bmp, second_bmp, after_bmp)):
                raise ValueError("missing real native controller/pixel observations")
            pre_a, pre_b, after = [read_bmp(p) for p in (
                first_bmp, second_bmp, after_bmp)]
            if any(p[:2] != (width, height) for p in (pre_a, pre_b, after)):
                raise ValueError("real HWND pixel geometry differs from initial plugin")
            drift = changed_pixels(pre_a, pre_b)
            changed = changed_pixels(pre_b, after)
            total, parameters = native_evidence(report, x, y, width, height)
            stable_visual_change = changed > 0 and drift == 0
            if parameters and stable_visual_change:
                classification = "PARAMETER_AND_VISUAL_CHANGE"
            elif parameters:
                classification = "PARAMETER_CHANGE"
            elif drift:
                classification = "UNSTABLE_BASELINE"
            elif stable_visual_change:
                classification = "VISUAL_CHANGE"
            else:
                classification = "NO_OBSERVED_CHANGE"
            observed = {
                "x": x, "y": y, "classification": classification,
                "parameters_inspected": total,
                "changed_parameters": parameters,
                "painted_pixels_changed": changed,
                "painted_baseline_drift": drift,
                "painted_visual_observation": (
                    "UNSTABLE" if drift else
                    "OBSERVED" if changed else "NO_OBSERVED_CHANGE"),
            }
            result["probes"].append(observed)
            if parameters or stable_visual_change:
                result["candidates"].append({
                    "x": x, "y": y, "observation": classification,
                    "parameter_ids_changed": [p["param_id"] for p in parameters],
                })
            result["completed_points"] = index + 1
        if module_hash != digest(binary) or host_hash != digest(host):
            raise ValueError("plugin or host modified during GUI scan")
        result["status"] = "OBSERVATIONS_COMPLETE"
        result["gui_control_discovery"] = "OBSERVATIONS_ONLY"
    except (OSError, ValueError, UnicodeError, OverflowError,
            struct.error, subprocess.TimeoutExpired) as error:
        result["faults"].append(str(error))
    report_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True, type=Path)
    parser.add_argument("--gui-host", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--points", default=None,
                        help="Optional semicolon-separated x,y coordinates")
    parser.add_argument("--max-points", type=int, default=9)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--acknowledge-ui-clicks", action="store_true",
                        help="Required: can activate arbitrary plugin UI actions")
    args = parser.parse_args()
    try:
        report = run(args.plugin, args.gui_host, args.out, points=args.points,
                     max_points=args.max_points,
                     acknowledge=args.acknowledge_ui_clicks,
                     timeout=args.timeout)
    except (OSError, ValueError, TypeError) as error:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": SCHEMA, "status": "FAIL", "faults": [str(error)],
                  "gui_control_discovery": "NOT COVERED",
                  "product_gui_controls": "NOT COVERED", "release_approved": False}
        (args.out / "GUI-EXPLORATION-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("[%s] real VST3 GUI exploration; candidates are NOT product certification" %
          report["status"])
    return 0 if report["status"] == "OBSERVATIONS_COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
