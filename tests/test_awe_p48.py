#!/usr/bin/env python3
"""P48 independent negative oracles: reject stale AWE and fake sound release."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile


spec = importlib.util.spec_from_file_location(
    "p48", Path(__file__).with_name("verify_awe_p48.py"))
p48 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p48)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    module = root / "125A_AWE_Synthesizer.vst3"
    module.write_bytes(b"Real tested binary identity, not a mock product!" * 150)
    ctest = root / "ctest.txt"
    names = [*p48.EXPECTED_NATIVE_TESTS] + [
        f"125A_independent_fixture_{i:02}" for i in range(18)]
    lines = [f" {i}/{len(names)} Test #{i}: {name} ... Passed"
             for i, name in enumerate(names, 1)]
    lines.append(f"100% tests passed, 0 tests failed out of {len(names)}")
    ctest.write_text("\n".join(lines) + "\n")
    quick = root / "QUICKCHECK-RESULT.json"
    coverage = {name: "PASS" for name in p48.TECHNICAL_HOST}
    coverage.update({
        "commercial_daw_integration": "NOT COVERED",
        "independent_musical_audio": "NOT COVERED",
        "preset_semantics": "NOT COVERED",
        "product_gui_controls": "NOT COVERED",
    })
    report = {
        "schema": "125a-quickcheck-result-v1", "status": "TECHNICAL_PASS",
        "release_approved": False,
        "verified_module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "coverage": coverage
    }
    quick.write_text(json.dumps(report))
    good = p48.audit(ctest, quick, module, p48.AWE_STABLE_SOURCE)
    assert good["status"] == "TECHNICAL_PASS"
    assert good["release_approved"] is False
    assert good["commercial_release_status"] == "NO-GO"
    assert good["actual_product_ctests_passed"] == len(names)
    assert len(good["unverified_product_release_requirements"]) >= 8
    assert all(v == "NOT COVERED" for v in
               good["unverified_product_release_requirements"].values())
    assert good["target_asio_deadlines_approved"] is False

    def reject(note, *, source=p48.AWE_STABLE_SOURCE):
        try:
            p48.audit(ctest, quick, module, source)
        except (ValueError, OSError):
            return
        raise AssertionError("P48 accepted a fake/stale AWE release PASS: " + note)

    reject("unrelated stale branch", source="a" * 40)
    original_log = ctest.read_text()
    ctest.write_text(original_log.replace(
        p48.EXPECTED_NATIVE_TESTS[0], "missing_state_snapshot"))
    reject("removed state regression")
    ctest.write_text(original_log.replace("100% tests passed", "98% tests passed"))
    reject("ctest false green")
    ctest.write_text(original_log)

    original_report = quick.read_text()
    invalid = json.loads(original_report)
    invalid["coverage"]["native_gui_lifecycle"] = "NOT COVERED"
    quick.write_text(json.dumps(invalid))
    reject("missing native GUI smoke")
    invalid = json.loads(original_report)
    invalid["coverage"]["independent_musical_audio"] = "PASS"
    quick.write_text(json.dumps(invalid))
    reject("fabricated ROM sound")
    invalid = json.loads(original_report)
    invalid["coverage"]["commercial_daw_integration"] = "PASS"
    quick.write_text(json.dumps(invalid))
    reject("fabricated Studio One test")
    invalid = json.loads(original_report)
    invalid["verified_module_sha256"] = "f" * 64
    quick.write_text(json.dumps(invalid))
    reject("wrong AWE binary hash")
    quick.write_text(original_report)

print("[PASS] P48 exact-source AWE test lab gate rejects fake native CTest, ROM, chorus and DAW certifications")
