#!/usr/bin/env python3
"""P31 independent rendered pixel vs processor state/audio oracle.

Native pixels are read from the plugin's real HWND paint surface. Expected
colors are specified outside the VST3 implementation, never inferred from it.
"""
from pathlib import Path
import argparse
import math
import sys

EXPECTED={
    "initial":(11,22,.11,.22,.25,40,140,220),
    "after_reject":(11,22,.11,.22,.25,40,140,220),
    "after_reconnect":(33,44,.33,.44,.125,220,110,40),
    "after_restore":(11,22,.11,.22,.25,40,140,220),
}

def verify(path:Path,mode:str)->None:
    lines=path.read_text(encoding="utf-8").splitlines()
    assert lines.pop(0)=="schema\t125A-P31-v1", "missing P31 evidence schema"
    found={}
    for line in lines:
        parts=line.split("\t")
        assert len(parts)==9 and parts[0] not in found,"invalid stage, duplicates or incomplete GUI sample"
        key=parts[0]
        assert key in EXPECTED,"unknown recorded stage"
        values=[int(parts[1]),int(parts[2])]+[float(x) for x in parts[3:6]]+[int(x) for x in parts[6:9]]
        assert all(math.isfinite(v) for v in values),"nonfinite controller or audio"
        found[key]=values
    assert set(found)==set(EXPECTED),"missing real GUI lifecycle stage"
    mismatches={}
    for key,expected in EXPECTED.items():
        mismatches[key]=[i for i,(a,b) in enumerate(zip(found[key],expected))
                         if abs(a-b)>1e-5]
    if mode=="good":
        assert not any(mismatches.values()),f"visible GUI, processor or controller mismatch {mismatches}"
    else:
        # Broken VST3 must be wrong at reconnect both semantically and VISUALLY.
        assert all(not mismatches[x] for x in ("initial","after_reject","after_restore")),mismatches
        assert set(mismatches["after_reconnect"])=={2,3,5,6,7},(
            f"wrong failure mode: stale normalized controller and RGB expected; got {mismatches}")
        assert found["after_reconnect"][5:]==[40,140,220],(
            "broken fixture did not actually retain stale blue painted GUI")
    print(f"[PASS] P31 {mode}: actual native HWND center pixel, "
          "processor state, controller normalized values, and stereo PCM")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("report",type=Path)
    parser.add_argument("expect",choices=("good","broken"))
    args=parser.parse_args()
    try:verify(args.report,args.expect)
    except (OSError,AssertionError,ValueError,IndexError) as err:
        print("[FAIL] P31 independent native visual-state oracle:",err,file=sys.stderr)
        sys.exit(1)
