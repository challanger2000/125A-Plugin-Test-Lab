#!/usr/bin/env python3
"""Independent P02 PCM24 renderer oracle (standard-library only).

EXPECTED OUTPUT IS CALCULATED FROM TEST SPECIFICATION, NOT THE VST3 PROCESSOR.
Every quarter note at 120 BPM emits 128 frames at amplitude 0.25, 16 beats.
All other samples MUST be silent. Both channels must agree exactly.
"""
import argparse
import pathlib
import sys
import wave

RATE = 44100
BPM = 120
BEATS = 16
PULSE_FRAMES = 128
PULSE_LEVEL = round(0.25 * ((1 << 23) - 1))
SAMPLES_PER_BEAT = RATE * 60 // BPM
FRAMES = SAMPLES_PER_BEAT * BEATS


def verify(path: pathlib.Path) -> None:
    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 2, "expected stereo"
        assert wav.getsampwidth() == 3, "expected 24-bit integer PCM"
        assert wav.getframerate() == RATE, "wrong sample rate"
        assert wav.getcomptype() == "NONE", "not uncompressed PCM"
        assert wav.getnframes() == FRAMES, (
            f"wrong number of frames: {wav.getnframes()} != {FRAMES}"
        )
        data = wav.readframes(FRAMES)
        assert not wav.readframes(1), "unexpected extra WAV frames"

    assert len(data) == FRAMES * 6, "truncated WAV data"
    nonzero_frames = 0
    for frame in range(FRAMES):
        pulse_position = frame % SAMPLES_PER_BEAT
        expected = PULSE_LEVEL if pulse_position < PULSE_FRAMES else 0
        if expected:
            nonzero_frames += 1
        for channel in (0, 1):
            offset = frame * 6 + channel * 3
            actual = int.from_bytes(data[offset:offset + 3], "little", signed=True)
            if actual != expected:
                raise AssertionError(
                    f"sample mismatch at frame {frame}, channel {channel}: "
                    f"actual {actual}, expected {expected}"
                )
    assert nonzero_frames == BEATS * PULSE_FRAMES
    print(
        f"[PASS] Independent oracle: {FRAMES} frames / {BEATS} pulses "
        f"/ {nonzero_frames} nonzero frames / PCM24 stereo"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=pathlib.Path)
    args = parser.parse_args()
    try:
        verify(args.wav)
    except (AssertionError, OSError, ValueError, wave.Error) as exc:
        print(f"[FAIL] Independent render verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
