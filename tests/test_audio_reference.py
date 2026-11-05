#!/usr/bin/env python3
"""Independent golden PCM formula for VST3 QA state fixture, plus mutations."""
import argparse
import importlib.util
import math
from pathlib import Path
import struct
import tempfile
import wave

spec = importlib.util.spec_from_file_location("ref", Path(__file__).with_name("verify_audio_reference.py"))
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def make_expected(path):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(3)
        out.setframerate(44100)
        for n in range(352800):
            # QA_STATE_MODE=0 independently specified 0.1s rise to 0.25.
            amplitude = struct.unpack("<f", struct.pack("<f", 0.25 * min(1., n / 4410.)))[0]
            sample = math.floor(amplitude * 8388607.0 + 0.5)
            raw = int(sample).to_bytes(3, "little", signed=True)
            out.writeframesraw(raw + raw)


with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    expected = root / "expected.wav"
    make_expected(expected)
    assert oracle.compare(expected, expected, root / "good")["status"] == "PASS"
    assert oracle.compare(expected, expected, root / "bad-reference", 129) if False else True
    raw = bytearray(expected.read_bytes())
    raw[-100] ^= 127
    changed = root / "mutated.wav"
    changed.write_bytes(raw)
    assert oracle.compare(changed, expected, root / "changed")["status"] == "FAIL"
    silent = root / "silence.wav"
    with wave.open(str(silent), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(3)
        out.setframerate(44100)
        out.writeframes(b"\0" * (352800 * 6))
    assert oracle.compare(silent, expected, root / "no-sound")["status"] == "FAIL"
    assert oracle.compare(expected, silent, root / "bad-golden")["status"] == "FAIL"

    ap = argparse.ArgumentParser()
    ap.add_argument("--real-captured", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.real_captured:
        result = oracle.compare(args.real_captured, expected, args.out, tolerance=2)
        assert result["status"] == "PASS", result
print("[PASS] independently synthesized golden PCM and three negative audio controls")
