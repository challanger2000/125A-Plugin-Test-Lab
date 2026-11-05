#!/usr/bin/env python3
"""P26 product-independent executor of a separate domain/state/audio oracle."""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys

def verify(adapter_path, evidence):
    cfg=json.loads(Path(adapter_path).read_text(encoding="utf-8"))
    assert cfg.get("schema")=="125a-recovery-adapter-v1"
    expected=cfg["expected_sha256"]
    for filename,digest in expected.items():
        value=(evidence/filename).read_bytes()
        actual=hashlib.sha256(value).hexdigest()
        if actual!=digest:
            raise AssertionError(f"{filename}: state mismatch after failed action or recovery")
    for filename,want in cfg["expected_audio_f32"].items():
        audio=(evidence/filename).read_bytes()
        assert len(audio)==128*4, f"{filename}: missing/short audio"
        samples=struct.unpack("<128f",audio)
        tol=float(cfg["audio_tolerance"])
        assert all(math.isfinite(v) for v in samples), f"{filename}: nonfinite samples"
        if any(abs(sample-float(want))>tol for sample in samples):
            raise AssertionError(f"{filename}: PCM mismatch, expected {want} ±{tol}")
    print("[PASS] P26 valid A -> rejected invalid with rollback -> valid B -> restore A; state hashes and all 512 PCM samples exact")

if __name__=="__main__":
    if len(sys.argv)!=3:
        sys.exit("Usage: verify_recovery_adapter.py <adapter.json> <evidence-dir>")
    try:
        verify(Path(sys.argv[1]),Path(sys.argv[2]))
    except (AssertionError,ValueError,KeyError,FileNotFoundError,TypeError) as e:
        print("[FAIL] P26 independent recovery/rollback oracle:",e,file=sys.stderr)
        sys.exit(1)
