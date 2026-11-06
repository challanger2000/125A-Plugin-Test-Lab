#!/usr/bin/env python3
"""Adversarial parameter-sweep audit fixtures, including forged green reports."""
import importlib.util
from pathlib import Path
import tempfile


spec = importlib.util.spec_from_file_location(
    "sweep_audit", Path(__file__).with_name("verify_parameter_sweep.py"))
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

with tempfile.TemporaryDirectory() as root:
    path = Path(root) / "native-sweep.tsv"
    # Writable boolean, three-step discrete, continuous and unautomatable.
    correct = (
        "format\t125A-GUI-SWEEP-v1\n"
        "param_count\t4\n"
        "tested\t3\nskipped\t1\nfailed\t0\nobservations\t11\n"
        "param\t0\t9001\t1\t1\t0\tPASS\t1\n"
        "probe\t0\t9001\t0\t0\t1\n"
        "probe\t0\t9001\t1\t1\t1\n"
        "param\t1\t9002\t3\t1\t0.3333333333333333\tPASS\t1\n"
        "probe\t1\t9002\t0\t0\t1\n"
        "probe\t1\t9002\t0.3333333333333333\t0.3333333333333333\t1\n"
        "probe\t1\t9002\t0.6666666666666666\t0.6666666666666666\t1\n"
        "probe\t1\t9002\t1\t1\t1\n"
        "param\t2\t9003\t0\t1\t0.5\tPASS\t1\n"
        "probe\t2\t9003\t0\t0\t1\n"
        "probe\t2\t9003\t0.25\t0.25\t1\n"
        "probe\t2\t9003\t0.5\t0.5\t1\n"
        "probe\t2\t9003\t0.75\t0.75\t1\n"
        "probe\t2\t9003\t1\t1\t1\n"
        "param\t3\t9004\t1\t0\t0\tSKIP\t1\n"
    )
    path.write_text(correct, encoding="utf-8")
    checked = audit_module.audit(path)
    assert checked["status"] == "PASS", checked
    assert checked["writable_parameters"] == 3
    assert checked["independent_points_verified"] == 11
    assert checked["pixel_gui_controls"] == "NOT COVERED"
    assert checked["product_parameter_semantics"] == "NOT COVERED"

    # A broken VST3 legitimately reports a failed set/get boundary.
    broken = correct.replace("failed\t0", "failed\t1").replace(
        "param\t0\t9001\t1\t1\t0\tPASS\t1",
        "param\t0\t9001\t1\t1\t0\tFAIL\t1").replace(
        "probe\t0\t9001\t1\t1\t1", "probe\t0\t9001\t1\t0\t0")
    path.write_text(broken, encoding="utf-8")
    verdict = audit_module.audit(path)
    assert verdict["status"] == "FAIL" and verdict["failed_parameters"] == 1

    mutations = {
        "missing_case": correct.replace("probe\t2\t9003\t0.75\t0.75\t1\n", ""),
        "extra_case": correct + "probe\t2\t9003\t1\t1\t1\n",
        "duplicate_id": correct.replace("param\t1\t9002", "param\t1\t9001"),
        "wrong_count": correct.replace("param_count\t4", "param_count\t5"),
        "wrong_probe_count": correct.replace("observations\t11", "observations\t10"),
        "faked_green": broken.replace("failed\t1", "failed\t0").replace(
            "param\t0\t9001\t1\t1\t0\tFAIL\t1",
            "param\t0\t9001\t1\t1\t0\tPASS\t1"),
        "wrong_id": correct.replace("probe\t0\t9001\t1", "probe\t0\t9002\t1"),
        "wrong_set_target": correct.replace("probe\t2\t9003\t0.75", "probe\t2\t9003\t0.65"),
        "wrong_observed_value": correct.replace(
            "probe\t2\t9003\t0.75\t0.75\t1",
            "probe\t2\t9003\t0.75\t0.05\t1"),
        "readonly_falsely_tested": correct.replace(
            "param\t3\t9004\t1\t0\t0\tSKIP\t1",
            "param\t3\t9004\t1\t2\t0\tPASS\t1"),
        "missed_restore": correct.replace(
            "param\t0\t9001\t1\t1\t0\tPASS\t1",
            "param\t0\t9001\t1\t1\t0\tPASS\t0"),
        "nonfinite": correct.replace(
            "probe\t2\t9003\t0.5\t0.5\t1",
            "probe\t2\t9003\t0.5\tnan\t1"),
    }
    for title, body in mutations.items():
        path.write_text(body, encoding="utf-8")
        try:
            audit_module.audit(path)
        except (ValueError, OverflowError):
            pass
        else:
            raise AssertionError("forged native sweep evidence was accepted: " + title)

    path.write_text(
        "format\t125A-GUI-SWEEP-v1\nparam_count\t0\ntested\t0\n"
        "skipped\t0\nfailed\t0\nobservations\t0\n", encoding="utf-8")
    empty = audit_module.audit(path)
    assert empty["status"] == "PASS"
    assert empty["controller_roundtrip"] == "NOT COVERED"

print("[PASS] independent controller sweep rejects forged values and missing cases")
