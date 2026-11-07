#!/usr/bin/env python3
"""P65: universal, versioned plugin-specific test plans without core edits.

Product developers declare approved GUI workflows / analog sweeps as JSON.
The shared Test Lab validates all contracts before dispatch and requires
independent, exact VST3 and host identity plus strict evidence counts.
Unsupported claims never become PASS and product release is NEVER approved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from run_gui_workflow import run as gui_run, validate as validate_gui
from run_gui_gesture_sweep import run as sweep_run, compile_contract

SCHEMA = "125a-product-test-plan-v1"
RESULT = "125a-product-test-plan-result-v1"
ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
KINDS = {"gui_workflow", "gesture_sweep"}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def validate(plan):
    if not isinstance(plan, dict) or set(plan) != {
            "schema", "product", "hosts", "cases"} or plan["schema"] != SCHEMA:
        raise ValueError("P65 exact versioned product-test-plan schema required")
    product, hosts, cases = plan["product"], plan["hosts"], plan["cases"]
    if not isinstance(product, dict) or set(product) != {"id", "module", "sha256"}:
        raise ValueError("P65 product identity must be explicit")
    if not isinstance(product["id"], str) or not ID.fullmatch(product["id"]):
        raise ValueError("P65 invalid product identifier")
    if not isinstance(product["sha256"], str) or not HEX.fullmatch(product["sha256"]):
        raise ValueError("P65 invalid product digest")
    if not isinstance(hosts, dict) or set(hosts) != {"gui"}:
        raise ValueError("P65 exact supported GUI host declaration required")
    if not isinstance(hosts["gui"], dict) or set(hosts["gui"]) != {"path", "sha256"}:
        raise ValueError("P65 GUI host path and independent SHA-256 required")
    if not isinstance(hosts["gui"]["sha256"], str) or not HEX.fullmatch(hosts["gui"]["sha256"]):
        raise ValueError("P65 invalid host hash")
    module = Path(product["module"]).resolve(strict=True)
    host = Path(hosts["gui"]["path"]).resolve(strict=True)
    if (not module.is_file() or module.suffix.lower() != ".vst3"
            or not any(p.suffix.lower() == ".vst3" and p.is_dir()
                       for p in module.parents) or not host.is_file()):
        raise ValueError("P65 real DLL must belong to a native VST3 bundle")
    if sha256(module) != product["sha256"] or sha256(host) != hosts["gui"]["sha256"]:
        raise ValueError("P65 pinned plugin/host changed or wrong hash")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("P65 requires 1..32 product-specific cases")
    ids = set()
    compiled = []
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "kind", "contract"}:
            raise ValueError("P65 invalid case keys")
        cid, kind, contract = case["id"], case["kind"], case["contract"]
        if not isinstance(cid, str) or not ID.fullmatch(cid) or cid in ids:
            raise ValueError("P65 missing or duplicate bounded case ID")
        ids.add(cid)
        if kind not in KINDS or not isinstance(contract, dict):
            raise ValueError("P65 unknown or unapproved adapter kind")
        if kind == "gui_workflow":
            workflow = contract
        else:
            workflow = compile_contract(contract)
        # Invoke the actual native GUI contract validator. This prevents
        # accepting malformed instructions or manually guessed param values.
        gui_host, _, gui_module, _, steps = validate_gui(workflow)
        if gui_host != host or gui_module != module:
            raise ValueError("P65 case references a different host or plugin")
        if (workflow["product"]["sha256"] != product["sha256"] or
                Path(workflow["product"]["binary"]).resolve(strict=True) != module or
                Path(workflow["gui_host"]).resolve(strict=True) != host):
            raise ValueError("P65 each case must share the pinned binary and host")
        compiled.append({"id": cid, "kind": kind, "contract": contract,
                         "expected_actions": len(steps)})
    return module, host, compiled


def execute(plan, out, *, gui_runner=gui_run, sweep_runner=sweep_run, timeout=90):
    # Validate the ENTIRE plan before doing a single real GUI click.
    module, host, cases = validate(plan)
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise ValueError("P65 invalid bounded native test timeout")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result_file = out / "PRODUCT-TEST-PLAN-RESULT.json"
    result_file.unlink(missing_ok=True)
    fingerprint = sha256(module)
    hostprint = sha256(host)
    report = {
        "schema": RESULT, "status": "FAIL",
        "product_id": plan["product"]["id"],
        "verified_module_sha256": fingerprint, "verified_gui_host_sha256": hostprint,
        "declared_cases": len(cases), "passed_cases": 0, "failed_cases": 0,
        "not_run_cases": len(cases), "cases": [],
        "physical_asio_hardware": "NOT RUN",
        "real_commercial_daw_session": "NOT RUN",
        "full_product_functional_coverage": "NOT COVERED",
        "release_approved": False
    }
    fail_closed = False
    for idx, case in enumerate(cases):
        cid, kind = case["id"], case["kind"]
        entry = {"id": cid, "kind": kind, "status": "NOT RUN",
                 "expected_actions": case["expected_actions"],
                 "verified_actions": 0, "faults": []}
        if fail_closed:
            entry["faults"].append("prior case failed; remaining actions deliberately skipped")
        else:
            try:
                if sha256(module) != fingerprint or sha256(host) != hostprint:
                    raise ValueError("P65 executable or VST3 module changed before case")
                folder = out / ("%02d-%s" % (idx + 1, cid))
                if kind == "gui_workflow":
                    observed = gui_runner(case["contract"], folder, timeout=timeout)
                    expected_status = "TECHNICAL_PASS"
                    counter = "verified_actions"
                else:
                    observed = sweep_runner(case["contract"], folder, timeout=timeout)
                    expected_status = "CONTRACT_PASS"
                    counter = "verified_checkpoints"
                if (not isinstance(observed, dict)
                        or observed.get("status") != expected_status
                        or type(observed.get(counter)) is not int
                        or observed[counter] != case["expected_actions"]
                        or observed.get("release_approved") is True):
                    raise ValueError("P65 nested native result failed independent expected counts")
                if kind == "gui_workflow" and (
                        observed.get("verified_module_sha256") != fingerprint or
                        observed.get("gui_host_sha256") != hostprint or
                        observed.get("declared_actions") != case["expected_actions"]):
                    raise ValueError("P65 workflow result belongs to another module/host")
                if sha256(module) != fingerprint or sha256(host) != hostprint:
                    raise ValueError("P65 binary changed during case")
                entry["status"] = "PASS"
                entry["verified_actions"] = case["expected_actions"]
            except (ValueError, OSError, TypeError, KeyError, IndexError) as exc:
                entry["status"] = "FAIL"
                entry["faults"].append(str(exc))
                fail_closed = True
        report["cases"].append(entry)
    report["passed_cases"] = sum(c["status"] == "PASS" for c in report["cases"])
    report["failed_cases"] = sum(c["status"] == "FAIL" for c in report["cases"])
    report["not_run_cases"] = sum(c["status"] == "NOT RUN" for c in report["cases"])
    if report["passed_cases"] == report["declared_cases"]:
        report["status"] = "CONTRACT_PASS"
    result_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        report = execute(plan, args.out, timeout=args.timeout)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": RESULT, "status": "FAIL", "faults": [str(exc)],
                  "physical_asio_hardware": "NOT RUN",
                  "real_commercial_daw_session": "NOT RUN",
                  "release_approved": False}
        (args.out / "PRODUCT-TEST-PLAN-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "CONTRACT_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
