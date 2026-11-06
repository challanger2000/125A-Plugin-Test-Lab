#!/usr/bin/env python3
"""P45 independent A->B->A observation of mapped native GUI candidates.

Never claims to understand what an undocumented button is meant to do.
Uses only P44 sham-verified observations and real same-instance Windows
VST3 clicks. Toggle-like stability is evidence, NOT a semantic oracle.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from run_gui_exploration import native_evidence, read_bmp, changed_pixels


SCHEMA = "125a-gui-roundtrip-observations-v1"
NATIVE = "125A-GUI-ROUNDTRIP-v1"


def sha256(file):
    h = hashlib.sha256()
    with Path(file).open("rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def normalized(s):
    number = float(s)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError("native GUI roundtrip contains nonfinite/out-of-range VST3 value")
    return number


def read_native(path, x, y, width, height):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if (len(lines) < 7 or
            lines[:4] != [
                "format\t" + NATIVE, "mode\troundtrip",
                f"coordinate\t{x}\t{y}", f"canvas\t{width}\t{height}"] or
            lines[-1] != "end\tCOMPLETE"):
        raise ValueError("native GUI roundtrip is missing or belongs to another click")
    depth = lines[4].split("\t")
    count = lines[5].split("\t")
    if (len(depth) != 2 or depth[0] != "target_depth" or
            not depth[1].isdigit() or int(depth[1]) > 16 or
            len(count) != 2 or count[0] != "param_count" or
            not count[1].isdigit() or int(count[1]) > 8192 or
            len(lines) != 7 + int(count[1])):
        raise ValueError("native GUI roundtrip metadata/count corrupted")
    ids = set()
    values = {}
    for index, line in enumerate(lines[6:-1]):
        parts = line.split("\t")
        if (len(parts) != 6 or parts[0] != "param" or
                parts[1] != str(index) or not parts[2].isdigit()):
            raise ValueError("native roundtrip parameter row omitted/reordered")
        identifier = int(parts[2])
        if identifier > 4294967295 or identifier in ids:
            raise ValueError("roundtrip duplicated or invalid VST3 parameter ID")
        ids.add(identifier)
        values[identifier] = tuple(normalized(v) for v in parts[3:])
    return int(depth[1]), values


def read_rgb(frame, x, y):
    width, height, buf = frame
    if x < 0 or y < 0 or x >= width or y >= height:
        raise ValueError("approved native sample outside actual editor")
    off = (y * width + x) * 3
    return [buf[off + 2], buf[off + 1], buf[off]]


def check_existing_scan(scan, draft, module_hash, host_hash):
    if (scan.get("status") != "OBSERVATIONS_COMPLETE" or
        scan.get("sham_control") != "COMPLETE" or
        scan.get("verified_module_sha256") != module_hash or
        scan.get("verified_gui_host_sha256") != host_hash or
        not isinstance(scan.get("probes"), list) or
        scan.get("requested_points") != len(scan["probes"]) or
        scan.get("completed_points") != len(scan["probes"]) or
        scan.get("sham_verified_points") != len(scan["probes"]) or
        scan.get("release_approved") is not False or
        scan.get("product_gui_controls") != "NOT COVERED"):
        raise ValueError("untrusted, stale or incomplete original VST3 GUI exploration")
    if (draft.get("schema") != "125a-gui-control-review-draft-v1" or
        draft.get("status") != "REVIEW_REQUIRED" or
        draft.get("verified_module_sha256") != module_hash or
        draft.get("verified_gui_host_sha256") != host_hash or
        draft.get("automatically_approved_oracles") != 0 or
        draft.get("executable_workflow_manifest") != "NOT GENERATED" or
        draft.get("release_approved") is not False or
        draft.get("product_gui_controls") != "NOT COVERED" or
        draft.get("candidate_count") != len(draft.get("candidates", [])) or
        draft.get("candidate_count") != len(scan.get("candidates", [])) or
        any(c.get("approved_for_execution") is not False or
            c.get("requires_independent_product_review") is not True
            for c in draft["candidates"])):
        raise ValueError("P44 candidate review draft missing or falsely approved")


def run(bundle, gui_host, exploration, out, *, acknowledge=False,
        timeout=30, runner=subprocess.run):
    if acknowledge is not True:
        raise ValueError("real GUI double-click exploration requires explicit user opt-in")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("invalid GUI roundtrip timeout")
    bundle = Path(bundle).resolve(strict=True)
    host = Path(gui_host).resolve(strict=True)
    if bundle.suffix.lower() != ".vst3" or not bundle.is_dir() or not host.is_file():
        raise ValueError("roundtrip needs actual Windows VST3 bundle and host")
    modules = list(bundle.rglob("*.vst3"))
    if len(modules) != 1 or not modules[0].is_file():
        raise ValueError("roundtrip needs one unambiguous native VST3 module")
    binary = modules[0].resolve()
    module_hash, host_hash = sha256(binary), sha256(host)
    exploration = Path(exploration)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "GUI-ROUNDTRIP-RESULT.json"
    report_path.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_hash,
        "verified_gui_host_sha256": host_hash,
        "tested_candidates": 0, "observed_reversible": 0,
        "observed_nonreversible": 0, "not_reproduced": 0,
        "cases": [], "faults": [],
        "product_gui_controls": "NOT COVERED",
        "audio_midi_export_correctness": "NOT COVERED",
        "independent_product_semantics": "NOT COVERED",
        "release_approved": False,
    }
    try:
        scan = json.loads(
            (exploration / "GUI-EXPLORATION-RESULT.json").read_text(encoding="utf-8"))
        draft = json.loads(
            (exploration / "GUI-CONTROL-REVIEW-DRAFT.json").read_text(encoding="utf-8"))
        check_existing_scan(scan, draft, module_hash, host_hash)
        width, height = scan["editor_dimensions"]
        if (type(width) is not int or type(height) is not int or
                width < 1 or height < 1 or width * height > 4194304):
            raise ValueError("roundtrip encountered impossible editor bounds")
        if len(draft["candidates"]) > 16:
            raise ValueError("GUI roundtrip exceeded maximum 16 candidate actions")
        overview = read_bmp(exploration / "untouched-editor.bmp")
        if overview[:2] != (width, height):
            raise ValueError("native editor initial screenshot dimensions invalid")
        for case_index, candidate in enumerate(draft["candidates"]):
            if module_hash != sha256(binary) or host_hash != sha256(host):
                raise ValueError("VST3/host changed during roundtrip exploration")
            source_index = candidate.get("probe_index")
            if (type(source_index) is not int or
                    not 0 <= source_index < len(scan["probes"])):
                raise ValueError("roundtrip candidate references a missing native probe")
            observed = scan["probes"][source_index]
            x, y = observed["x"], observed["y"]
            if (candidate.get("click") != [x, y] or
                    observed.get("sham_control_attribution") != "SUPPORTED" or
                    observed.get("classification") not in
                    ("VISUAL_CHANGE", "PARAMETER_CHANGE", "PARAMETER_AND_VISUAL_CHANGE") or
                    candidate.get("classification") != observed["classification"] or
                    not 0 <= x < width or not 0 <= y < height):
                raise ValueError("unverified or mismatched GUI candidate")
            source_dir = exploration / f"probe-{source_index:02d}"
            native = source_dir / "click.tsv"
            source_n, source_changes, source_values, source_depth = native_evidence(
                native, x, y, width, height, mode="click")
            if (source_depth != observed.get("native_child_depth") or
                    source_n != observed.get("parameters_inspected") or
                    source_changes != observed.get("changed_parameters")):
                raise ValueError("original GUI click evidence contradicts candidate")
            case_dir = out / f"candidate-{case_index:02d}"
            case_dir.mkdir(parents=True, exist_ok=True)
            raw = case_dir / "native.tsv"
            base_a = case_dir / "before-a.bmp"
            base_b = case_dir / "before-b.bmp"
            after_a = case_dir / "after-click1.bmp"
            after_b = case_dir / "after-click2.bmp"
            for path in (raw, base_a, base_b, after_a, after_b):
                path.unlink(missing_ok=True)
            command = [
                str(host), "--gui-observe-roundtrip", str(bundle),
                str(x), str(y), str(raw), str(base_a),
                str(base_b), str(after_a), str(after_b)]
            response = runner(command, capture_output=True, text=True,
                              check=False, timeout=timeout, errors="replace")
            (case_dir / "native.log").write_text(
                (response.stdout or "") + "\n" + (response.stderr or ""),
                encoding="utf-8")
            if response.returncode != 0:
                raise ValueError("native VST3 roundtrip host failed (%d)" %
                                 response.returncode)
            if any(not p.is_file() for p in (raw, base_a, base_b, after_a, after_b)):
                raise ValueError("native roundtrip missing controller or screenshot evidence")
            a, b, first, second = [
                read_bmp(p) for p in (base_a, base_b, after_a, after_b)]
            if any(p[:2] != (width, height) for p in (a, b, first, second)):
                raise ValueError("native GUI changed geometry during double click")
            depth, values = read_native(raw, x, y, width, height)
            if depth != source_depth or set(values) != set(source_values):
                raise ValueError("second native control hits an inconsistent VST3 target")
            stable_start = (changed_pixels(a, b) == 0 and
                            all(abs(values[pid][0] - vals[0]) <= 1e-5
                                for pid, vals in source_values.items()))
            first_controller = [
                pid for pid, val in values.items()
                if abs(val[1] - val[0]) > 1e-5]
            original_controller = [
                p["param_id"] for p in observed["changed_parameters"]]
            first_pixels = changed_pixels(b, first)
            original_visual = observed["classification"] in (
                "VISUAL_CHANGE", "PARAMETER_AND_VISUAL_CHANGE")
            first_reproduced = (
                stable_start and first_controller == original_controller and
                (first_pixels > 0 if original_visual else True) and
                (first_controller or first_pixels > 0))
            controller_restored = all(
                abs(before - after2) <= 1e-5
                for before, _, after2 in values.values())
            pixels_restored = changed_pixels(b, second) == 0
            reversibility = (
                "NOT_REPRODUCED" if not first_reproduced else
                "OBSERVED_REVERSIBLE" if controller_restored and pixels_restored else
                "OBSERVED_NONREVERSIBLE")
            result["cases"].append({
                "probe_index": source_index, "x": x, "y": y,
                "classification": reversibility,
                "controller_after_first_click": first_controller,
                "controller_restored_after_second_click": controller_restored,
                "painted_pixels_changed_after_first": first_pixels,
                "painted_pixels_remaining_after_second": changed_pixels(b, second),
                "before_baseline_stable": stable_start,
                "semantic_expectation": "NOT APPROVED",
                "independent_product_oracle": "NOT COVERED",
            })
            result["tested_candidates"] += 1
            if reversibility == "NOT_REPRODUCED":
                result["not_reproduced"] += 1
            elif reversibility == "OBSERVED_REVERSIBLE":
                result["observed_reversible"] += 1
            else:
                result["observed_nonreversible"] += 1
        if module_hash != sha256(binary) or host_hash != sha256(host):
            raise ValueError("VST3 binary changed during GUI roundtrip evidence")
        result["status"] = "OBSERVATIONS_COMPLETE"
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            UnicodeError, OverflowError, subprocess.TimeoutExpired) as error:
        result["status"] = "FAIL"
        result["faults"].append(str(error))
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--gui-host", type=Path, required=True)
    p.add_argument("--exploration", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--acknowledge-ui-clicks", action="store_true")
    a = p.parse_args()
    try:
        report = run(a.plugin, a.gui_host, a.exploration, a.out,
                     timeout=a.timeout, acknowledge=a.acknowledge_ui_clicks)
    except (OSError, ValueError, TypeError) as error:
        a.out.mkdir(parents=True, exist_ok=True)
        report = {
            "schema": SCHEMA, "status": "FAIL", "faults": [str(error)],
            "release_approved": False, "product_gui_controls": "NOT COVERED",
        }
        (a.out / "GUI-ROUNDTRIP-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("[%s] P45 genuine VST3 GUI A/B/A observations, not product certification" %
          report["status"])
    return 0 if report["status"] == "OBSERVATIONS_COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
