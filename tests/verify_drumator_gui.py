#!/usr/bin/env python3
"""P09 true product GUI action oracle: inspect processor's own DM18 snapshots.

A real Windows VST3 editor receives mouse events, no direct calls into
Drumator's Beat Creator engine. A separate VST3 component serializes itself
before CANCEL, after CANCEL, and after APPLY. This parser independently checks
observable project state transitions; product code is not imported.
"""
from __future__ import annotations

import json
import pathlib
import sys

HEADER = b"DM18"
GRID_OFFSET = 8 + 6 + 16 * 5 + 4 + 64 * 2 + 1 + 16
ROWS = 16
STEPS = 32
PATTERNS = 8
PATTERN_BYTES = ROWS * STEPS
GRID_LENGTH = PATTERN_BYTES * PATTERNS


class Failed(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def state(path: pathlib.Path):
    data = path.read_bytes()
    require(len(data) >= GRID_OFFSET + GRID_LENGTH + 4,
            f"{path.name}: VST3 component state truncated")
    require(data[:4] == HEADER, f"{path.name}: not DM18 state")
    length = int.from_bytes(data[4:8], "little")
    require(length == len(data) - 8,
            f"{path.name}: component state length mismatched")
    crc = 2166136261
    for item in data[8:-4]:
        crc ^= item
        crc = (crc * 16777619) & 0xFFFFFFFF
    require(crc == int.from_bytes(data[-4:], "little"),
            f"{path.name}: corrupted DM18 state checksum")
    raw = data[GRID_OFFSET:GRID_OFFSET + GRID_LENGTH]
    grid = [raw[i * PATTERN_BYTES:(i + 1) * PATTERN_BYTES]
            for i in range(PATTERNS)]
    return data, grid


def note(pattern: bytes, row: int, step: int) -> int:
    return pattern[row * STEPS + step]


def verify(before: pathlib.Path, canceled: pathlib.Path,
           applied: pathlib.Path) -> None:
    baseline, old = state(before)
    canceled_bytes, canceled_grid = state(canceled)
    changed_bytes, new = state(applied)

    require(baseline == canceled_bytes,
            "GUI CANCEL unexpectedly changed Drumator component state")
    require(old == canceled_grid,
            "GUI CANCEL unexpectedly changed existing step grid")
    require(baseline != changed_bytes,
            "GUI GENERATE/APPLY failed to change any component state")

    summary = {"status": "PASS", "actions": ["open", "generate", "cancel",
               "reopen", "generate", "apply"], "patterns": []}
    for pat in range(3):
        original = old[pat]
        updated = new[pat]
        changed = sum(a != b for a, b in zip(original, updated))
        kick = sum(note(updated, 0, i) > 0 for i in range(STEPS))
        snare = sum(note(updated, 1, i) > 0 for i in range(STEPS))
        require(changed > 0, f"pattern {'ABC'[pat]} unchanged after GUI APPLY")
        require(kick > 0 and snare > 0,
                f"pattern {'ABC'[pat]} missing generated kick or snare")
        require(all(note(updated, row, step) == note(original, row, step)
                    for row in range(8, ROWS) for step in range(STEPS)),
                f"pattern {'ABC'[pat]} edited protected rows 9–16")
        require(all(not (note(updated, 2, step) and note(updated, 3, step))
                    for step in range(STEPS)),
                f"pattern {'ABC'[pat]} has overlapping OHH+CHH")
        summary["patterns"].append({
            "pattern": "ABC"[pat], "changed_cells": changed,
            "kick_hits": kick, "snare_hits": snare
        })
    require(len({new[0], new[1], new[2]}) == 3,
            "GUI Beat Creator A/B/C are not distinct")
    for pat in range(3, PATTERNS):
        require(new[pat] == old[pat],
                f"GUI Beat Creator changed unselected pattern {'ABCDEFGH'[pat]}")

    print("[PASS] P09 actual Drumator VST3 GUI: mouse GENERATE/CANCEL"
          " preserved all project state")
    print("[PASS] P09 actual Drumator VST3 GUI: GENERATE/APPLY changed"
          " A/B/C to distinct valid drum patterns")
    print("[PASS] P09 untouched patterns D-H, protected rows 9-16"
          " and CHH/OHH exclusivity")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: verify_drumator_gui.py <before.bin> <canceled.bin> <applied.bin>",
              file=sys.stderr)
        raise SystemExit(2)
    try:
        verify(*(pathlib.Path(p) for p in sys.argv[1:]))
    except (Failed, ValueError, OSError) as error:
        print(f"[FAIL] P09 real Drumator GUI oracle: {error}", file=sys.stderr)
        raise SystemExit(1)
