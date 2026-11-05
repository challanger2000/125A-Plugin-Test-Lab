#!/usr/bin/env python3
"""Check real VST3 PCM against a separately approved audio reference."""
import argparse
import hashlib
import json
from pathlib import Path
import wave


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(actual, reference, out, tolerance=0):
    actual, reference, out = Path(actual), Path(reference), Path(out)
    if not 0 <= tolerance <= 128:
        raise ValueError("invalid PCM tolerance")
    out.mkdir(parents=True, exist_ok=True)
    report = {"status": "FAIL", "musical_correctness": "NOT COVERED",
              "reference_provenance": "NOT ATTESTED"}
    try:
        with wave.open(str(actual), "rb") as a, wave.open(str(reference), "rb") as b:
            attrs = lambda w: (w.getnchannels(), w.getframerate(), w.getsampwidth(), w.getnframes())
            if attrs(a) != attrs(b) or attrs(a)[:3] != (2, 44100, 3) or attrs(a)[3] != 352800:
                raise ValueError("audio format or frame count differs")
            aa, bb = a.readframes(352800), b.readframes(352800)
            if len(aa) != 352800 * 6 or len(bb) != len(aa):
                raise ValueError("truncated PCM data")
            if not any(bb):
                raise ValueError("independent audio reference is silent")
            if not any(aa):
                raise ValueError("actual VST3 rendering is silent")
            errors = 0
            peak = 0
            for i in range(0, len(aa), 3):
                av = int.from_bytes(aa[i:i+3], "little", signed=True)
                bv = int.from_bytes(bb[i:i+3], "little", signed=True)
                d = abs(av - bv)
                peak = max(peak, d)
                errors += d > tolerance
            report.update({"captured_sha256": sha(actual), "reference_sha256": sha(reference),
                           "tolerance_lsb": tolerance, "mismatched_samples": errors,
                           "max_error_lsb": peak})
            if errors:
                raise ValueError("independent reference PCM mismatch")
            report["status"] = "PASS"
            report["musical_correctness"] = "REFERENCE_MATCH"
    except (OSError, ValueError, wave.Error) as exc:
        report["error"] = str(exc)
    (out / "AUDIO-REFERENCE-RESULT.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--captured", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tolerance-lsb", type=int, default=0)
    args = p.parse_args()
    result = compare(args.captured, args.reference, args.out, args.tolerance_lsb)
    print("[" + result["status"] + "] independent audio reference")
    raise SystemExit(0 if result["status"] == "PASS" else 1)
