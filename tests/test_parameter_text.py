#!/usr/bin/env python3
"""Adversarial VST3 label / normalized value conversion evidence tests."""
import importlib.util
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location(
    "text_verify", Path(__file__).with_name("verify_parameter_text.py"))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def utf16(s):
    return s.encode("utf-16-be").hex()


def text_probe(index, identifier, target, display=None, reverse=None,
               reverse_label=None, outcome=None):
    if display is None:
        return "text\t%d\t%d\t%.17g\t-\t-\t-\t-\tNOT_COVERED" % (
            index, identifier, target)
    if reverse is None:
        return "text\t%d\t%d\t%.17g\t%s\tN\t-\t-\t%s" % (
            index, identifier, target, utf16(display),
            outcome or "PASS")
    return "text\t%d\t%d\t%.17g\t%s\tR\t%.17g\t%s\t%s" % (
        index, identifier, target, utf16(display), reverse,
        utf16(reverse_label), outcome or "PASS")


def evidence(bad=False):
    rows = [
        "format\t125A-GUI-TEXT-v1", "param_count\t3",
        "tested\t2", "skipped\t1", "failed\t%d" % int(bad),
        "observations\t7", "readable\t7", "reversible\t2",
        "param\t0\t9001\t1\t1\t" + ("FAIL" if bad else "PASS"),
        text_probe(0, 9001, 0, "OFF", 1 if bad else 0,
                   "ON" if bad else "OFF", "FAIL" if bad else "PASS"),
        text_probe(0, 9001, 1, "ON", 0 if bad else 1,
                   "OFF" if bad else "ON", "FAIL" if bad else "PASS"),
        "param\t1\t9002\t0\t0\tSKIP",
        "param\t2\t9003\t0\t1\tPASS",
    ]
    rows += [text_probe(2, 9003, target, "%.2f dB" % (target * 12))
             for target in (0, .25, .5, .75, 1)]
    return "\n".join(rows) + "\n"


with tempfile.TemporaryDirectory() as root:
    path = Path(root) / "native-text.tsv"
    path.write_text(evidence(), encoding="utf-8")
    passed = verify.audit(path)
    assert passed["status"] == "PASS", passed
    assert passed["parameters_with_readable_labels"] == 2
    assert passed["parameters_with_reversible_labels"] == 1
    assert passed["parameter_label_probes"] == 7
    assert passed["parameter_reverse_probes"] == 2
    assert passed["text_label_api"] == "PASS"
    assert passed["reverse_text_api"] == "NOT COVERED", "partial parser coverage misclassified"
    assert passed["actual_editor_painted_values"] == "NOT COVERED"
    assert passed["release_approved"] is False

    path.write_text(evidence(bad=True), encoding="utf-8")
    failed = verify.audit(path)
    assert failed["status"] == "FAIL"
    assert failed["failed_parameter_text_mappings"] == 1
    assert failed["text_label_api"] == "FAIL"

    base = evidence()
    mutations = {
        "missing_native_case": base.replace(
            text_probe(2, 9003, .75, "9.00 dB") + "\n", ""),
        "fake_green_count": evidence(bad=True).replace("failed\t1", "failed\t0"),
        "fake_green_param": evidence(bad=True).replace(
            "param\t0\t9001\t1\t1\tFAIL", "param\t0\t9001\t1\t1\tPASS"),
        "fake_green_point": evidence(bad=True).replace(
            "text\t0\t9001\t0\t" + utf16("OFF") + "\tR\t1\t" + utf16("ON") + "\tFAIL",
            "text\t0\t9001\t0\t" + utf16("OFF") + "\tR\t1\t" + utf16("ON") + "\tPASS"),
        "missing_param": base.replace("param\t1\t9002\t0\t0\tSKIP\n", ""),
        "wrong_schema": base.replace("125A-GUI-TEXT-v1", "125A-GUI-TEXT-v0"),
        "reordered_cases": base.replace(
            "text\t0\t9001\t0\t", "text\t0\t9001\t1\t"),
        "surrogate_error": base.replace(utf16("ON"), "d800"),
        "nonhex_text": base.replace(utf16("OFF"), "000g"),
        "not_terminated": base.replace(utf16("ON"), "0061" * 128),
        "skipped_marked_pass": base.replace(
            "param\t1\t9002\t0\t0\tSKIP", "param\t1\t9002\t0\t0\tPASS"),
        "reverse_forged": base.replace(
            "\tR\t0\t" + utf16("OFF"), "\tN\t0\t" + utf16("OFF")),
        "quantized_wrong_discrete": base.replace(
            "\tR\t1\t" + utf16("ON"), "\tR\t0.5\t" + utf16("ON")),
        "wrong_last_counter": base.replace("reversible\t2", "reversible\t1"),
        "duplicate_id": base.replace("param\t2\t9003", "param\t2\t9001"),
        "extra_tail": base + "unverified\tPASS\n",
    }
    for name, broken in mutations.items():
        path.write_text(broken, encoding="utf-8")
        try:
            verify.audit(path)
        except (ValueError, OverflowError, UnicodeError):
            pass
        else:
            raise AssertionError("forged green VST3 label evidence accepted: " + name)

    # All reversible cases => global reverse PASS, unlike the mixed
    # instrument whose continuous parameter has no reverse text parser.
    only_reversible = "\n".join([
        "format\t125A-GUI-TEXT-v1", "param_count\t1", "tested\t1",
        "skipped\t0", "failed\t0", "observations\t2",
        "readable\t2", "reversible\t2",
        "param\t0\t9001\t1\t1\tPASS",
        text_probe(0, 9001, 0, "OFF", 0, "OFF"),
        text_probe(0, 9001, 1, "ON", 1, "ON"),
        "",
    ])
    path.write_text(only_reversible, encoding="utf-8")
    all_supported = verify.audit(path)
    assert all_supported["status"] == "PASS"
    assert all_supported["reverse_text_api"] == "PASS"
    assert all_supported["text_label_api"] == "PASS"

    # A valid instrument may not implement textual reverse conversion.
    no_text = "\n".join([
        "format\t125A-GUI-TEXT-v1", "param_count\t1", "tested\t1",
        "skipped\t0", "failed\t0", "observations\t2",
        "readable\t0", "reversible\t0",
        "param\t0\t9001\t1\t1\tNOT_COVERED",
        text_probe(0, 9001, 0), text_probe(0, 9001, 1),
        "",
    ])
    path.write_text(no_text, encoding="utf-8")
    missing_api = verify.audit(path)
    assert missing_api["status"] == "PASS"
    assert missing_api["text_label_api"] == "NOT COVERED"
    assert missing_api["reverse_text_api"] == "NOT COVERED"
    assert missing_api["parameters_with_readable_labels"] == 0
print("[PASS] independent VST3 parameter text oracle rejects wrong labels and fake PASS data")
