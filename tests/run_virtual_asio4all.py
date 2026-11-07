#!/usr/bin/env python3
"""P94: real registered ASIO4ALL + active VB-CABLE WDM endpoints, no physical claims.

This is a real driver callback test only on opted-in, driver-equipped Windows.
It installs no drivers, modifies no Windows audio settings, uses no simulator,
and never promotes virtual evidence to physical hardware or DAW acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys

from run_physical_asio import check_evidence, digest, validate as validate_native_plan
from generate_physical_asio_plan import registry_clsid

SCHEMA = "125a-virtual-asio4all-plan-v1"
RESULT_SCHEMA = "125a-virtual-asio4all-result-v1"
ASIO_NAME = re.compile(r"^ASIO4ALL[^\\/\x00-\x1f]{0,120}$", re.I)
MAX_CAPTURE = 1024 * 1024


def validate(plan):
    if (not isinstance(plan, dict) or set(plan) !=
            {"schema", "product", "executor", "asio_driver", "scenarios"}
            or plan["schema"] != SCHEMA):
        raise ValueError("P94 exact virtual-only ASIO4ALL plan required")
    driver = plan["asio_driver"]
    if (not isinstance(driver, dict) or
            not ASIO_NAME.fullmatch(str(driver.get("name", "")))):
        raise ValueError("P94 requires a registered ASIO4ALL driver, not arbitrary ASIO")
    native_plan = dict(plan)
    native_plan["schema"] = "125a-physical-asio-plan-v1"
    return validate_native_plan(native_plan)


def generate(plugin, executor, asio_name, *, rate=44100, frames=128,
             callbacks=12000, registry_reader=registry_clsid,
             platform=sys.platform):
    if platform != "win32":
        raise ValueError("P94 virtual ASIO4ALL requires real Windows drivers")
    if not isinstance(asio_name, str) or not ASIO_NAME.fullmatch(asio_name):
        raise ValueError("P94 virtual driver must be named ASIO4ALL")
    clsid = registry_reader(asio_name)
    plan = {
        "schema": SCHEMA,
        "product": {"path": str(Path(plugin).resolve(strict=True)),
                    "sha256": digest(plugin)},
        "executor": {"path": str(Path(executor).resolve(strict=True)),
                     "sha256": digest(executor)},
        "asio_driver": {"name": asio_name, "clsid": clsid},
        "scenarios": [{"sample_rate": rate,
                       "buffer_frames": frames, "callbacks": callbacks}]
    }
    validate(plan)
    return plan


def detect_live_wdm_endpoints(*, probe_runner=subprocess.run, platform=sys.platform):
    """Get actual Windows PnP audio endpoints, not user-authored evidence."""
    if platform != "win32":
        raise ValueError("P94 Windows WDM endpoint detection unavailable")
    script = (
        "$ErrorActionPreference='Stop'; "
        "$a=@(Get-PnpDevice -Class AudioEndpoint -ErrorAction Stop | "
        "Where-Object { $_.Status -eq 'OK' } | "
        "Select-Object -ExpandProperty FriendlyName); "
        "ConvertTo-Json -Compress -InputObject $a"
    )
    result = probe_runner(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=20, check=False)
    if result.returncode != 0 or not isinstance(result.stdout, str) or (
            len(result.stdout.encode("utf-8")) > MAX_CAPTURE):
        raise ValueError("P94 cannot obtain active Windows WDM audio endpoints")
    names = json.loads(result.stdout)
    if not isinstance(names, list) or len(names) > 128 or any(
            not isinstance(x, str) or len(x) > 256 for x in names):
        raise ValueError("P94 malformed live Windows audio endpoint inventory")
    # VB-CABLE naming follows CABLE Input (playback) / CABLE Output (recording).
    # Both sides must exist and be in Windows' enabled PnP audio endpoint class.
    matches = {
        "playback": sorted(x for x in names if re.search(
            r"\bCABLE Input\b", x, re.I) and re.search(
            r"VB-Audio|VB-CABLE|Virtual Cable", x, re.I)),
        "recording": sorted(x for x in names if re.search(
            r"\bCABLE Output\b", x, re.I) and re.search(
            r"VB-Audio|VB-CABLE|Virtual Cable", x, re.I))
    }
    if not matches["playback"] or not matches["recording"]:
        raise ValueError("P94 no enabled VB-CABLE playback/recording endpoint pair")
    return matches


def run(plan, output, *, opt_in=False, platform=sys.platform,
        endpoint_reader=detect_live_wdm_endpoints,
        registry_reader=registry_clsid, process_runner=subprocess.run,
        timeout=120):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": RESULT_SCHEMA, "status": "NOT_RUN",
        "virtual_asio_driver": "NOT_RUN",
        "virtual_wdm_endpoints": "NOT_VERIFIED",
        "actual_asio_callbacks": 0,
        "physical_asio_hardware": "NOT_TESTED",
        "commercial_daw_session": "NOT_TESTED",
        "physical_hardware_verified": False,
        "daw_session_verified": False,
        "release_approved": False,
        "scenarios": [], "faults": []
    }
    attempted = False
    try:
        if platform != "win32":
            raise ValueError("P94 requires installed Windows ASIO/WDM drivers")
        if opt_in is not True:
            raise ValueError("P94 explicit isolated virtual audio test opt-in required")
        if type(timeout) is not int or not 10 <= timeout <= 300:
            raise ValueError("P94 invalid bounded real driver timeout")
        plugin, executor = validate(plan)
        driver = plan["asio_driver"]
        registered = registry_reader(driver["name"])
        if str(registered).casefold() != driver["clsid"].casefold():
            raise ValueError("P94 registered local ASIO4ALL CLSID differs from plan")
        endpoints = endpoint_reader()
        if (not isinstance(endpoints, dict) or set(endpoints) !=
                {"playback", "recording"} or
                any(not isinstance(endpoints[k], list) or not endpoints[k]
                    for k in ("playback", "recording"))):
            raise ValueError("P94 live VB-CABLE endpoint inventory missing")
        report["virtual_wdm_endpoints"] = "VB_CABLE_PAIR_ACTIVE"
        report["virtual_asio_driver"] = "ASIO4ALL_REGISTERED"
        report["verified_module_sha256"] = digest(plugin)
        report["verified_executor_sha256"] = digest(executor)
        report["asio_driver_name"] = driver["name"]
        report["asio_driver_clsid"] = driver["clsid"]
        for index, scenario in enumerate(plan["scenarios"], 1):
            case = out / ("scenario-%02d" % index)
            case.mkdir(exist_ok=True)
            evidence = case / "virtual-asio-callbacks.json"
            evidence.unlink(missing_ok=True)
            nonce = secrets.token_hex(24)
            if (digest(plugin) != report["verified_module_sha256"] or
                    digest(executor) != report["verified_executor_sha256"]):
                raise ValueError("P94 native executables changed between driver callbacks")
            command = [
                str(executor), "--physical-asio-probe",
                "--plugin", str(plugin),
                "--driver-clsid", driver["clsid"],
                "--driver-name", driver["name"],
                "--rate", str(scenario["sample_rate"]),
                "--frames", str(scenario["buffer_frames"]),
                "--callbacks", str(scenario["callbacks"]),
                "--nonce", nonce, "--out", str(evidence)]
            # Legacy native command name describes the existing ABI, not
            # evidence classification. P94's result is always VIRTUAL.
            attempted = True
            proc = process_runner(command, check=False, capture_output=True,
                                  text=True, timeout=timeout)
            (case / "driver.log").write_text(
                str(proc.stdout or "")[:32768] + "\n" +
                str(proc.stderr or "")[:32768], encoding="utf-8")
            if proc.returncode != 0 or not evidence.is_file():
                raise ValueError("P94 ASIO4ALL native callback host failed or has no evidence")
            if evidence.stat().st_size > MAX_CAPTURE:
                raise ValueError("P94 oversized native driver evidence")
            actual = json.loads(evidence.read_text(encoding="utf-8"))
            check_evidence(actual, nonce=nonce,
                           product_sha=report["verified_module_sha256"],
                           executor_sha=report["verified_executor_sha256"],
                           driver=driver, scenario=scenario)
            if (digest(plugin) != report["verified_module_sha256"] or
                    digest(executor) != report["verified_executor_sha256"]):
                raise ValueError("P94 executable changed during ASIO4ALL callback run")
            report["actual_asio_callbacks"] += actual["completed_callbacks"]
            report["scenarios"].append({
                "sample_rate": scenario["sample_rate"],
                "buffer_frames": scenario["buffer_frames"],
                "completed_callbacks": actual["completed_callbacks"],
                "deadline_misses": actual["deadline_misses"],
                "xruns": actual["xruns"],
                "status": "VIRTUAL_DRIVER_CALLBACKS_VERIFIED"})
        report["status"] = "VIRTUAL_ASIO_CALLBACK_PASS"
        report["virtual_asio_driver"] = "REAL_ASIO4ALL_CALLBACKS"
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        report["faults"].append(str(error))
        if attempted:
            report["status"] = "FAIL"
            report["virtual_asio_driver"] = "FAIL"
    (out / "VIRTUAL-ASIO4ALL-RESULT.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    plan = sub.add_parser("plan", help="Prepare actual registered driver plan")
    plan.add_argument("--plugin", type=Path, required=True)
    plan.add_argument("--executor", type=Path, required=True)
    plan.add_argument("--driver-name", default="ASIO4ALL v2")
    plan.add_argument("--rate", type=int, default=44100)
    plan.add_argument("--frames", type=int, default=128)
    plan.add_argument("--callbacks", type=int, default=12000)
    plan.add_argument("--out", type=Path, required=True)
    scan = sub.add_parser("run", help="Execute actual virtual ASIO4ALL callbacks")
    scan.add_argument("--plan", type=Path, required=True)
    scan.add_argument("--out", type=Path, required=True)
    scan.add_argument("--timeout", type=int, default=120)
    scan.add_argument("--acknowledge-virtual-drivers", action="store_true")
    args = p.parse_args()
    try:
        if args.action == "plan":
            prepared = generate(
                args.plugin, args.executor, args.driver_name,
                rate=args.rate, frames=args.frames, callbacks=args.callbacks)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(prepared, indent=2) + "\n",
                                encoding="utf-8")
            print("[PASS] Real ASIO4ALL registry plan created; virtual audio NOT RUN")
            return 0
        result = run(json.loads(args.plan.read_text(encoding="utf-8")),
                     args.out, opt_in=args.acknowledge_virtual_drivers,
                     timeout=args.timeout)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "VIRTUAL_ASIO_CALLBACK_PASS" else 1
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as err:
        print("[FAIL] P94: " + str(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
