#!/usr/bin/env python3
"""Adversarial acceptance tests: no stale Drumator release or false GUI PASS."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile


spec = importlib.util.spec_from_file_location(
    "p47", Path(__file__).with_name("verify_drumator_v15_acceptance.py"))
p47 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p47)


def midi_17():
    tracks = []
    for idx in range(17):
        body = b"\x00\xff\x2f\x00"
        tracks.append(b"MTrk" + struct.pack(">I", len(body)) + body)
    return b"MThd" + struct.pack(">IHHH", 6, 1, 17, 960) + b"".join(tracks)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    binary = root / "Drumator.vst3"
    binary.write_bytes(b"source-built exact test identity" * 100)
    exports = root / "GUI"
    exports.mkdir()
    for name in p47.EXPECTED_EXPORTS:
        (exports / name).write_bytes(midi_17())
    gates = {name: {"status": "PASS"} for feature in p47.PASS_DOMAINS.values()
             for name in feature}
    proof = {
        "schema": "125a-testlab-release-evidence-v1",
        "summary": "PASS",
        "exact_tested_product_sha": p47.VERIFIED_SOURCE,
        "checked_gates": gates,
    }
    evidence = root / "RELEASE-EVIDENCE.json"
    evidence.write_text(json.dumps(proof), encoding="utf-8")

    passed = p47.audit(evidence, exports, p47.VERIFIED_SOURCE, binary)
    assert passed["status"] == "TECHNICAL_PASS", passed
    assert passed["checks_passed"] == len(p47.PASS_DOMAINS)
    assert passed["requirements_not_covered"] == len(
        p47.REQUIRES_PRODUCT_SPEC_AND_LIVE_HOST)
    assert passed["release_approved"] is False
    assert passed["exact_customer_package_file_tested"] == "NOT VERIFIED"
    assert passed["full_gui_interaction_coverage"] == "NOT COVERED"
    assert passed["commercial_daw_tested"] is False
    assert passed["external_ole_drop_target_tested"] is False
    for n in p47.EXPECTED_EXPORTS:
        assert passed["independently_checked_gui_midi"][n]["tracks"] == 17

    def reject(label, **kwargs):
        try:
            p47.audit(kwargs.get("evidence", evidence),
                      kwargs.get("exports", exports),
                      kwargs.get("sha", p47.VERIFIED_SOURCE),
                      kwargs.get("binary", binary))
        except (ValueError, OSError):
            return
        raise AssertionError("P47 accepted forged product proof: " + label)

    reject("old P03 benchmark", sha="eed1bf232b61f6fb725ca00d82a99658cfba07e2")
    reject("unverified branch tip", sha="52dedc399424261a93905c622ca3ef42606e9207")
    reject("source hash mismatch", sha="a" * 40)
    reject("missing GUI MIDI", exports=root)
    reject("missing built VST3", binary=root / "missing.vst3")

    invalid = dict(proof, exact_tested_product_sha="a" * 40)
    evidence.write_text(json.dumps(invalid), encoding="utf-8")
    reject("forged release SHA")
    evidence.write_text(json.dumps(proof), encoding="utf-8")

    invalid = dict(proof, summary="FAIL")
    evidence.write_text(json.dumps(invalid), encoding="utf-8")
    reject("false technical release success")
    evidence.write_text(json.dumps(proof), encoding="utf-8")

    broken = dict(gates)
    broken["P09_live_gui"] = {"status": "FAIL"}
    invalid = dict(proof, checked_gates=broken)
    evidence.write_text(json.dumps(invalid), encoding="utf-8")
    reject("broken real GUI acceptance gate")
    evidence.write_text(json.dumps(proof), encoding="utf-8")

    file = exports / "song-midi.mid"
    original = file.read_bytes()
    # A superficially valid MIDI with 1 track (instead of 17) is a
    # commercial V1.5 format regression regardless of whether notes sound.
    file.write_bytes(
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, 960) +
        b"MTrk" + struct.pack(">I", 4) + b"\x00\xff\x2f\x00")
    reject("MIDI Format 0 / one merged track")
    file.write_bytes(original)
    file.write_bytes(original[:-3])
    reject("truncated MIDI EOT")
    file.write_bytes(original)

print("[PASS] P47 exact latest Drumator V1.5 evidence rejects stale source, wrong MIDI format and false feature coverage")
