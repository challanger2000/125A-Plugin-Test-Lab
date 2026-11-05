#!/usr/bin/env python3
"""Native P04 Windows GUI image capture: independent RGB and mutation controls."""
import argparse
import importlib.util
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location("p33", Path(__file__).with_name("verify_p33_artifacts.py"))
p33 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p33)

parser = argparse.ArgumentParser()
parser.add_argument("bmp", type=Path)
args = parser.parse_args()
file = args.bmp
data = file.read_bytes()
assert data[:2] == b"BM", "not a real Win32 BMP"
assert struct.unpack_from("<ii", data, 18) == (320, -180), "wrong native GUI dimensions"
assert p33.rgb_at(file, 10, 10) == [30, 36, 48], "independent GUI fixture pixel mismatch"
manifest = {"schema": "125a-p33-oracle-v1", "cases": [
    {"id": "real_hwnd_painted_pixel", "artifacts": {"gui_bmp": str(file)},
     "expected": {"gui": {"x": 10, "y": 10, "rgb": [30, 36, 48]}}}]}
assert p33.check(manifest)["status"] == "PASS", "captured HWND pixel did not match expected"
manifest["cases"][0]["expected"]["gui"]["rgb"] = [31, 36, 48]
assert p33.check(manifest)["status"] == "FAIL", "wrong RGB reference accepted"
manifest["cases"][0]["expected"]["gui"]["rgb"] = [30, 36, 48]
# Mutate the physical bitmap payload, never the declared oracle.
payload = bytearray(data)
offset = struct.unpack_from("<I", payload, 10)[0]
payload[offset+10*320*4+10*4] ^= 0xFF
mutated = file.with_name("mutated-pixel.bmp")
mutated.write_bytes(payload)
manifest["cases"][0]["artifacts"]["gui_bmp"] = str(mutated)
assert p33.check(manifest)["status"] == "FAIL", "altered native GUI pixel accepted"
print("[PASS] real editor HWND BMP pixels, wrong-reference and corrupted-capture controls")
