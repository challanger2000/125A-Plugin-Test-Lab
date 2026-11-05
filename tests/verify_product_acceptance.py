#!/usr/bin/env python3
"""Independent production acceptance gate: missing user-facing tests are NO-GO.

A green infrastructure build or a synthetic QA fixture cannot approve a
commercial plugin. This command records precisely what is and is not covered.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

REQUIREMENTS = {
    "host_load_and_lifecycle": "Host load, close, reopen, disable/enable",
    "audio_callback_stability": "Audio callback, buffers, rate changes and realtime safety",
    "audio_output_correctness": "Independent audible PCM/reference comparison",
    "project_save_reload": "Real save/reload including new process and host session",
    "preset_switch_save_reload": "Preset load, switch, save and recall",
    "parameter_automation": "Real parameter automation and restored values",
    "gui_all_controls": "Every visible actionable control and its effect",
    "gui_lifecycle": "Editor close/open, reconnect and state refresh",
    "gui_dialogs": "Dialogs, file selection, cancellation and bad paths",
    "midi_input_mapping": "MIDI channel, mapping, velocity, notes and timing",
    "midi_export_roundtrip": "MIDI drag/export and independent re-import",
    "audio_export_roundtrip": "WAV export, exact frames, format, tails, re-import",
    "tempo_song_loop": "Host tempo, song mode, fills, loops and tails",
    "undo_redo_history": "Undo/redo, branching history and recovery",
    "invalid_state_rollback": "Invalid/corrupt project state rejected without damage",
    "concurrent_playback_save": "Playback plus repeated simultaneous state saves",
    "stress_resource_lifetime": "Rapid interaction, long sessions, leaks and crashes",
    "multi_instance_isolation": "Multiple plugin instances independent",
}
ID = re.compile(r"^[a-z][a-z0-9_]*$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(1048576), b""):
            h.update(piece)
    return h.hexdigest()


def inside(base, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("evidence path must be a relative file")
    p = (base / relative).resolve()
    if not p.is_relative_to(base.resolve()):
        raise ValueError("evidence path leaves report directory")
    return p


def evaluate(manifest, base):
    if manifest.get("schema") != "125a-product-acceptance-v1":
        raise ValueError("invalid acceptance schema")
    product = manifest.get("product")
    if not isinstance(product, dict) or not all(
            isinstance(product.get(k), str) and product[k].strip()
            for k in ("name", "version", "binary_sha256")):
        raise ValueError("product name, version and exact binary digest required")
    if not HEX64.fullmatch(product["binary_sha256"]):
        raise ValueError("invalid product binary SHA-256")
    entries = manifest.get("checks")
    if not isinstance(entries, dict):
        raise ValueError("checks must be a mapping")
    if set(entries) - set(REQUIREMENTS):
        raise ValueError("unknown acceptance requirement")
    results = {}
    for key, label in REQUIREMENTS.items():
        item = entries.get(key)
        faults = []
        if not isinstance(item, dict):
            faults.append("NO EVIDENCE")
        else:
            # An explicit declaration is never considered evidence itself.
            if item.get("plugin_sha256") != product["binary_sha256"]:
                faults.append("artifact not bound to exact product binary")
            if item.get("source") not in ("real-vst3", "real-windows-gui", "real-daw"):
                faults.append("synthetic or untrusted execution source")
            path = item.get("report")
            hash_expected = item.get("report_sha256")
            if not isinstance(hash_expected, str) or not HEX64.fullmatch(hash_expected):
                faults.append("independent report SHA-256 absent")
            try:
                evidence_path = inside(base, path)
                if not evidence_path.is_file():
                    faults.append("evidence report missing")
                elif isinstance(hash_expected, str) and HEX64.fullmatch(hash_expected):
                    if digest(evidence_path) != hash_expected:
                        faults.append("evidence report was altered")
                    else:
                        data = json.loads(evidence_path.read_text(encoding="utf-8"))
                        if not isinstance(data, dict) or data.get("status") != "PASS":
                            faults.append("independent report did not PASS")
                        if data.get("product_sha256") != product["binary_sha256"]:
                            faults.append("independent report product mismatch")
                        if data.get("requirement") != key:
                            faults.append("independent report tested another requirement")
                        if data.get("oracle") != "independent":
                            faults.append("no independent expected-vs-observed oracle")
                        if data.get("negative_control") != "DETECTED":
                            faults.append("no proven negative control")
            except (ValueError, OSError, json.JSONDecodeError, TypeError) as exc:
                faults.append("invalid evidence: " + str(exc))
        results[key] = {"title": label, "status": "PASS" if not faults else "NOT COVERED",
                        "faults": faults}
    passed = all(r["status"] == "PASS" for r in results.values())
    return {"schema": "125a-product-acceptance-result-v1",
            "product": product, "status": "PASS" if passed else "NO-GO",
            "covered": sum(r["status"] == "PASS" for r in results.values()),
            "required": len(REQUIREMENTS),
            "checks": results,
            "warning": "Evidence index checks do not independently authenticate the capture host or DAW."}


def main():
    p = argparse.ArgumentParser(description="Fail closed on missing user-acceptance evidence")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        obj = json.loads(a.manifest.read_text(encoding="utf-8"))
        result = evaluate(obj, a.manifest.parent)
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        result = {"schema": "125a-product-acceptance-result-v1",
                  "status": "NO-GO", "error": str(exc)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[{}] production acceptance".format(result["status"]))
    if "covered" in result:
        print("{}/{} requirements verified".format(result["covered"], result["required"]))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
