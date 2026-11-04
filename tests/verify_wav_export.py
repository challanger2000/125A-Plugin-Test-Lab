#!/usr/bin/env python3
"""P08 independent PCM24 WAV export / MIDI-to-WAV agreement oracle.

Product code is not imported. The already independently validated P06
Standard MIDI Files define note start ticks, converted using MIDI PPQ and
tempo. The real offline WAV exporter must agree with that musical timeline,
preserve stereo polarity, and write the exact bar count at 48 kHz.
"""
from __future__ import annotations

import io
import json
import math
import pathlib
import sys
import wave
from fractions import Fraction

from verify_midi_export import parse, validate as validate_midi

RATE = 48000
THRESHOLD = int(0.03 * 8388607)


class Rejected(ValueError):
    pass


def check(ok: bool, message: str) -> None:
    if not ok:
        raise Rejected(message)


def pcm24(sample: bytes) -> int:
    return int.from_bytes(sample, "little", signed=True)


def analyse_wave(data: bytes, bpm: int, mode: str, expected_ticks: list[int]):
    with wave.open(io.BytesIO(data), "rb") as wav:
        count = wav.getnframes()
        step_count = 16 if mode == "pattern" else 48
        expected_frames = round(Fraction(step_count * RATE * 15, bpm))
        check(wav.getframerate() == RATE, "WAV sample rate is not 48 kHz")
        check(wav.getnchannels() == 2 and wav.getsampwidth() == 3,
              "WAV is not stereo PCM24")
        check(wav.getcomptype() == "NONE", "WAV is compressed")
        check(count == expected_frames,
              f"incorrect WAV export duration: {count} != {expected_frames}")
        audio = wav.readframes(count)
        check(not wav.readframes(1), "WAV contains unexpected extra frames")
        check(len(audio) == count * 6, "incomplete PCM24 audio")
    hits = []
    active_before = False
    peak_max = 0
    for i in range(count):
        b = 6 * i
        l = pcm24(audio[b:b + 3])
        r = pcm24(audio[b + 3:b + 6])
        peak = max(abs(l), abs(r))
        peak_max = max(peak_max, peak)
        active_now = peak >= THRESHOLD
        if active_now and not active_before:
            hits.append(i)
        active_before = active_now
    check(peak_max >= 100000, "WAV was silent or nearly silent")
    expected = [
        math.ceil(Fraction(tick * RATE * 60, 960 * bpm))
        for tick in expected_ticks
    ]
    check(len(hits) == len(expected),
          f"Wrong number of exported WAV attacks: {hits} != {expected}")
    for i, (hit, musical) in enumerate(zip(hits, expected)):
        check(abs(hit - musical) <= 96,
              f"WAV onset {i} at {hit}, MIDI musical onset is {musical}")
        # L positive and R negative in the test source: detects lost stereo,
        # a collapsed mono stream, and an L/R polarity/channel swap.
        at = hit + 20
        check(at < count, "WAV attack near EOF")
        off = at * 6
        left = pcm24(audio[off:off + 3])
        right = pcm24(audio[off + 3:off + 6])
        check(left > 10000 and right < -10000,
              f"stereo source signature lost: L={left}, R={right}")
        check(abs(right) > 1.2 * abs(left),
              "stereo amplitude relationship is reversed")
    return hits, expected, count, peak_max


def expect_rejected(data: bytes, bpm: int, mode: str, ticks: list[int],
                    reason: str) -> None:
    try:
        analyse_wave(data, bpm, mode, ticks)
    except (Rejected, EOFError, wave.Error):
        print(f"[PASS] P08 rejected deliberately corrupt WAV: {reason}")
        return
    raise Rejected(f"P08 oracle incorrectly accepted {reason}")


def run(wav_dir: pathlib.Path, midi_dir: pathlib.Path) -> None:
    summary = []
    for bpm in (90, 120, 150):
        for swing in (0, 25, 50):
            for mode in ("pattern", "song"):
                base = f"{mode}-bpm{bpm}-swing{swing}"
                mid = midi_dir / (base + ".mid")
                wav = wav_dir / (base + ".wav")
                check(mid.is_file() and wav.is_file(),
                      f"Missing MIDI/WAV source for {base}")
                midi_content = mid.read_bytes()
                validate_midi(midi_content, mode, bpm, swing)
                tick_onsets = [event[0] for event in parse(midi_content).on]
                content = wav.read_bytes()
                got, want, frames, peak = analyse_wave(content, bpm, mode, tick_onsets)
                summary.append({
                    "scenario": base, "onsets": got, "reference": want,
                    "frames": frames, "peak_int24": peak, "result": "PASS",
                })
                print(f"[PASS] P08 {base}: WAV {frames} frames; attacks {got}, "
                      f"independent MIDI positions {want}")
    check(len(summary) == 18, "Missing one or more WAV scenarios")

    good = (wav_dir / "pattern-bpm120-swing0.wav").read_bytes()
    midi = (midi_dir / "pattern-bpm120-swing0.mid").read_bytes()
    ticks = [event[0] for event in parse(midi).on]
    expect_rejected(good[:-32], 120, "pattern", ticks, "truncated PCM24 payload")
    rate = bytearray(good)
    rate[24:28] = (44100).to_bytes(4, "little")
    expect_rejected(bytes(rate), 120, "pattern", ticks, "wrong sample rate")

    corrupted = bytearray(good)
    hits, _, _, _ = analyse_wave(good, 120, "pattern", ticks)
    off = 44 + (hits[0] + 20) * 6 + 3
    sign = int.from_bytes(corrupted[off:off + 3], "little", signed=True)
    check(sign < 0, "negative corruption source lacks right-channel negative sample")
    corrupted[off:off + 3] = abs(sign).to_bytes(3, "little", signed=True)
    expect_rejected(bytes(corrupted), 120, "pattern", ticks,
                    "wrong right-channel polarity")

    target = wav_dir.parent / "p08-independent-wav-midi-report.json"
    target.write_text(json.dumps({
        "overall": "PASS",
        "verified_wav_files": len(summary),
        "negative_mutations_rejected": 3,
        "scenarios": summary,
    }, indent=2) + "\n", encoding="utf-8")
    print("[PASS] P08: 18 real offline WAV exports, exact duration/format, "
          "correct MIDI-to-WAV timing, stereo polarity and 3 corruptions")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: verify_wav_export.py <wav-directory> <midi-directory>",
              file=sys.stderr)
        raise SystemExit(2)
    try:
        run(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
    except (Rejected, ValueError, OSError, EOFError, wave.Error) as error:
        print(f"[FAIL] P08 independent WAV export oracle: {error}",
              file=sys.stderr)
        raise SystemExit(1)
