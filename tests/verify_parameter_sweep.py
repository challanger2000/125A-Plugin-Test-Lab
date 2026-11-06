#!/usr/bin/env python3
"""Independent verifier of native VST3 controller boundary sweeps.

A successful controller API call is not a mouse click or proof that a
product-specific GUI label, preset, or audio effect is correct.
"""
import argparse
import json
import math
from pathlib import Path
import sys


MAX_PARAMS = 8192
CAN_AUTOMATE = 1
IS_READ_ONLY = 2


def integer(field, *, lower=0, upper=4294967295):
    if not field.isascii() or not field.isdecimal():
        raise ValueError("nondecimal or signed native evidence integer")
    value = int(field)
    if not lower <= value <= upper:
        raise ValueError("out-of-range native evidence integer")
    return value


def normalized(field):
    value = float(field)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("nonfinite/out-of-range controller value")
    return value


def audit(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    labels = ("format", "param_count", "tested", "skipped", "failed", "observations")
    if len(lines) < len(labels):
        raise ValueError("truncated controller sweep")
    header = [line.split("\t") for line in lines[:len(labels)]]
    if any(len(row) != 2 or row[0] != label
           for row, label in zip(header, labels)):
        raise ValueError("missing/misordered sweep header")
    if header[0][1] != "125A-GUI-SWEEP-v1":
        raise ValueError("wrong controller-sweep schema")
    expected_params = integer(header[1][1], upper=MAX_PARAMS)
    advertised_tested = integer(header[2][1], upper=MAX_PARAMS)
    advertised_skipped = integer(header[3][1], upper=MAX_PARAMS)
    advertised_failed = integer(header[4][1], upper=MAX_PARAMS)
    advertised_points = integer(header[5][1], upper=MAX_PARAMS * 5)
    if advertised_tested + advertised_skipped != expected_params:
        raise ValueError("not all VST3 parameters accounted for")
    if advertised_failed > advertised_tested:
        raise ValueError("failure count exceeds tested parameters")

    cursor = len(labels)
    seen = set()
    tested = skipped = failed = points = 0
    for index in range(expected_params):
        if cursor >= len(lines):
            raise ValueError("missing controller parameter row")
        row = lines[cursor].split("\t")
        cursor += 1
        if len(row) != 8 or row[0] != "param":
            raise ValueError("malformed parameter row")
        if integer(row[1], upper=MAX_PARAMS) != index:
            raise ValueError("missing/reordered controller parameter")
        identifier = integer(row[2])
        steps = integer(row[3], upper=2147483647)
        flags = integer(row[4], upper=2147483647)
        initial = normalized(row[5])
        verdict = row[6]
        restore = integer(row[7], upper=1)
        if identifier in seen:
            raise ValueError("duplicate controller parameter identifier")
        seen.add(identifier)
        eligible = bool(flags & CAN_AUTOMATE) and not bool(flags & IS_READ_ONLY)
        if not eligible:
            if verdict != "SKIP" or restore != 1:
                raise ValueError("unwritable VST3 parameter certified as writable")
            skipped += 1
            continue
        tested += 1
        expected_values = []
        for n in range(5):
            target = n / 4
            if steps:
                target = math.floor(target * steps + 0.5) / steps
            if not expected_values or abs(expected_values[-1] - target) >= 1e-12:
                expected_values.append(target)
        probe_ok = True
        for target in expected_values:
            if cursor >= len(lines):
                raise ValueError("missing normalized parameter probe")
            sample = lines[cursor].split("\t")
            cursor += 1
            if len(sample) != 6 or sample[0] != "probe":
                raise ValueError("invalid parameter probe shape")
            if integer(sample[1], upper=MAX_PARAMS) != index or integer(sample[2]) != identifier:
                raise ValueError("parameter probe attributed to wrong control")
            actual_target = normalized(sample[3])
            observed = normalized(sample[4])
            ok = integer(sample[5], upper=1) == 1
            if abs(actual_target - target) > 1e-9:
                raise ValueError("native probe tested incorrect normalized step")
            if ok != (abs(observed - target) <= 1e-5):
                raise ValueError("native probe success marker contradicts evidence")
            probe_ok = probe_ok and ok
            points += 1
        passed = probe_ok and restore == 1
        if verdict != ("PASS" if passed else "FAIL"):
            raise ValueError("native summary contradicts independently checked probes")
        failed += 0 if passed else 1
    if cursor != len(lines):
        raise ValueError("unexpected/unverified native sweep data")
    if (tested, skipped, failed, points) != (
            advertised_tested, advertised_skipped,
            advertised_failed, advertised_points):
        raise ValueError("native sweep counts do not match independent reconstruction")
    coverage = ("NOT COVERED" if tested == 0 else
                "FAIL" if failed else "PASS")
    return {"schema": "125a-parameter-sweep-audit-v1",
            "status": "FAIL" if failed else "PASS",
            "advertised_parameters": expected_params,
            "writable_parameters": tested,
            "skipped_nonautomatable_or_readonly": skipped,
            "failed_parameters": failed,
            "independent_points_verified": points,
            "controller_roundtrip": coverage,
            "pixel_gui_controls": "NOT COVERED",
            "product_parameter_semantics": "NOT COVERED",
            "commercial_daw_integration": "NOT COVERED"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sweep", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    report = a.out / "PARAMETER-SWEEP-RESULT.json"
    report.unlink(missing_ok=True)
    try:
        data = audit(a.sweep)
    except (OSError, ValueError, OverflowError, UnicodeError) as error:
        data = {"schema": "125a-parameter-sweep-audit-v1", "status": "FAIL",
                "error": str(error), "controller_roundtrip": "NOT COVERED",
                "pixel_gui_controls": "NOT COVERED"}
    report.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("[" + data["status"] + "] independent native VST3 controller boundary sweep")
    return 0 if data["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
