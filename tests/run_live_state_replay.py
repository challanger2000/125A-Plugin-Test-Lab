#!/usr/bin/env python3
"""Opt-in real VST3 active-playback state replay: genuine getState snapshots only.

This is a deliberately demanding concurrency test. It makes 500 genuine
setState calls while an audio worker processes 2500 buffers; no synthetic
plugin-state bytes, preset-name assumptions, or false musical PASS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from verify_state_stress import parse


RATES = (44100, 48000, 96000)
BLOCKS = (64, 512)


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def run(plugin, host, out, *, timeout=90, runner=subprocess.run):
    plugin = Path(plugin).resolve(strict=True)
    host = Path(host).resolve(strict=True)
    if not plugin.is_dir() or plugin.suffix.lower() != ".vst3" or not host.is_file():
        raise ValueError("requires real VST3 bundle and genuine native Windows stress host")
    modules = [x for x in plugin.rglob("*.vst3") if x.is_file()]
    if len(modules) != 1:
        raise ValueError("VST3 bundle must contain exactly one processor module")
    if not 5 <= timeout <= 300:
        raise ValueError("timeout must be within 5..300 seconds")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_file = out / "LIVE-STATE-REPLAY-RESULT.json"
    report_file.unlink(missing_ok=True)
    identity = sha256(modules[0])
    result = {
        "schema": "125a-live-state-replay-v1", "status": "FAIL",
        "release_approved": False, "verified_module_sha256": identity,
        "native_host_sha256": sha256(host),
        "scenario": "replay-genuine-state",
        "total_expected_set_state_calls": 3000,
        "total_expected_get_state_calls": 3000,
        "total_expected_audio_callbacks": 15000,
        "bank_program_correctness": "NOT COVERED",
        "commercial_daw_concurrency": "NOT COVERED",
        "cases": [],
    }
    for rate in RATES:
        for block in BLOCKS:
            name = f"live-replay-{rate}-{block}"
            state_file = out / f"{name}.tsv"
            log_file = out / f"{name}.log"
            state_file.unlink(missing_ok=True)
            log_file.unlink(missing_ok=True)
            case = {"id": name, "sample_rate": rate, "block": block,
                    "status": "FAIL", "sets_during_playback": 0,
                    "saves_during_playback": 0}
            try:
                cmd = [str(host), "--stress", str(plugin), str(state_file),
                       str(rate), str(block), "2500", "none",
                       "--replay-valid-state"]
                run_result = runner(cmd, check=False, capture_output=True,
                                    text=True, timeout=timeout, errors="replace")
                output = (run_result.stdout or "") + "\n" + (run_result.stderr or "")
                log_file.write_text(output, encoding="utf-8")
                if not state_file.is_file():
                    raise ValueError("native host did not produce fresh replay evidence")
                rows = parse(state_file)
                if rows.get("scenario") != "replay-genuine-state" or rows.get("oracle") != "none":
                    raise ValueError("unexpected replay mode or fabricated domain oracle")
                if rows.get("sample_rate") != rate or rows.get("block_size") != block or rows.get("iterations") != 2500:
                    raise ValueError("native rate/block evidence does not match requested case")
                if str(plugin) != rows.get("plugin"):
                    raise ValueError("native replay evidence belongs to a different VST3 bundle")
                case["sets_during_playback"] = rows["sets_during_playback"]
                case["saves_during_playback"] = rows["saves_during_playback"]
                case["callback_overruns"] = rows["callback_overruns"]
                if run_result.returncode != 0 or rows.get("result") != "PASS":
                    raise ValueError("native genuine setState/getState playback regression failed")
                if rows.get("domain_correctness") != "NOT_COVERED":
                    raise ValueError("native state replay falsely certified bank semantics")
                if (rows["set_success"] != 500 or rows["set_failures"] != 0 or
                    rows["save_success"] != 500 or rows["save_failures"] != 0 or
                    rows["process_failures"] != 0 or rows["torn_snapshots"] != 0 or
                    rows["sets_during_playback"] < 1 or
                    rows["saves_during_playback"] < 1):
                    raise ValueError("500 real state replays/saves or playback overlap not proven")
                if "[PASS] universal VST3 live process/set/get" not in output:
                    raise ValueError("native executable success marker is absent")
                case["status"] = "PASS"
            except (OSError, ValueError, KeyError, AssertionError, subprocess.TimeoutExpired) as error:
                case["reason"] = str(error)
            result["cases"].append(case)
    if len(result["cases"]) == 6 and all(case["status"] == "PASS" for case in result["cases"]):
        result["status"] = "TECHNICAL_PASS"
    result_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description="Genuine live VST3 state reload stress")
    p.add_argument("--plugin", required=True, type=Path)
    p.add_argument("--host", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--timeout", type=int, default=90)
    a = p.parse_args()
    try:
        result = run(a.plugin, a.host, a.out, timeout=a.timeout)
    except (OSError, ValueError, TypeError) as error:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": "125a-live-state-replay-v1", "status": "FAIL",
                  "release_approved": False, "reason": str(error)}
        (a.out / "LIVE-STATE-REPLAY-RESULT.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[" + result["status"] + "] genuine VST3 state replays concurrent with playback")
    return 0 if result["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
