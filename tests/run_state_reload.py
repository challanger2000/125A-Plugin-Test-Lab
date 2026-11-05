#!/usr/bin/env python3
"""Real VST3 fresh-process state-reload regression with independent WAV comparison.

Runs existing Steinberg VST3 host twice, one OS process per roundtrip.
Never reports musical correctness without an externally pinned PCM oracle.
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
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def check(request, output, runner=subprocess.run, timeout=120):
    if request.get("schema") != "125a-state-reload-v1":
        raise ValueError("invalid recall manifest")
    product = request["product"]
    identity = product["sha256"]
    if not isinstance(identity, str) or len(identity) != 64 or any(
            char not in "0123456789abcdef" for char in identity):
        raise ValueError("invalid exact binary identity")
    binary = Path(product["binary"]).resolve(strict=True)
    host = Path(request["host"]).resolve(strict=True)
    state = Path(request["initial_state"]).resolve(strict=True)
    if not all(p.is_file() for p in (binary, host, state)):
        raise ValueError("missing module, host or captured state")
    if not 0 < state.stat().st_size < 128 * 1024 * 1024:
        raise ValueError("invalid state size")
    if digest(binary) != identity:
        raise ValueError("module binary SHA-256 mismatch")
    bundle = next((p for p in binary.parents if p.is_dir() and p.suffix.lower() == ".vst3"), None)
    if not bundle or binary.suffix.lower() != ".vst3":
        raise ValueError("binary outside valid bundle")
    if not 5 <= timeout <= 300:
        raise ValueError("timeout outside bounds")
    deterministic = request.get("deterministic_audio", False)
    if type(deterministic) is not bool:
        raise ValueError("deterministic_audio must be a boolean")
    ref = request.get("expected_audio_sha256")
    if ref is not None and (not isinstance(ref, str) or len(ref) != 64 or any(
            c not in "0123456789abcdef" for c in ref)):
        raise ValueError("invalid independent PCM reference")
    expected_state = request.get("expected_saved_state_sha256")
    if expected_state is not None and (
            not isinstance(expected_state, str) or len(expected_state) != 64 or
            any(c not in "0123456789abcdef" for c in expected_state)):
        raise ValueError("invalid independently expected saved-state SHA-256")
    report = {"schema": "125a-state-reload-result-v1",
              "status": "FAIL", "verified_vst3_sha256": identity,
              "new_process_instances": 0, "fresh_process_recall": "FAIL",
              "audio_determinism": "NOT COVERED",
              "musical_correctness": "NOT COVERED",
              "saved_state_integrity": "NOT COVERED",
              "artifacts": {}}
    output.mkdir(parents=True, exist_ok=True)
    for index in (1, 2):
        wav = output / ("recall-%s.wav" % index)
        saved = output / ("recall-%s.bin" % index)
        for path in (wav, saved):
            path.unlink(missing_ok=True)
    for index in (1, 2):
        wav = output / ("recall-%s.wav" % index)
        saved = output / ("recall-%s.bin" % index)
        cmd = [str(host), "--render-state-save", str(bundle),
               str(state), str(wav), str(saved)]
        try:
            proc = runner(cmd, capture_output=True, text=True, timeout=timeout,
                          check=False, errors="replace")
            (output / ("recall-%s.log" % index)).write_text(
                (proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
            if proc.returncode != 0:
                raise ValueError("native fresh host %d exit %d" % (index, proc.returncode))
            if not wav.is_file() or not saved.is_file() or saved.stat().st_size == 0:
                raise ValueError("missing fresh host output %d" % index)
            with wave.open(str(wav), "rb") as w:
                format_ok = (w.getnchannels(), w.getframerate(), w.getsampwidth(),
                             w.getnframes()) == (2, 44100, 3, 352800)
            if not format_ok:
                raise ValueError("wrong host audio format/duration")
            report["new_process_instances"] += 1
            report["artifacts"][str(index)] = {
                "wav_sha256": digest(wav), "state_sha256": digest(saved)}
        except (OSError, ValueError, subprocess.TimeoutExpired, wave.Error) as exc:
            report["error"] = str(exc)
            return report
    if expected_state is not None:
        saved_hashes = [report["artifacts"][str(i)]["state_sha256"] for i in (1, 2)]
        if any(value != expected_state for value in saved_hashes):
            report["saved_state_integrity"] = "FAIL"
            report["error"] = "reloaded state differs from independent expected state hash"
            return report
        report["saved_state_integrity"] = "PASS"
    report["fresh_process_recall"] = "PASS"
    first = report["artifacts"]["1"]["wav_sha256"]
    second = report["artifacts"]["2"]["wav_sha256"]
    if deterministic:
        if first != second:
            report["audio_determinism"] = "FAIL"
            report["error"] = "fresh-process PCM mismatch"
            return report
        report["audio_determinism"] = "PASS"
    if ref is not None:
        if first != ref:
            report["musical_correctness"] = "FAIL"
            report["error"] = "independent PCM reference mismatch"
            return report
        report["musical_correctness"] = "PASS"
    report["status"] = "PASS"
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        request = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = check(request, args.out, timeout=args.timeout)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        report = {"schema": "125a-state-reload-result-v1",
                  "status": "FAIL", "error": str(error)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "RECALL-RESULT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("[%s] fresh-process VST3 state recall" % report["status"])
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
