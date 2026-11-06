#!/usr/bin/env python3
"""Real Win32 VST3 control probes with external click positions and parameter oracles.

Only declared controls are verified. Never claims an entire product UI is covered.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from verify_p33_artifacts import rgb_at

IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
HASH = re.compile(r"^[0-9a-f]{64}$")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(manifest):
    if manifest.get("schema") != "125a-gui-controls-v1":
        raise ValueError("invalid GUI manifest schema")
    plugin = manifest.get("product")
    if not isinstance(plugin, dict) or not HASH.fullmatch(str(plugin.get("sha256", ""))):
        raise ValueError("exact VST3 module SHA-256 missing")
    host = Path(manifest["gui_host"]).resolve(strict=True)
    binary = Path(plugin["binary"]).resolve(strict=True)
    if not host.is_file() or not binary.is_file() or digest(binary) != plugin["sha256"]:
        raise ValueError("GUI host or exact binary identity invalid")
    bundle = next((p for p in binary.parents if p.is_dir() and p.suffix.lower() == ".vst3"), None)
    if bundle is None or binary.suffix.lower() != ".vst3":
        raise ValueError("GUI binary not inside VST3 bundle")
    controls = manifest.get("controls")
    if not isinstance(controls, list) or not 1 <= len(controls) <= 128:
        raise ValueError("no GUI controls declared")
    seen = set()
    for control in controls:
        if not isinstance(control, dict) or not IDENTIFIER.fullmatch(str(control.get("id", ""))):
            raise ValueError("invalid GUI control ID")
        if control["id"] in seen:
            raise ValueError("duplicate GUI control ID")
        seen.add(control["id"])
        if type(control.get("param_id")) is not int or not 0 <= control["param_id"] <= 4294967295:
            raise ValueError("invalid VST3 parameter ID")
        for axis in ("x", "y"):
            if type(control.get(axis)) is not int or not 0 <= control[axis] <= 8191:
                raise ValueError("invalid GUI coordinate")
        val = control.get("expected_normalized")
        initial = control.get("initial_normalized", 0.0)
        if (type(initial) not in (float, int) or not 0.0 <= initial <= 1.0 or
                type(val) not in (float, int) or not 0.0 <= val <= 1.0 or
                abs(initial - val) <= 1e-5):
            raise ValueError("initial and final GUI values must be distinct normalized numbers")
        pixel = control.get("expected_pixel")
        if pixel is not None:
            if not isinstance(pixel, dict) or set(pixel) != {"x", "y", "rgb"}:
                raise ValueError("invalid painted-pixel oracle")
            if any(type(pixel.get(k)) is not int or pixel[k] < 0 or pixel[k] > 4095
                   for k in ("x", "y")):
                raise ValueError("invalid painted-pixel location")
            rgb = pixel["rgb"]
            if not isinstance(rgb, list) or len(rgb) != 3 or any(
                    type(c) is not int or c < 0 or c > 255 for c in rgb):
                raise ValueError("invalid independently expected painted RGB")
    return host, bundle, binary, controls


def run(manifest, out, timeout=90, runner=subprocess.run):
    if not 5 <= timeout <= 300:
        raise ValueError("invalid process timeout")
    host, bundle, binary, controls = validate(manifest)
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema": "125a-gui-controls-result-v1",
              "status": "FAIL", "verified_module_sha256": digest(binary),
              "declared_controls": len(controls), "tested_controls": 0,
              "painted_pixel_oracles": sum("expected_pixel" in c for c in controls),
              "all_product_controls": "NOT COVERED",
              "product_audio_semantics": "NOT COVERED",
              "commercial_daw_integration": "NOT COVERED",
              "cases": []}
    for control in controls:
        screenshot = out / (control["id"] + ".bmp")
        screenshot.unlink(missing_ok=True)
        has_initial = "initial_normalized" in control
        cmd = [str(host), ("--prove-click-and-snapshot-from" if has_initial
                          else "--prove-click-and-snapshot")
               if "expected_pixel" in control else
               ("--prove-click-at-from" if has_initial else "--prove-click-at"),
               str(bundle), str(control["param_id"]), str(control["x"]),
               str(control["y"])]
        if has_initial:
            cmd.append(str(control["initial_normalized"]))
        cmd.append(str(control["expected_normalized"]))
        if "expected_pixel" in control:
            cmd.append(str(screenshot))
        log = out / (control["id"] + ".log")
        log.unlink(missing_ok=True)
        failures = []
        try:
            proc = runner(cmd, capture_output=True, text=True, errors="replace",
                          check=False, timeout=timeout)
            body = (proc.stdout or "") + "\n" + (proc.stderr or "")
            log.write_text(body, encoding="utf-8")
            if proc.returncode != 0:
                failures.append("real GUI host failed with code %s" % proc.returncode)
            expected_observation = "native click changed VST3 parameter %s" % control["param_id"]
            if body.count(expected_observation) != 2:
                failures.append("two native editor cycles not independently observed")
            if "two actual editor attach/message/input/detach cycles" not in body:
                failures.append("editor lifecycle proof missing")
            if "expected_pixel" in control:
                pixel = control["expected_pixel"]
                if not screenshot.is_file():
                    failures.append("real native GUI screenshot missing")
                else:
                    try:
                        observed = rgb_at(screenshot, pixel["x"], pixel["y"])
                        if observed != pixel["rgb"]:
                            failures.append("painted GUI RGB mismatch: expected %s got %s" % (
                                pixel["rgb"], observed))
                    except (OSError, ValueError, IndexError) as error:
                        failures.append("invalid real GUI screenshot: " + str(error))
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(str(error))
        report["tested_controls"] += 1
        report["cases"].append({"id": control["id"],
                                "status": "FAIL" if failures else "PASS",
                                "faults": failures})
    report["status"] = ("TECHNICAL_PASS" if all(
        case["status"] == "PASS" for case in report["cases"]) else "FAIL")
    (out / "GUI-CONTROL-RESULT.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    try:
        report = run(json.loads(args.manifest.read_text(encoding="utf-8")),
                     args.out, timeout=args.timeout)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        report = {"schema": "125a-gui-controls-result-v1",
                  "status": "FAIL", "error": str(error)}
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "GUI-CONTROL-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("[%s] real Windows VST3 GUI control matrix" % report["status"])
    return 0 if report["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
