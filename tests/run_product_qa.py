#!/usr/bin/env python3
"""Run available real VST3 test stages and report unsupported user checks.

This is a technical smoke/regression runner, NOT a product release approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p32", type=Path, required=True, help="playback-save test adapter manifest")
    ap.add_argument("--p34", type=Path, required=True, help="native PCM/state capture manifest")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    report_path = a.out / "PRODUCT-QA-RESULT.json"
    report_path.unlink(missing_ok=True)
    summary = {"schema": "125a-product-qa-run-v1",
               "status": "FAIL", "release_approved": False,
               "stages": {}, "user_acceptance": "NOT COVERED"}
    try:
        m32 = json.loads(a.p32.read_text(encoding="utf-8"))
        m34 = json.loads(a.p34.read_text(encoding="utf-8"))
        p32 = m32["product"]
        p34 = m34["product"]
        expected_sha = p32["sha256"]
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError("P32 missing module identity")
        if expected_sha != p34["sha256"]:
            raise ValueError("P32/P34 disagree on tested module")
        b32 = Path(p32["binary"]).resolve(strict=True)
        b34 = Path(p34["binary"]).resolve(strict=True)
        if b32 != b34 or sha(b32) != expected_sha:
            raise ValueError("P32/P34 product binary mismatch")
        summary["verified_vst3_sha256"] = expected_sha
        scripts = Path(__file__).resolve().parent
        for stage, script, manifest_key, folder in (
                ("playback_save", "run_product_adapter.py", a.p32, "P32"),
                ("native_capture", "run_p34_capture.py", a.p34, "P34")):
            out = a.out / folder
            cmd = [sys.executable, str(scripts / script), "--manifest" if stage == "native_capture" else "--adapter",
                   str(manifest_key), "--out", str(out), "--timeout", str(a.timeout)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout * 70,
                                  check=False, errors="replace")
            (a.out / (stage + ".log")).write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
            result_path = out / ("CAPTURE-RESULT.json" if stage == "native_capture" else "ADAPTER-RESULT.json")
            if not result_path.is_file():
                raise ValueError(stage + " did not produce a fresh report")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            stage_ok = proc.returncode == 0 and result.get("status") == "PASS"
            if stage == "playback_save" and result.get("verified_vst3_sha256") != expected_sha:
                stage_ok = False
            if stage == "native_capture" and result.get("verified_module_sha256") != expected_sha:
                stage_ok = False
            summary["stages"][stage] = {"status": "PASS" if stage_ok else "FAIL",
                                         "report": str(result_path)}
            if not stage_ok:
                raise ValueError(stage + " failed independent technical evidence")
        summary["status"] = "TECHNICAL_PASS"
        summary["coverage"] = {"native_audio_and_state_capture": "PASS",
                               "playback_save_api": "PASS",
                               "product_audio_semantics": "NOT COVERED",
                               "user_gui_controls": "NOT COVERED",
                               "midi_wav_export_semantics": "NOT COVERED",
                               "commercial_daw_integration": "NOT COVERED"}
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        summary["error"] = str(exc)
    report_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("[{}] exact-binary real VST3 technical QA; release approval: NO".format(summary["status"]))
    return 0 if summary["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
