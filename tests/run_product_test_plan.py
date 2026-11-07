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
from run_plugin_quickcheck import run as quick_run
from product_feature_coverage import validate_matrix, evaluate
from run_export_artifact_oracle import validate as validate_export, verify as verify_export
from run_export_action_chain import validate as validate_chain, run as run_chain

SCHEMA = "125a-product-test-plan-v1"
RESULT = "125a-product-test-plan-result-v1"
ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
KINDS = {"gui_workflow", "gesture_sweep", "technical_quickcheck", "export_artifact", "export_action_chain"}
QUICK_COVERAGE = {"api_playback_save", "sample_rate_buffer_matrix",
                  "native_audio_state_capture", "fresh_process_project_recall"}


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
    if (not isinstance(hosts, dict) or "gui" not in hosts
            or not set(hosts) <= {"gui", "audio", "stress"}):
        raise ValueError("P66 supported GUI/audio/stress host declarations only")
    for name, spec in hosts.items():
        if not isinstance(spec, dict) or set(spec) != {"path", "sha256"}:
            raise ValueError("P66 each native host requires path and SHA-256")
        if not isinstance(spec["sha256"], str) or not HEX.fullmatch(spec["sha256"]):
            raise ValueError("P66 host hash invalid")
    module = Path(product["module"]).resolve(strict=True)
    host = Path(hosts["gui"]["path"]).resolve(strict=True)
    if (not module.is_file() or module.suffix.lower() != ".vst3"
            or not any(p.suffix.lower() == ".vst3" and p.is_dir()
                       for p in module.parents) or not host.is_file()):
        raise ValueError("P65 real DLL must belong to a native VST3 bundle")
    if sha256(module) != product["sha256"]:
        raise ValueError("P66 native VST3 module hash changed")
    host_paths = {}
    for name, spec in hosts.items():
        actual = Path(spec["path"]).resolve(strict=True)
        if not actual.is_file() or sha256(actual) != spec["sha256"]:
            raise ValueError("P66 pinned native host missing or changed")
        host_paths[name] = actual
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
        if kind == "export_action_chain":
            chain_host, chain_module, action_count, output_paths = validate_chain(contract)
            if chain_host != host or chain_module != module:
                raise ValueError("P77 action chain belongs to a different host or plugin")
            if (contract["workflow"]["product"]["sha256"] != product["sha256"]
                    or contract["export"]["module_sha256"] != product["sha256"]):
                raise ValueError("P77 action chain does not match pinned product")
            compiled.append({"id": cid, "kind": kind, "contract": contract,
                             "expected_actions": action_count + len(output_paths)})
            continue
        if kind == "export_artifact":
            file_entries = validate_export(contract, product["sha256"])
            compiled.append({"id": cid, "kind": kind, "contract": contract,
                             "expected_actions": len(file_entries)})
            continue
        if kind == "technical_quickcheck":
            if not {"audio", "stress"} <= set(host_paths):
                raise ValueError("P66 technical quickcheck requires two native audio/stress hosts")
            if (set(contract) != {"required_coverage"} or
                    not isinstance(contract["required_coverage"], list)
                    or not 1 <= len(contract["required_coverage"]) <= len(QUICK_COVERAGE)
                    or any(type(v) is not str or v not in QUICK_COVERAGE
                           for v in contract["required_coverage"])
                    or len(set(contract["required_coverage"])) !=
                    len(contract["required_coverage"])):
                raise ValueError("P66 only explicitly approved technical quickcheck assertions")
            compiled.append({"id": cid, "kind": kind, "contract": contract,
                             "expected_actions": 1})
            continue
        workflow = contract if kind == "gui_workflow" else compile_contract(contract)
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
    return module, host_paths, compiled


def execute(plan, out, *, gui_runner=gui_run, sweep_runner=sweep_run,
            quick_runner=quick_run, chain_runner=run_chain, timeout=90, coverage_matrix=None):
    # Validate the ENTIRE plan before doing a single real GUI click.
    module, hosts, cases = validate(plan)
    # P67 validates ALL feature declarations and case links before performing
    # any GUI click or native audio operation.
    if coverage_matrix is not None:
        validate_matrix(coverage_matrix, plan)
    host = hosts["gui"]
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise ValueError("P65 invalid bounded native test timeout")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result_file = out / "PRODUCT-TEST-PLAN-RESULT.json"
    result_file.unlink(missing_ok=True)
    fingerprint = sha256(module)
    hostprints = {name: sha256(path) for name, path in hosts.items()}
    hostprint = hostprints["gui"]
    report = {
        "schema": RESULT, "status": "FAIL",
        "product_id": plan["product"]["id"],
        "verified_module_sha256": fingerprint, "verified_gui_host_sha256": hostprint,
        "declared_cases": len(cases), "passed_cases": 0, "failed_cases": 0,
        "not_run_cases": len(cases), "cases": [],
        "physical_asio_hardware": "NOT RUN",
        "real_commercial_daw_session": "NOT RUN",
        "full_product_functional_coverage": "NOT COVERED",
        "required_feature_coverage": "NOT DECLARED",
        "required_feature_gaps": [],
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
                if (sha256(module) != fingerprint or
                        any(sha256(path) != hostprints[name]
                            for name, path in hosts.items())):
                    raise ValueError("P66 executable or VST3 module changed before case")
                folder = out / ("%02d-%s" % (idx + 1, cid))
                if kind == "export_action_chain":
                    observed = chain_runner(case["contract"], folder, timeout=timeout)
                    if (not isinstance(observed, dict)
                            or observed.get("schema") != "125a-export-action-chain-result-v1"
                            or observed.get("status") != "ACTION_AND_ARTIFACT_PASS"
                            or observed.get("verified_module_sha256") != fingerprint
                            or observed.get("verified_gui_host_sha256") != hostprint
                            or observed.get("release_approved") is not False
                            or observed.get("actual_plugin_export_tested") is not True
                            or type(observed.get("verified_actions")) is not int
                            or type(observed.get("verified_outputs")) is not int
                            or observed.get("expected_actions") != observed.get("verified_actions")
                            or observed.get("expected_outputs") != observed.get("verified_outputs")
                            or observed["verified_actions"] + observed["verified_outputs"] != case["expected_actions"]):
                        raise ValueError("P77 native action/export chain evidence incomplete")
                elif kind == "export_artifact":
                    observed = verify_export(case["contract"], folder,
                                             module_sha=fingerprint)
                    if (not isinstance(observed, dict)
                            or observed.get("schema") != "125a-export-artifact-result-v1"
                            or observed.get("status") != "ARTIFACT_PASS"
                            or observed.get("verified_module_sha256") != fingerprint
                            or observed.get("release_approved") is not False
                            or observed.get("declared_actions") != case["expected_actions"]
                            or observed.get("verified_actions") != case["expected_actions"]
                            or not isinstance(observed.get("outputs"), list)
                            or len(observed["outputs"]) != case["expected_actions"]
                            or any(x.get("status") != "PASS" for x in observed["outputs"])):
                        raise ValueError("P76 WAV/MIDI artifact oracle lacks independent complete evidence")
                elif kind == "technical_quickcheck":
                    bundle = next(x for x in module.parents if
                                  x.is_dir() and x.suffix.lower() == ".vst3")
                    observed = quick_runner(bundle, hosts["audio"], hosts["stress"],
                                            folder, timeout=timeout)
                    if (not isinstance(observed, dict)
                            or observed.get("schema") != "125a-quickcheck-result-v1"
                            or observed.get("status") != "TECHNICAL_PASS"
                            or observed.get("release_approved") is not False
                            or observed.get("verified_module_sha256") != fingerprint
                            or not isinstance(observed.get("coverage"), dict)
                            or any(observed["coverage"].get(name) != "PASS"
                                   for name in case["contract"]["required_coverage"])
                            or observed["coverage"].get("physical_asio_hardware") != "NOT RUN"
                            or observed["coverage"].get("real_commercial_daw_session") != "NOT RUN"):
                        raise ValueError("P66 actual native technical quickcheck coverage incomplete")
                else:
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
                if (sha256(module) != fingerprint or
                        any(sha256(path) != hostprints[name]
                            for name, path in hosts.items())):
                    raise ValueError("P66 plugin or native test host changed during case")
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
    if coverage_matrix is not None:
        covered = evaluate(coverage_matrix, plan, report)
        report["required_feature_coverage"] = covered["status"]
        report["required_feature_gaps"] = covered["required_unverified"]
        (out / "PRODUCT-FEATURE-COVERAGE.json").write_text(
            json.dumps(covered, indent=2) + "\n", encoding="utf-8")
    result_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--coverage-matrix", type=Path,
                    help="P67 independent required product feature inventory")
    args = ap.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        matrix = (json.loads(args.coverage_matrix.read_text(encoding="utf-8"))
                  if args.coverage_matrix is not None else None)
        report = execute(plan, args.out, timeout=args.timeout,
                         coverage_matrix=matrix)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": RESULT, "status": "FAIL", "faults": [str(exc)],
                  "physical_asio_hardware": "NOT RUN",
                  "real_commercial_daw_session": "NOT RUN",
                  "required_feature_coverage": "INVALID OR NOT DECLARED",
                  "release_approved": False}
        (args.out / "PRODUCT-TEST-PLAN-RESULT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if (report["status"] == "CONTRACT_PASS" and
                 (args.coverage_matrix is None or
                  report.get("required_feature_coverage") ==
                  "REQUIRED_COVERAGE_COMPLETE")) else 1


if __name__ == "__main__":
    sys.exit(main())
