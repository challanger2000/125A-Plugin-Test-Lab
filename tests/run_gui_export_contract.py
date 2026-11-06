#!/usr/bin/env python3
"""P46: Independently audit files created by approved *real* VST3 GUI actions.

This does not manufacture a semantic oracle from observed plugin data:
the exact SHA256 and WAV/MIDI format requirements must be independently
specified before running the plugin. Only explicitly declared controls
and explicitly listed output files can be credited.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave

from run_gui_workflow import run as gui_workflow_run, validate as gui_validate, digest

SCHEMA = "125a-gui-export-contract-v1"
RESULT = "125a-gui-export-contract-result-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")


def require_field(data, key, kind):
    if not isinstance(data, dict) or key not in data or type(data[key]) is not kind:
        raise ValueError("missing/invalid independent export field: " + key)
    return data[key]


def validate(contract):
    if not isinstance(contract, dict) or set(contract) != {
            "schema", "workflow", "expected_exports"} or contract["schema"] != SCHEMA:
        raise ValueError("unrecognized or incomplete independent GUI export contract")
    wf = contract["workflow"]
    host, bundle, binary, initial, steps = gui_validate(wf)
    expected = contract["expected_exports"]
    if not isinstance(expected, list) or not 1 <= len(expected) <= 16:
        raise ValueError("independent file oracle requires 1-16 expected outputs")
    seen = set()
    for item in expected:
        if not isinstance(item, dict):
            raise ValueError("invalid independent file oracle")
        kind = require_field(item, "type", str)
        name = require_field(item, "filename", str)
        exact_hash = require_field(item, "sha256", str)
        if not NAME.fullmatch(name) or name in (".", "..") or name in seen:
            raise ValueError("unsafe, duplicated or nested export name")
        if not HEX.fullmatch(exact_hash):
            raise ValueError("missing approved independent export SHA-256")
        seen.add(name)
        if kind == "wav":
            if set(item) != {
                    "filename", "type", "sha256", "channels", "sample_rate",
                    "sample_width_bits", "frames"}:
                raise ValueError("WAV must specify independent frame/rate/channel/bit oracle")
            for k, low, high in (
                    ("channels", 1, 32), ("sample_rate", 8000, 384000),
                    ("sample_width_bits", 8, 32), ("frames", 1, 20000000)):
                v = require_field(item, k, int)
                if v < low or v > high:
                    raise ValueError("invalid approved WAV field: " + k)
            if item["sample_width_bits"] not in (8, 16, 24, 32):
                raise ValueError("unsupported WAV PCM width")
            if not name.lower().endswith(".wav"):
                raise ValueError("WAV contract file extension mismatch")
        elif kind == "midi":
            if set(item) != {"filename", "type", "sha256", "format",
                             "tracks", "ticks_per_quarter", "note_on_count"}:
                raise ValueError("MIDI oracle requires format/tracks/PPQ/note count")
            for key, low, high in (
                    ("format", 0, 1), ("tracks", 1, 64),
                    ("ticks_per_quarter", 1, 32767), ("note_on_count", 0, 200000)):
                value = require_field(item, key, int)
                if not low <= value <= high:
                    raise ValueError("invalid approved MIDI expected " + key)
            if item["format"] == 0 and item["tracks"] != 1:
                raise ValueError("SMF Format 0 must have exactly one track")
            if not name.lower().endswith((".mid", ".midi")):
                raise ValueError("MIDI contract extension mismatch")
        else:
            raise ValueError("only independently validated WAV and MIDI outputs supported")
    return host, bundle, binary, steps, expected


def midi_vlq(data, cursor):
    value = 0
    for _ in range(4):
        if cursor >= len(data):
            raise ValueError("truncated MIDI VLQ")
        b = data[cursor]
        cursor += 1
        value = (value << 7) | (b & 127)
        if not b & 128:
            return value, cursor
    raise ValueError("oversized MIDI VLQ")


def midi_evidence(data):
    if len(data) < 22 or data[:4] != b"MThd" or int.from_bytes(
            data[4:8], "big") != 6:
        raise ValueError("export is not strict SMF MIDI")
    fmt = int.from_bytes(data[8:10], "big")
    tracks = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    if fmt not in (0, 1) or not 1 <= tracks <= 64 or (
            fmt == 0 and tracks != 1) or division == 0 or division & 0x8000:
        raise ValueError("invalid independent MIDI header")
    pos = 14
    ons = 0
    for _ in range(tracks):
        if pos + 8 > len(data) or data[pos:pos + 4] != b"MTrk":
            raise ValueError("missing MIDI track")
        length = int.from_bytes(data[pos + 4:pos + 8], "big")
        pos += 8
        end = pos + length
        if end > len(data):
            raise ValueError("MIDI track length extends beyond file")
        running = 0
        ended = False
        while pos < end:
            _, pos = midi_vlq(data, pos)
            if pos >= end:
                raise ValueError("MIDI event status missing")
            status = data[pos]
            if status < 128:
                if not 128 <= running <= 239:
                    raise ValueError("MIDI running status missing")
                status = running
            else:
                pos += 1
                running = status if status < 240 else 0
            if status == 255:
                if pos >= end:
                    raise ValueError("MIDI meta type missing")
                event = data[pos]
                pos += 1
                size, pos = midi_vlq(data, pos)
                if pos + size > end:
                    raise ValueError("truncated MIDI meta event")
                if event == 47:
                    if size or pos + size != end:
                        raise ValueError("invalid MIDI track end event")
                    ended = True
                pos += size
            elif status in (240, 247):
                size, pos = midi_vlq(data, pos)
                pos += size
                if pos > end:
                    raise ValueError("truncated MIDI sysex payload")
            elif 128 <= status <= 239:
                command = status & 240
                n = 1 if command in (192, 208) else 2
                if pos + n > end or any(b >= 128 for b in data[pos:pos + n]):
                    raise ValueError("invalid MIDI channel data")
                if command == 144 and data[pos + 1] != 0:
                    ons += 1
                pos += n
            else:
                raise ValueError("unsupported malformed MIDI status event")
        if not ended:
            raise ValueError("MIDI track missing End Of Track")
    if pos != len(data):
        raise ValueError("unexpected trailing SMF bytes")
    return {"format": fmt, "tracks": tracks,
            "ticks_per_quarter": division, "note_on_count": ons}


def wav_evidence(path):
    # Python's wave module rejects unsupported compressed formats.
    with wave.open(str(path), "rb") as wav:
        if wav.getcomptype() != "NONE":
            raise ValueError("WAV export is compressed, expected PCM")
        return {
            "channels": wav.getnchannels(),
            "sample_rate": wav.getframerate(),
            "sample_width_bits": wav.getsampwidth() * 8,
            "frames": wav.getnframes(),
        }


def audit_outputs(folder, expected):
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("missing/unsafe isolated real plugin export directory")
    names = {x["filename"] for x in expected}
    observed = {}
    actual = list(folder.iterdir())
    if set(p.name for p in actual) != names or len(actual) != len(names):
        raise ValueError("GUI export missing, extra, or silently renamed files")
    for spec in expected:
        path = folder / spec["filename"]
        if not path.is_file() or path.is_symlink():
            raise ValueError("GUI export is not a genuine regular file")
        if not 0 < path.stat().st_size <= 128 * 1024 * 1024:
            raise ValueError("GUI output is empty or exceeds bounded audit size")
        hash_ = digest(path)
        if hash_ != spec["sha256"]:
            raise ValueError("independent GUI output SHA mismatch: " + spec["filename"])
        if spec["type"] == "wav":
            meta = wav_evidence(path)
        else:
            meta = midi_evidence(path.read_bytes())
        expected_meta = {k: v for k, v in spec.items()
                         if k not in ("filename", "sha256", "type")}
        if meta != expected_meta:
            raise ValueError("independent %s output properties wrong" % spec["type"])
        observed[path.name] = {"sha256": hash_, "format": spec["type"],
                               "metadata": meta, "bytes": path.stat().st_size}
    return observed


def run(manifest, out, timeout=90, runner=subprocess.run):
    host, bundle, binary, steps, expected = validate(manifest)
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise ValueError("invalid bounded GUI semantic export timeout")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "GUI-EXPORT-CONTRACT-RESULT.json"
    report_path.unlink(missing_ok=True)
    module_hash, host_hash = digest(binary), digest(host)
    report = {
        "schema": RESULT, "status": "FAIL",
        "verified_module_sha256": module_hash,
        "verified_gui_host_sha256": host_hash,
        "declared_gui_actions": len(steps),
        "expected_export_count": len(expected),
        "verified_export_count": 0, "verified_exports": {},
        "gui_declared_action_oracles": "NOT COVERED",
        "approved_independent_file_oracles": "NOT COVERED",
        "unmapped_gui_controls": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
        "release_approved": False, "faults": []
    }
    try:
        with tempfile.TemporaryDirectory(prefix="attempt-", dir=out) as sandbox:
            export_root = Path(sandbox)
            if list(export_root.iterdir()):
                raise ValueError("fresh export directory is contaminated")
            def native_runner(cmd, **kwargs):
                child_env = dict(os.environ)
                # Plugin-specific contract may use this as a tested output
                # directory hint; a normal plugin can also show a Save dialog.
                child_env["QA_TEST_LAB_EXPORT_ROOT"] = str(export_root)
                return runner(cmd, env=child_env, **kwargs)
            workflow_out = out / "gui-action-evidence"
            result = gui_workflow_run(
                manifest["workflow"], workflow_out, timeout=timeout,
                runner=native_runner)
            if (result.get("status") != "TECHNICAL_PASS" or
                    result.get("verified_actions") != len(steps) or
                    result.get("verified_module_sha256") != module_hash or
                    result.get("gui_host_sha256") != host_hash or
                    result.get("product_gui_complete") != "NOT COVERED"):
                raise ValueError("real GUI action did not satisfy independent workflow")
            report["gui_declared_action_oracles"] = "PASS"
            observed = audit_outputs(export_root, expected)
            if digest(binary) != module_hash or digest(host) != host_hash:
                raise ValueError("tested VST3 host/module changed during file export")
            report["verified_exports"] = observed
            report["verified_export_count"] = len(observed)
            report["approved_independent_file_oracles"] = "PASS"
            report["status"] = "CONTRACT_PASS"
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            wave.Error, subprocess.TimeoutExpired) as error:
        report["faults"].append(str(error))
        report["approved_independent_file_oracles"] = "FAIL"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=90)
    args = p.parse_args()
    try:
        contract = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = run(contract, args.out, timeout=args.timeout)
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            json.JSONDecodeError) as error:
        args.out.mkdir(parents=True, exist_ok=True)
        result = {
            "schema": RESULT, "status": "FAIL", "release_approved": False,
            "approved_independent_file_oracles": "FAIL", "faults": [str(error)]}
        (args.out / "GUI-EXPORT-CONTRACT-RESULT.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[%s] real VST3 GUI functional WAV/MIDI file contract" % result["status"])
    return 0 if result["status"] == "CONTRACT_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
