#!/usr/bin/env python3
"""P33 independent oracle positive/negative fixtures; standard library only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import wave

spec = importlib.util.spec_from_file_location("p33", Path(__file__).with_name("verify_p33_artifacts.py"))
p33 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p33)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bmp(path, rgb):
    r, g, b = rgb
    # 2x2 bottom-up BMP, 24 bits with two bytes of row padding.
    pixels = bytes([b, g, r] * 2 + [0, 0]) * 2
    path.write_bytes(b"BM" + struct.pack("<IHHI", 54 + len(pixels), 0, 0, 54) +
                     struct.pack("<IiiHHIIiiII", 40, 2, 2, 1, 24, 0,
                                 len(pixels), 0, 0, 0, 0) + pixels)


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    state, audio, gui = [root / n for n in ("state.bin", "audio.wav", "editor.bmp")]
    state.write_bytes(b"real captured state placeholder")
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x00\x00\x01\x00" * 8)
    bmp(gui, [255, 90, 0])
    manifest = {"schema": "125a-p33-oracle-v1", "cases": [{
        "id": "capture",
        "artifacts": {"state": str(state), "audio": str(audio), "gui_bmp": str(gui)},
        "expected": {
            "state_sha256": digest(state),
            "audio": {"sha256": digest(audio), "channels": 2, "sample_rate": 44100,
                      "bits": 16, "frames": 8},
            "gui": {"x": 1, "y": 1, "rgb": [255, 90, 0]}}}]}
    assert p33.check(manifest)["status"] == "PASS", "known-good artifacts rejected"

    state.write_bytes(b"tampered")
    report = p33.check(manifest)
    assert report["status"] == "FAIL" and "state bytes differ" in report["cases"][0]["failures"]
    state.write_bytes(b"real captured state placeholder")

    bmp(gui, [0, 0, 255])
    report = p33.check(manifest)
    assert report["status"] == "FAIL" and "painted GUI pixel differs" in report["cases"][0]["failures"]
    bmp(gui, [255, 90, 0])

    audio.write_bytes(audio.read_bytes()[:-3])
    report = p33.check(manifest)
    assert report["status"] == "FAIL", "corrupt WAV accepted"

    manifest["cases"][0]["expected"]["audio"]["sha256"] = "0" * 64
    assert p33.check(manifest)["status"] == "FAIL", "wrong audio oracle accepted"

    manifest["cases"][0]["expected"] = {}
    try:
        p33.check(manifest)
    except ValueError:
        pass
    else:
        raise AssertionError("missing independent oracle accepted")
print("[PASS] P33 independent good + state/audio/GUI corruption and missing-oracle controls")
