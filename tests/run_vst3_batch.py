#!/usr/bin/env python3
"""P23/P24: isolate, inspect and optionally audio-smoke every VST3 bundle.

Each module is loaded in a separate subprocess with a hard timeout.
No audio, state or GUI PASS is implied by capability discovery alone.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import subprocess
import sys
import time
import wave

from verify_universal_discovery import check


def discover(root: pathlib.Path) -> list[pathlib.Path]:
    assert root.is_dir(), "plugin scan root is not a directory"
    paths = []
    for path in root.rglob("*"):
        if path.suffix.lower() != ".vst3":
            continue
        if any(p.suffix.lower() == ".vst3" for p in path.parents):
            continue
        if path.is_dir() or path.is_file():
            paths.append(path)
    return sorted(paths, key=lambda p: str(p).lower())


def validate_render(path: pathlib.Path) -> str:
    """WAV container and PCM checks independent of the native VST3 host."""
    with wave.open(str(path), "rb") as wav:
        assert wav.getframerate() == 44100, "invalid sample rate"
        assert wav.getnchannels() == 2, "expected stereo PCM"
        assert wav.getsampwidth() == 3, "expected 24-bit PCM"
        assert wav.getnframes() == 352800, "unexpected render duration"
        audio = wav.readframes(wav.getnframes())
        assert len(audio) == 352800 * 6, "truncated audio"
        assert not wav.readframes(1), "extra frames"
    return "INCONCLUSIVE" if not any(audio) else "PASS"


def scan(host: pathlib.Path, root: pathlib.Path, out: pathlib.Path,
         timeout: int, audio_smoke: bool = False) -> bool:
    assert host.is_file(), "universal test host executable missing"
    assert 1 <= timeout <= 300, "invalid timeout range"
    plugins = discover(root)
    assert plugins, "no .vst3 modules in root"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for i, plugin in enumerate(plugins, 1):
        record = {"relative_path": str(plugin.relative_to(root)), "status": "FAIL"}
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [str(host.resolve()), "--inspect", str(plugin.resolve())],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, check=False,
            )
            log = (proc.stdout or "") + "\n" + (proc.stderr or "")
            (out / f"module-{i:03d}.log").write_text(log, encoding="utf-8")
            record["exit_code"] = proc.returncode
            if proc.returncode == 0:
                capabilities = check(proc.stdout)
                record["status"] = "PASS"
                record["classes"] = capabilities["classes"]
                if audio_smoke:
                    eligible = capabilities["classes"][0]["recommended_gates"]["sample32_processing"] == "ELIGIBLE"
                    if not eligible:
                        record["audio_smoke"] = "NOT_APPLICABLE"
                    else:
                        wave_path = out / f"module-{i:03d}-audio.wav"
                        rendered = subprocess.run(
                            [str(host.resolve()), "--render", str(plugin.resolve()), str(wave_path.resolve())],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout, check=False)
                        (out / f"module-{i:03d}-render.log").write_text(
                            (rendered.stdout or "") + "\n" + (rendered.stderr or ""), encoding="utf-8")
                        if rendered.returncode != 0 or not wave_path.is_file():
                            record["status"] = "FAIL"
                            record["audio_smoke"] = "FAIL"
                            record["reason"] = "isolated VST3 rendering failed or produced no WAV"
                        else:
                            record["audio_smoke"] = validate_render(wave_path)
                            if record["audio_smoke"] == "INCONCLUSIVE":
                                record["audio_reason"] = "valid silent output; musical function unproven"
                            wave_path.unlink()
            else:
                record["reason"] = "host exited nonzero (load, interface or runtime error)"
        except subprocess.TimeoutExpired:
            record["reason"] = f"host exceeded {timeout}s timeout"
            if audio_smoke: record["audio_smoke"] = "FAIL"
        except (OSError, AssertionError, ValueError, wave.Error) as err:
            record["reason"] = str(err)
            if audio_smoke: record["audio_smoke"] = "FAIL"
        record["elapsed_ms"] = round((time.monotonic() - start) * 1000)
        results.append(record)
        print(f"[{record['status']}] P23 {record['relative_path']}")
    passed = all(item["status"] == "PASS" for item in results)
    report = {
        "schema": "125a-universal-vst3-batch-v1",
        "status": "PASS" if passed else "FAIL",
        "discovered": len(results),
        "passed": sum(item["status"] == "PASS" for item in results),
        "failed": sum(item["status"] == "FAIL" for item in results),
        "modules": results,
        "coverage": {"capability_discovery": "EXECUTED",
                     "audio_rendering": "EXECUTED_WHERE_APPLICABLE" if audio_smoke else "NOT_EXECUTED",
                     "gui_interaction": "NOT_EXECUTED",
                     "state_recall": "NOT_EXECUTED"}
    }
    (out / "BATCH-RESULT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[{report['status']}] P23 batch {report['passed']}/{report['discovered']} modules")
    return passed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", type=pathlib.Path, required=True)
    p.add_argument("--root", type=pathlib.Path, required=True)
    p.add_argument("--out", type=pathlib.Path, required=True)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--audio-smoke", action="store_true", help="Also render first audio class if 32-bit processing and output are available")
    args = p.parse_args()
    try:
        if not scan(args.host, args.root, args.out, args.timeout, args.audio_smoke):
            sys.exit(1)
    except (AssertionError, OSError, ValueError) as error:
        print(f"[FAIL] P23 scan: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
