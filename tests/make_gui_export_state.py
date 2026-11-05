#!/usr/bin/env python3
"""P11 synthetic, rights-free DM18 pattern/song GUI export fixture.

Converts an existing proven P03 one-shot kit into A -> REST -> A,
retaining its original synthetic sample and 0% swing. No product code.
"""
import pathlib
import struct
import sys


def make(src: pathlib.Path, dst: pathlib.Path) -> None:
    b = bytearray(src.read_bytes())
    assert b[:4] == b"DM18" and len(b) > 4096
    assert struct.unpack_from("<I", b, 4)[0] == len(b) - 8
    payload = memoryview(b)[8:-4]
    crc = 2166136261
    for byte in payload:
        crc = (crc ^ byte) * 16777619 & 0xFFFFFFFF
    assert struct.unpack_from("<I", b, len(b) - 4)[0] == crc, "source CRC"
    settings = 6 + 16 * 5
    assert b[8 + settings] == 0, "expected zero Swing"
    assert b[8 + settings + 1] == 0, "expected zero Humanize"
    b[8 + settings + 2] = 1  # songEnabled ON
    b[8 + settings + 3] = 3  # chain count 3
    base = 8 + settings + 4
    b[base:base + 6] = bytes([0, 16, 8, 16, 0, 16])
    crc = 2166136261
    for byte in b[8:-4]:
        crc = (crc ^ byte) * 16777619 & 0xFFFFFFFF
    struct.pack_into("<I", b, len(b) - 4, crc)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b)
    print(f"[PASS] P11 generated A/REST/A GUI export kit: {len(b)} bytes, FNV32={crc:08x}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: make_gui_export_state.py <source_DM18> <output_DM18>")
    make(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
