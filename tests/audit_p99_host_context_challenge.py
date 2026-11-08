#!/usr/bin/env python3
"""P99 self-challenge of advertised VST3 process musical position validity.

Pure SOURCE-contract evidence, not a native ASIO driver run.
"""
import json
import pathlib
import re


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    asio = (root / "src" / "physical_asio.cpp").read_text(encoding="utf-8")
    offline = (root / "src" / "main.cpp").read_text(encoding="utf-8")
    oracle = (root / "tests" / "signal_fixture.cpp").read_text(encoding="utf-8")
    decl = re.search(r"\bcontext\.state\s*=\s*(.*?);", asio, re.S)
    main = re.search(r"\bctx\.state\s*=\s*(.*?);", offline, re.S)
    if not decl or not main:
        raise AssertionError("Cannot independently find the two actual VST3 context declarations")
    if ("kProjectTimeMusicValid" not in main.group(1) or
            "kProjectTimeMusicValid" not in oracle):
        raise AssertionError("Independent main host and actual VST3 fixture do not establish expected music-position validity")
    if not re.search(r"p\.context\.projectTimeMusic\s*=", asio):
        raise AssertionError("ASIO host does not actually report musical position")
    mismatch = "kProjectTimeMusicValid" not in decl.group(1)
    report = {
        "schema": "125a-audit-p99-host-context-challenge-v1",
        "source_comparison": {
            "asio_host_music_position_written": True,
            "asio_host_music_position_valid_flag": not mismatch,
            "main_host_music_position_valid_flag": True,
            "real_vst3_fixture_requires_music_position_valid_flag": True
        },
        "missing_ppq_validity_source_defect": mismatch,
        "real_asio_vst3_session": "NOT RUN",
        "actual_runtime_fault_reproduced": False,
        "release_approved": False
    }
    folder = root / "artifacts" / "P99-audit"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ASIO-PROCESS-CONTEXT-COUNTERPROOF.json").write_text(
        json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if mismatch:
        raise AssertionError("P99 ASIO host writes projectTimeMusic but omits kProjectTimeMusicValid")
    print("[AUDIT] Source contracts now agree. Actual ASIO driver still NOT RUN.")


if __name__ == "__main__":
    main()
