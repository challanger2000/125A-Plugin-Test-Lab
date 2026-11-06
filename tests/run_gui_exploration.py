#!/usr/bin/env python3
"""P42: Sham-controlled, bounded Win32 VST3 GUI candidate exploration.

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

from gui_change_regions import create_review_draft, locate_change_regions


NATIVE = "125A-GUI-EXPLORE-v3"
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


def native_evidence(path, x, y, width, height, *, mode):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if mode not in ("click", "sham"):
        raise ValueError("unknown GUI exploration control mode")
    if len(lines) < 7 or lines[0] != "format\t" + NATIVE or (
            lines[1] != "mode\t" + mode) or (
            lines[2] != "coordinate\t%d\t%d" % (x, y)) or (
            lines[3] != "canvas\t%d\t%d" % (width, height)) or (
            lines[-1] != "end\tCOMPLETE"):
        raise ValueError("missing/stale/misattributed native GUI control evidence")
    hit = lines[4].split("\t")
    if len(hit) != 2 or hit[0] != "target_depth":
        raise ValueError("P43 native child hit depth not reported")
    depth = positive_int(hit[1], 16)
    fields = lines[5].split("\t")
    if len(fields) != 2 or fields[0] != "param_count":
        raise ValueError("no declared native GUI parameter observation count")
    count = positive_int(fields[1], 8192)
    if len(lines) != count + 7:
        raise ValueError("missing/extra native GUI parameter observations")
    ids = set()
    changed = []
    values = {}
    for index, line in enumerate(lines[6:-1]):
        parts = line.split("\t")
        if len(parts) != 5 or parts[0] != "param" or (
                positive_int(parts[1], 8192) != index):
            raise ValueError("bad native GUI parameter observation order")
        identifier = positive_int(parts[2], 4294967295)
        if identifier in ids:
            raise ValueError("duplicate native GUI parameter identifier")
        ids.add(identifier)
        before, after = normalized(parts[3]), normalized(parts[4])
        values[identifier] = (before, after)
        if abs(before - after) > 1e-5:
            changed.append({"param_id": identifier,
                            "before_normalized": before,
                            "after_normalized": after})
    return count, changed, values, depth


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
    review_file = out / "GUI-CONTROL-REVIEW-DRAFT.json"
    report_file.unlink(missing_ok=True)
    review_file.unlink(missing_ok=True)
    overview = out / "untouched-editor.bmp"
    overview.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_hash,
        "verified_gui_host_sha256": host_hash,
        "requested_points": 0, "completed_points": 0,
        "sham_verified_points": 0, "sham_control": "NOT COVERED",
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
            captures = {}
            for mode in ("sham", "click"):
                # Independent process/plugin instance per mode. A sham uses
                # exactly the same delays and repainting but sends NO mouse
                # event. It must not be treated as a successful button click.
                report = run_dir / (mode + ".tsv")
                first_bmp = run_dir / (mode + "-before-a.bmp")
                second_bmp = run_dir / (mode + "-before-b.bmp")
                after_bmp = run_dir / (mode + "-after.bmp")
                for path in (report, first_bmp, second_bmp, after_bmp):
                    path.unlink(missing_ok=True)
                proc = runner([
                    str(host), "--explore-gui-" + mode, str(bundle),
                    str(x), str(y), str(report), str(first_bmp),
                    str(second_bmp), str(after_bmp)
                ], capture_output=True, text=True, check=False,
                    errors="replace", timeout=timeout)
                (run_dir / (mode + ".log")).write_text(
                    (proc.stdout or "") + "\n" + (proc.stderr or ""),
                    encoding="utf-8")
                if proc.returncode != 0:
                    raise ValueError("real Win32 GUI %s failed at %d,%d (exit %d)" %
                                     (mode, x, y, proc.returncode))
                if any(not path.is_file() for path in
                       (report, first_bmp, second_bmp, after_bmp)):
                    raise ValueError("missing genuine %s controller/pixel evidence" % mode)
                a, b, after = [
                    read_bmp(path) for path in
                    (first_bmp, second_bmp, after_bmp)]
                if any(p[:2] != (width, height) for p in (a, b, after)):
                    raise ValueError("native %s editor dimensions changed" % mode)
                total, changed, values, depth = native_evidence(
                    report, x, y, width, height, mode=mode)
                captures[mode] = (a, b, after, total, changed, values, depth)
                if module_hash != digest(binary) or host_hash != digest(host):
                    raise ValueError("VST3 module or host changed during %s control" % mode)
            sham_a, sham_b, sham_after, sham_total, sham_changes, sham_values, sham_depth = (
                captures["sham"])
            click_a, click_b, click_after, total, parameters, click_values, click_depth = (
                captures["click"])
            if sham_depth != click_depth:
                raise ValueError("P43 sham and actual click routed to different child HWND depths")
            if total != sham_total or set(click_values) != set(sham_values):
                raise ValueError("native sham and click returned incompatible parameter inventories")
            matching_initial = all(
                abs(click_values[pid][0] - sham_values[pid][0]) <= 1e-5
                for pid in click_values)
            sham_drift = changed_pixels(sham_a, sham_b)
            click_drift = changed_pixels(click_a, click_b)
            sham_motion = changed_pixels(sham_b, sham_after)
            click_motion = changed_pixels(click_b, click_after)
            baseline_mismatch = changed_pixels(sham_b, click_b)
            differential = changed_pixels(sham_after, click_after)
            reliable_control = (matching_initial and not sham_changes and
                                not sham_drift and not click_drift and
                                not sham_motion and not baseline_mismatch)
            # If a changing background or spontaneous VST3 state is detected
            # in the sham, the click is NOT assigned an observed effect.
            visual = reliable_control and click_motion > 0 and differential > 0
            attributed_parameters = parameters if reliable_control else []
            # P44: physical BGR pixel changes are localized in tile-connected
            # regions ONLY after the paired sham proves attribution is stable.
            # Observed RGB samples remain unapproved until an independent
            # product specification confirms the expected control behavior.
            regions = (locate_change_regions(click_b, click_after)
                       if visual else None)
            if regions is not None and regions["painted_pixels_changed"] != click_motion:
                raise ValueError("P44 localized screenshot pixel count mismatches native comparison")
            if not reliable_control:
                classification = "UNSTABLE_CONTROL"
            elif attributed_parameters and visual:
                classification = "PARAMETER_AND_VISUAL_CHANGE"
            elif attributed_parameters:
                classification = "PARAMETER_CHANGE"
            elif visual:
                classification = "VISUAL_CHANGE"
            else:
                classification = "NO_OBSERVED_CHANGE"
            observed = {
                "x": x, "y": y, "classification": classification,
                "native_child_depth": click_depth,
                "routed_to_descendant_hwnd": click_depth > 0,
                "parameters_inspected": total,
                "changed_parameters": attributed_parameters,
                "unattributed_parameters_changed": (
                    parameters if not reliable_control else []),
                "painted_pixels_changed": click_motion,
                "painted_baseline_drift": click_drift,
                "sham_pixels_changed": sham_motion,
                "sham_baseline_drift": sham_drift,
                "cross_process_baseline_mismatch": baseline_mismatch,
                "click_minus_sham_pixels_changed": differential,
                "sham_parameter_changes": sham_changes,
                "sham_control_attribution": (
                    "SUPPORTED" if reliable_control else "UNSTABLE"),
                "painted_visual_observation": (
                    "UNSTABLE" if not reliable_control else
                    "OBSERVED" if visual else "NO_OBSERVED_CHANGE"),
                "pixel_localization": (
                    regions if regions is not None else {
                        "painted_pixels_changed": 0,
                        "observed_region_count": 0, "reported_region_count": 0,
                        "truncated": False, "regions": [],
                        "localization": (
                            "UNSTABLE_CONTROL" if not reliable_control else
                            "NO_VISUAL_CHANGE"),
                    }),
            }
            result["probes"].append(observed)
            if attributed_parameters or visual:
                result["candidates"].append({
                    "x": x, "y": y, "observation": classification,
                    "native_child_depth": click_depth,
                    "parameter_ids_changed": [
                        p["param_id"] for p in attributed_parameters],
                })
            result["sham_verified_points"] = index + 1
            result["completed_points"] = index + 1
        if module_hash != digest(binary) or host_hash != digest(host):
            raise ValueError("plugin or host modified during GUI scan")
        result["status"] = "OBSERVATIONS_COMPLETE"
        result["sham_control"] = "COMPLETE"
        result["gui_control_discovery"] = "OBSERVATIONS_ONLY"
        draft = create_review_draft(result)
        review_file.write_text(json.dumps(draft, indent=2) + "\n",
                               encoding="utf-8")
    except (OSError, ValueError, UnicodeError, OverflowError,
            struct.error, subprocess.TimeoutExpired) as error:
        result["sham_control"] = "FAIL"
        result["status"] = "FAIL"
        result["gui_control_discovery"] = "NOT COVERED"
        review_file.unlink(missing_ok=True)
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
