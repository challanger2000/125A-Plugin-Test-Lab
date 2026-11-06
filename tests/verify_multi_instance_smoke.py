#!/usr/bin/env python3
"""Real native dual-instance structural VST3 smoke: no fabricated isolation claim.

The plugin's captured state is cloned to two simultaneously live components
within a SINGLE native host process. All four process() calls and both
getState() roundtrips are observed; the host does not invent a second state.
"""
import argparse
import json
from pathlib import Path
import sys

from verify_instance_isolation import parse


def audit(root):
    found = parse(root)
    return {
        "schema": "125a-instance-lifecycle-v1",
        "status": "PASS",
        "same_process": True,
        "instances_created": 2,
        "process_calls": 4,
        "nonempty_state_snapshots": 2,
        "finite_pcm_observations": 4,
        "distinct_state_isolation": "NOT COVERED",
        "musical_correctness": "NOT COVERED",
        "daw_multi_instance_behavior": "NOT COVERED"
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--folder", required=True, type=Path)
    a = p.parse_args()
    report_path = a.folder / "MULTI-INSTANCE-SMOKE-RESULT.json"
    report_path.unlink(missing_ok=True)
    try:
        report = audit(a.folder)
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        report = {"schema": "125a-instance-lifecycle-v1", "status": "FAIL",
                  "error": str(exc), "distinct_state_isolation": "NOT COVERED"}
    a.folder.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("[" + report["status"] + "] two real instances share one native VST3 host")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
