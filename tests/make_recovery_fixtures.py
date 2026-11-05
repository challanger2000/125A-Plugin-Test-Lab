#!/usr/bin/env python3
"""P26 independent adapter fixture; no production VST3 implementation imports."""
from pathlib import Path
import hashlib
import json
import struct
import sys

MAGIC=0x125A2526

def state(bank,program):
    return struct.pack("<IiiI", MAGIC,bank,program,
                       MAGIC ^ bank ^ (program<<8))

def write(out):
    out.mkdir(parents=True,exist_ok=True)
    a=state(11,22);b=state(33,44)
    bad=bytearray(a);bad[15]^=1
    paths={"A":a,"B":b,"invalid":bytes(bad)}
    for name,blob in paths.items():
        (out/f"{name}.bin").write_bytes(blob)
    adapter={
        "schema":"125a-recovery-adapter-v1",
        "oracle":"fixture-state-pcm",
        "expected_sha256":{
           "state-before.bin":hashlib.sha256(a).hexdigest(),
           "state-after-error.bin":hashlib.sha256(a).hexdigest(),
           "state-after-recovery.bin":hashlib.sha256(b).hexdigest(),
           "state-after-restore.bin":hashlib.sha256(a).hexdigest()
        },
        "expected_audio_f32":{
           "audio-before.f32":0.25,
           "audio-after-error.f32":0.25,
           "audio-after-recovery.f32":0.125,
           "audio-after-restore.f32":0.25
        },
        "audio_tolerance":1e-7,
        "source":"independent fixture contract, not production internal state"
    }
    (out/"adapter.json").write_text(json.dumps(adapter,indent=2)+"\n",encoding="utf-8")
    print("[PASS] P26 independent state and PCM recovery adapter written")

if __name__=="__main__":
    if len(sys.argv)!=2: sys.exit("Usage: make_recovery_fixtures.py <outdir>")
    write(Path(sys.argv[1]))
