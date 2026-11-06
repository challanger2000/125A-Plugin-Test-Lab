#!/usr/bin/env python3
"""Independent fail-closed oracle for all VST3 parameter text/value conversions.

This tests IEditController's text API, not the actual pixel labels in a
product-specific editor.  Continuous parameters are allowed to round their
visible text; discrete steps must reconstruct the identical normalized step.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = "125A-GUI-TEXT-v1"
MAX_PARAMETERS = 8192
HEX = re.compile(r"(?:[0-9a-f]{4}){1,127}\Z")


def integer(value, maximum):
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError("text oracle has signed or nondecimal integer")
    number = int(value)
    if number > maximum:
        raise ValueError("text oracle count or parameter metadata out of range")
    return number


def numeric(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("malformed normalized VST3 text value") from error
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError("nonfinite/out-of-range normalized VST3 text value")
    return number


def decode_hex(hex_text):
    if not HEX.fullmatch(hex_text):
        raise ValueError("malformed or oversized UTF-16 VST3 parameter label")
    raw = bytes.fromhex(hex_text)
    text = raw.decode("utf-16-be", errors="strict")
    if "\x00" in text:
        raise ValueError("embedded NUL in visible VST3 parameter label")
    return text


def audit(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    labels = ("format", "param_count", "tested", "skipped", "failed",
              "observations", "readable", "reversible")
    if len(lines) < len(labels):
        raise ValueError("truncated VST3 parameter text mapping evidence")
    head = [line.split("\t") for line in lines[:len(labels)]]
    if any(len(row) != 2 or row[0] != name for row, name in zip(head, labels)):
        raise ValueError("missing or reordered native text evidence counters")
    if head[0][1] != SCHEMA:
        raise ValueError("wrong VST3 parameter text schema")
    count = integer(head[1][1], MAX_PARAMETERS)
    declared = [integer(row[1], MAX_PARAMETERS * 5 if i > 4 else MAX_PARAMETERS)
                for i, row in enumerate(head[2:], start=2)]
    advertised_tested, advertised_skipped, advertised_failed, observations, readable, reversible = declared
    if (advertised_tested + advertised_skipped != count or
            advertised_failed > advertised_tested):
        raise ValueError("invalid VST3 text audit coverage counts")
    if readable > observations or reversible > readable:
        raise ValueError("unsupported VST3 parameter text count relationship")

    cursor = len(labels)
    ids = set()
    tested = skipped = failed = observed = readable_seen = reverse_seen = 0
    readable_params = reverse_params = 0
    for index in range(count):
        if cursor >= len(lines):
            raise ValueError("missing text parameter row")
        row = lines[cursor].split("\t")
        cursor += 1
        if len(row) != 6 or row[0] != "param":
            raise ValueError("malformed native text parameter record")
        if integer(row[1], MAX_PARAMETERS) != index:
            raise ValueError("reordered/missing native VST3 parameter")
        identifier = integer(row[2], 4294967295)
        steps = integer(row[3], 2147483647)
        flags = integer(row[4], 2147483647)
        verdict = row[5]
        if identifier in ids:
            raise ValueError("VST3 parameter text oracle saw duplicate parameter IDs")
        ids.add(identifier)
        eligible = bool(flags & 1) and not bool(flags & 2)
        if not eligible:
            if verdict != "SKIP":
                raise ValueError("unwritable VST3 parameter certified as readable")
            skipped += 1
            continue
        tested += 1
        has_text = has_reverse = is_bad = False
        previous = None
        for point in range(5):
            target = point / 4
            if steps:
                target = math.floor(target * steps + 0.5) / steps
            if previous is not None and abs(previous - target) < 1e-12:
                continue
            previous = target
            if cursor >= len(lines):
                raise ValueError("native text probe missing")
            sample = lines[cursor].split("\t")
            cursor += 1
            if len(sample) != 9 or sample[0] != "text":
                raise ValueError("native text probe shape is malformed")
            if integer(sample[1], MAX_PARAMETERS) != index or integer(sample[2], 4294967295) != identifier:
                raise ValueError("text probe belongs to wrong parameter")
            expected = numeric(sample[3])
            if abs(target - expected) > 1e-9:
                raise ValueError("text probe skipped or substituted a boundary value")
            encoded, reverse_state, parsed, canonical, outcome = sample[4:]
            good = True
            if encoded == "-":
                if (reverse_state, parsed, canonical, outcome) != ("-", "-", "-", "NOT_COVERED"):
                    raise ValueError("absent VST3 parameter label falsely classified as tested")
            else:
                has_text = True
                readable_seen += 1
                decode_hex(encoded)
                if reverse_state == "N":
                    if parsed != "-" or canonical != "-":
                        raise ValueError("unimplemented reverse parser claimed native data")
                elif reverse_state == "R":
                    has_reverse = True
                    reverse_seen += 1
                    value = numeric(parsed)
                    decode_hex(canonical)
                    good = canonical == encoded
                    if steps:
                        good = good and abs(value - target) <= 1e-5
                else:
                    raise ValueError("unrecognized VST3 text reverse support marker")
                if outcome not in ("PASS", "FAIL") or (outcome == "PASS") != good:
                    raise ValueError("native VST3 label status contradicts independent audit")
                if not good:
                    is_bad = True
            observed += 1
        expected_verdict = "FAIL" if is_bad else "PASS" if has_text else "NOT_COVERED"
        if verdict != expected_verdict:
            raise ValueError("native text parameter summary is falsely green")
        if has_text:
            readable_params += 1
        if has_reverse:
            reverse_params += 1
        if is_bad:
            failed += 1
    if cursor != len(lines):
        raise ValueError("unverified extra native VST3 text records")
    if (tested, skipped, failed, observed, readable_seen, reverse_seen) != (
            advertised_tested, advertised_skipped, advertised_failed,
            observations, readable, reversible):
        raise ValueError("native VST3 text evidence counts fail independent reconstruction")
    return {
        "schema": "125a-parameter-text-audit-v1",
        "status": "FAIL" if failed else "PASS",
        "advertised_parameters": count,
        "automatable_parameters": tested,
        "skipped_parameters": skipped,
        "parameter_label_probes": readable_seen,
        "parameter_reverse_probes": reverse_seen,
        "parameters_with_readable_labels": readable_params,
        "parameters_with_reversible_labels": reverse_params,
        "failed_parameter_text_mappings": failed,
        # A single supported label does not make every parameter readable.
        # Partial coverage remains NOT COVERED until every requested point
        # has been proven, never a misleading global PASS.
        "text_label_api": "FAIL" if failed else (
            "PASS" if observed > 0 and readable_seen == observed else "NOT COVERED"),
        "reverse_text_api": "FAIL" if failed else (
            "PASS" if observed > 0 and reverse_seen == observed else "NOT COVERED"),
        "actual_editor_painted_values": "NOT COVERED",
        "product_specific_value_meaning": "NOT COVERED",
        "release_approved": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = args.out / "PARAMETER-TEXT-RESULT.json"
    result.unlink(missing_ok=True)
    try:
        answer = audit(args.native)
    except (OSError, ValueError, OverflowError, UnicodeError) as error:
        answer = {"schema": "125a-parameter-text-audit-v1",
                  "status": "FAIL", "text_label_api": "FAIL",
                  "reverse_text_api": "NOT COVERED",
                  "actual_editor_painted_values": "NOT COVERED",
                  "release_approved": False, "reason": str(error)}
    result.write_text(json.dumps(answer, indent=2) + "\n", encoding="utf-8")
    print("[" + answer["status"] + "] independently audited VST3 parameter text")
    return 0 if answer["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
