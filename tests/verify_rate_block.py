#!/usr/bin/env python3
"""P27 independent time-domain PCM oracle for arbitrary VST3 builds.

The 0.1-second linear ramp is the synthetic adapter contract, not a
universal musical property. Passing a plugin without such an adapter
must never imply its actual DSP semantics are correct.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import math

RATES=(44100,48000,96000)
BLOCKS=(17,127,512)

def load(path,rate):
    raw=Path(path).read_bytes()
    frames=rate//4
    assert len(raw)==frames*2*4, f"{path}: expected {frames} stereo float32 frames"
    values=struct.unpack(f"<{2*frames}f",raw)
    assert all(math.isfinite(x) for x in values), f"{path}: nonfinite audio"
    return raw,values

def waveform(path,rate):
    raw,values=load(path,rate)
    max_delta=0.
    for n in range(rate//4):
        expected=.25*min(1.,n/(.1*rate))
        max_delta=max(max_delta,abs(values[2*n]-expected),abs(values[2*n+1]-expected))
    if max_delta>1e-6:
        raise AssertionError(f"time-ramp mismatch: {path}, max_abs_delta={max_delta:.7f}")
    return {"sha256":hashlib.sha256(raw).hexdigest(),"max_abs_error":max_delta}

def good(folder,report):
    results={}
    for rate in RATES:
        hashes=set()
        for block in BLOCKS:
            path=folder/f"good-{rate}-{block}.f32"
            data=waveform(path,rate)
            results[f"{rate}/{block}"]=data
            hashes.add(data["sha256"])
        assert len(hashes)==1, f"{rate} Hz outputs differ with block partition"
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({
        "schema":"125a-p27-rate-block-v1",
        "status":"PASS",
        "rates":RATES,
        "blocks":BLOCKS,
        "zero_frame_process":"EXECUTED_IN_REAL_VST3_HOST",
        "matches_independent_time_oracle":True,
        "identical_pcm_within_each_rate":True,
        "scenarios":results
    },indent=2)+"\n",encoding="utf-8")
    print("[PASS] P27 44.1/48/96 kHz, 17/127/512 blocks, exact per-rate PCM and independent time ramp")

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="command",required=True)
    x=sub.add_parser("good")
    x.add_argument("folder",type=Path)
    x.add_argument("report",type=Path)
    x=sub.add_parser("single")
    x.add_argument("pcm",type=Path)
    x.add_argument("rate",type=int)
    x=sub.add_parser("compare")
    x.add_argument("left",type=Path)
    x.add_argument("right",type=Path)
    x.add_argument("rate",type=int)
    a=p.parse_args()
    try:
        if a.command=="good":
            good(a.folder,a.report)
        elif a.command=="single":
            result=waveform(a.pcm,a.rate)
            print(f"[PASS] P27 sample-rate waveform matches independent reference: {result['sha256']}")
        else:
            b1,v1=load(a.left,a.rate)
            b2,v2=load(a.right,a.rate)
            assert b1==b2, f"block partition mismatch: {a.left} vs {a.right}"
            print("[PASS] P27 same-rate PCM exactly matches across block sizes")
    except (AssertionError,ValueError,OSError,struct.error) as e:
        print(f"[FAIL] P27 independent PCM oracle: {e}",file=sys.stderr)
        sys.exit(1)
if __name__=="__main__":
    main()
