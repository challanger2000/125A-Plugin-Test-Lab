#!/usr/bin/env python3
"""P87 independent ABI/P86 GUI gap reconciliation tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from run_gui_parameter_coverage import run, SCHEMA
from run_universal_qa import execute
from run_vst3_auto_discovery import digest
from run_vst3_batch_qa import load_selection
from test_product_test_plan import make_plan
from test_universal_qa import onboard_for
from test_vst3_batch_qa import setup


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan, self.module, self.host = make_plan(self.root)
        self.cap = self.root / "cap.tsv"
        self.par = self.root / "par.tsv"
        self.dense_path = self.root / "dense.json"
        self.cap.write_text(
            "format\t125A-VST3-CAPABILITIES-v1\n"
            "audio_classes\t1\n"
            "parameter_count\t2\n"
            "editable_parameters\t2\n"
            "readonly_parameters\t0\n"
            "bypass_parameters\t0\n"
            "program_parameters\t0\n"
            "editor_available\t1\n"
            "editor_win32_hwnd\t1\n"
            "bus_count\t0\n"
            "end\tCOMPLETE\n")
        self.par.write_text(
            "format\t125A-GUI-PARAMS-v1\n"
            "param_count\t2\n"
            "param\t0\t9001\t0\t0\t0\t0\n"
            "param\t1\t9002\t0\t0\t0\t0\n")
        self.dense = {
            "schema": "125a-dense-gui-audit-v1",
            "status": "SAMPLED_GRID_COMPLETE",
            "verified_module_sha256": digest(self.module),
            "verified_gui_host_sha256": digest(self.host),
            "grid_side": 3, "repeat_count": 1,
            "planned_points": 9, "completed_points": 9,
            "sham_click_pairs": 9,
            "observed_parameter_ids": [9001],
            "distinct_observed_candidates": 1,
            "observations": [
                {"x":i,"y":i,"classification": "PARAMETER_CHANGE" if i==4
                 else "NO_OBSERVED_CHANGE",
                 "parameter_transitions": [[9001,0,1]] if i==4 else []}
                for i in range(9)
            ],
            "control_semantics": "NOT ESTABLISHED",
            "all_controls_discovered": False,
            "all_product_features_tested": False,
            "release_approved": False
        }
        self.dense_path.write_text(json.dumps(self.dense))

    def test_real_abi_counts_unobserved_parameters_without_inventing_gui_semantics(self):
        report = run(self.cap, self.par, self.dense_path, self.root / "report")
        self.assertEqual(report["status"], "ABI_AND_SAMPLED_GUI_RECONCILED")
        self.assertEqual(report["native_parameter_count"], 2)
        self.assertEqual(report["sampled_grid_observed_parameter_count"], 1)
        self.assertEqual(report["editable_parameters_without_sampled_gui_transition"], [9002])
        self.assertEqual(report["parameter_observation_ratio"], 0.5)
        self.assertTrue(report["unobserved_does_not_mean_broken"])
        self.assertFalse(report["complete_gui_control_inventory"])
        self.assertFalse(report["release_approved"])

    def test_unknown_parameter_or_forged_transition_rejected(self):
        for mutation in ("unknown", "missing", "duplicate", "incomplete"):
            with self.subTest(mutation=mutation):
                row = copy.deepcopy(self.dense)
                if mutation == "unknown":
                    row["observed_parameter_ids"] = [123]
                elif mutation == "missing":
                    row["observations"][4]["parameter_transitions"] = []
                elif mutation == "duplicate":
                    row["observed_parameter_ids"] = [9001,9001]
                else:
                    row["completed_points"] = 8
                self.dense_path.write_text(json.dumps(row))
                with self.assertRaises(ValueError):
                    run(self.cap, self.par, self.dense_path, self.root / mutation)

    def test_p74_opted_in_crosscheck_reports_unobserved_count(self):
        onboard = onboard_for(self.plan, self.host)
        onboard["gui_editor_status"] = "EDITOR_OBSERVED"
        onboard["reviewable_gui_click_coordinates"] = []
        calls = []
        dense = copy.deepcopy(self.dense)
        def fake_dense(*args, **kwargs):
            return dense
        def fake_coverage(*args):
            calls.append(args)
            return {
                "schema": SCHEMA,
                "status": "ABI_AND_SAMPLED_GUI_RECONCILED",
                "verified_module_sha256": digest(self.module),
                "verified_gui_host_sha256": digest(self.host),
                "sampled_grid_points": 9,
                "sampled_grid_observed_parameter_ids": [9001],
                "abi_parameters_without_sampled_gui_transition": [9002],
                "complete_gui_control_inventory": False,
                "musical_correctness": "NOT ESTABLISHED",
                "release_approved": False
            }
        report = execute(self.module.parents[2], self.host, self.root / "p74",
                         onboarding=lambda *_a, **_kw: onboard,
                         explore_unknown_gui=True, dense_grid=3,
                         crosscheck_abi_gui=True, dense_runner=fake_dense,
                         coverage_gap_runner=fake_coverage)
        self.assertEqual(report["status"], "INVENTORY_WITH_EXPLORATORY_OBSERVATIONS")
        self.assertEqual(report["abi_gui_parameter_crosscheck"], "ABI_AND_SAMPLED_GUI_RECONCILED")
        self.assertEqual(report["abi_parameters_without_sampled_gui_transition"], 1)
        self.assertEqual(len(calls), 1)
        self.assertFalse(report["release_approved"])

    def test_p74_rejects_crosscheck_without_dense_grid(self):
        with self.assertRaises(ValueError):
            execute(self.module.parents[2], self.host, self.root / "no",
                    explore_unknown_gui=True, crosscheck_abi_gui=True)

    def test_batch_requires_explicit_paired_dense_opt_in(self):
        selection, gui = setup(self.root)
        spec = json.loads(selection.read_text())
        spec["plugins"][0]["crosscheck_abi_gui"] = True
        selection.write_text(json.dumps(spec))
        with self.assertRaises(ValueError):
            load_selection(selection=selection)
        spec["plugins"][0].update(explore_unknown_gui=True,dense_gui_grid=3)
        selection.write_text(json.dumps(spec))
        rows = load_selection(selection=selection)
        self.assertTrue(rows[0]["crosscheck_abi_gui"])
        self.assertNotIn("crosscheck_abi_gui", rows[1])


if __name__ == "__main__":
    unittest.main()
