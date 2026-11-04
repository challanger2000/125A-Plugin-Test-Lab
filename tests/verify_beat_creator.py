#!/usr/bin/env python3
"""Independent P07 Beat Creator structure, musical role and mutation oracle.

The byte fixture protocol is documented here; no product Beat Creator
implementation is imported. A/B/C must be distinct, C a late break,
and CHH/OHH must never collide on the same step.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

ROWS = 16
STEPS = 32
PATTERN_BYTES = ROWS * STEPS
HEADER = b"125ABC01"
COUNT = 10 * 2 * 2 * 32


class Rejected(ValueError):
    pass


def check(value: bool, text: str) -> None:
    if not value:
        raise Rejected(text)


def note(pattern: bytes, row: int, step: int) -> int:
    return pattern[row * STEPS + step]


def validate(contents: bytes, style: int, steps: int, complexity: int) -> dict:
    check(len(contents) == 12 + 3 * PATTERN_BYTES, "invalid ABC fixture byte length")
    check(contents[:8] == HEADER, "wrong ABC fixture magic")
    actual_style, actual_complexity, actual_steps, reserved = contents[8:12]
    check((actual_style, actual_complexity, actual_steps, reserved) ==
          (style, complexity, steps, 0), "wrong ABC fixture metadata")
    abc = [
        contents[12 + p * PATTERN_BYTES:12 + (p + 1) * PATTERN_BYTES]
        for p in range(3)
    ]
    a, b, c = abc
    counts = []
    for name, pattern in zip(("A", "B", "C"), abc):
        check(all(v <= 127 for v in pattern), f"{name}: invalid velocity > 127")
        check(all(note(pattern, row, step) == 0
                  for row in range(8, ROWS) for step in range(STEPS)),
              f"{name}: changed protected user rows 9–16")
        check(all(note(pattern, row, step) == 0
                  for row in range(8) for step in range(steps, STEPS)),
              f"{name}: nonzero note outside chosen pattern length")
        check(all(not (note(pattern, 2, step) and note(pattern, 3, step))
                  for step in range(steps)),
              f"{name}: open and closed hi-hat collision")
        kick = sum(bool(note(pattern, 0, step)) for step in range(steps))
        snare = sum(bool(note(pattern, 1, step)) for step in range(steps))
        check(kick > 0 and snare > 0, f"{name}: missing basic kick/snare groove")
        counts.append((kick, snare))
    b_changes = [(row, step) for row in range(8) for step in range(steps)
                 if note(a, row, step) != note(b, row, step)]
    check(len(b_changes) >= 2, "B is not a musically meaningful variation")
    check(any(step < min(12, steps - 4) for row, step in b_changes),
          "B changes only the end; no early variation")

    c_changes = [(row, step) for row in range(8) for step in range(steps)
                 if note(a, row, step) != note(c, row, step)]
    check(c_changes, "C does not differ from base A")
    check(all(step >= steps - 8 for row, step in c_changes),
          "C changed the groove before the intended final eight-step break")

    return {
        "a_kick_snare": counts[0],
        "b_kick_snare": counts[1],
        "c_kick_snare": counts[2],
        "b_changes": len(b_changes),
        "c_changes": len(c_changes),
        "crash": int(any(note(a, 6, s) for s in range(steps))),
        "distinct": len({a, b, c}),
    }


def reject_mutation(data: bytes, style: int, steps: int, complexity: int,
                    name: str) -> None:
    try:
        validate(data, style, steps, complexity)
    except Rejected:
        print(f"[PASS] P07 independent oracle rejects {name}")
        return
    raise Rejected(f"independent oracle accepted broken vector: {name}")


def run(directory: pathlib.Path) -> None:
    styles = collections.defaultdict(lambda: collections.Counter())
    sample = None
    total = 0
    for style in range(10):
        for steps in (16, 32):
            for complexity in (35, 100):
                for seed in range(32):
                    path = directory / (
                        f"style{style}-steps{steps}-complexity{complexity}-seed{seed}.abc"
                    )
                    check(path.is_file(), f"missing vector {path.name}")
                    source = path.read_bytes()
                    result = validate(source, style, steps, complexity)
                    check(result["distinct"] == 3, "A/B/C not mutually distinct")
                    stats = styles[(style, steps, complexity)]
                    stats["cases"] += 1
                    stats["a_crash"] += result["crash"]
                    stats["b_changes"] += result["b_changes"]
                    stats["c_changes"] += result["c_changes"]
                    total += 1
                    if (style, steps, complexity, seed) == (0, 16, 35, 0):
                        sample = source
    check(total == COUNT, f"expected {COUNT} full A/B/C vectors, got {total}")
    check(sample is not None, "negative test source missing")

    for (style, steps, complexity), stats in styles.items():
        check(stats["cases"] == 32, "style coverage incomplete")
        check(stats["a_crash"] >= 1,
              f"style {style}: no Crash used across 32 generator seeds")
        print(f"[PASS] style {style}, {steps} steps, complexity={complexity}: "
              f"32 seeds, crash seeds={stats['a_crash']}, "
              f"B differences={stats['b_changes']}, C differences={stats['c_changes']}")

    wrong_header = bytearray(sample)
    wrong_header[0] ^= 1
    reject_mutation(bytes(wrong_header), 0, 16, 35, "wrong fixture magic")
    hidden = bytearray(sample)
    hidden[12 + 8 * STEPS + 0] = 127
    reject_mutation(bytes(hidden), 0, 16, 35, "notes in protected row 9")
    invalid_velocity = bytearray(sample)
    invalid_velocity[12 + 0 * STEPS + 0] = 255
    reject_mutation(bytes(invalid_velocity), 0, 16, 35, "velocity outside MIDI 1..127")
    improper_c = bytearray(sample)
    improper_c[12 + 2 * PATTERN_BYTES + 0] ^= 1
    reject_mutation(bytes(improper_c), 0, 16, 35, "C modifying a non-break step")
    metadata = bytearray(sample)
    metadata[9] = 100
    reject_mutation(bytes(metadata), 0, 16, 35, "wrong complexity metadata")

    result = directory.parent / "p07-beat-creator-report.json"
    report = {
        "status": "PASS",
        "vector_count": total,
        "styles": 10,
        "pattern_lengths": [16, 32],
        "complexities": [35, 100],
        "seeds_per_case": 32,
        "style_stats": [
            {"style": style, "steps": steps, "complexity": complexity, **dict(stats)}
            for (style, steps, complexity), stats in sorted(styles.items())
        ],
        "negative_mutations_rejected": 5,
    }
    result.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] P07: {total} independent A/B/C pattern verifications, "
          "10 styles, Crash coverage, B/C variation, hi-hat exclusivity, "
          "protected rows and five deliberate corruptions")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: verify_beat_creator.py <abc-vectors-dir>", file=sys.stderr)
        raise SystemExit(2)
    try:
        run(pathlib.Path(sys.argv[1]))
    except (Rejected, OSError, ValueError) as error:
        print(f"[FAIL] P07 independent Beat Creator oracle: {error}",
              file=sys.stderr)
        raise SystemExit(1)
