#!/usr/bin/env python3
"""P30 independent VST3 component/controller reconnect state+audio oracle.

The fixture's correlated state tuples and levels are independently specified.
A functioning transport API does not itself prove GUI visual correctness.
"""
from pathlib import Path
import argparse
import math
import sys

EXPECTED={
    "initial":(11,22,.11,.22,.25),
    "after_reject":(11,22,.11,.22,.25),
    "after_reconnect":(33,44,.33,.44,.125),
    "after_restore":(11,22,.11,.22,.25),
}

def run(path:Path,kind:str)->None:
    lines=path.read_text(encoding="utf-8").splitlines()
    assert lines.pop(0)=="schema\t125A-P30-v1", "P30 evidence schema invalid"
    found={}
    for line in lines:
        parts=line.split("\t")
        assert len(parts)==6 and parts[0] not in found,"P30 duplicate/malformed row"
        name=parts[0]
        assert name in EXPECTED,"P30 unknown state stage"
        values=(int(parts[1]),int(parts[2]),*(float(x) for x in parts[3:]))
        assert all(math.isfinite(x) for x in values),"P30 nonfinite state/audio"
        found[name]=values
    assert set(found)==set(EXPECTED),"P30 missing lifecycle stage"
    errors=[]
    for stage,expected in EXPECTED.items():
        got=found[stage]
        for idx,(value,want) in enumerate(zip(got,expected)):
            if abs(value-want)>1e-5:
                errors.append((stage,idx,want,value))
    if kind=="good":
        assert not errors,f"P30 stale UI/controller, processor or audio state: {errors}"
    else:
        assert errors,"P30 broken controller was not detected"
        assert any(stage=="after_reconnect" and index in (2,3) for stage,index,_,_ in errors),(
            f"P30 broken fixture not detected by controller state oracle: {errors}")
        assert all(index in (2,3) and stage=="after_reconnect"
                   for stage,index,_,_ in errors),(
            f"P30 negative fixture failed for unrelated processor/audio reason: {errors}")
    print(f"[PASS] P30 {kind}: reconnect rollback and independent controller+processor+PCM oracle")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("evidence",type=Path)
    p.add_argument("expect",choices=("good","broken"))
    a=p.parse_args()
    try:run(a.evidence,a.expect)
    except (OSError,AssertionError,ValueError,IndexError) as e:
        print(f"[FAIL] P30 independent state oracle: {e}",file=sys.stderr)
        sys.exit(1)
