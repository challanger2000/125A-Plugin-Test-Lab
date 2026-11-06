#!/usr/bin/env python3
"""Adversarial verification for controller parameter inventory evidence."""
import importlib.util
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location(
    "param_audit", Path(__file__).with_name("verify_parameter_inventory.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

with tempfile.TemporaryDirectory() as td:
    file = Path(td) / "parameters.tsv"
    positive = ("format\t125A-GUI-PARAMS-v1\nparam_count\t2\n"
                "param\t0\t9001\t1\t0\t0\t1\n"
                "param\t1\t9002\t127\t0.5\t0.25\t1\n")
    file.write_text(positive, encoding="utf-8")
    assert mod.audit(file)["unique_ids_checked"] == 2
    assert mod.audit(file)["user_visible_control_coverage"] == "NOT COVERED"
    mutations = {
        "duplicate": positive.replace("param\t1\t9002", "param\t1\t9001"),
        "missing": positive.replace("param_count\t2", "param_count\t3"),
        "reordered": positive.replace("param\t1\t9002", "param\t0\t9002"),
        "nonfinite": positive.replace("0.5\t0.25", "nan\t0.25"),
        "infinite": positive.replace("0.5\t0.25", "0.5\tinf"),
        "out_of_range": positive.replace("0.5\t0.25", "0.5\t1.5"),
        "bad_schema": positive.replace("125A-GUI-PARAMS-v1", "faked"),
        "bad_id": positive.replace("9002", "4294967296"),
        "extra_fields": positive.replace("0.5\t0.25\t1", "0.5\t0.25\t1\tbogus"),
    }
    for name, body in mutations.items():
        file.write_text(body, encoding="utf-8")
        try:
            mod.audit(file)
        except (ValueError, OverflowError):
            pass
        else:
            raise AssertionError("untrustworthy parameter inventory was green: "+name)
    file.write_text("format\t125A-GUI-PARAMS-v1\nparam_count\t0\n", encoding="utf-8")
    assert mod.audit(file)["advertised_parameters"] == 0
print("[PASS] VST3 parameter inventory detects all malformed and forged records")
