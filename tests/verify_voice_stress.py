#!/usr/bin/env python3
"""P29 independent instrument adapter oracle. Voice ceiling and amplitude come
from independent test requirements, NOT the VST3 module or its return code.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import math
import sys

def inspect(path: Path, target: int, defect: str) -> None:
    data={}
    for line in path.read_text(encoding="utf-8").splitlines():
        name,separator,value=line.partition("\t")
        assert separator and name not in data, "malformed evidence or duplicate field"
        data[name]=value
    assert data["schema"]=="125A-P29-v1"
    requested=int(data["voices_requested"])
    max_supported=int(data["max_voices_adapter"])
    assert requested==target and max_supported==32
    assert int(data["audio_calls"])==2500
    assert int(data["audio_failures"])==0
    assert int(data["save_attempts"])==500
    assert int(data["saves_while_playing"])==500, "saves were not concurrent with active playback"
    assert int(data["save_success"])+int(data["save_failures"])==500
    assert int(data["invalid_state_payloads"])==0
    assert int(data["state_bytes"])==12
    before=float(data["pre_recall_amplitude"])
    restored=float(data["after_fresh_recall_amplitude"])
    assert math.isfinite(before) and math.isfinite(restored)
    expected=0.01*target
    if defect=="good":
        assert int(data["save_failures"])==0, "unexpected save failure during playback"
        assert abs(before-expected)<1e-6 and abs(restored-expected)<1e-6, (
            f"independent polyphony/recall oracle: {target} voices expected {expected}, "
            f"observed {before} / {restored}")
    elif defect=="broken-saves":
        assert int(data["save_failures"])==100, "intentionally broken save failed for unexpected reason"
        assert abs(before-expected)<1e-6 and abs(restored-expected)<1e-6
    elif defect=="broken-voices":
        assert target==32 and int(data["save_failures"])==0
        assert abs(before-expected)>0.1 and abs(restored-expected)>0.1
        assert abs(before-0.04)<1e-6 and abs(restored-0.04)<1e-6, (
            "broken fixture not detected as silent 4-voice cap")
    else:
        raise AssertionError("unknown oracle mode")
    print(f"[PASS] P29 {defect}: {target} actual MIDI notes, 2500 audio calls, "
          f"500 live saves, exact fresh-instance PCM={before:.6f}/{restored:.6f}")

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("evidence",type=Path)
    p.add_argument("voices",type=int)
    p.add_argument("mode",choices=("good","broken-saves","broken-voices"))
    args=p.parse_args()
    try: inspect(args.evidence,args.voices,args.mode)
    except (AssertionError,OSError,KeyError,ValueError) as e:
        print(f"[FAIL] independent P29 voice oracle: {e}",file=sys.stderr)
        sys.exit(1)
if __name__=="__main__":
    main()
