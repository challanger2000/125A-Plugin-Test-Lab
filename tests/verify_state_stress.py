#!/usr/bin/env python3
"""Independent oracle for real VST3 process/setState/getState stress evidence.

Hard requirement: deliberately defective fixture MUST be detected for the
specified reason. A green C++ return code alone never constitutes a PASS.
"""
import argparse
from pathlib import Path
import sys

def parse(path):
    rows = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line: continue
        k,sep,v=line.partition("\t")
        assert sep and k not in rows, "malformed or duplicate evidence field"
        rows[k]=v
    assert rows.get("format")=="125A-P25-v1"
    for k in ("iterations","sample_rate","block_size","callbacks","process_failures",
              "set_failures","save_failures","save_success","torn_snapshots",
              "callback_max_ns","callback_overruns","callback_p95_ns",
              "callback_p99_ns","callback_deadline_ns","strict_realtime"):
        rows[k]=int(rows[k])
    rows["rate_sample"]=float(rows["rate_sample"])
    assert rows["callbacks"]==rows["iterations"], "not all callbacks executed"
    assert rows["save_success"]+rows["save_failures"]==500, "incomplete 500-save suite"
    assert rows["callback_max_ns"]>0, "invalid maximum callback runtime"
    assert 0 < rows["callback_p95_ns"] <= rows["callback_p99_ns"] <= rows["callback_max_ns"]
    assert rows["callback_deadline_ns"]>0
    assert rows["strict_realtime"] in (0,1)
    assert rows["sample_rate"] in (44100,48000,96000)
    assert rows["oracle"] in ("paired","ramp","none")
    assert rows["domain_correctness"] in ("PASS","FAIL","NOT_COVERED")
    return rows

def verify(path, mode):
    r=parse(path)
    if mode=="good-paired":
        assert r["oracle"]=="paired" and r["result"]=="PASS" and r["domain_correctness"]=="PASS"
        assert all(r[x]==0 for x in ("save_failures","set_failures","process_failures","torn_snapshots"))
    elif mode=="good-ramp":
        assert r["oracle"]=="ramp" and r["result"]=="PASS" and r["domain_correctness"]=="PASS"
        assert abs(r["rate_sample"]-0.125)<0.002
        assert r["save_failures"]==0 and r["process_failures"]==0
    elif mode=="bad-torn":
        assert r["oracle"]=="paired" and r["result"]=="FAIL"
        assert r["torn_snapshots"]>0, "broken fixture not detected via torn-state oracle"
    elif mode=="bad-save":
        assert r["result"]=="FAIL" and r["save_failures"]>=50, "broken save fixture missed"
    elif mode=="bad-rate":
        assert r["sample_rate"]==96000 and r["oracle"]=="ramp"
        assert r["result"]=="FAIL" and abs(r["rate_sample"]-0.125)>=0.002
    elif mode=="good-realtime":
        assert r["strict_realtime"]==1 and r["block_size"]==1024
        assert r["result"]=="PASS" and r["callback_overruns"]==0
        assert r["callback_max_ns"]<r["callback_deadline_ns"]
        assert all(r[x]==0 for x in ("save_failures","set_failures","process_failures","torn_snapshots"))
    elif mode=="bad-realtime":
        assert r["strict_realtime"]==1 and r["block_size"]==1024
        assert r["result"]=="FAIL" and r["callback_overruns"]>0
        assert r["callback_max_ns"]>r["callback_deadline_ns"]
        assert all(r[x]==0 for x in ("save_failures","set_failures","process_failures","torn_snapshots"))
        assert r["reason"]=="realtime callback deadline violated"
    else:
        raise ValueError(mode)
    print(f"[PASS] {mode}: {path} (500 saves, {r['callbacks']} process calls; "
          f"torn={r['torn_snapshots']}, rejected={r['save_failures']}, "
          f"rate_sample={r['rate_sample']:.6f})")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("report",type=Path)
    parser.add_argument("expect",choices=["good-paired","good-ramp","bad-torn","bad-save","bad-rate","good-realtime","bad-realtime"])
    args=parser.parse_args()
    try:
        verify(args.report,args.expect)
    except (AssertionError,ValueError,OSError,KeyError) as e:
        print("[FAIL] independent universal realtime/state oracle:",e,file=sys.stderr)
        raise SystemExit(1)
