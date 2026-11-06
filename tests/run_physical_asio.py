#!/usr/bin/env python3
"""P56 fail-closed physical ASIO qualification adapter (Windows x64 only).

This runner NEVER synthesizes ASIO samples or certifies cloud Windows runners.
It only invokes an independently provided, pinned ASIO-capable native executor
on an opted-in physical workstation. An external executor is REQUIRED; the
ordinary Test Lab VST3 hosts do NOT operate a hardware ASIO driver.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys

SCHEMA = "125a-physical-asio-plan-v1"
EVIDENCE = "125a-physical-asio-native-evidence-v1"
RESULT = "125a-physical-asio-result-v1"
HEX = re.compile(r"^[a-f0-9]{64}$")
CLSID = re.compile(r"^\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}$")
ALLOWED_RATE = (44100, 48000, 96000)
ALLOWED_BLOCK = (64, 128, 256, 512, 1024)


def digest(file):
    h = hashlib.sha256()
    with Path(file).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate(plan):
    if not isinstance(plan, dict) or set(plan) != {
            "schema", "product", "executor", "asio_driver", "scenarios"} or plan["schema"] != SCHEMA:
        raise ValueError("exact physical ASIO plan fields required")
    product, executor, driver, scenarios = (
        plan["product"], plan["executor"], plan["asio_driver"], plan["scenarios"])
    for obj in (product, executor):
        if not isinstance(obj, dict) or set(obj) != {"path", "sha256"}:
            raise ValueError("exact pinned binary specification required")
        if not isinstance(obj["sha256"], str) or not HEX.fullmatch(obj["sha256"]):
            raise ValueError("invalid binary SHA-256")
    if not isinstance(driver, dict) or set(driver) != {"name", "clsid"}:
        raise ValueError("physical driver identity required")
    if (not isinstance(driver["name"], str) or not 1 <= len(driver["name"]) <= 128
            or any(c in driver["name"] for c in (chr(92), "/", chr(0), chr(10), chr(13)))
            or not isinstance(driver["clsid"], str) or not CLSID.fullmatch(driver["clsid"])):
        raise ValueError("invalid ASIO driver registry identity")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 12:
        raise ValueError("1..12 explicitly configured ASIO scenarios required")
    pairs = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {
                "sample_rate", "buffer_frames", "callbacks"}:
            raise ValueError("invalid ASIO scenario")
        rate, frames, count = (scenario["sample_rate"], scenario["buffer_frames"],
                               scenario["callbacks"])
        if type(rate) is not int or rate not in ALLOWED_RATE:
            raise ValueError("unsupported scenario sample rate")
        if type(frames) is not int or frames not in ALLOWED_BLOCK:
            raise ValueError("unsupported ASIO buffer frames")
        if type(count) is not int or not 100 <= count <= 200000:
            raise ValueError("invalid minimum callback count")
        if (rate, frames) in pairs:
            raise ValueError("duplicate ASIO scenario")
        pairs.add((rate, frames))
    plugin = Path(product["path"]).resolve(strict=True)
    native = Path(executor["path"]).resolve(strict=True)
    if plugin.suffix.lower() != ".vst3" or not plugin.is_file():
        raise ValueError("ASIO plan requires exact native .vst3 module DLL")
    if native.suffix.lower() != ".exe" or not native.is_file():
        raise ValueError("physical ASIO executor must be a native Windows EXE")
    if digest(plugin) != product["sha256"] or digest(native) != executor["sha256"]:
        raise ValueError("pinned ASIO plugin/executor hash mismatch")
    return plugin, native


def present_driver(name, clsid, registry_reader=None):
    """Read the genuine local HKLM ASIO registration, never mere file names."""
    if registry_reader is not None:
        return registry_reader(name, clsid)
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\ASIO\\" + name) as key:
        found, kind = winreg.QueryValueEx(key, "CLSID")
    return (kind == winreg.REG_SZ and isinstance(found, str)
            and found.casefold() == clsid.casefold())


def check_evidence(data, *, nonce, product_sha, executor_sha,
                   driver, scenario):
    if not isinstance(data, dict) or set(data) != {
            "schema", "nonce", "product_sha256", "executor_sha256",
            "asio_driver_name", "asio_driver_clsid", "sample_rate",
            "buffer_frames", "completed_callbacks", "asio_callbacks",
            "deadline_misses", "xruns", "process_failures", "error_code"}:
        raise ValueError("ASIO evidence has missing, extra or misleading fields")
    if (data["schema"] != EVIDENCE or data["nonce"] != nonce or
            data["product_sha256"] != product_sha or
            data["executor_sha256"] != executor_sha or
            data["asio_driver_name"] != driver["name"] or
            str(data["asio_driver_clsid"]).casefold() != driver["clsid"].casefold() or
            data["sample_rate"] != scenario["sample_rate"] or
            data["buffer_frames"] != scenario["buffer_frames"]):
        raise ValueError("stale, replayed or wrong-device ASIO evidence")
    for field in ("completed_callbacks", "asio_callbacks", "deadline_misses",
                  "xruns", "process_failures", "error_code"):
        if type(data[field]) is not int or data[field] < 0:
            raise ValueError("non-integer or negative ASIO metric")
    if (data["completed_callbacks"] < scenario["callbacks"]
            or data["asio_callbacks"] < scenario["callbacks"] or
            data["asio_callbacks"] != data["completed_callbacks"]
            or data["deadline_misses"] or data["xruns"] or
            data["process_failures"] or data["error_code"]):
        raise ValueError("ASIO callbacks missing or deadline/xrun/process error occurred")
    return True


def run(plan, out, *, acknowledge=False, timeout=120,
        runner=subprocess.run, registry_reader=None, platform=sys.platform):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_file = out / "PHYSICAL-ASIO-RESULT.json"
    report_file.unlink(missing_ok=True)
    report = {
        "schema": RESULT, "status": "NOT_RUN", "release_approved": False,
        "hardware_asio": "NOT_RUN", "commercial_daw_session": "NOT_RUN",
        "executor_integrity": "NOT_VERIFIED", "scenarios": [], "faults": []
    }
    attempted_hardware = False
    try:
        if platform != "win32":
            raise ValueError("physical ASIO proof is Windows-only")
        if acknowledge is not True:
            raise ValueError("physical ASIO test requires explicit user-controlled machine opt-in")
        if type(timeout) is not int or not 10 <= timeout <= 600:
            raise ValueError("invalid bounded ASIO runtime timeout")
        plugin, native = validate(plan)
        product_sha, native_sha = digest(plugin), digest(native)
        driver = plan["asio_driver"]
        if not present_driver(driver["name"], driver["clsid"], registry_reader):
            raise ValueError("selected physical ASIO driver is not registered on this Windows host")
        report["executor_integrity"] = "PINNED_SHA256"
        for index, scenario in enumerate(plan["scenarios"]):
            folder = out / ("scenario-%02d" % (index + 1))
            folder.mkdir(exist_ok=True)
            target = folder / "native-asio-evidence.json"
            target.unlink(missing_ok=True)
            nonce = secrets.token_hex(24)
            if digest(plugin) != product_sha or digest(native) != native_sha:
                raise ValueError("ASIO plugin/executor binary changed between scenarios")
            args = [
                str(native), "--physical-asio-probe",
                "--plugin", str(plugin),
                "--driver-clsid", driver["clsid"],
                "--driver-name", driver["name"],
                "--rate", str(scenario["sample_rate"]),
                "--frames", str(scenario["buffer_frames"]),
                "--callbacks", str(scenario["callbacks"]),
                "--nonce", nonce,
                "--out", str(target)]
            attempted_hardware = True
            result = runner(args, check=False, capture_output=True,
                            text=True, errors="replace", timeout=timeout)
            (folder / "native.log").write_text(
                (result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8")
            if result.returncode != 0 or not target.is_file():
                raise ValueError("actual physical ASIO executor failed or produced no evidence")
            if digest(plugin) != product_sha or digest(native) != native_sha:
                raise ValueError("physical ASIO binary changed during callback run")
            check_evidence(json.loads(target.read_text(encoding="utf-8")),
                           nonce=nonce, product_sha=product_sha, executor_sha=native_sha,
                           driver=driver, scenario=scenario)
            report["scenarios"].append({
                "sample_rate": scenario["sample_rate"],
                "buffer_frames": scenario["buffer_frames"],
                "required_callbacks": scenario["callbacks"],
                "status": "EVIDENCE_ACCEPTED",
                "native_evidence": str(target)})
        report["status"] = "EVIDENCE_ACCEPTED"
        report["hardware_asio"] = "EXTERNAL_EXECUTOR_EVIDENCE_ACCEPTED"
        report["verified_module_sha256"] = product_sha
        report["verified_executor_sha256"] = native_sha
    except (OSError, ValueError, KeyError, TypeError, UnicodeError,
            json.JSONDecodeError, subprocess.TimeoutExpired) as err:
        report["faults"].append(str(err))
        if attempted_hardware or report["scenarios"]:
            report["status"] = "FAIL"
            report["hardware_asio"] = "FAIL"
    report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--acknowledge-physical-asio", action="store_true")
    args = ap.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        report = run(plan, args.out, timeout=args.timeout,
                     acknowledge=args.acknowledge_physical_asio)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as err:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": RESULT, "status": "NOT_RUN",
                  "hardware_asio": "NOT_RUN", "release_approved": False,
                  "faults": [str(err)]}
        (args.out / "PHYSICAL-ASIO-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "EVIDENCE_ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
