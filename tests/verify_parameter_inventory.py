#!/usr/bin/env python3
"""Independent audit of native VST3 controller parameter enumeration."""
import argparse
import json
import math
from pathlib import Path
import sys


def audit(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if len(lines) < 2 or lines[0] != "format\t125A-GUI-PARAMS-v1":
        raise ValueError("missing exact controller-inventory schema")
    heading = lines[1].split("\t")
    if len(heading) != 2 or heading[0] != "param_count" or not heading[1].isdigit():
        raise ValueError("invalid advertised VST3 parameter count")
    count = int(heading[1])
    if count > 8192 or len(lines) != count + 2:
        raise ValueError("parameter count mismatches the native enumeration")
    ids = set()
    for index, line in enumerate(lines[2:]):
        parts = line.split("\t")
        if len(parts) != 7 or parts[0] != "param":
            raise ValueError("invalid parameter TSV shape")
        if not all(parts[i].isdigit() for i in (1, 2, 3)):
            raise ValueError("invalid parameter index/id/step count")
        if int(parts[1]) != index:
            raise ValueError("missing, repeated or reordered parameter index")
        param_id = int(parts[2])
        if param_id > 4294967295 or param_id in ids:
            raise ValueError("duplicated/out-of-range VST3 parameter ID")
        ids.add(param_id)
        if int(parts[3]) > 2147483647:
            raise ValueError("invalid step count")
        for name, value in zip(("default", "current"), parts[4:6]):
            val = float(value)
            if not math.isfinite(val) or not 0.0 <= val <= 1.0:
                raise ValueError("nonfinite or out-of-range normalized "+name)
        # C++ flags is signed int32, not a fabricated classification.
        flags = int(parts[6])
        if not -2147483648 <= flags <= 2147483647:
            raise ValueError("invalid parameter flags")
    return {"status": "PASS", "advertised_parameters": count,
            "unique_ids_checked": len(ids),
            "user_visible_control_coverage": "NOT COVERED",
            "parameter_value_semantics": "NOT COVERED"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    report = a.out / "PARAMETER-INVENTORY-RESULT.json"
    report.unlink(missing_ok=True)
    try:
        data = audit(a.inventory)
    except (ValueError, OSError, OverflowError, UnicodeError) as exc:
        data = {"status": "FAIL", "error": str(exc),
                "user_visible_control_coverage": "NOT COVERED"}
    report.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
    print("["+data["status"]+"] native VST3 controller inventory")
    return 0 if data["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
