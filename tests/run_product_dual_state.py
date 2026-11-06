#!/usr/bin/env python3
"""Real VST3 two-bank isolation with externally approved state and PCM oracles.

Required inputs are *independent* of the test run: a manifest pins module
SHA256, two distinct initial saved-state SHA256 values, four reference PCM
samples and the expected post-processing state SHA256 for both instances.
No dynamically observed value is ever adopted as an expected value.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from verify_instance_isolation import parse

SHA = re.compile(r"[0-9a-f]{64}\Z")
PCM = ("A_first_pcm", "B_first_pcm", "B_second_pcm", "A_second_pcm")
MAX_STATE = 128 * 1024 * 1024


def hash_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validated_manifest(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema", "product", "host", "initial_states", "reference"}:
        raise ValueError("dual-state reference manifest has missing/unknown fields")
    if raw["schema"] != "125a-product-dual-state-oracle-v1":
        raise ValueError("wrong dual-state oracle manifest schema")
    if not isinstance(raw["product"], dict) or set(raw["product"]) != {"binary", "sha256"}:
        raise ValueError("module identity must contain binary and sha256 only")
    if not isinstance(raw["initial_states"], dict) or set(raw["initial_states"]) != {"A", "B"}:
        raise ValueError("exactly two distinct pinned input states required")
    for label in ("A", "B"):
        state = raw["initial_states"][label]
        if not isinstance(state, dict) or set(state) != {"path", "sha256"}:
            raise ValueError("input state requires independently pinned bytes")
        p = Path(state["path"]).resolve(strict=True)
        size = p.stat().st_size
        if not 0 < size < MAX_STATE:
            raise ValueError("empty/oversized initial project state")
        state["path"] = str(p)
        if not isinstance(state["sha256"], str) or not SHA.fullmatch(state["sha256"]):
            raise ValueError("invalid input state reference fingerprint")
        if hash_file(p) != state["sha256"]:
            raise ValueError("initial state bytes have changed since approval")
    if raw["initial_states"]["A"]["sha256"] == raw["initial_states"]["B"]["sha256"]:
        raise ValueError("reference A and B must be different")
    p = Path(raw["product"]["binary"]).resolve(strict=True)
    if not p.is_file() or not SHA.fullmatch(str(raw["product"]["sha256"])):
        raise ValueError("invalid VST3 product identity")
    if hash_file(p) != raw["product"]["sha256"]:
        raise ValueError("plugin module fingerprint differs from approved product")
    raw["product"]["binary"] = str(p)
    h = Path(raw["host"]).resolve(strict=True)
    if not h.is_file():
        raise ValueError("native same-process VST3 host missing")
    raw["host"] = str(h)
    reference = raw["reference"]
    if not isinstance(reference, dict) or set(reference) != {
        "expected_saved_sha256", "expected_pcm", "abs_tolerance"}:
        raise ValueError("separate saved-state and audio reference required")
    saved = reference["expected_saved_sha256"]
    if not isinstance(saved, dict) or set(saved) != {"A", "B"} or any(
            not isinstance(saved[v], str) or not SHA.fullmatch(saved[v])
            for v in ("A", "B")):
        raise ValueError("independent post-run saved-state fingerprint missing")
    pcm = reference["expected_pcm"]
    if not isinstance(pcm, dict) or set(pcm) != set(PCM):
        raise ValueError("independent four-point audio oracle incomplete")
    for val in pcm.values():
        if type(val) not in (int, float) or not math.isfinite(val) or not -1 <= val <= 1:
            raise ValueError("invalid reference PCM sample")
    tol = reference["abs_tolerance"]
    if type(tol) not in (int, float) or not math.isfinite(tol) or not 0 <= tol <= 0.01:
        raise ValueError("PCM absolute comparison tolerance must be 0..0.01")
    return raw


def run(manifest, out, timeout=60, runner=subprocess.run):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result_file = out / "PRODUCT-DUAL-STATE-RESULT.json"
    result_file.unlink(missing_ok=True)
    # Never reuse green native evidence from an earlier run.
    for name in ("MULTI-INSTANCE.tsv", "A-after.bin", "B-after.bin"):
        (out / name).unlink(missing_ok=True)
    report = {
        "schema": "125a-product-dual-state-result-v1",
        "status": "FAIL",
        "release_approved": False,
        "saved_state_isolation": "NOT EXECUTED",
        "reference_pcm_isolation": "NOT EXECUTED",
        "commercial_daw_isolation": "NOT COVERED",
    }
    try:
        m = validated_manifest(manifest)
        report["verified_module_sha256"] = m["product"]["sha256"]
        states = m["initial_states"]
        proc = runner([
            m["host"], "--dual-state", m["product"]["binary"],
            states["A"]["path"], states["B"]["path"], str(out.resolve())
        ], capture_output=True, text=True, timeout=timeout, check=False, errors="replace")
        (out / "native-run.log").write_text(
            (proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
        if proc.returncode != 0 or (
            "[PASS] two real VST3 instances processed in same host process"
            not in (proc.stdout or "")):
            raise ValueError("real native same-process VST3 host did not complete")
        observed = parse(out)  # strict structural audit; reads both new state files
        ref = m["reference"]
        report["native_instances"] = 2
        report["native_process_calls"] = 4
        found_state = {label: hashlib.sha256(observed[label + "_state"]).hexdigest()
                       for label in ("A", "B")}
        report["observed_saved_sha256"] = found_state
        report["saved_state_isolation"] = (
            "PASS" if found_state == ref["expected_saved_sha256"] else "FAIL")
        problems = {key: {"actual": observed["pcm"][key],
                          "expected": ref["expected_pcm"][key]}
                    for key in PCM if abs(observed["pcm"][key] -
                                          ref["expected_pcm"][key]) >
                    ref["abs_tolerance"]}
        report["reference_pcm_isolation"] = "FAIL" if problems else "PASS"
        report["audio_mismatches"] = problems
        report["status"] = ("TECHNICAL_PASS" if
                            report["saved_state_isolation"] == "PASS" and
                            report["reference_pcm_isolation"] == "PASS" else "FAIL")
        if report["status"] != "TECHNICAL_PASS":
            report["reason"] = "observed VST3 state or PCM differs from independent A/B references"
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired,
            json.JSONDecodeError) as exc:
        report["reason"] = str(exc)
    result_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description="Real two-instance VST3 product-state and PCM oracle")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=60)
    args = p.parse_args()
    if not 5 <= args.timeout <= 300:
        raise SystemExit("timeout must be between 5 and 300 seconds")
    result = run(args.manifest, args.out, args.timeout)
    print("[" + result["status"] + "] real same-process two-state VST3 reference test")
    return 0 if result["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
