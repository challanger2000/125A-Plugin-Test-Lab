#!/usr/bin/env python3
"""P80 isolated mixed/approved product QA, including negative contracts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from run_vst3_batch_qa import load_selection, run, SCHEMA
from test_vst3_batch_qa import setup, successful_child
from run_vst3_auto_discovery import digest


def approved(root, gui):
    bundle = root / "A.vst3"
    module = next(p for p in bundle.rglob("*.vst3") if p.is_file())
    sha = digest(module)
    workflow = {
        "schema": "125a-gui-workflow-v1",
        "product": {"binary": str(module), "sha256": sha},
        "gui_host": str(gui),
        "initial": [{"param_id": 9001, "normalized": 0.0}],
        "steps": [{"id": "press_apply", "action": "click", "x": 160, "y": 90,
                   "param_id": 9001, "before_normalized": 0.0,
                   "expected_normalized": 1.0}]
    }
    plan = {
        "schema": "125a-product-test-plan-v1",
        "product": {"id": "fixture_a", "module": str(module), "sha256": sha},
        "hosts": {"gui": {"path": str(gui), "sha256": digest(gui)}},
        "cases": [{"id": "click", "kind": "gui_workflow", "contract": workflow}]
    }
    matrix = {
        "schema": "125a-product-feature-matrix-v1",
        "product_id": "fixture_a", "module_sha256": sha,
        "features": [{"id": "button", "title": "Approved native GUI click",
                      "criticality": "required", "case_ids": ["click"], "waiver": None}]
    }
    pp, mp = root / "plan.json", root / "matrix.json"
    pp.write_text(json.dumps(plan))
    mp.write_text(json.dumps(matrix))
    return pp, mp


def mixed_child(cmd, **kwargs):
    result = successful_child(cmd, **kwargs)
    if "--approved-plan" in cmd:
        folder = Path(cmd[cmd.index("--out") + 1])
        report_path = folder / "UNIVERSAL-QA-RESULT.json"
        report = json.loads(report_path.read_text())
        report["status"] = "DECLARED_COVERAGE_PASS"
        report["approved_product_cases"] = "CONTRACT_PASS"
        report["required_feature_coverage"] = "REQUIRED_COVERAGE_COMPLETE"
        report_path.write_text(json.dumps(report))
    return result


class P80Tests(unittest.TestCase):
    def test_mixed_selected_batch_dispatch_and_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            selection, gui = setup(root)
            pp, mp = approved(root, gui)
            spec = json.loads(selection.read_text())
            spec["plugins"][0].update(approved_plan=str(pp), feature_matrix=str(mp))
            selection.write_text(json.dumps(spec))
            items = load_selection(selection=selection)
            report = run(items, gui, root / "results", runner=mixed_child)
            self.assertEqual(report["status"], "BATCH_MIXED_QA_PASS")
            self.assertEqual([r["verified_stage"] for r in report["plugins"]],
                             ["DECLARED_COVERAGE_PASS", "INVENTORY_COMPLETE"])
            self.assertFalse(report["release_approved"])

    def test_only_paired_declared_contracts_permitted(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            selection, gui = setup(root)
            pp, mp = approved(root, gui)
            obj = json.loads(selection.read_text())
            obj["plugins"][0]["approved_plan"] = str(pp)
            selection.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError, "paired"):
                load_selection(selection=selection)

    def test_broken_matrix_is_blocked_before_any_plugin(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            selection, gui = setup(root)
            pp, mp = approved(root, gui)
            obj = json.loads(selection.read_text())
            obj["plugins"][0].update(approved_plan=str(pp), feature_matrix=str(mp))
            selection.write_text(json.dumps(obj))
            matrix = json.loads(mp.read_text())
            matrix["module_sha256"] = "f" * 64
            mp.write_text(json.dumps(matrix))
            items = load_selection(selection=selection)
            with self.assertRaises(ValueError):
                run(items, gui, root / "results",
                    runner=lambda *_a, **_k: self.fail("no plugin may run"))

    def test_product_child_can_fail_without_preventing_later_inventory(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            selection, gui = setup(root)
            pp, mp = approved(root, gui)
            obj = json.loads(selection.read_text())
            obj["plugins"][0].update(approved_plan=str(pp), feature_matrix=str(mp))
            selection.write_text(json.dumps(obj))
            items = load_selection(selection=selection)
            called = []
            def failed_first(cmd, **kwargs):
                called.append(cmd)
                result = mixed_child(cmd, **kwargs)
                if "--approved-plan" in cmd:
                    folder = Path(cmd[cmd.index("--out") + 1])
                    target = folder / "UNIVERSAL-QA-RESULT.json"
                    report = json.loads(target.read_text())
                    report["required_feature_coverage"] = "REQUIRED_COVERAGE_INCOMPLETE"
                    target.write_text(json.dumps(report))
                return result
            report = run(items, gui, root / "results", runner=failed_first)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual([x["status"] for x in report["plugins"]],
                             ["FAIL", "PASS"])
            self.assertEqual(len(called), 2)


if __name__ == "__main__":
    unittest.main()
