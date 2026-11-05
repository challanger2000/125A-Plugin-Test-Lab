#!/usr/bin/env python3
"""P34 native capture manifest generator for disposable Windows fixtures."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--host", required=True, type=Path)
p.add_argument("--bundle", required=True, type=Path)
p.add_argument("--out", required=True, type=Path)
a = p.parse_args()
modules = [x for x in a.bundle.rglob("*.vst3") if x.is_file()]
if len(modules) != 1:
    raise SystemExit("P34 expected exactly one VST3 module in bundle")
module = modules[0].resolve()
m = {"schema": "125a-p34-capture-v1",
     "product": {"binary": str(module), "sha256": hashlib.sha256(module.read_bytes()).hexdigest()},
     "host": str(a.host.resolve())}
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
print("[PASS] P34 real VST3 capture manifest pinned")
