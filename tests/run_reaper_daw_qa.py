#!/usr/bin/env python3
"""P91 actual installed REAPER DAW integration (Windows, explicit opt-in).

Creates a real project through a Lua ReaScript inside REAPER, saves it,
reopens and independently verifies it, and renders via REAPER's own CLI.
No cloud-host simulated subprocess can establish real DAW coverage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import wave

SCHEMA = "125a-reaper-daw-test-v1"
RESULT = "125a-reaper-daw-test-result-v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
FX = re.compile(r"^VST3: [^\r\n\t]{1,150}$")
ALLOWED_RATES = {44100, 48000, 88200, 96000}
MAX_WAV_BYTES = 80000000


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def confined_lua(value):
    # Only strings trusted after manifest schema validation are embedded.
    # Lua long strings avoid escape ambiguity for Windows backslash paths.
    if not isinstance(value, str) or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("P91 cannot embed multiline/untrusted Lua string")
    level = 0
    while True:
        equals = "=" * level
        if ("]" + equals + "]") not in value:
            return "[" + equals + "[" + value + "]" + equals + "]"
        level += 1


def verified_file(value, expected_sha, name):
    if type(value) is not str or type(expected_sha) is not str or not HEX.fullmatch(expected_sha):
        raise ValueError("P91 missing exact " + name + " path/hash")
    path = Path(value).resolve(strict=True)
    if not path.is_file() or digest(path) != expected_sha:
        raise ValueError("P91 incorrect " + name + " binary fingerprint")
    return path


def verify_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {
            "schema", "reaper", "plugin", "test"} or plan["schema"] != SCHEMA:
        raise ValueError("P91 exact approved REAPER test plan required")
    reaper = plan["reaper"]
    plugin = plan["plugin"]
    config = plan["test"]
    if (not isinstance(reaper, dict) or set(reaper) != {"exe", "sha256"}
            or not isinstance(plugin, dict) or set(plugin) != {
                "module", "sha256", "reaper_fx_name"}
            or not isinstance(config, dict) or set(config) != {
                "sample_rate", "tempo_bpm", "note", "velocity", "seconds",
                "expect_audio", "minimum_rms"}):
        raise ValueError("P91 unknown or missing DAW/FX/test fields")
    executable = verified_file(reaper["exe"], reaper["sha256"], "REAPER")
    binary = verified_file(plugin["module"], plugin["sha256"], "VST3")
    if (executable.name.lower() != "reaper.exe"
            or binary.suffix.lower() != ".vst3"
            or not FX.fullmatch(plugin["reaper_fx_name"])):
        raise ValueError("P91 named REAPER VST3 instrument/FX must be explicit")
    rate = config["sample_rate"]
    tempo = config["tempo_bpm"]
    note = config["note"]
    velocity = config["velocity"]
    secs = config["seconds"]
    minimum_rms = config["minimum_rms"]
    if (type(rate) is not int or rate not in ALLOWED_RATES
            or type(tempo) is not int or not 60 <= tempo <= 200
            or type(note) is not int or not 0 <= note <= 127
            or type(velocity) is not int or not 1 <= velocity <= 127
            or type(secs) is not int or not 2 <= secs <= 8
            or type(config["expect_audio"]) is not bool
            or type(minimum_rms) not in (int, float)
            or not 0 < minimum_rms <= 0.2):
        raise ValueError("P91 invalid bounded musical/PCM oracle")
    if config["expect_audio"] is False:
        # An FX may be silent on MIDI-only input; its expected musical
        # response is explicitly NOT inferred by the REAPER integration.
        pass
    return executable, binary


def read_status(path):
    if not path.is_file() or not 10 <= path.stat().st_size <= 4096:
        return None
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            raise ValueError("P91 corrupt REAPER ReaScript result")
        key, value = line.split("=", 1)
        if key not in ("phase", "fx_name", "note_count", "reaper_version",
                       "project", "pitch", "velocity", "error") or key in data:
            raise ValueError("P91 invalid or duplicate REAPER status field")
        data[key] = value
    return data


def generate_script(template, plan, target, status_file, project_file, phase):
    if phase not in ("setup", "reload"):
        raise ValueError("P91 invalid REAPER script phase")
    config = plan["test"]
    values = {
        "TEST_PHASE": confined_lua(phase),
        "TEST_FX": confined_lua(plan["plugin"]["reaper_fx_name"]),
        "TEST_PROJECT": confined_lua(str(project_file)),
        "TEST_OUTPUT_DIR": confined_lua(str(target)),
        "TEST_RENDER_NAME": confined_lua("125A_Reaper_Render"),
        "TEST_STATUS": confined_lua(str(status_file)),
        "TEST_RATE": str(config["sample_rate"]),
        "TEST_BPM": str(config["tempo_bpm"]),
        "TEST_DURATION": str(config["seconds"]),
        "TEST_NOTE": str(config["note"]),
        "TEST_VELOCITY": str(config["velocity"])
    }
    script = "\n".join("local %s = %s" % item for item in values.items())
    script += "\n" + Path(template).read_text(encoding="utf-8")
    output = target / ("script-" + phase + ".lua")
    output.write_text(script, encoding="utf-8")
    return output


def check_pcm(path, rate, seconds, minimum_rms, expect_audio):
    if not path.is_file() or not 46 <= path.stat().st_size <= MAX_WAV_BYTES:
        raise ValueError("P91 genuine REAPER render WAV missing or abnormal size")
    with wave.open(str(path), "rb") as wav:
        channels, width, sample_rate = (
            wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
        frames = wav.getnframes()
        if (sample_rate != rate or channels not in (1, 2)
                or width not in (2, 3, 4)
                or not rate * (seconds - 0.1) <= frames <= rate * (seconds + 0.1)
                or wav.getcomptype() != "NONE"):
            raise ValueError("P91 REAPER rendered unexpected PCM format/duration")
        raw = wav.readframes(frames)
    if len(raw) != frames * channels * width:
        raise ValueError("P91 truncated REAPER PCM")
    total = 0
    peak = 0
    count = 0
    for idx in range(0, len(raw), width):
        n = int.from_bytes(raw[idx:idx + width], "little", signed=True)
        x = n / float(1 << (width * 8 - 1))
        total += x * x
        peak = max(peak, abs(x))
        count += 1
    rms = (total / count) ** 0.5
    if expect_audio and (rms < minimum_rms or peak >= 0.99999):
        raise ValueError("P91 actual REAPER render silent or clipped")
    return {"sha256": digest(path), "frames": frames, "channels": channels,
            "sample_rate": sample_rate, "bits": width * 8,
            "rms": round(rms, 7), "peak": round(peak, 7),
            "audible_in_render": rms >= minimum_rms}


def run_process(command, status_file=None, timeout=90):
    """A fresh process per phase. Existing user REAPER session is untouched."""
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    try:
        if status_file is not None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                status = read_status(status_file)
                if status:
                    if status.get("phase") == "FAIL":
                        raise ValueError("P91 REAPER ReaScript error: " +
                                         status.get("error", "unknown"))
                    return status
                if process.poll() is not None:
                    raise ValueError("P91 REAPER exited without actual in-DAW evidence")
                time.sleep(.1)
            raise ValueError("P91 REAPER ReaScript timed out")
        code = process.wait(timeout=timeout)
        if code != 0:
            raise ValueError("P91 REAPER render process failed")
        return {"exit_code": code}
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)


def execute(plan, out, *, timeout=90, script_template=None, process_runner=run_process):
    exe, module = verify_plan(plan)
    if type(timeout) is not int or not 10 <= timeout <= 300:
        raise ValueError("P91 bounded live REAPER timeout required")
    folder = Path(out).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError("P91 requires a new empty, isolated evidence folder")
    if script_template is None:
        script_template = Path(__file__).with_name("reaper_qa_driver.lua")
    project = folder / "125A_Reaper_Project.RPP"
    status_setup = folder / "setup.status"
    status_reload = folder / "reload.status"
    rendered = folder / "125A_Reaper_Render.wav"
    report = {
        "schema": RESULT, "status": "FAIL",
        "verified_reaper_sha256": digest(exe),
        "verified_module_sha256": digest(module),
        "fx_name_requested": plan["plugin"]["reaper_fx_name"],
        "genuine_reaper_process_launched": False,
        "reloaded_project_verified": False,
        "rendered_by_reaper_process": False,
        "loaded_module_file_provenance": "NOT INDEPENDENTLY VERIFIED",
        "physical_asio_hardware": "NOT RUN",
        "release_approved": False, "faults": []
    }
    try:
        setup_script = generate_script(
            script_template, plan, folder, status_setup, project, "setup")
        cmd = [str(exe), "-newinst", "-new", str(setup_script)]
        setup = process_runner(cmd, status_setup, timeout)
        report["genuine_reaper_process_launched"] = True
        if (setup.get("phase") != "setup" or setup.get("note_count") != "1"
                or not setup.get("fx_name") or not setup.get("reaper_version")
                or not project.is_file()):
            raise ValueError("P91 REAPER setup/save evidence incomplete")
        report["reaper_version"] = setup["reaper_version"]
        report["loaded_fx_name"] = setup["fx_name"]
        report["saved_project_sha256"] = digest(project)
        reload_script = generate_script(
            script_template, plan, folder, status_reload, project, "reload")
        reload_cmd = [str(exe), "-newinst", str(project), str(reload_script)]
        loaded = process_runner(reload_cmd, status_reload, timeout)
        if (loaded.get("phase") != "reload" or
                loaded.get("note_count") != "1" or
                loaded.get("pitch") != str(plan["test"]["note"]) or
                loaded.get("velocity") != str(plan["test"]["velocity"]) or
                loaded.get("fx_name") != setup["fx_name"]):
            raise ValueError("P91 real DAW reload changed stored instrument/MIDI")
        report["reloaded_project_verified"] = True
        if digest(project) != report["saved_project_sha256"]:
            raise ValueError("P91 project changed unexpectedly during reload")
        # CLI documented by ReaTeam; REAPER, not our host, renders the FX.
        process_runner([str(exe), "-renderproject", str(project)], None, timeout)
        if not rendered.is_file():
            raise ValueError("P91 real REAPER CLI render did not produce WAV")
        report["rendered_by_reaper_process"] = True
        report["render"] = check_pcm(
            rendered, plan["test"]["sample_rate"], plan["test"]["seconds"],
            plan["test"]["minimum_rms"], plan["test"]["expect_audio"])
        if digest(exe) != report["verified_reaper_sha256"] or (
                digest(module) != report["verified_module_sha256"]):
            raise ValueError("P91 REAPER or plugin module changed during live DAW run")
        report["status"] = "REAL_REAPER_DAW_PIPELINE_PASS"
    except (OSError, ValueError, TypeError, wave.Error,
            subprocess.TimeoutExpired) as err:
        report["faults"].append(str(err))
    (folder / "REAPER-DAW-ACCEPTANCE.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=90)
    args = p.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        report = execute(plan, args.out, timeout=args.timeout)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as err:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": RESULT, "status": "FAIL", "faults": [str(err)],
                  "genuine_reaper_process_launched": False,
                  "physical_asio_hardware": "NOT RUN",
                  "release_approved": False}
        (args.out / "REAPER-DAW-ACCEPTANCE.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "REAL_REAPER_DAW_PIPELINE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
