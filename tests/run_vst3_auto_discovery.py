#!/usr/bin/env python3
"""P68 read-only discovery and non-executable proposed test-plan draft.

No guessed GUI coordinates, DSP results, feature names or expected values.
The product owner must approve/complete a P65/P66 plan and P67 matrix
before automated actions can run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "125a-vst3-discovery-v1"
DRAFT = "125a-vst3-test-plan-draft-v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"[^a-z0-9_-]+")


def digest(file):
    h = hashlib.sha256()
    with Path(file).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def verify_bundle(bundle):
    bundle = Path(bundle).resolve(strict=True)
    if not bundle.is_dir() or bundle.suffix.lower() != ".vst3":
        raise ValueError("P68 requires an actual VST3 bundle directory")
    candidates = [f for f in bundle.rglob("*.vst3") if f.is_file()]
    if len(candidates) != 1:
        raise ValueError("P68 cannot uniquely identify a real VST3 module DLL")
    return bundle, candidates[0].resolve(strict=True)


def integer(raw, minimum, maximum, field):
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal():
        raise ValueError("P68 noncanonical native integer in " + field)
    n = int(raw)
    if not minimum <= n <= maximum or str(n) != raw:
        raise ValueError("P68 invalid native value for " + field)
    return n


def parse_capabilities(raw):
    lines = raw.splitlines()
    header = "format\t125A-VST3-CAPABILITIES-v1"
    names = ("audio_classes", "parameter_count", "editable_parameters",
             "readonly_parameters", "bypass_parameters", "program_parameters",
             "editor_available", "editor_win32_hwnd", "bus_count")
    if len(lines) < len(names) + 2 or lines[0] != header or lines[-1] != "end\tCOMPLETE":
        raise ValueError("P68 native capabilities evidence missing or truncated")
    values = {}
    for index, name in enumerate(names, 1):
        parts = lines[index].split("\t")
        if len(parts) != 2 or parts[0] != name:
            raise ValueError("P68 reordered or missing native capability field")
        values[name] = integer(parts[1], 0, 8192, name)
    if values["audio_classes"] != 1:
        raise ValueError("P68 ambiguous/missing VST3 audio class")
    if (values["parameter_count"] != values["editable_parameters"] +
            values["readonly_parameters"] or
            values["bypass_parameters"] > values["parameter_count"] or
            values["program_parameters"] > values["parameter_count"] or
            values["editor_available"] not in (0, 1) or
            values["editor_win32_hwnd"] not in (0, 1) or
            values["editor_win32_hwnd"] > values["editor_available"] or
            values["bus_count"] > 512):
        raise ValueError("P68 inconsistent native capability totals")
    if len(lines) != len(names) + 2 + values["bus_count"]:
        raise ValueError("P68 declared native bus count differs from data")
    buses = []
    seen = set()
    for line in lines[len(names)+1:-1]:
        fields = line.split("\t")
        if len(fields) != 7 or fields[0] != "bus":
            raise ValueError("P68 invalid native bus metadata record")
        media, direction, index, channels, bus_type, flags = [
            integer(token, 0, bound, "bus")
            for token, bound in zip(fields[1:], (1, 1, 127, 1024, 4, 4294967295))
        ]
        key = (media, direction, index)
        if key in seen:
            raise ValueError("P68 duplicate VST3 bus")
        seen.add(key)
        buses.append({"media": "audio" if media == 0 else "event",
                      "direction": "input" if direction == 0 else "output",
                      "index": index, "channels": channels,
                      "bus_type": bus_type, "flags": flags})
    values["buses"] = buses
    return values


def parse_parameters(raw, expected_count):
    lines = raw.splitlines()
    if len(lines) != expected_count + 2 or lines[0] != "format\t125A-GUI-PARAMS-v1":
        raise ValueError("P68 native VST3 parameter inventory missing or truncated")
    prefix = lines[1].split("\t")
    if len(prefix) != 2 or prefix[0] != "param_count" or integer(
            prefix[1], 0, 8192, "param_count") != expected_count:
        raise ValueError("P68 native parameter inventory count mismatch")
    output = []
    ids = set()
    for offset, line in enumerate(lines[2:]):
        fields = line.split("\t")
        if len(fields) != 7 or fields[0] != "param":
            raise ValueError("P68 incorrect native parameter record")
        idx = integer(fields[1], 0, 8191, "index")
        param = integer(fields[2], 0, 4294967295, "param_id")
        steps = integer(fields[3], 0, 2147483647, "step_count")
        flags = integer(fields[6], 0, 4294967295, "flags")
        if idx != offset or param in ids:
            raise ValueError("P68 parameter order or uniqueness invalid")
        ids.add(param)
        try:
            default = float(fields[4])
            current = float(fields[5])
        except ValueError as error:
            raise ValueError("P68 nonnumeric VST3 parameter value") from error
        import math
        if any(not math.isfinite(x) or not 0 <= x <= 1
               for x in (default, current)):
            raise ValueError("P68 invalid normalized parameter state")
        output.append({"index": idx, "param_id": param, "step_count": steps,
                       "flags": flags, "default_normalized": default,
                       "current_normalized": current,
                       "semantic_meaning": "NOT DISCOVERED",
                       "gui_coordinates": "NOT DISCOVERED"})
    return output


def build_draft(bundle, module, gui, caps, parameters, host_extra):
    name = IDENT.sub("_", bundle.stem.lower()).strip("_")[:64]
    if not name or not name[0].isalpha():
        name = "vst3_" + name[:59]
    hosts = {"gui": {"path": str(gui), "sha256": digest(gui)}}
    hosts.update({key: {"path": str(file), "sha256": digest(file)}
                  for key, file in host_extra.items()})
    proposed = []
    if {"audio", "stress"} <= hosts.keys():
        proposed.append({
            "id": "technical_baseline", "kind": "technical_quickcheck",
            "contract": {"required_coverage": [
                "api_playback_save", "sample_rate_buffer_matrix",
                "native_audio_state_capture"]},
            "approval": "REQUIRES PRODUCT OWNER REVIEW",
            "prerequisites": "Confirm compatible plugin state and playback behavior"
        })
    if caps["editable_parameters"]:
        proposed.append({
            "id": "parameter_controller_sweep",
            "kind": "UNAVAILABLE_IN_P65_PLAN",
            "approval": "REQUIRES OWNER EXPECTED VALUES",
            "parameter_ids": [p["param_id"] for p in parameters
                              if not p["flags"] & (1 << 1)][:256],
            "note": "P65 GUI sweep requires real approved coordinates, not guessed",
        })
    proposed.append({
        "id": "custom_product_functions", "kind": "NOT DISCOVERABLE_FROM_VST3_ABI",
        "approval": "REQUIRES PLUGIN CHAT FUNCTION INVENTORY",
        "note": "MIDI/WAV export, presets, musical semantics and special GUI require independent expectations"
    })
    return {
        "schema": DRAFT, "product": {"id": name, "bundle": str(bundle),
                                     "module": str(module), "sha256": digest(module)},
        "hosts": hosts, "inventory_summary": {
            "parameter_count": len(parameters),
            "audio_inputs": sum(1 for b in caps["buses"] if
                                b["media"] == "audio" and b["direction"] == "input"),
            "audio_outputs": sum(1 for b in caps["buses"] if
                                 b["media"] == "audio" and b["direction"] == "output"),
            "event_inputs": sum(1 for b in caps["buses"] if
                                b["media"] == "event" and b["direction"] == "input"),
            "event_outputs": sum(1 for b in caps["buses"] if
                                 b["media"] == "event" and b["direction"] == "output"),
            "editor_available": bool(caps["editor_available"])
        },
        "proposed_cases": proposed,
        "executable_p65_plan": False,
        "required_feature_inventory": "NOT DECLARED",
        "musical_oracles": "NOT DISCOVERED",
        "release_approved": False
    }


def discover(bundle, gui_host, out, *, audio_host=None, stress_host=None,
             timeout=35, runner=subprocess.run):
    bundle, module = verify_bundle(bundle)
    gui_host = Path(gui_host).resolve(strict=True)
    if not gui_host.is_file():
        raise ValueError("P68 native VST3 GUI host executable missing")
    if type(timeout) is not int or not 5 <= timeout <= 120:
        raise ValueError("P68 invalid bounded process timeout")
    other = {}
    for key, value in (("audio", audio_host), ("stress", stress_host)):
        if value is not None:
            p = Path(value).resolve(strict=True)
            if not p.is_file():
                raise ValueError("P68 pinned host missing")
            other[key] = p
    if bool(audio_host) != bool(stress_host):
        raise ValueError("P68 audio and stress host must be supplied together")
    pins = {str(p): digest(p) for p in (module, gui_host, *other.values())}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    capability = out / "native-capabilities.tsv"
    parameters = out / "native-parameters.tsv"
    draft_file = out / "PROPOSED-TEST-PLAN.json"
    result_file = out / "DISCOVERY-RESULT.json"
    for file in (capability, parameters, draft_file, result_file):
        file.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": pins[str(module)],
        "verified_gui_host_sha256": pins[str(gui_host)],
        "faults": [], "product_feature_completeness": "NOT ESTABLISHED",
        "executable_plan_generated": False, "release_approved": False
    }
    try:
        for flag, evidence in (("--inventory-capabilities", capability),
                               ("--inventory-parameters", parameters)):
            cmd = [str(gui_host), flag, str(bundle), str(evidence)]
            response = runner(cmd, capture_output=True, text=True, errors="replace",
                              check=False, timeout=timeout)
            if response.returncode != 0 or not evidence.is_file():
                raise ValueError("P68 actual native discovery command failed: " + flag)
            if evidence.stat().st_size > 2_000_000:
                raise ValueError("P68 oversized native evidence rejected")
            (out / (flag[2:] + ".log")).write_text(
                (response.stdout or "") + "\n" + (response.stderr or ""),
                encoding="utf-8")
        caps = parse_capabilities(capability.read_text(encoding="utf-8"))
        params = parse_parameters(parameters.read_text(encoding="utf-8"),
                                  caps["parameter_count"])
        if any(digest(Path(name)) != sha for name, sha in pins.items()):
            raise ValueError("P68 binaries modified during native inventory")
        draft = build_draft(bundle, module, gui_host, caps, params, other)
        draft_file.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
        result["status"] = "DISCOVERY_COMPLETE"
        result["parameter_count"] = len(params)
        result["bus_count"] = len(caps["buses"])
        result["reported_editor_available"] = bool(caps["editor_available"])
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as error:
        result["faults"].append(str(error))
    result_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--gui-host", type=Path, required=True)
    parser.add_argument("--audio-host", type=Path)
    parser.add_argument("--stress-host", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = discover(args.plugin, args.gui_host, args.out,
                          audio_host=args.audio_host, stress_host=args.stress_host)
    except (OSError, ValueError) as error:
        args.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL", "faults": [str(error)],
                  "product_feature_completeness": "NOT ESTABLISHED",
                  "release_approved": False}
        (args.out / "DISCOVERY-RESULT.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "DISCOVERY_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
