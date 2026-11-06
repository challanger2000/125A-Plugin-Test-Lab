#!/usr/bin/env python3
"""ONLY the fixed QA state fixture: independent mathematical A/B references.

Never use this helper to manufacture 'golden' values for a production plugin.
Product references must be separately approved and supplied, not guessed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

MAGIC=0x125A2526
def state(bank,program):
    return struct.pack("<IiiI",MAGIC,bank,program,
                       MAGIC ^ bank ^ (program<<8))
def hash_bytes(v):
    return hashlib.sha256(v).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",required=True,type=Path)
    p.add_argument("--host",required=True,type=Path)
    p.add_argument("--states",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    bundle=a.bundle.resolve(strict=True)
    modules=[v for v in bundle.rglob("*.vst3") if v.is_file()]
    if len(modules)!=1: raise ValueError("QA fixture must have exactly one VST3 module")
    module=modules[0]
    a.out.parent.mkdir(parents=True,exist_ok=True)
    ref_a=state(11,22)
    ref_b=state(33,44)
    files={"A":a.states/"A.bin","B":a.states/"B.bin"}
    for label,expected in (("A",ref_a),("B",ref_b)):
        if files[label].read_bytes()!=expected:
            raise ValueError("known fixture state has been changed: "+label)
    manifest={
        "schema":"125a-product-dual-state-oracle-v1",
        "product":{"bundle":str(bundle),"binary":str(module),
                   "sha256":hash_bytes(module.read_bytes())},
        "host":str(a.host.resolve(strict=True)),
        "initial_states":{
            "A":{"path":str(files["A"].resolve()),"sha256":hash_bytes(ref_a)},
            "B":{"path":str(files["B"].resolve()),"sha256":hash_bytes(ref_b)}
        },
        "reference":{
            "expected_saved_sha256":{"A":hash_bytes(ref_a),"B":hash_bytes(ref_b)},
            "expected_pcm":{"A_first_pcm":0.25,"A_second_pcm":0.25,
                            "B_first_pcm":0.125,"B_second_pcm":0.125},
            "abs_tolerance":0.000001
        }
    }
    a.out.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("[PASS] separately defined QA state/PCM expectations and exact module fingerprint")
if __name__=="__main__":
    main()
