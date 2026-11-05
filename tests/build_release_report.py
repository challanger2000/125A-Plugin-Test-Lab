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

# Verify the domain-specific *terminal independent-oracle* observations,
# not just a stray [PASS] emitted by unrelated setup or negative controls.
REQUIRED = {
    "P03_audio_swing": ("[PASS] P03 real Drumator VST3: 4 independent audible offbeats per scenario",),
    "P05_audio_matrix": ("[PASS] P05: 36 real Drumator VST3 scenarios",),
    "P06_midi_export": ("[PASS] P06: 18 real product MIDI exports parsed independently",),
    "P07_beat_creator": ("[PASS] P07: 1280 independent A/B/C pattern verifications",),
    "P08_wav_export": ("[PASS] P08: 18 real offline WAV exports, exact duration/format",),
    "P09_live_gui": (
        "[PASS] P09 actual Drumator VST3 GUI: mouse GENERATE/CANCEL",
        "[PASS] P09 actual Drumator VST3 GUI: GENERATE/APPLY changed",
        "[PASS] P09 untouched patterns D-H, protected rows 9-16",
    ),
    "P10_save_dialogs": ("[PASS] P10 independent 4/4 native dialog cancellation evidence",),
    "P11_gui_save_as": ("[PASS] P11: four genuine GUI Save As exports verified independently",),
    "P13_drag_source": ("[PASS] P11: four genuine GUI Save As exports verified independently",),
    "P17_gui_lifecycle": ("[PASS] P17 all 16 editor lifecycle cycles stable",),
    "P18_fresh_process_recall": (
        "[PASS] Real VST3 getState -> fresh process -> setState:",
        "[PASS] Saved DM18 state length, CRC and 24-bit PCM format validated",
    ),
    "P19_gui_stress": ("[PASS] P19 96 real GUI clicks and 48 state roundtrips",),
    "P20_corrupt_state_rejection": (
        "[PASS] P20 all 16 invalid VST3 project states rejected with no audio output",),
}
COUNTS = {
    "P18_fresh_process_recall": 3,
}
if set(REQUIRED) != set(CASES):
    raise RuntimeError("release proof gate mappings are not exhaustive")

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
        required = REQUIRED[gate]
        n = COUNTS.get(gate, 1)
        missing = [marker for marker in required if body.count(marker) != n]
        if "[FAIL]" in body or "[INCONCLUSIVE]" in body or missing:
            checks[gate] = {
                "status": "FAIL",
                "reason": ("negative or inconclusive marker" if
                           "[FAIL]" in body or "[INCONCLUSIVE]" in body else
                           "missing or repeated independent terminal observation"),
                "log": path,
                "missing_expected": missing,
            }
            continue
        checks[gate] = {"status": "PASS", "log": path,
                        "verified_terminal_observations": len(required) * n}
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
