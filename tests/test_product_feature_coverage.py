#!/usr/bin/env python3
"""P67 regression: passing tests do not imply required feature coverage."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from product_feature_coverage import validate_matrix, evaluate
from run_product_test_plan import execute
from test_product_test_plan import make_plan


def matrix_for(plan, *, include_missing=True):
    features = [
        {"id": "gui_buttons", "title": "All approved native GUI button actions",
         "criticality": "required", "case_ids": ["button"], "waiver": None},
        {"id": "gain_sweep", "title": "Continuous gain response in both directions",
         "criticality": "required", "case_ids": ["knob"], "waiver": None},
    ]
    if include_missing:
        features.append({
            "id": "midi_export", "title": "MIDI export remains untested by generic GUI checks",
            "criticality": "required", "case_ids": [], "waiver": None
        })
    features.append({
        "id": "optional_history", "title": "Optional history feature is not available",
        "criticality": "optional", "case_ids": [],
        "waiver": {"disposition": "not_applicable",
                   "reason": "The tested fixture has no optional history function"}
    })
    return {
        "schema": "125a-product-feature-matrix-v1",
        "product_id": plan["product"]["id"],
        "module_sha256": plan["product"]["sha256"],
        "features": features
    }


def workflow_success(plan, contract, folder, timeout):
    return {
        "status": "TECHNICAL_PASS", "verified_actions": 1,
        "declared_actions": 1, "controller_action_chain": "PASS",
        "verified_module_sha256": plan["product"]["sha256"],
        "gui_host_sha256": plan["hosts"]["gui"]["sha256"]
    }


def sweep_success(contract, folder, timeout):
    return {"status": "CONTRACT_PASS", "verified_checkpoints": 2}


class RequiredCoverageTests(unittest.TestCase):
    def test_all_native_pass_with_one_untested_required_feature_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, _, _ = make_plan(root)
            matrix = matrix_for(plan)
            report = execute(plan, root / "uncovered",
                             gui_runner=lambda *args, **kw: workflow_success(plan, *args, **kw),
                             sweep_runner=sweep_success, coverage_matrix=matrix)
            self.assertEqual(report["status"], "CONTRACT_PASS")
            self.assertEqual(report["passed_cases"], 2)
            self.assertEqual(report["required_feature_coverage"],
                             "REQUIRED_COVERAGE_INCOMPLETE")
            self.assertEqual(report["required_feature_gaps"], ["midi_export"])
            self.assertFalse(report["release_approved"])
            coverage = json.loads((root / "uncovered" /
                                   "PRODUCT-FEATURE-COVERAGE.json").read_text())
            self.assertEqual(coverage["required_features"], 3)
            self.assertEqual(coverage["required_passed"], 2)
            self.assertEqual(coverage["features"][2]["status"], "NOT COVERED")
            self.assertEqual(coverage["features"][3]["status"], "NOT APPLICABLE")
            self.assertFalse(coverage["whole_product_certified"])

    def test_declared_required_complete_does_not_authorize_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, _, _ = make_plan(root)
            matrix = matrix_for(plan, include_missing=False)
            report = execute(plan, root / "complete",
                             gui_runner=lambda *args, **kw: workflow_success(plan, *args, **kw),
                             sweep_runner=sweep_success, coverage_matrix=matrix)
            self.assertEqual(report["required_feature_coverage"],
                             "REQUIRED_COVERAGE_COMPLETE")
            self.assertFalse(report["release_approved"])
            self.assertEqual(report["full_product_functional_coverage"], "NOT COVERED")
            self.assertEqual(report["physical_asio_hardware"], "NOT RUN")
            self.assertEqual(report["real_commercial_daw_session"], "NOT RUN")

    def test_failed_test_cannot_certify_feature_and_skips_remaining(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, _, _ = make_plan(root)
            def fail(*args, **kwargs):
                return {"status": "FAIL", "verified_actions": 0}
            report = execute(plan, root / "failure", gui_runner=fail,
                             sweep_runner=lambda *args, **kw: self.fail("unapproved follow-up"),
                             coverage_matrix=matrix_for(plan))
            self.assertEqual(report["required_feature_coverage"],
                             "REQUIRED_COVERAGE_INCOMPLETE")
            cov = json.loads((root / "failure" / "PRODUCT-FEATURE-COVERAGE.json").read_text())
            self.assertEqual([x["status"] for x in cov["features"]],
                             ["FAIL", "NOT RUN", "NOT COVERED", "NOT APPLICABLE"])

    def test_matrix_must_validate_before_first_gui_click(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, _, _ = make_plan(root)
            wrong = matrix_for(plan)
            wrong["features"][0]["case_ids"] = ["made_up_pass"]
            calls = []
            with self.assertRaises(ValueError):
                execute(plan, root / "bad", coverage_matrix=wrong,
                        gui_runner=lambda *a, **kw: calls.append(1))
            self.assertEqual(calls, [])
            self.assertFalse((root / "bad" / "PRODUCT-TEST-PLAN-RESULT.json").exists())

    def test_rejects_duplicate_ambiguous_or_waived_required_features(self):
        with tempfile.TemporaryDirectory() as temp:
            plan, _, _ = make_plan(Path(temp))
            base = matrix_for(plan)
            candidates = []
            m = copy.deepcopy(base)
            m["features"][1]["id"] = "gui_buttons"
            candidates.append(m)
            m = copy.deepcopy(base)
            m["features"][1]["case_ids"] = ["knob", "knob"]
            candidates.append(m)
            m = copy.deepcopy(base)
            m["features"][0]["waiver"] = {
                "disposition": "not_applicable",
                "reason": "Someone wrote an insufficient exemption reason"}
            candidates.append(m)
            m = copy.deepcopy(base)
            m["features"][0]["criticality"] = "informational"
            candidates.append(m)
            m = copy.deepcopy(base)
            m["module_sha256"] = "0" * 64
            candidates.append(m)
            m = copy.deepcopy(base)
            m["features"] = [m["features"][-1]]
            candidates.append(m)
            m = copy.deepcopy(base)
            m["features"][0]["case_ids"] = ["unlisted_case"]
            candidates.append(m)
            m = copy.deepcopy(base)
            m["features"][1]["unexpected"] = "PASS"
            candidates.append(m)
            for candidate in candidates:
                with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                    validate_matrix(candidate, plan)

    def test_forged_native_evidence_cannot_fill_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, _, _ = make_plan(root)
            normal = {
                "schema": "125a-product-test-plan-result-v1",
                "status": "CONTRACT_PASS",
                "product_id": plan["product"]["id"],
                "verified_module_sha256": plan["product"]["sha256"],
                "release_approved": False,
                "declared_cases": 2, "passed_cases": 2, "failed_cases": 0, "not_run_cases": 0,
                "cases": [
                    {"id": "button", "status": "PASS", "expected_actions": 1, "verified_actions": 1},
                    {"id": "knob", "status": "PASS", "expected_actions": 2, "verified_actions": 2}
                ]
            }
            self.assertEqual(evaluate(matrix_for(plan, include_missing=False),
                                      plan, normal)["status"], "REQUIRED_COVERAGE_COMPLETE")
            bads = []
            m = copy.deepcopy(normal)
            m["cases"].pop()
            bads.append(m)
            m = copy.deepcopy(normal)
            m["cases"].append(copy.deepcopy(m["cases"][0]))
            bads.append(m)
            m = copy.deepcopy(normal)
            m["cases"][0]["verified_actions"] = 0
            bads.append(m)
            m = copy.deepcopy(normal)
            m["passed_cases"] = 1
            bads.append(m)
            m = copy.deepcopy(normal)
            m["verified_module_sha256"] = "0" * 64
            bads.append(m)
            m = copy.deepcopy(normal)
            m["release_approved"] = True
            bads.append(m)
            for record in bads:
                with self.subTest(record=record):
                    try:
                        result = evaluate(matrix_for(plan, include_missing=False), plan, record)
                        self.assertNotEqual(result["status"], "REQUIRED_COVERAGE_COMPLETE")
                    except ValueError:
                        pass


if __name__ == "__main__":
    unittest.main()
