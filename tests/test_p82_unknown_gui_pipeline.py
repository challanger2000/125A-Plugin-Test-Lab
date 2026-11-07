#!/usr/bin/env python3
"""P82 bounded, sham-controlled unknown VST3 GUI exploration integration."""
import copy
from pathlib import Path
import tempfile
import unittest

from run_universal_qa import execute
from test_universal_qa import onboard_for
from test_product_test_plan import make_plan


def observation(plan, host, count=1, candidates=None):
    return {
        "schema": "125a-gui-exploration-result-v1",
        "status": "OBSERVATIONS_COMPLETE",
        "verified_module_sha256": plan["product"]["sha256"],
        "verified_gui_host_sha256": plan["hosts"]["gui"]["sha256"],
        "requested_points": count, "completed_points": count,
        "sham_verified_points": count, "sham_control": "COMPLETE",
        "gui_control_discovery": "OBSERVATIONS_ONLY",
        "product_gui_controls": "NOT COVERED",
        "candidates": ([] if candidates is None else candidates),
        "release_approved": False
    }


class P82UnknownControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan, self.module, self.host = make_plan(self.root)

    def scanned(self, status="EDITOR_OBSERVED", candidates=None):
        report = onboard_for(self.plan, self.host)
        report["gui_editor_status"] = status
        report["reviewable_gui_click_coordinates"] = (
            [] if candidates is None else candidates)
        return lambda *_a, **_k: report

    def test_default_has_no_unknown_click(self):
        report = execute(self.module.parents[2], self.host, self.root / "read_only",
                         onboarding=self.scanned(),
                         explorer=lambda *_a, **_k: self.fail("never click by default"))
        self.assertEqual(report["status"], "INVENTORY_COMPLETE")
        self.assertEqual(report["unknown_gui_exploration"], "NOT RUN")
        self.assertEqual(report["exploratory_clicks_performed"], 0)

    def test_explicit_coordinate_opt_in_with_real_count_tracking(self):
        observed = []
        def explorer(*args, **kwargs):
            observed.append(kwargs)
            return observation(self.plan, self.host, 1, [{
                "x":160,"y":90,"parameter_ids_changed":[9001]
            }])
        report = execute(self.module.parents[2], self.host, self.root / "active",
                         onboarding=self.scanned(), explorer=explorer,
                         explore_unknown_gui=True, exploration_points="160,90")
        self.assertEqual(report["status"], "INVENTORY_WITH_EXPLORATORY_OBSERVATIONS")
        self.assertEqual(report["exploratory_clicks_performed"], 1)
        self.assertEqual(report["exploratory_candidates_observed"], 1)
        self.assertEqual(report["unknown_gui_semantics"], "UNAPPROVED OBSERVATIONS ONLY")
        self.assertEqual(observed[0]["points"], "160,90")
        self.assertTrue(observed[0]["acknowledge"])
        self.assertEqual(report["gui_clicks_automatically_authorized"], 0)
        self.assertFalse(report["release_approved"])

    def test_candidates_prioritized_without_guessing_coordinates(self):
        captured = []
        coordinates = [{"x":160,"y":90,"approved_to_click":False},
                       {"x":240,"y":90,"approved_to_click":False}]
        def explorer(*args, **kwargs):
            captured.append(kwargs)
            return observation(self.plan, self.host, 2)
        report = execute(self.module.parents[2], self.host, self.root / "candidates",
                         onboarding=self.scanned(candidates=coordinates),
                         explorer=explorer, explore_unknown_gui=True,
                         exploration_max_points=2)
        self.assertEqual(captured[0]["points"], "160,90;240,90")
        self.assertEqual(report["exploratory_clicks_performed"], 2)

    def test_headless_is_not_clicked(self):
        report = execute(self.module.parents[2], self.host, self.root / "headless",
                         onboarding=self.scanned("VST3_NO_EDITOR_EXPOSED"),
                         explorer=lambda *_a, **_k: self.fail("headless must not click"),
                         explore_unknown_gui=True)
        self.assertEqual(report["unknown_gui_exploration"], "NOT APPLICABLE - NO EDITOR")
        self.assertEqual(report["exploratory_clicks_performed"], 0)
        self.assertFalse(report["release_approved"])

    def test_inconsistent_sham_or_missing_observations_fail_closed(self):
        for key, value in (("sham_verified_points", 0),
                           ("gui_control_discovery", "PASS"),
                           ("product_gui_controls", "ALL COVERED"),
                           ("release_approved", True)):
            with self.subTest(key=key):
                forged = observation(self.plan, self.host)
                forged[key] = value
                report = execute(self.module.parents[2], self.host, self.root / key,
                                 onboarding=self.scanned(),
                                 explorer=lambda *_a, obj=forged, **_k: obj,
                                 explore_unknown_gui=True,
                                 exploration_points="160,90")
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(report["unknown_gui_exploration"], "NOT RUN")
                self.assertFalse(report["release_approved"])

    def test_missing_opt_in_and_invalid_probe_budget_rejected(self):
        with self.assertRaises(ValueError):
            execute(self.module.parents[2], self.host, self.root / "invalid1",
                    exploration_points="160,90")
        with self.assertRaises(ValueError):
            execute(self.module.parents[2], self.host, self.root / "invalid2",
                    exploration_max_points=17)


if __name__ == "__main__":
    unittest.main()
