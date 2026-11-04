#!/usr/bin/env python3
"""Real VST3 host save/reload oracle: no Drumator serialization code imported."""
import argparse
import hashlib
import pathlib
import struct
import sys
import wave

FRAMES = 352800
RATE = 44100


def read_audio(path: pathlib.Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        assert w.getnframes() == FRAMES, "wrong frame count"
        assert w.getframerate() == RATE, "wrong sample rate"
        assert w.getsampwidth() == 3 and w.getnchannels() == 2, "wrong WAV format"
        data = w.readframes(FRAMES)
        assert not w.readframes(1), "extra WAV frames"
        assert len(data) == FRAMES * 6, "truncated WAV"
        return data


def validate_state(state: pathlib.Path) -> bytes:
    content = state.read_bytes()
    assert len(content) >= 12, "empty state"
    assert content[:4] == b"DM18", "wrong Drumator state magic"
    declared = struct.unpack_from("<I", content, 4)[0]
    assert declared == len(content) - 8, "incorrect state length"
    expected_crc = struct.unpack_from("<I", content, len(content) - 4)[0]
    checksum = 2166136261
    for value in content[8:-4]:
        checksum ^= value
        checksum = (checksum * 16777619) & 0xFFFFFFFF
    assert checksum == expected_crc, "invalid saved state checksum"
    return content


def verify(first: pathlib.Path, after_recall: pathlib.Path, saved: pathlib.Path) -> None:
    original = read_audio(first)
    reproduced = read_audio(after_recall)
    validate_state(saved)
    assert original == reproduced, (
        "fresh-instance rendering changed after VST3 component getState/setState"
    )
    assert any(original), "matching silence is not evidence of correct recall"
    print(
        f"[PASS] Real VST3 getState -> fresh process -> setState: "
        f"{FRAMES} sample frames identical for both stereo channels"
    )
    print("[PASS] Saved DM18 state length, CRC and 24-bit PCM format validated")
    print(f"[INFO] PCM SHA256 = {hashlib.sha256(original).hexdigest()}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("first", type=pathlib.Path)
    p.add_argument("after_recall", type=pathlib.Path)
    p.add_argument("saved", type=pathlib.Path)
    args = p.parse_args()
    try:
        verify(args.first, args.after_recall, args.saved)
    except (OSError, AssertionError, ValueError, wave.Error) as error:
        print(f"[FAIL] VST3 state recall: {error}", file=sys.stderr)
        sys.exit(1)
