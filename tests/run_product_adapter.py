#!/usr/bin/env python3
"""P32 strict external adapter: binary-pinned real VST3 playback/save gates.

Never feeds synthetic bank/program state to arbitrary production plugins.
Semantic audio, state relationships and GUI are NOT COVERED by this host.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ID = re.compile(r"^[a-z][a-z0-9_]*$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
RATES = (44100, 48000, 96000)
BLOCKS = (17, 64, 127, 512, 1024)
FIELDS = {"format", "plugin", "sample_rate", "block_size", "iterations",
          "callbacks", "process_failures", "set_failures", "save_failures",
          "save_success", "domain_correctness", "result", "timing_certification",
          "callback_overruns", "callback_p99_ns"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(manifest):
    assert manifest.get("schema") == "125a-p32-adapter-v1", "unknown schema"
    product = manifest.get("product")
    assert isinstance(product, dict), "product identity missing"
    for field in ("name", "version", "binary", "commit_sha", "sha256"):
        assert isinstance(product.get(field), str) and product[field], "missing " + field
    assert SHA40.fullmatch(product["commit_sha"]), "invalid product commit SHA"
    assert SHA64.fullmatch(product["sha256"]), "invalid pinned VST3 SHA-256"
    assert str(product["binary"]).lower().endswith(".vst3"), "binary must be .vst3"
    assert isinstance(manifest.get("host"), str), "native host missing"
    cases = manifest.get("cases")
    assert isinstance(cases, list) and 1 <= len(cases) <= 64, "cases missing"
    seen = set()
    for case in cases:
        assert isinstance(case, dict), "invalid test case"
        name = case.get("id")
        assert isinstance(name, str) and ID.fullmatch(name) and name not in seen, "invalid case ID"
        seen.add(name)
        assert case.get("rate") in RATES and case.get("block") in BLOCKS, "invalid host conditions"
        assert type(case.get("iterations")) is int and 2000 <= case["iterations"] <= 30000
        assert case.get("mode") == "save-only", "cannot feed unknown product synthetic state"
        oracle = case.get("assertions")
        assert isinstance(oracle, dict) and oracle, "independent oracle missing"
        assert oracle.get("result") == {"eq": "PASS"}, "missing PASS expectation"
        assert oracle.get("save_failures") == {"eq": 0}, "save failure gate required"
        assert oracle.get("process_failures") == {"eq": 0}, "process failure gate required"
        assert oracle.get("domain_correctness") == {"eq": "NOT_COVERED"}, "false semantic PASS"
        for key, pred in oracle.items():
            assert key in FIELDS, "unknown observable field"
            assert isinstance(pred, dict) and len(pred) == 1
            op, val = next(iter(pred.items()))
            assert op in ("eq", "min", "max", "within"), "invalid assertion"
            if op == "within":
                assert isinstance(val, list) and len(val) == 2
                assert all(type(x) in (int, float) and math.isfinite(x) for x in val)
                assert val[0] <= val[1]
            elif op != "eq":
                assert type(val) in (int, float) and math.isfinite(val)
            else:
                assert type(val) in (str, int, float) and (not isinstance(val, float) or math.isfinite(val))
    return manifest


def evidence(path):
    data = {}
    for row in path.read_text(encoding="utf-8").splitlines():
        key, tab, val = row.partition("\t")
        assert tab and key in FIELDS and key not in data, "missing/duplicate/unknown evidence field"
        data[key] = val
    assert data.get("format") == "125A-P25-v1", "wrong host evidence format"
    return data


def check(actual, assertions):
    faults = []
    for key, pred in assertions.items():
        if key not in actual:
            faults.append("missing " + key)
            continue
        op, val = next(iter(pred.items()))
        try:
            if op == "eq": ok = actual[key] == str(val)
            else:
                v = float(actual[key])
                assert math.isfinite(v)
                ok = (v >= val if op == "min" else
                      v <= val if op == "max" else val[0] <= v <= val[1])
        except (ValueError, AssertionError, OverflowError):
            ok = False
        if not ok: faults.append(f"{key}: expected {op} {val}, observed {actual[key]}")
    return faults


def run(adapter_path, folder, timeout):
    manifest = validate(json.loads(adapter_path.read_text(encoding="utf-8")))
    product = manifest["product"]
    binary = Path(product["binary"]).resolve()
    host = Path(manifest["host"]).resolve()
    assert binary.is_file() and host.is_file(), "native binaries missing"
    assert digest(binary) == product["sha256"], "VST3 binary checksum mismatch"
    bundle = next((x for x in binary.parents if x.suffix.lower() == ".vst3"
                   and x.is_dir()), None)
    assert bundle is not None, "VST3 must reside in a bundle directory"
    assert 5 <= timeout <= 300
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for case in manifest["cases"]:
        output = folder / (case["id"] + ".tsv")
        argv = [str(host), "--stress", str(bundle), str(output), str(case["rate"]),
                str(case["block"]), str(case["iterations"]), "none", "--save-only"]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                                  check=False, errors="replace")
            (folder / (case["id"] + ".log")).write_text(
                (proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
            faults = [] if proc.returncode == 0 else [f"native VST3 host exited {proc.returncode}"]
            if output.exists():
                observed = evidence(output)
                faults += check(observed, case["assertions"])
                for field, val in (("sample_rate", case["rate"]),
                                   ("block_size", case["block"]),
                                   ("iterations", case["iterations"])):
                    if observed.get(field) != str(val): faults.append("conditions: " + field)
            else: faults.append("native result missing")
        except subprocess.TimeoutExpired:
            faults = ["native host timed out"]
        except (OSError, AssertionError, ValueError) as exc:
            faults = [str(exc)]
        results.append({"id": case["id"], "status": "FAIL" if faults else "PASS",
                        "faults": faults})
    passed = all(c["status"] == "PASS" for c in results)
    report = {"schema": "125a-p32-result-v1", "status": "PASS" if passed else "FAIL",
              "declared_product": {"name": product["name"], "version": product["version"],
                                   "commit_sha": product["commit_sha"]},
              "verified_vst3_sha256": digest(binary),
              "cases": results,
              "coverage": {"playback_save_api": "PASS" if passed else "FAIL",
                           "bank_program_semantics": "NOT COVERED",
                           "actual_musical_audio": "NOT COVERED",
                           "polyphony_limit": "NOT COVERED",
                           "gui_status": "NOT COVERED"}}
    (folder / "ADAPTER-RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for case in results: print(f"[{case['status']}] P32 {case['id']} {case['faults']}")
    return 0 if passed else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()
    try: sys.exit(run(args.adapter, args.out, args.timeout))
    except (OSError, AssertionError, ValueError, KeyError) as error:
        print("[FAIL] P32 invalid adapter:", error, file=sys.stderr)
        sys.exit(2)
