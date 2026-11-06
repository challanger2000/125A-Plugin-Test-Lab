#!/usr/bin/env python3
"""P37: Ordered native Win32 GUI clicks/drags in a single VST3 editor instance.

Every action needs an independent parameter-before/after oracle. This is not
blind GUI discovery and does not claim all product buttons are covered.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from verify_p33_artifacts import rgb_at


HEX = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
SCHEMA = "125a-gui-workflow-v1"
NATIVE = "125A-GUI-WORKFLOW-v1"
RESULT = "125A-GUI-WORKFLOW-RESULT-v1"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def unsigned(value, maximum):
    if type(value) is not int or value < 0 or value > maximum:
        raise ValueError("invalid bounded GUI workflow integer")
    return value


def normalized(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("invalid normalized GUI workflow value")
    return value


def validate(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {
            "schema", "product", "gui_host", "initial", "steps"} or manifest["schema"] != SCHEMA:
        raise ValueError("invalid exact GUI workflow manifest")
    product = manifest["product"]
    if not isinstance(product, dict) or set(product) != {"binary", "sha256"}:
        raise ValueError("missing exact tested VST3 module identity")
    if not isinstance(product["sha256"], str) or not HEX.fullmatch(product["sha256"]):
        raise ValueError("invalid source module fingerprint")
    binary = Path(product["binary"]).resolve(strict=True)
    host = Path(manifest["gui_host"]).resolve(strict=True)
    if not binary.is_file() or not host.is_file() or digest(binary) != product["sha256"]:
        raise ValueError("GUI workflow tested binary or host missing/incorrect")
    bundle = next((p for p in binary.parents if p.is_dir() and p.suffix.lower() == ".vst3"), None)
    if bundle is None or binary.suffix.lower() != ".vst3":
        raise ValueError("workflow module is not inside a VST3 bundle")
    initial = manifest["initial"]
    steps = manifest["steps"]
    if not isinstance(initial, list) or not 0 <= len(initial) <= 64:
        raise ValueError("invalid GUI workflow initial count")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 64:
        raise ValueError("GUI workflow requires 1-64 explicit actions")
    seen = set()
    for item in initial:
        if not isinstance(item, dict) or set(item) != {"param_id", "normalized"}:
            raise ValueError("invalid initial VST3 parameter statement")
        p = unsigned(item["param_id"], 4294967295)
        normalized(item["normalized"])
        if p in seen:
            raise ValueError("duplicated VST3 workflow initial parameter")
        seen.add(p)
    ids = set()
    screenshots = 0
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("invalid GUI action")
        if not {"id", "action", "x", "y", "param_id", "before_normalized",
                "expected_normalized"} <= set(step):
            raise ValueError("missing action coordinate or independent oracle")
        if set(step) - {"id", "action", "x", "y", "end_x", "end_y", "param_id",
                        "before_normalized", "expected_normalized", "screenshot",
                        "expected_pixel"}:
            raise ValueError("unknown GUI workflow command")
        if not isinstance(step["id"], str) or not IDENTIFIER.fullmatch(step["id"]):
            raise ValueError("invalid GUI workflow action identifier")
        if step["id"] in ids:
            raise ValueError("repeated GUI workflow action identifier")
        ids.add(step["id"])
        if step["action"] not in ("click", "drag"):
            raise ValueError("unsupported native GUI workflow action")
        unsigned(step["x"], 8191)
        unsigned(step["y"], 8191)
        if step["action"] == "drag":
            if "end_x" not in step or "end_y" not in step:
                raise ValueError("drag gesture needs end coordinates")
            unsigned(step["end_x"], 8191)
            unsigned(step["end_y"], 8191)
        elif "end_x" in step or "end_y" in step:
            raise ValueError("click cannot silently specify drag coordinates")
        unsigned(step["param_id"], 4294967295)
        before = normalized(step["before_normalized"])
        expected = normalized(step["expected_normalized"])
        if abs(before - expected) <= 1e-5:
            raise ValueError("step has no observable controller transition")
        capture = step.get("screenshot", False)
        if type(capture) is not bool:
            raise ValueError("screenshot option must be a boolean")
        if "expected_pixel" in step:
            if not capture:
                raise ValueError("pixel reference requires a real screenshot")
            pixel = step["expected_pixel"]
            if not isinstance(pixel, dict) or set(pixel) != {"x", "y", "rgb"}:
                raise ValueError("invalid independent painted-pixel reference")
            unsigned(pixel["x"], 4095)
            unsigned(pixel["y"], 4095)
            rgb = pixel["rgb"]
            if not isinstance(rgb, list) or len(rgb) != 3:
                raise ValueError("missing independent RGB triplet")
            for value in rgb:
                unsigned(value, 255)
        if capture:
            screenshots += 1
    if screenshots > 16:
        raise ValueError("at most 16 saved editor snapshots in one workflow")
    return host, bundle, binary, initial, steps


def make_native_manifest(initial, steps):
    rows = ["format\t" + NATIVE, "init_count\t" + str(len(initial))]
    for item in initial:
        rows.append("init\t%d\t%.17g" % (item["param_id"], item["normalized"]))
    rows.append("step_count\t" + str(len(steps)))
    for index, item in enumerate(steps):
        x2 = item.get("end_x", item["x"])
        y2 = item.get("end_y", item["y"])
        rows.append("step\t%d\t%s\t%d\t%d\t%d\t%d\t%d\t%.17g\t%.17g\t%d" % (
            index, item["action"], item["x"], item["y"], x2, y2,
            item["param_id"], item["before_normalized"], item["expected_normalized"],
            int(item.get("screenshot", False))))
    return "\n".join(rows) + "\n"


def audit_native(path, steps):
    rows = Path(path).read_text(encoding="utf-8").splitlines()
    if len(rows) != len(steps) + 3 or rows[0] != "format\t" + RESULT or (
            rows[1] != "step_count\t" + str(len(steps))) or rows[-1] != "end\tPASS":
        raise ValueError("missing/stale/incomplete native workflow evidence")
    for index, (line, step) in enumerate(zip(rows[2:-1], steps)):
        parts = line.split("\t")
        if len(parts) != 6 or parts[0] != "step" or parts[1] != str(index) or (
                parts[2] != str(step["param_id"])):
            raise ValueError("native action step missing/attributed to another control")
        before, after = float(parts[3]), float(parts[4])
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in (before, after)):
            raise ValueError("invalid native observed controller value")
        good = abs(before - step["before_normalized"]) <= 1e-5 and (
            abs(after - step["expected_normalized"]) <= 1e-5)
        if (parts[5] == "PASS") != good or parts[5] != "PASS":
            raise ValueError("real GUI action did not satisfy its independent oracle")
    return True


def run(manifest, out, timeout=90, runner=subprocess.run):
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise ValueError("invalid GUI workflow host timeout")
    host, bundle, binary, initial, steps = validate(manifest)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    host_hash = digest(host)
    source_hash = digest(binary)
    native_input = out / "approved-actions.tsv"
    native_output = out / "native-workflow.tsv"
    report_path = out / "GUI-WORKFLOW-RESULT.json"
    log_path = out / "native-workflow.log"
    capture_dir = out / "snapshots"
    capture_dir.mkdir(exist_ok=True)
    report_path.unlink(missing_ok=True)
    native_output.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)
    for index in range(len(steps)):
        (capture_dir / (str(index) + ".bmp")).unlink(missing_ok=True)
    expected_native = make_native_manifest(initial, steps)
    native_input.write_text(expected_native, encoding="utf-8")
    approved_hash = digest(native_input)
    report = {
        "schema": "125a-gui-workflow-result-v1",
        "status": "FAIL", "verified_module_sha256": source_hash,
        "gui_host_sha256": host_hash,
        "declared_actions": len(steps), "verified_actions": 0,
        "controller_action_chain": "NOT COVERED",
        "product_gui_complete": "NOT COVERED",
        "product_audio_semantics": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
        "faults": []
    }
    command = [str(host), "--gui-workflow", str(bundle), str(native_input),
               str(native_output), str(capture_dir)]
    try:
        if digest(host) != host_hash or digest(binary) != source_hash:
            raise ValueError("GUI workflow host or tested VST3 changed before run")
        proc = runner(command, capture_output=True, text=True,
                      check=False, errors="replace", timeout=timeout)
        log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""),
                            encoding="utf-8")
        if digest(host) != host_hash or digest(binary) != source_hash or (
                digest(native_input) != approved_hash):
            raise ValueError("approved workflow input, tested VST3 or host changed during run")
        if proc.returncode != 0:
            raise ValueError("native GUI workflow exit code %d" % proc.returncode)
        if not native_output.is_file():
            raise ValueError("native GUI workflow produced no fresh action evidence")
        audit_native(native_output, steps)
        for index, item in enumerate(steps):
            if item.get("screenshot", False):
                image = capture_dir / (str(index) + ".bmp")
                if not image.is_file():
                    raise ValueError("requested native editor snapshot missing at step %d" % index)
                pixel = item.get("expected_pixel")
                if pixel is not None:
                    actual = rgb_at(image, pixel["x"], pixel["y"])
                    if actual != pixel["rgb"]:
                        raise ValueError("native painted UI mismatch at step %d" % index)
        report["status"] = "TECHNICAL_PASS"
        report["verified_actions"] = len(steps)
        report["controller_action_chain"] = "PASS"
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired) as error:
        report["faults"].append(str(error))
        report["controller_action_chain"] = "FAIL"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=90)
    args = p.parse_args()
    try:
        report = run(json.loads(args.manifest.read_text(encoding="utf-8")),
                     args.out, args.timeout)
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            json.JSONDecodeError) as error:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": "125a-gui-workflow-result-v1", "status": "FAIL",
                  "controller_action_chain": "NOT COVERED", "faults": [str(error)],
                  "product_gui_complete": "NOT COVERED"}
        (args.out / "GUI-WORKFLOW-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("[%s] real VST3 persistent Win32 GUI workflow" % report["status"])
    return 0 if report["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
