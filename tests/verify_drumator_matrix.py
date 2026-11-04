#!/usr/bin/env python3
"""P05 independent DAW transport / host-buffer partition timing oracle.

The musical reference uses rational quarter-note fractions (not Drumator's
step scheduler): an eighth offbeat is 1/2 quarter at 0% swing, 7/12 at
25%, 2/3 at 50%. Each pattern repeats every four quarter notes.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import pathlib
import sys
import wave
from fractions import Fraction

RATE = 44100
BPM = (90, 120, 150)
SWING = (0, 25, 50)
BLOCKS = (64, 127, 512, 1024)
BARS = 4
THRESHOLD = int(0.03 * 8388607)


def decode(path: pathlib.Path, bpm: int):
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        expected_frames = RATE * 60 * 4 * BARS // bpm
        assert RATE * 60 % bpm == 0, "bpm is not sample-exact"
        assert wav.getframerate() == RATE, "wrong output sample rate"
        assert wav.getnchannels() == 2 and wav.getsampwidth() == 3, \
            "not stereo PCM24"
        assert wav.getcomptype() == "NONE", "compressed WAV not allowed"
        assert frames == expected_frames, (
            f"incorrect total audio frames {frames} != {expected_frames}"
        )
        pcm = wav.readframes(frames)
        assert not wav.readframes(1), "unexpected extra frames"
        assert len(pcm) == frames * 6, "truncated audio"

    hits = []
    was_active = False
    max_sample = 0
    for frame in range(frames):
        offset = frame * 6
        left = int.from_bytes(pcm[offset:offset + 3], "little", signed=True)
        right = int.from_bytes(pcm[offset + 3:offset + 6], "little", signed=True)
        peak = max(abs(left), abs(right))
        max_sample = max(max_sample, peak)
        active = peak >= THRESHOLD
        if active and not was_active:
            hits.append(frame)
        was_active = active
    assert max_sample >= 838860, f"silence/inaudible output: peak={max_sample}"
    assert len(hits) == BARS, f"expected four distinct hits, found {hits}"
    return pcm, hits


def verify(root: pathlib.Path):
    report = {"scenarios": [], "overall": "FAIL"}
    for bpm, swing in itertools.product(BPM, SWING):
        quarter = Fraction(RATE * 60, bpm)
        offbeat = Fraction(1, 2) + Fraction(swing, 300)
        expected = [
            math.ceil(quarter * (4 * bar + offbeat))
            for bar in range(BARS)
        ]
        reference_pcm = None
        reference_hash = None
        for block in BLOCKS:
            path = root / f"bpm{bpm}-swing{swing}-block{block}.wav"
            assert path.exists(), f"missing expected render {path}"
            pcm, hits = decode(path, bpm)
            assert all(abs(actual - target) <= 1 for actual, target in zip(hits, expected)), (
                f"{path.name}: detected offbeats {hits}, independently expected {expected}"
            )
            digest = hashlib.sha256(pcm).hexdigest()
            if reference_pcm is None:
                reference_pcm = pcm
                reference_hash = digest
            else:
                assert pcm == reference_pcm, (
                    f"{path.name}: audio depends on host block size "
                    f"(expected SHA256 {reference_hash}, got {digest})"
                )
            report["scenarios"].append({
                "bpm": bpm,
                "swing": swing,
                "block": block,
                "expected_onsets": expected,
                "observed_onsets": hits,
                "audio_sha256": digest,
                "result": "PASS",
            })
            print(f"[PASS] {path.name} onsets={hits} sha256={digest[:16]}")
    report["overall"] = "PASS"
    report["count"] = len(report["scenarios"])
    report_path = root.parent / "p05-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] P05: {len(report['scenarios'])} real Drumator VST3 scenarios "
          "(3 BPM x 3 swing x 4 process block sizes), independent onsets "
          "and bit-exact block-partition equivalence")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: verify_drumator_matrix.py <wav-directory>", file=sys.stderr)
        raise SystemExit(2)
    try:
        verify(pathlib.Path(sys.argv[1]))
    except (AssertionError, ValueError, OSError, wave.Error) as error:
        print(f"[FAIL] P05 independent matrix oracle: {error}", file=sys.stderr)
        raise SystemExit(1)
