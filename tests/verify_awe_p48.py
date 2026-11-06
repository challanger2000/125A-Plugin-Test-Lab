#!/usr/bin/env python3
"""P48 exact current AWE source, native regression and independent VST3 host audit.

A green VST3 technical result does NOT prove ROM/SF2 preset sound, chorus
hardware equivalence, 128-sample ASIO deadlines or a commercial DAW.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "125a-awe-p48-source-host-acceptance-v1"
AWE_STABLE_SOURCE = "c7d803c1b328166f6f5edcb770aa9c9f8b49ecda"
EXPECTED_NATIVE_TESTS = (
    "125A_p122_state_snapshot",
    "125A_p128_sample_accurate_program_pcm",
    "125A_p128_persistent_controls",
    "125A_p130_no_cpp_new_on_audio_thread",
)
TECHNICAL_HOST = (
    "api_playback_save", "sample_rate_buffer_matrix",
    "native_audio_state_capture", "fresh_process_project_recall",
    "native_gui_lifecycle", "same_process_dual_instance_lifecycle",
)
RELEASE_BLOCKERS = (
    "user_supplied_rom_sf2_actual_preset_audio",
    "independent_emu8000_analog_hardware_reference",
    "chorus_hardware_feedback_equivalence",
    "128_256_frame_target_asio_deadline_validation",
    "all_bank_program_and_gui_controls_end_to_end",
    "save_recall_under_simultaneous_running_notes",
    "windows_real_daw_open_edit_save_reload",
    "commercial_product_manual_approval",
)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def audit(ctest_path, quickcheck_path, module_path, source_sha):
    if source_sha != AWE_STABLE_SOURCE:
        raise ValueError("AWE source drift: not the independently pinned 6 Nov production branch revision")
    native = Path(ctest_path).read_text(encoding="utf-8-sig", errors="replace")
    if (re.search(r"100% tests passed,\s*0 tests failed out of (\d+)", native)
            is None or "[FAIL]" in native or "No tests were found" in native):
        raise ValueError("actual AWE source-built Windows native CTests are missing or failed")
    count = int(re.search(
        r"100% tests passed,\s*0 tests failed out of (\d+)", native).group(1))
    if count < len(EXPECTED_NATIVE_TESTS) + 15:
        raise ValueError("AWE native suite unexpectedly shrank")
    if any(native.count(name) != 1 for name in EXPECTED_NATIVE_TESTS):
        # CTest prints every test name on its result line once.
        raise ValueError("essential AWE recall/GUI/program/allocation regression missing")
    quick = json.loads(Path(quickcheck_path).read_text(encoding="utf-8"))
    actual_hash = sha_file(module_path)
    if (quick.get("schema") != "125a-quickcheck-result-v1" or
            quick.get("status") != "TECHNICAL_PASS" or
            quick.get("release_approved") is not False or
            quick.get("verified_module_sha256") != actual_hash):
        raise ValueError("AWE native Test Lab quickcheck failed or binary SHA mismatch")
    coverage = quick.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError("missing independent technical AWE coverage")
    missing = [name for name in TECHNICAL_HOST if coverage.get(name) != "PASS"]
    if missing:
        raise ValueError("AWE real VST3 host tests were omitted or failed: " + ",".join(missing))
    if (coverage.get("commercial_daw_integration") != "NOT COVERED" or
            coverage.get("independent_musical_audio") != "NOT COVERED" or
            coverage.get("preset_semantics") != "NOT COVERED" or
            coverage.get("product_gui_controls") != "NOT COVERED"):
        raise ValueError("AWE quickcheck falsely credited product or commercial DAW semantics")
    return {
        "schema": SCHEMA, "status": "TECHNICAL_PASS",
        "verified_awe_source_sha": source_sha,
        "verified_vst3_binary_sha256": actual_hash,
        "actual_product_ctests_passed": count,
        "required_native_regression_names": list(EXPECTED_NATIVE_TESTS),
        "independent_vst3_host_passes": list(TECHNICAL_HOST),
        "unverified_product_release_requirements":
            {item: "NOT COVERED" for item in RELEASE_BLOCKERS},
        "rom_sf2_preset_pcm_approved": False,
        "chorus_hardware_reference_approved": False,
        "target_asio_deadlines_approved": False,
        "all_gui_controls_approved": False,
        "studio_one_integration_tested": False,
        "release_approved": False,
        "product_gui_status": "NO-GO",
        "commercial_release_status": "NO-GO",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ctest", type=Path, required=True)
    ap.add_argument("--quickcheck", type=Path, required=True)
    ap.add_argument("--module", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.unlink(missing_ok=True)
    try:
        result = audit(a.ctest, a.quickcheck, a.module, a.source_sha)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        result = {"schema": SCHEMA, "status": "FAIL", "release_approved": False,
                  "commercial_release_status": "NO-GO", "error": str(error)}
    a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print("[{}] real AWE VST3 product and independent Test Lab host; release: NO-GO".format(
        result["status"]))
    return 0 if result["status"] == "TECHNICAL_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
