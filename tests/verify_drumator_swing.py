#!/usr/bin/env python3
"""Independent timing check against the real Drumator VST3 output.

One one-bar pattern contains a single offbeat eighth-note on step 3
(zero-based 16th-step 2), played from a synthetic 1024-frame PCM16 sample.
At 120 BPM the musical onset is 11025 frames (0% swing) or 14700 frames
(50% swing, 2:1 triplet eighth feel). No plugin scheduling code is imported.
"""
import argparse
import math
import pathlib
import sys
import wave

RATE = 44100
BPM = 120
BARS = 4
BEATS_PER_BAR = 4
FRAMES_PER_BAR = RATE * 60 * BEATS_PER_BAR // BPM
TOTAL_FRAMES = FRAMES_PER_BAR * BARS
THRESHOLD = 0.03


def unpack_24(value: bytes) -> int:
    return int.from_bytes(value, byteorder="little", signed=True)


def onsets(path: pathlib.Path) -> list[int]:
    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 2, "not stereo"
        assert w.getsampwidth() == 3, "not 24-bit PCM"
        assert w.getframerate() == RATE, "wrong sample rate"
        assert w.getnframes() == TOTAL_FRAMES, "wrong number of frames"
        data = w.readframes(TOTAL_FRAMES)
        assert not w.readframes(1), "unexpected extra audio frames"
    assert len(data) == TOTAL_FRAMES * 6, "truncated or excess PCM bytes"

    detected = []
    previous_active = False
    max_peak = 0.0
    for n in range(TOTAL_FRAMES):
        left = unpack_24(data[n * 6:n * 6 + 3]) / 8388607.
        right = unpack_24(data[n * 6 + 3:n * 6 + 6]) / 8388607.
        peak = max(abs(left), abs(right))
        max_peak = max(max_peak, peak)
        is_active = peak >= THRESHOLD
        if is_active and not previous_active:
            detected.append(n)
        previous_active = is_active
    assert max_peak >= 0.1, f"no meaningful audible sound (peak={max_peak:.6f})"
    assert len(detected) == BARS, (
        f"expected {BARS} distinct offbeat hits, found {len(detected)}: {detected}"
    )
    return detected


def verify(straight: pathlib.Path, swung: pathlib.Path) -> None:
    zero = onsets(straight)
    half = onsets(swung)
    quarter_frames = RATE * 60 // BPM
    straight_beat = quarter_frames // 2
    triplet_beat = quarter_frames * 2 // 3
    expected_shift = triplet_beat - straight_beat  # 3675 samples, not arbitrary
    observed = []
    for bar, (start0, start50) in enumerate(zip(zero, half)):
        expected0 = bar * FRAMES_PER_BAR + straight_beat
        expected50 = bar * FRAMES_PER_BAR + triplet_beat
        # Allow a short equal attack/fade threshold delay, but never a wrong
        # rhythm position; the DELTA must be within four source frames.
        assert 0 <= start0 - expected0 <= 256, (
            f"bar {bar} straight onset {start0}, expected near {expected0}"
        )
        assert 0 <= start50 - expected50 <= 256, (
            f"bar {bar} swung onset {start50}, expected near {expected50}"
        )
        diff = start50 - start0
        assert abs(diff - expected_shift) <= 4, (
            f"bar {bar} swing shift {diff}, expected {expected_shift} samples"
        )
        observed.append(diff)
    print(f"[PASS] P03 real Drumator VST3: 4 independent audible offbeats per scenario")
    print(f"[PASS] straight={zero}; swing50={half}")
    print(f"[PASS] 50% swing moved offbeats by {observed} samples "
          f"(musical 2:1 triplet reference = {expected_shift})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("straight", type=pathlib.Path)
    parser.add_argument("swing50", type=pathlib.Path)
    opts = parser.parse_args()
    try:
        verify(opts.straight, opts.swing50)
    except (OSError, AssertionError, ValueError, wave.Error) as exc:
        print(f"[FAIL] P03 independent oracle: {exc}", file=sys.stderr)
        raise SystemExit(1)
