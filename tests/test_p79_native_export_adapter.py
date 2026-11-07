#!/usr/bin/env python3
"""P79 P65 adapter contract tests; real source-built VST3 runs in Windows CI."""
import copy
from pathlib import Path
import tempfile
import unittest

from run_product_test_plan import execute, validate
from test_product_test_plan import make_plan


def export_case(plan):
    return {
        "id": "real_gui_export", "kind": "gui_export_contract",
        "contract": {
            "schema": "125a-gui-export-contract-v1",
            "workflow": copy.deepcopy(plan["cases"][0]["contract"]),
            "expected_exports": [{
                "filename": "gui-export.wav", "type": "wav",
                "sha256": "3c548b8ac23f3be44063b4afce2609137a6e274e409af17f2397f0c95172741b",
                "channels": 1, "sample_rate": 44100,
                "sample_width_bits": 16, "frames": 16
            }]
        }
    }


class NativeExportAdapterTests(unittest.TestCase):
    def test_adapter_accepts_valid_contract(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan, _, _ = make_plan(root)
            plan["cases"] = [export_case(plan)]
            _, _, cases = validate(plan)
            self.assertEqual(cases[0]["expected_actions"], 2)

    def test_full_evidence_required_and_release_stays_false(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan, _, _ = make_plan(root)
            plan["cases"] = [export_case(plan)]
            observed = []
            def fake_runner(contract, folder, timeout):
                observed.append(contract)
                return {
                    "schema": "125a-gui-export-contract-result-v1",
                    "status": "CONTRACT_PASS",
                    "verified_module_sha256": plan["product"]["sha256"],
                    "verified_gui_host_sha256": plan["hosts"]["gui"]["sha256"],
                    "declared_gui_actions": 1, "expected_export_count": 1,
                    "verified_export_count": 1, "gui_declared_action_oracles": "PASS",
                    "approved_independent_file_oracles": "PASS",
                    "verified_exports": {"gui-export.wav": {"sha256": "3c548b8ac23f3be44063b4afce2609137a6e274e409af17f2397f0c95172741b", "format": "wav", "metadata": {"channels": 1, "sample_rate": 44100, "sample_width_bits": 16, "frames": 16}}},
                    "release_approved": False
                }
            result = execute(plan, root / "reports", gui_export_runner=fake_runner)
            self.assertEqual(result["status"], "CONTRACT_PASS")
            self.assertEqual(result["passed_cases"], 1)
            self.assertEqual(len(observed), 1)
            self.assertFalse(result["release_approved"])

    def test_incomplete_native_evidence_rejects_and_skips_rest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan, _, _ = make_plan(root)
            plan["cases"] = [export_case(plan), plan["cases"][0]]
            report = execute(plan, root / "reports",
                gui_export_runner=lambda *_a, **_kw: {
                    "schema": "125a-gui-export-contract-result-v1",
                    "status": "CONTRACT_PASS", "verified_export_count": 1
                },
                gui_runner=lambda *_a, **_kw: self.fail("must not click"))
            self.assertEqual([x["status"] for x in report["cases"]], ["FAIL", "NOT RUN"])

    def test_wrong_module_rejected_before_click(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan, _, _ = make_plan(root)
            plan["cases"] = [export_case(plan)]
            plan["cases"][0]["contract"]["workflow"]["product"]["sha256"] = "f" * 64
            with self.assertRaises(ValueError):
                validate(plan)


if __name__ == "__main__":
    unittest.main()
