#!/usr/bin/env python3
"""Generate CI-only synthetic Drumator DM18 project states.

No bundled third-party samples: we synthesize a short mono PCM16 constant
signal. A fixed one-step pattern (step 3: zero-based 2) is used so Swing can
be tested using an independent musical oracle.
This codec fixture targets the pinned Drumator commit, not arbitrary vendors.
"""
import argparse
import pathlib
import struct
import wave

ROWS = 16
PATTERNS = 8
STEPS = 32
CELLS = ROWS * PATTERNS * STEPS


def pcm16_wav() -> bytes:
    # Standard-library wave cannot reliably write to immutable buffers;
    # compose a conventional 44-byte PCM16 mono RIFF header directly.
    frames = 1024
    sample = 16384  # 0.5 amplitude, safely below clipping.
    data = struct.pack("<h", sample) * frames
    fmt = struct.pack("<HHIIHH", 1, 1, 44100, 44100 * 2, 2, 16)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE" +
            b"fmt " + struct.pack("<I", len(fmt)) + fmt +
            b"data" + struct.pack("<I", len(data)) + data)


def encode(swing: int) -> bytes:
    assert swing in (0, 50)
    b = bytearray()
    b += struct.pack("<BBHH", 0, 8, 0, 0)  # selected, visible, mute, solo
    b += bytes([100]) * ROWS  # per-row volume
    b += bytes([100]) * ROWS  # per-row pan (center)
    b += bytes([24]) * ROWS   # neutral pitch
    b += bytes(ROWS)         # choke groups disabled
    b += bytes(ROWS)         # all MAIN
    b += struct.pack("<BBBB", swing, 0, 0, PATTERNS)  # swing, humanize, song, chain count
    for entry in range(64):
        b += struct.pack("<BB", entry if entry < PATTERNS else 0, 32)
    b += struct.pack("<B", 100)  # master level
    b += bytes(ROWS)             # no randomized velocity

    grid = bytearray(CELLS)
    grid[2] = 127  # pattern A, Kick row (0), musical step 3 (16th offset 2)
    b += grid

    synthetic = pcm16_wav()
    for row in range(ROWS):
        name = b"P03-synthetic-kick.wav" if row == 0 else b""
        sound = synthetic if row == 0 else b""
        b += struct.pack("<HI", len(name), len(sound))
        b += name + sound

    b += bytes(ROWS)          # no user display-name overrides
    b += bytes([16]) * PATTERNS  # one-bar patterns
    for _ in range(ROWS):
        b += struct.pack("<IIII f", 0, 0, 0, 0, 1.0)  # untouched sample editor
    b += struct.pack("<HB", 1, 0)  # song start=bar 1, limiter OFF

    checksum = 2166136261
    for value in b:
        checksum ^= value
        checksum = (checksum * 16777619) & 0xFFFFFFFF
    return b"DM18" + struct.pack("<I", len(b) + 4) + b + struct.pack("<I", checksum)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for swing in (0, 50):
        path = args.output_dir / f"Drumator-Swing-{swing}.bin"
        contents = encode(swing)
        path.write_bytes(contents)
        print(f"[INFO] {path.name}: {len(contents)} bytes, swing={swing}%")


if __name__ == "__main__":
    main()
