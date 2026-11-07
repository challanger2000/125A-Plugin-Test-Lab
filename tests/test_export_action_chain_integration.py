#!/usr/bin/env python3
"""P77 P65/P74 integration regression using deliberately simulated producers.

These tests DO NOT constitute evidence of a real VST3's export functionality.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from run_product_test_plan import validate, execute
from test_product_test_plan import make_plan, checksum


def chain_case(plan, output):
    return {
        "id": "generated_export", "kind": "export_action_chain",
        "contract": {
            "schema": "125a-export-action-chain-v1",
            "workflow": copy.deepcopy(plan["cases"][0]["contract"]),
            "export": {
                "schema": "125a-export-artifact-oracle-v1",
                "module_sha256": plan["product"]["sha256"],
                "outputs": [{
                    "id": "out", "path": str(output), "kind": "wav",
                    "expected_sha256": "a" * 64,
                    "format_expectations": {
                        "channels": 1, "sample_rate": 44100,
                        "sample_width_bytes": 2, "frames": 100
                    }
                }]
            }
        }
    }


class Integration(unittest.TestCase):
    def test_p65_dispatch_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, _, _ = make_plan(root)
            plan["cases"] = [chain_case(plan, root / "future.wav")]
            module, hosts, compiled = validate(plan)
            self.assertEqual(compiled[0]["expected_actions"], 2)
            called = []
            def fake_chain(contract, folder, timeout):
                called.append(contract)
                return {
                    "schema": "125a-export-action-chain-result-v1",
                    "status": "ACTION_AND_ARTIFACT_PASS",
                    "verified_module_sha256": plan["product"]["sha256"],
                    "verified_gui_host_sha256": plan["hosts"]["gui"]["sha256"],
                    "expected_actions": 1, "verified_actions": 1,
                    "expected_outputs": 1, "verified_outputs": 1,
                    "actual_plugin_export_tested": True,
                    "release_approved": False
                }
            result = execute(plan, root / "results", chain_runner=fake_chain)
            self.assertEqual(result["status"], "CONTRACT_PASS")
            self.assertEqual(len(called), 1)
            self.assertFalse(result["release_approved"])

    def test_p65_rejects_false_report_and_skips_other_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, _, _ = make_plan(root)
            plan["cases"] = [chain_case(plan, root / "future.wav"),
                             plan["cases"][0]]
            report = execute(plan, root / "results",
                             chain_runner=lambda *_a, **_kw: {
                                 "schema": "125a-export-action-chain-result-v1",
                                 "status": "ACTION_AND_ARTIFACT_PASS",
                                 "verified_actions": 1,
                                 "verified_outputs": 1,
                                 "actual_plugin_export_tested": False
                             },
                             gui_runner=lambda *_a, **_kw: self.fail("must skip"))
            self.assertEqual([x["status"] for x in report["cases"]], ["FAIL", "NOT RUN"])

    def test_preflight_rejects_wrong_chain_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, _, _ = make_plan(root)
            plan["cases"] = [chain_case(plan, root / "future.wav")]
            plan["cases"][0]["contract"]["export"]["module_sha256"] = "b" * 64
            with self.assertRaises(ValueError):
                validate(plan)

    def test_stale_output_blocks_entire_plan_before_any_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, _, _ = make_plan(root)
            path = root / "future.wav"
            plan["cases"] = [chain_case(plan, path)]
            path.write_bytes(b"old")
            with self.assertRaisesRegex(ValueError, "already exists"):
                validate(plan)


if __name__ == "__main__":
    unittest.main()
