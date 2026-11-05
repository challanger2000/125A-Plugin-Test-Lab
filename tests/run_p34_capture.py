#!/usr/bin/env python3
"""P34: pinned native VST3 PCM/state capture, with independently auditable hashes.

This wrapper never manufactures product state and never claims GUI coverage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def capture(manifest_path, output, timeout=120, runner=subprocess.run):
    request = json.loads(manifest_path.read_text(encoding="utf-8"))
    if request.get("schema") != "125a-p34-capture-v1":
        raise ValueError("invalid capture schema")
    product = request.get("product")
    if not isinstance(product, dict):
        raise ValueError("product identity missing")
    pinned = product.get("sha256")
    if not isinstance(pinned, str) or len(pinned) != 64 or any(c not in "0123456789abcdef" for c in pinned):
        raise ValueError("missing valid pinned module SHA-256")
    binary = Path(product["binary"]).resolve(strict=True)
    host = Path(request["host"]).resolve(strict=True)
    if not binary.is_file() or not host.is_file():
        raise ValueError("native binary or host absent")
    bundle = next((p for p in binary.parents if p.is_dir() and p.suffix.lower() == ".vst3"), None)
    if not bundle or binary.suffix.lower() != ".vst3":
        raise ValueError("binary must be inside a VST3 bundle")
    if digest(binary) != pinned:
        raise ValueError("VST3 module SHA-256 mismatch")
    if not 5 <= timeout <= 300:
        raise ValueError("invalid timeout")
    output.mkdir(parents=True, exist_ok=True)
    wav, state = output / "captured.wav", output / "captured-state.bin"
    for path in (wav, state):
        path.unlink(missing_ok=True)  # no stale evidence
    report = {"schema": "125a-p34-result-v1", "status": "FAIL",
              "verified_module_sha256": pinned,
              "bundle": str(bundle), "artifacts": {},
              "capture": {"state": "FAIL", "audio": "FAIL", "gui": "NOT COVERED"},
              "provenance": "native-host-invocation; source commit is not cryptographically proven"}
    try:
        argv = [str(host), "--capture", str(bundle), str(wav), str(state)]
        proc = runner(argv, capture_output=True, text=True, timeout=timeout, check=False)
        (output / "capture.log").write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
        if proc.returncode != 0:
            raise ValueError("native host exit " + str(proc.returncode))
        if not wav.is_file() or not state.is_file() or state.stat().st_size == 0:
            raise ValueError("fresh audio/state capture missing")
        with wave.open(str(wav), "rb") as w:
            attrs = {"channels": w.getnchannels(), "rate": w.getframerate(),
                     "bits": w.getsampwidth() * 8, "frames": w.getnframes()}
        if attrs != {"channels": 2, "rate": 44100, "bits": 24, "frames": 352800}:
            raise ValueError("native PCM format or duration mismatch: " + str(attrs))
        report["artifacts"] = {"audio": {"path": str(wav), "sha256": digest(wav), **attrs},
                               "state": {"path": str(state), "sha256": digest(state),
                                         "size": state.stat().st_size}}
        report["capture"].update({"state": "PASS", "audio": "PASS"})
        report["status"] = "PASS"
    except (OSError, ValueError, subprocess.TimeoutExpired, wave.Error) as exc:
        report["error"] = str(exc)
    (output / "CAPTURE-RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--timeout", default=120, type=int)
    a = p.parse_args()
    try:
        result = capture(a.manifest, a.out, a.timeout)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": "125a-p34-result-v1", "status": "FAIL", "error": str(exc)}
        (a.out / "CAPTURE-RESULT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[{}] P34 native capture".format(result["status"]))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
