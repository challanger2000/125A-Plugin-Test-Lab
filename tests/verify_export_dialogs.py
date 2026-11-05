#!/usr/bin/env python3
"""P10 independent host-evidence integrity and negative control.

Native HWND discovery and dialog closing are done in the real Windows host
without hooks in product code. This separate script verifies that *all four*
supported export menu choices completed and never created a MIDI/WAV file.
"""
from pathlib import Path
import sys

SCENARIOS = ("PATTERN MIDI", "PATTERN WAV", "SONG MIDI", "SONG WAV")


def check(folder: Path) -> None:
    found = sorted(p.name for p in folder.iterdir() if p.is_file())
    required = sorted(f"cancel-{i}.ok" for i in range(4))
    assert found == required, f"unexpected/missing P10 evidence: {found} != {required}"
    for i, name in enumerate(SCENARIOS):
        path = folder / f"cancel-{i}.ok"
        expected = f"{name}: OS modal opened and canceled; component state byte-identical\n"
        assert path.read_text(encoding="utf-8") == expected, (
            f"{path.name}: invalid native dialog evidence"
        )
    assert not list(folder.glob("*.mid")) and not list(folder.glob("*.wav")), (
        "A canceled export created output!"
    )

    # Independent negative control: a missing scenario must not be passed.
    negative = set(found)
    negative.remove("cancel-3.ok")
    assert sorted(negative) != required, "P10 false positive in completeness oracle"
    print("[PASS] P10 independent 4/4 native dialog cancellation evidence "
          "and missing-case negative control")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: verify_export_dialogs.py <evidence-directory>")
    try:
        check(Path(sys.argv[1]))
    except (AssertionError, OSError, UnicodeError) as e:
        print(f"[FAIL] P10 independent export dialog oracle: {e}", file=sys.stderr)
        sys.exit(1)
