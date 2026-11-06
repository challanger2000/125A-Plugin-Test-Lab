#!/usr/bin/env python3
"""Independent same-process VST3 two-instance state and PCM oracle.

The known QA state-format and expected output values are defined outside
the native test host and the plugin. Never derives expected from observed.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import sys

MAGIC = 0x125A2526


def approved(bank, program):
    return struct.pack("<IiiI", MAGIC, bank, program,
                       MAGIC ^ bank ^ (program << 8))


def parse(root):
    root = Path(root)
    evidence = root / "MULTI-INSTANCE.tsv"
    rows = {}
    for line in evidence.read_text(encoding="utf-8").splitlines():
        key, sep, val = line.partition("\t")
        if not sep or key in rows:
            raise ValueError("invalid or duplicate native multi-instance evidence")
        rows[key] = val
    expected_keys = {"format", "same_process_instances", "process_callbacks",
                     "A_first_pcm", "B_first_pcm", "B_second_pcm", "A_second_pcm"}
    if set(rows) != expected_keys or rows["format"] != "125A-DUAL-INSTANCE-v1":
        raise ValueError("missing or fabricated multi-instance evidence fields")
    if rows["same_process_instances"] != "2" or rows["process_callbacks"] != "4":
        raise ValueError("native host did not run both VST3 instances")
    pcm = {}
    for key in ("A_first_pcm", "B_first_pcm", "B_second_pcm", "A_second_pcm"):
        pcm[key] = float(rows[key])
        if not math.isfinite(pcm[key]):
            raise ValueError("invalid/nonfinite PCM from native VST3 instance")
    a = (root / "A-after.bin").read_bytes()
    b = (root / "B-after.bin").read_bytes()
    if not 0 < len(a) < 128 * 1024 * 1024 or not 0 < len(b) < 128 * 1024 * 1024:
        raise ValueError("missing or excessive serialized state")
    return {"pcm": pcm, "A_state": a, "B_state": b}


def audit(root, *, expect):
    if expect not in ("good", "broken"):
        raise ValueError("invalid expected fixture type")
    observed = parse(root)
    expected_a = approved(11, 22)
    expected_b = approved(33, 44)
    state_matches = (observed["A_state"] == expected_a and
                     observed["B_state"] == expected_b)
    desired = {"A_first_pcm": 0.25, "A_second_pcm": 0.25,
               "B_first_pcm": 0.125, "B_second_pcm": 0.125}
    pcm_matches = all(abs(observed["pcm"][key] - value) < 0.000001
                      for key, value in desired.items())
    isolation = "PASS" if state_matches and pcm_matches else "FAIL"
    report = {"schema": "125a-instance-isolation-v1",
              "status": "PASS" if (isolation == "PASS") == (expect == "good")
              else "FAIL",
              "same_process": True, "separate_instance_count": 2,
              "tested_process_calls": 4,
              "expected_fixture": expect, "state_isolation": isolation,
              "state_A_matched": observed["A_state"] == expected_a,
              "state_B_matched": observed["B_state"] == expected_b,
              "pcm_isolation": "PASS" if pcm_matches else "FAIL",
              "recorded_pcm": observed["pcm"],
              "commercial_daw_isolation": "NOT COVERED"}
    if expect == "broken" and isolation != "FAIL":
        report["reason"] = "shared-global-state negative fixture was not detected"
    elif expect == "good" and isolation != "PASS":
        report["reason"] = "genuine independent native VST3 instances leaked state/audio"
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--folder", required=True, type=Path)
    p.add_argument("--expect", required=True, choices=("good", "broken"))
    args = p.parse_args()
    try:
        result = audit(args.folder, expect=args.expect)
    except (OSError, ValueError, KeyError, TypeError) as ex:
        result = {"status": "FAIL", "error": str(ex)}
    args.folder.mkdir(parents=True, exist_ok=True)
    (args.folder / "INSTANCE-ISOLATION-RESULT.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[" + result["status"] + "] independent same-process dual-instance state/PCM oracle")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
