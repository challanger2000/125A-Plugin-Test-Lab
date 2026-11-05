#!/usr/bin/env python3
"""Independent fail-closed release evidence summary for this exact Windows CI run.

This report NEVER infers commercial DAW acceptance or a separate P16 run.
"""
from __future__ import annotations
import argparse
import datetime
import json
import pathlib
import re
import sys

CASES = {
    "P03_audio_swing": "build/p03-independent-oracle.log",
    "P05_audio_matrix": "build/p05-independent-matrix-oracle.log",
    "P06_midi_export": "build/p06-independent-midi-oracle.log",
    "P07_beat_creator": "build/p07-independent-beat-oracle.log",
    "P08_wav_export": "build/p08-independent-wav-midi-oracle.log",
    "P09_live_gui": "build/p09-independent-gui-oracle.log",
    "P10_save_dialogs": "build/p10-independent-dialog-oracle.log",
    "P11_gui_save_as": "build/p11-independent-export-oracle.log",
    "P13_drag_source": "build/p13-independent-dropped-midi-wav.log",
    "P17_gui_lifecycle": "build/p17-gui-stress.log",
    "P18_fresh_process_recall": "build/p18-independent-oracle.log",
    "P19_gui_stress": "build/p19-control-stress.log",
    "P20_corrupt_state_rejection": "build/p20-summary.log",
}

def make_report(sha: str, output: pathlib.Path) -> bool:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected exact 40-character lowercase product commit SHA")
    checks = {}
    for gate, path in CASES.items():
        p = pathlib.Path(path)
        if not p.is_file():
            checks[gate] = {"status": "FAIL", "reason": "missing test evidence", "log": path}
            continue
        body = p.read_text(encoding="utf-8-sig", errors="replace")
        if "[PASS]" not in body or "[FAIL]" in body:
            checks[gate] = {"status": "FAIL", "reason": "no PASS or contains FAIL", "log": path}
            continue
        checks[gate] = {"status": "PASS", "log": path}
    passed = all(v["status"] == "PASS" for v in checks.values())
    report = {
        "schema": "125a-testlab-release-evidence-v1",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "exact_tested_product_sha": sha,
        "repository": "125A-Plugin-Test-Lab",
        "summary": "PASS" if passed else "FAIL",
        "checked_gates": checks,
        "separate_workflows_not_proved_by_this_report": {
            "P02_P04": "NOT_COVERED_IN_THIS_REPORT",
            "P15_P16_native_OLE": "NOT_COVERED_IN_THIS_REPORT",
            "commercial_DAW_integration": "NOT_COVERED"
        }
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[{'PASS' if passed else 'FAIL'}] release evidence: {sum(v['status']=='PASS' for v in checks.values())}/{len(checks)} checked gates")
    print(f"[INFO] exact product SHA: {sha}")
    print(f"[INFO] report: {output}")
    return passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sha")
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    try:
        if not make_report(args.sha,args.output):
            sys.exit(1)
    except (OSError,ValueError) as error:
        print(f"[FAIL] release evidence: {error}",file=sys.stderr)
        sys.exit(1)
