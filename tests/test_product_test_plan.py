#!/usr/bin/env python3
"""P65 adversarial contract validation and aggregate fail-closed product QA."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from run_product_test_plan import execute, validate, SCHEMA


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_plan(root):
    module = root / "Demo.vst3" / "Contents" / "x86_64-win" / "Demo.vst3"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"product DLL identity")
    host = root / "GUI.exe"
    host.write_bytes(b"native host identity")
    pinned = {"binary": str(module), "sha256": checksum(module)}
    contract = {"schema": "125a-gui-workflow-v1",
                "product": pinned, "gui_host": str(host),
                "initial": [{"param_id": 9001, "normalized": 0.0}],
                "steps": [{"id": "press_apply", "action": "click", "x": 100,
                           "y": 90, "param_id": 9001,
                           "before_normalized": 0.0,
                           "expected_normalized": 1.0}]}
    sweep = {"schema": "125a-gui-gesture-sweep-v1",
             "product": pinned, "gui_host": str(host),
             "param_id": 9001, "initial_normalized": 0.0,
             "checkpoints": [
                 {"start_x": 40, "start_y": 90, "end_x": 220, "end_y": 90,
                  "expected_normalized": 0.75},
                 {"start_x": 220, "start_y": 90, "end_x": 40, "end_y": 90,
                  "expected_normalized": 0.0}]}
    plan = {
        "schema": SCHEMA,
        "product": {"id": "demo_plugin", "module": str(module),
                    "sha256": checksum(module)},
        "hosts": {"gui": {"path": str(host), "sha256": checksum(host)}},
        "cases": [
            {"id": "button", "kind": "gui_workflow", "contract": contract},
            {"id": "knob", "kind": "gesture_sweep", "contract": sweep}
        ]
    }
    return plan, module, host


class StandardProductPlanTests(unittest.TestCase):
    def test_compiles_two_real_existing_adapter_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, _, _ = make_plan(Path(tmp))
            _, _, cases = validate(p)
            self.assertEqual([(c["id"], c["expected_actions"]) for c in cases],
                             [("button", 1), ("knob", 2)])

    def test_all_cases_require_real_independent_native_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p, _, _ = make_plan(root)
            called = []
            def gui(contract, folder, timeout):
                called.append("gui")
                return {"status": "TECHNICAL_PASS", "verified_actions": 1,
                        "declared_actions": 1, "controller_action_chain": "PASS",
                        "verified_module_sha256": p["product"]["sha256"],
                        "gui_host_sha256": p["hosts"]["gui"]["sha256"]}
            def sweep(contract, folder, timeout):
                called.append("sweep")
                return {"status": "CONTRACT_PASS", "verified_checkpoints": 2}
            report = execute(p, root / "all", gui_runner=gui, sweep_runner=sweep)
            self.assertEqual(called, ["gui", "sweep"])
            self.assertEqual(report["status"], "CONTRACT_PASS")
            self.assertEqual(report["passed_cases"], 2)
            self.assertEqual(report["failed_cases"], 0)
            self.assertEqual(report["physical_asio_hardware"], "NOT RUN")
            self.assertEqual(report["real_commercial_daw_session"], "NOT RUN")
            self.assertFalse(report["release_approved"])

    def test_fail_closed_skip_following_case_on_first_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p, _, _ = make_plan(root)
            def failed(*args, **kwargs):
                return {"status": "TECHNICAL_PASS", "verified_actions": 0}
            def no_second(*args, **kwargs):
                raise AssertionError("unapproved second case executed")
            report = execute(p, root / "fail", gui_runner=failed,
                             sweep_runner=no_second)
            self.assertEqual([c["status"] for c in report["cases"]],
                             ["FAIL", "NOT RUN"])
            self.assertEqual((report["failed_cases"], report["not_run_cases"]), (1, 1))
            self.assertFalse(report["release_approved"])

    def test_rejects_wrong_module_changed_host_and_unknown_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, module, host = make_plan(root)
            bad_cases = []
            p = copy.deepcopy(original)
            p["cases"][1]["id"] = "button"
            bad_cases.append(p)
            p = copy.deepcopy(original)
            p["cases"][1]["kind"] = "execute_shell"
            bad_cases.append(p)
            p = copy.deepcopy(original)
            p["cases"][0]["contract"]["steps"][0]["action"] = "shell"
            bad_cases.append(p)
            p = copy.deepcopy(original)
            p["cases"][0]["contract"]["product"]["sha256"] = "f" * 64
            bad_cases.append(p)
            p = copy.deepcopy(original)
            p["cases"][0]["contract"]["gui_host"] = str(root / "unknown.exe")
            bad_cases.append(p)
            p = copy.deepcopy(original)
            p["cases"][0]["contract"]["steps"][0]["expected_normalized"] = 0.0
            bad_cases.append(p)
            p = copy.deepcopy(original)
            p["cases"][1]["contract"]["checkpoints"][1]["expected_normalized"] = 0.75
            bad_cases.append(p)
            p = copy.deepcopy(original)
            p["unexpected"] = "unsafe"
            bad_cases.append(p)
            for case in bad_cases:
                with self.subTest(case=case), self.assertRaises((ValueError, TypeError, OSError)):
                    validate(case)
            host.write_bytes(b"tampered after plan")
            with self.assertRaises(ValueError):
                validate(original)

    def test_pins_module_against_mutation_after_first_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p, module, _ = make_plan(root)
            def mutate(*args, **kwargs):
                module.write_bytes(b"mutated while native host supposedly runs")
                return {"status": "TECHNICAL_PASS", "verified_actions": 1,
                        "declared_actions": 1,
                        "verified_module_sha256": p["product"]["sha256"],
                        "gui_host_sha256": p["hosts"]["gui"]["sha256"]}
            def no_second(*args, **kwargs):
                raise AssertionError("second case must not run")
            report = execute(p, root / "mutable", gui_runner=mutate,
                             sweep_runner=no_second)
            self.assertEqual([c["status"] for c in report["cases"]],
                             ["FAIL", "NOT RUN"])


if __name__ == "__main__":
    unittest.main()
