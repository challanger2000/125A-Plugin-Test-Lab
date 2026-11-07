#!/usr/bin/env python3
"""P95 actual isolated Windows virtual ASIO4ALL -> VB-CABLE -> ASIO4ALL loopback.

Needs a rebooted dedicated Windows machine with VB-CABLE WDM input and
output enabled in the ASIO4ALL panel. Never runs on generic cloud CI.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys

from run_virtual_asio4all import (
    detect_live_wdm_endpoints, validate, digest, registry_clsid)
from run_physical_asio import check_evidence
from verify_virtual_asio_loopback import verify_pcm

RESULT = "125a-virtual-asio-loopback-run-v1"


def run(plan, out, *, acknowledge=False, platform=sys.platform,
        registry_reader=registry_clsid,
        endpoint_reader=detect_live_wdm_endpoints,
        runner=subprocess.run, timeout=120):
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    report_path = folder / "P95-VIRTUAL-LOOPBACK-RUN.json"
    report = {"schema": RESULT, "status": "NOT_RUN",
              "loopback_pcm": "NOT_RUN", "asio4all_callbacks": "NOT_RUN",
              "physical_asio_hardware_verified": False,
              "commercial_daw_verified": False, "release_approved": False,
              "faults": []}
    attempted = False
    try:
        if platform != "win32" or acknowledge is not True:
            raise ValueError("P95 opt-in actual isolated Windows audio workstation required")
        if type(timeout) is not int or not 10 <= timeout <= 300:
            raise ValueError("P95 bounded native ASIO timeout required")
        exe, native = validate(plan)
        # validate() returns (plugin module, native .exe) in that order.
        if not native.name.lower().endswith(".exe") or "virtual_asio_loopback" not in native.name.lower():
            raise ValueError("P95 dedicated virtual ASIO loopback executable is required")
        driver = plan["asio_driver"]
        if str(registry_reader(driver["name"])).casefold() != driver["clsid"].casefold():
            raise ValueError("P95 actual ASIO4ALL registration not consistent with plan")
        endpoints = endpoint_reader()
        if (not isinstance(endpoints, dict) or set(endpoints) !=
                {"playback", "recording"} or any(
                not isinstance(endpoints[k], list) or not endpoints[k]
                for k in ("playback", "recording"))):
            raise ValueError("P95 no enabled real VB-CABLE WDM endpoint pair")
        if len(plan["scenarios"]) != 1:
            raise ValueError("P95 one exact virtual ASIO scenario required")
        s = plan["scenarios"][0]
        if not 200 <= s["callbacks"] <= 1000:
            raise ValueError("P95 bounded native PCM capture requires 200..1000 callbacks")
        nonce = secrets.token_hex(24)
        evidence = folder / "native-asio-callbacks.json"
        trace = folder / "native-loopback-pcm.f32"
        # Reject previous artifacts to prevent accidentally reusing stale
        # PCM recordings from a different session or driver configuration.
        if evidence.exists() or trace.exists():
            raise ValueError("P95 fresh isolated native callback/PCM paths required")
        product_sha, native_sha = digest(exe), digest(native)
        cmd = [
            str(native), "--virtual-asio-loopback",
            "--plugin", str(exe),
            "--driver-clsid", driver["clsid"],
            "--driver-name", driver["name"],
            "--rate", str(s["sample_rate"]), "--frames", str(s["buffer_frames"]),
            "--callbacks", str(s["callbacks"]), "--nonce", nonce,
            "--out", str(evidence), "--pcm", str(trace)
        ]
        attempted = True
        finished = runner(cmd, capture_output=True, text=True,
                          timeout=timeout, check=False)
        (folder / "native.log").write_text(
            (finished.stdout or "")[:16000] + "\n" +
            (finished.stderr or "")[:16000], encoding="utf-8")
        if finished.returncode != 0 or not evidence.is_file() or not trace.is_file():
            raise ValueError("P95 native real ASIO4ALL input/output capture failed")
        if digest(exe) != product_sha or digest(native) != native_sha:
            raise ValueError("P95 native test module changed during driver session")
        observed = json.loads(evidence.read_text(encoding="utf-8"))
        check_evidence(
            observed, nonce=nonce, product_sha=product_sha,
            executor_sha=native_sha, driver=driver, scenario=s)
        report["asio4all_callbacks"] = "ACTUAL_CALLBACK_EVIDENCE_ACCEPTED"
        pcm = verify_pcm(trace, evidence, folder / "independent")
        if pcm["status"] != "VIRTUAL_ASIO_PCM_LOOPBACK_PASS":
            raise ValueError("P95 independently captured PCM invalid: " +
                             ";".join(pcm["faults"]))
        report["status"] = "VIRTUAL_ASIO_LOOPBACK_PASS"
        report["loopback_pcm"] = pcm["status"]
        report["metrics"] = pcm["metrics"]
        report["verified_module_sha256"] = product_sha
        report["verified_executor_sha256"] = native_sha
        report["completed_asio_callbacks"] = observed["completed_callbacks"]
        report["captured_native_pcm_sha256"] = digest(trace)
    except (OSError, KeyError, ValueError, TypeError, UnicodeError,
            json.JSONDecodeError, subprocess.TimeoutExpired) as err:
        report["faults"].append(str(err))
        if attempted:
            report["status"] = "FAIL"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--acknowledge-virtual-drivers", action="store_true")
    args = p.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        report = run(plan, args.out, acknowledge=args.acknowledge_virtual_drivers,
                     timeout=args.timeout)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as err:
        report = {"schema": RESULT, "status": "NOT_RUN", "faults": [str(err)],
                  "physical_asio_hardware_verified": False,
                  "commercial_daw_verified": False, "release_approved": False}
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "VIRTUAL_ASIO_LOOPBACK_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
