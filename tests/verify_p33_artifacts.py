#!/usr/bin/env python3
"""P33: independently verify externally captured native product artifacts.

This verifier does not launch a VST3 or claim that submitted artifacts came
from one: production provenance requires a separately trusted capture adapter.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import wave

HEX = set("0123456789abcdef")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pinned(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in HEX for c in value):
        raise ValueError("required lowercase SHA-256 missing or invalid")
    return value


def rgb_at(path, x, y):
    """Read a physical pixel from an uncompressed Win32 24/32-bit BMP."""
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("invalid BMP")
    offset = struct.unpack_from("<I", data, 10)[0]
    header = struct.unpack_from("<I", data, 14)[0]
    if header < 40:
        raise ValueError("unsupported BMP header")
    width, height, planes, depth, compression = struct.unpack_from("<iiHHI", data, 18)
    if width <= 0 or height == 0 or planes != 1 or depth not in (24, 32) or compression:
        raise ValueError("unsupported BMP format")
    if not (0 <= x < width and 0 <= y < abs(height)):
        raise ValueError("pixel outside BMP")
    stride = ((width * depth + 31) // 32) * 4
    start = offset + (abs(height) - 1 - y if height > 0 else y) * stride + x * (depth // 8)
    if start < 54 or start + 3 > len(data) or offset + abs(height) * stride > len(data):
        raise ValueError("truncated BMP pixels")
    b, g, r = data[start:start + 3]
    return [r, g, b]


def check(manifest):
    if manifest.get("schema") != "125a-p33-oracle-v1":
        raise ValueError("unsupported P33 manifest schema")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases or len(cases) > 128:
        raise ValueError("required cases absent")
    results = []
    used = set()
    for case in cases:
        name = case.get("id")
        if not isinstance(name, str) or not name or name in used:
            raise ValueError("missing or duplicate case id")
        used.add(name)
        expectations = case.get("expected")
        artifacts = case.get("artifacts")
        if not isinstance(expectations, dict) or not expectations or not isinstance(artifacts, dict):
            raise ValueError("independent expectations and artifacts required")
        if set(expectations) - {"state_sha256", "audio", "gui"}:
            raise ValueError("unknown oracle expectation")
        failures = []
        for field in expectations:
            try:
                if field == "state_sha256":
                    expected = pinned(expectations[field])
                    actual = sha256(Path(artifacts["state"]))
                    if actual != expected:
                        failures.append("state bytes differ")
                elif field == "audio":
                    e = expectations[field]
                    expected = pinned(e["sha256"])
                    path = Path(artifacts["audio"])
                    with wave.open(str(path), "rb") as wav:
                        actual_format = [wav.getnchannels(), wav.getframerate(),
                                         wav.getsampwidth() * 8, wav.getnframes()]
                    required = [e["channels"], e["sample_rate"], e["bits"], e["frames"]]
                    if actual_format != required:
                        failures.append("audio format/duration mismatch")
                    if sha256(path) != expected:
                        failures.append("audio file bytes differ")
                elif field == "gui":
                    e = expectations[field]
                    expected = e["rgb"]
                    if not isinstance(expected, list) or len(expected) != 3 or any(
                            type(v) is not int or not 0 <= v <= 255 for v in expected):
                        raise ValueError("invalid RGB reference")
                    actual = rgb_at(Path(artifacts["gui_bmp"]), e["x"], e["y"])
                    if actual != expected:
                        failures.append("painted GUI pixel differs")
            except (OSError, EOFError, KeyError, IndexError, TypeError, ValueError,
                    struct.error, wave.Error) as ex:
                failures.append(field + ": " + str(ex))
        results.append({"id": name, "status": "FAIL" if failures else "PASS",
                        "failures": failures,
                        "covered": sorted(expectations),
                        "not_covered": sorted({"state_sha256", "audio", "gui"} - set(expectations))})
    return {"schema": "125a-p33-result-v1",
            "status": "PASS" if all(x["status"] == "PASS" for x in results) else "FAIL",
            "cases": results,
            "provenance": "NOT VERIFIED: artifact producer and tested VST3 binary are external"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        result = check(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (ValueError, OSError, KeyError, TypeError) as e:
        result = {"schema": "125a-p33-result-v1", "status": "FAIL", "error": str(e)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[{}] P33 independent artifact oracle".format(result["status"]))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
