#!/usr/bin/env python3
"""P83 per-plugin sham-controlled GUI probing in isolated batch runners."""
import json
from pathlib import Path
import tempfile
import unittest

from run_vst3_batch_qa import load_selection, run
from test_vst3_batch_qa import setup, successful_child


def exploratory_child(cmd, **kwargs):
    result = successful_child(cmd, **kwargs)
    if "--explore-unknown-gui" in cmd:
        output = Path(cmd[cmd.index("--out")+1]) / "UNIVERSAL-QA-RESULT.json"
        report = json.loads(output.read_text(encoding="utf-8"))
        report.update(
            status="INVENTORY_WITH_EXPLORATORY_OBSERVATIONS",
            unknown_gui_exploration="OBSERVATIONS_COMPLETE",
            exploratory_clicks_performed=1,
            exploratory_candidates_observed=1,
            unknown_gui_semantics="UNAPPROVED OBSERVATIONS ONLY")
        output.write_text(json.dumps(report), encoding="utf-8")
    return result


class P83BatchUnknownGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.selection, self.gui = setup(self.root)

    def select_exploration(self):
        spec = json.loads(self.selection.read_text())
        spec["plugins"][0].update(
            explore_unknown_gui=True, exploration_points="160,90",
            exploration_max_points=1)
        self.selection.write_text(json.dumps(spec), encoding="utf-8")
        return load_selection(selection=self.selection)

    def test_mixed_opt_in_probes_only_selected_plugin(self):
        items = self.select_exploration()
        commands = []
        def fake(cmd, **kwargs):
            commands.append(cmd)
            return exploratory_child(cmd, **kwargs)
        report = run(items, self.gui, self.root / "results", runner=fake)
        self.assertEqual(report["status"], "BATCH_EXPLORATORY_OBSERVATIONS_COMPLETE")
        self.assertEqual([p["verified_stage"] for p in report["plugins"]],
                         ["INVENTORY_WITH_EXPLORATORY_OBSERVATIONS", "INVENTORY_COMPLETE"])
        self.assertEqual([p["exploratory_clicks_performed"] for p in report["plugins"]],
                         [1, 0])
        self.assertIn("--explore-unknown-gui", commands[0])
        self.assertNotIn("--explore-unknown-gui", commands[1])
        self.assertFalse(report["release_approved"])

    def test_missing_explicit_opt_in_fails_before_plugins(self):
        spec = json.loads(self.selection.read_text())
        spec["plugins"][0]["exploration_points"] = "160,90"
        self.selection.write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError, "explicit true"):
            load_selection(selection=self.selection)

    def test_probe_budget_and_format_checked_in_preflight(self):
        for points, limit in (("160,90;240,90",1), ("a,b",1),
                              ("160,90;160,90",2)):
            with self.subTest(points=points):
                spec = json.loads(self.selection.read_text())
                spec["plugins"][0].update(
                    explore_unknown_gui=True, exploration_points=points,
                    exploration_max_points=limit)
                self.selection.write_text(json.dumps(spec))
                with self.assertRaises(ValueError):
                    load_selection(selection=self.selection)
                # Restore pristine data for next subtest.
                _,_ = setup(self.root)

    def test_false_exploration_evidence_blocks_one_plugin_not_next(self):
        items = self.select_exploration()
        called = []
        def fake(cmd, **kw):
            called.append(cmd)
            response = exploratory_child(cmd, **kw)
            if "--explore-unknown-gui" in cmd:
                file = Path(cmd[cmd.index("--out")+1]) / "UNIVERSAL-QA-RESULT.json"
                report = json.loads(file.read_text())
                report["unknown_gui_semantics"] = "ALL FEATURE PASS"
                file.write_text(json.dumps(report))
            return response
        report = run(items, self.gui, self.root / "results", runner=fake)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual([p["status"] for p in report["plugins"]], ["FAIL","PASS"])
        self.assertEqual(len(called), 2)
        self.assertFalse(report["release_approved"])

    def test_no_manifest_root_scan_stays_read_only(self):
        items = load_selection(root=self.root)
        report = run(items, self.gui, self.root / "root-scan",
                     runner=successful_child)
        self.assertEqual(report["status"], "BATCH_TECHNICAL_PASS")
        self.assertEqual([p["exploratory_clicks_performed"] for p in report["plugins"]],
                         [0, 0])


if __name__ == "__main__":
    unittest.main()
