#!/usr/bin/env python3
"""P20: deterministic corrupt DM18 VST3 project states; never imports product code."""
from __future__ import annotations
import hashlib
import pathlib
import struct
import sys

def make(src: pathlib.Path, dest: pathlib.Path) -> int:
    original = src.read_bytes()
    assert len(original) > 4096 and original[:4] == b"DM18"
    assert struct.unpack_from("<I", original, 4)[0] == len(original) - 8
    before = hashlib.sha256(original).hexdigest()
    dest.mkdir(parents=True, exist_ok=True)
    cases: dict[str, bytes] = {}
    for i in range(12):
        pos = 8 + ((i + 1) * (len(original) - 12)) // 13
        changed = bytearray(original)
        changed[pos] ^= 1 << (i % 8)
        cases[f"payload-{i:02d}.bin"] = bytes(changed)
    for name, index in [("magic.bin", 0), ("length.bin", 4), ("checksum.bin", len(original)-1)]:
        changed = bytearray(original)
        changed[index] ^= 0x01
        cases[name] = bytes(changed)
    cases["truncated.bin"] = original[:len(original)//2]
    assert len(cases) == 16
    for name, content in cases.items():
        assert content != original, name
        (dest / name).write_bytes(content)
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    print(f"[PASS] P20 generated {len(cases)} distinct invalid project states without changing input")
    return len(cases)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: make_invalid_state_matrix.py <valid DM18> <output dir>")
    try:
        make(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
    except (AssertionError, OSError, ValueError) as error:
        print(f"[FAIL] P20 fixture generation: {error}", file=sys.stderr)
        sys.exit(1)
