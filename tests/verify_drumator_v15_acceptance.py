#!/usr/bin/env python3
"""P47: exact real Drumator V1.5 acceptance matrix, never a fake GUI release.

This reads *actual* native Windows P03 evidence and product tests against a
separately pinned, already validated V1.5 source commit. It distinguishes
what the host really proved from requirements it did not exercise.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from verify_midi_export import parse

SCHEMA = "125a-drumator-v15-real-acceptance-v1"
VERIFIED_SOURCE = "3f1e82c99e716071486fa73b81c3e4f062400276"
DOCUMENTED_RELEASE_BINARY = "33bcf9e5d270192ba55cf211e63f1efa004f6e5230d33bc4090ad6b300e189be"
PASS_DOMAINS = {
    "swing_live_audio": ("P03_audio_swing", "P05_audio_matrix"),
    "beat_creator_structural_10_styles": ("P07_beat_creator",),
    "beat_creator_gui_cancel_apply": ("P09_live_gui",),
    "gui_save_as_pattern_song_wav_midi": ("P11_gui_save_as",),
    "export_dialog_open_cancel": ("P10_save_dialogs",),
    "midi_smftype1_17tracks_960ppq": ("P06_midi_export", "P11_gui_save_as"),
    "offline_wav_musical_timing": ("P08_wav_export", "P11_gui_save_as"),
    "saved_state_fresh_process_recall": ("P18_fresh_process_recall",),
    "corrupt_state_rejected": ("P20_corrupt_state_rejection",),
    "gui_96_clicks_state_recovery": ("P19_gui_stress",),
    "gui_detach_reattach": ("P17_gui_lifecycle",),
    "drag_source_files_generated": ("P13_drag_source",),
}
# Real production feature coverage, not estimates from source code or image.
REQUIRES_PRODUCT_SPEC_AND_LIVE_HOST = (
    "beat_creator_complexity_plus_minus_5_live_clicks",
    "all_gui_buttons_and_knobs_end_to_end",
    "velocity_multi_edit_curve_shortcuts",
    "swing_knob_live_gui_numeric_0_to_100",
    "mute_solo_running_audio_tails",
    "song_playback_pattern_indicator_sync",
    "kit_and_preset_browser_restore",
    "sample_preview_and_clear",
    "row_name_edit_and_wav_editor",
    "midi_drag_to_real_daw_tracks",
    "wav_drag_to_real_daw",
    "commercial_daw_save_reload",
    "commercial_daw_mute_solo",
    "commercial_daw_audio_realtime",
)
EXPECTED_EXPORTS = ("pattern-midi.mid", "song-midi.mid")
SHA = re.compile(r"[0-9a-f]{40}\Z")


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(evidence, midi_folder, product_sha, built_binary,
          *, expected_source=VERIFIED_SOURCE):
    if not isinstance(product_sha, str) or not SHA.fullmatch(product_sha):
        raise ValueError("tested product revision is not an exact 40-character SHA")
    if product_sha != expected_source or expected_source != VERIFIED_SOURCE:
        raise ValueError("stale/wrong Drumator V1.5 reference; must test independently verified 6 Nov source")
    native = json.loads(Path(evidence).read_text(encoding="utf-8"))
    if (native.get("schema") != "125a-testlab-release-evidence-v1" or
            native.get("summary") != "PASS" or
            native.get("exact_tested_product_sha") != product_sha):
        raise ValueError("P47 acceptance evidence does not belong to verified V1.5 product SHA")
    gates = native.get("checked_gates", {})
    needed = {gate for group in PASS_DOMAINS.values() for gate in group}
    if not isinstance(gates, dict) or not needed <= set(gates):
        raise ValueError("missing independently recorded P03 product acceptance gates")
    if any(gates[gate].get("status") != "PASS" for gate in needed):
        raise ValueError("independent real Drumator Windows product gate failed")
    # A tested source SHA does not prove the exact DLL shipped to customers.
    # Record both hashes and give an independent, honest match indicator.
    binary = Path(built_binary)
    if not binary.is_file() or binary.stat().st_size < 1024:
        raise ValueError("actual built Drumator VST3 DLL missing")
    built_hash = file_hash(binary)
    midi_folder = Path(midi_folder)
    if not midi_folder.is_dir():
        raise ValueError("missing real Drumator Windows GUI Save As exports")
    evidence_files = {}
    for name in EXPECTED_EXPORTS:
        file = midi_folder / name
        if not file.is_file():
            raise ValueError("actual GUI MIDI export missing: " + name)
        parsed = parse(file.read_bytes())
        if parsed.format != 1 or parsed.tracks != 17 or parsed.division != 960:
            raise ValueError("Drumator V1.5 MIDI regression: expected single Type-1 SMF with 17 tracks at PPQ 960")
        evidence_files[name] = {
            "sha256": file_hash(file), "smf_format": parsed.format,
            "tracks": parsed.tracks, "ppq": parsed.division,
            "notes_on": len(parsed.on),
        }
    covered = {feature: "PASS" for feature in PASS_DOMAINS}
    uncovered = {feature: "NOT COVERED" for feature in REQUIRES_PRODUCT_SPEC_AND_LIVE_HOST}
    report = {
        "schema": SCHEMA,
        "status": "TECHNICAL_PASS",
        "release_approved": False,
        "verified_product_source_sha": product_sha,
        "independently_verified_source_sha": VERIFIED_SOURCE,
        "built_vst3_dll_sha256": built_hash,
        "documented_customer_package_dll_sha256": DOCUMENTED_RELEASE_BINARY,
        "source_built_dll_byteidentical_to_customer_package":
            built_hash == DOCUMENTED_RELEASE_BINARY,
        "exact_customer_package_file_tested": "NOT VERIFIED",
        "independently_checked_gui_midi": evidence_files,
        "covered": covered,
        "not_covered": uncovered,
        "checks_passed": len(covered),
        "requirements_not_covered": len(uncovered),
        "commercial_daw_tested": False,
        "external_ole_drop_target_tested": False,
        "full_gui_interaction_coverage": "NOT COVERED",
        "actual_customer_v15_release_approval": "NOT GRANTED",
        "why_not_fully_approved": (
            "The tests verify real standalone VST3 GUI/DSP/export actions, not every user-visible "
            "control, Studio One or the exact customer ZIP binary; untested requirements stay NOT COVERED."
        ),
    }
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release-evidence", type=Path, required=True)
    p.add_argument("--gui-exports", type=Path, required=True)
    p.add_argument("--product-sha", required=True)
    p.add_argument("--built-binary", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.unlink(missing_ok=True)
    try:
        result = audit(args.release_evidence, args.gui_exports,
                       args.product_sha, args.built_binary)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {
            "schema": SCHEMA, "status": "FAIL", "release_approved": False,
            "actual_customer_v15_release_approval": "NOT GRANTED",
            "error": str(error),
        }
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print("[{}] Real V1.5 source-pinned product acceptance: {} proven, {} untested".format(
        result["status"], result.get("checks_passed", 0),
        result.get("requirements_not_covered", "unknown")))
    return 0 if result["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
