#!/usr/bin/env python3
"""P84 fresh-instance reproducibility, adversarial report mutation."""
import copy
from pathlib import Path
import tempfile
import unittest
from run_gui_probe_repeatability import run, fingerprint
from run_gui_exploration import digest
from run_universal_qa import execute
from test_product_test_plan import make_plan
from test_universal_qa import onboard_for


def result(module, host, *, active=True):
    changes = [{"param_id": 9001, "before_normalized": 0.0,
                "after_normalized": 1.0}] if active else []
    return {
        "schema": "125a-gui-exploration-result-v1",
        "status": "OBSERVATIONS_COMPLETE",
        "verified_module_sha256": digest(module),
        "verified_gui_host_sha256": digest(host),
        "sham_control": "COMPLETE", "gui_control_discovery": "OBSERVATIONS_ONLY",
        "product_gui_controls": "NOT COVERED", "release_approved": False,
        "requested_points": 1, "completed_points": 1, "sham_verified_points": 1,
        "probes": [{
            "x": 160, "y": 90, "classification": (
                "PARAMETER_CHANGE" if active else "NO_OBSERVED_CHANGE"),
            "native_child_depth": 0,
            "sham_control_attribution": "SUPPORTED",
            "changed_parameters": changes,
            "painted_visual_observation": "NO_OBSERVED_CHANGE"
        }]
    }


class RepeatabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan, self.module, self.host = make_plan(self.root)

    def test_reproduced_real_parameter_transition(self):
        calls = []
        def explorer(*a, **kw):
            calls.append(a[2])
            return result(self.module, self.host)
        out = run(self.module.parents[2], self.host, self.root / "out",
                  points="160,90", repeats=3, explorer=explorer)
        self.assertEqual(out["status"], "REPRODUCIBLE_OBSERVATIONS")
        self.assertEqual(out["completed_repetitions"], 3)
        self.assertEqual(len(set(calls)), 3)
        self.assertFalse(out["release_approved"])
        self.assertEqual(out["semantic_correctness"], "NOT ESTABLISHED")

    def test_inert_control_is_reproducibly_inert_not_passed_as_button(self):
        out = run(self.module.parents[2], self.host, self.root / "inert",
                  repeats=2, explorer=lambda *_a, **_kw: result(self.module, self.host,active=False))
        self.assertEqual(out["status"], "REPRODUCIBLE_OBSERVATIONS")
        self.assertEqual(out["reproduced_control_signatures"][0]["classification"],
                         "NO_OBSERVED_CHANGE")

    def test_inconsistent_run_must_fail(self):
        calls = []
        def unstable(*args, **kwargs):
            calls.append(1)
            return result(self.module, self.host, active=(len(calls) == 1))
        out = run(self.module.parents[2], self.host, self.root / "broken",
                  repeats=2, explorer=unstable)
        self.assertEqual(out["status"], "FAIL")
        self.assertEqual(out["completed_repetitions"], 1)
        self.assertFalse(out["identical_fresh_instance_observations"])

    def test_forged_identity_and_unstable_sham_rejected(self):
        for key, value in (("verified_module_sha256", "b"*64),
                           ("sham_control", "FAIL")):
            with self.subTest(key=key):
                forged = result(self.module, self.host)
                forged[key] = value
                out = run(self.module.parents[2], self.host, self.root / key,
                          explorer=lambda *_a, **_kw: forged)
                self.assertEqual(out["status"], "FAIL")

    def test_wrong_repeat_count_rejected_preflight(self):
        for n in (1, 6, True, -1):
            with self.subTest(n=n):
                with self.assertRaises(ValueError):
                    run(self.module.parents[2], self.host, self.root / "invalid",
                        repeats=n)

    def test_p74_dispatch_repeats_and_no_semantic_credit(self):
        onboard = onboard_for(self.plan, self.host)
        onboard["gui_editor_status"] = "EDITOR_OBSERVED"
        onboard["reviewable_gui_click_coordinates"] = []
        called = []
        def repeated(*a, **kw):
            called.append(kw)
            signatures = fingerprint(result(self.module, self.host))
            return {
                "schema": "125a-repeatable-gui-observation-v1",
                "status": "REPRODUCIBLE_OBSERVATIONS",
                "verified_module_sha256": digest(self.module),
                "verified_gui_host_sha256": digest(self.host),
                "requested_repetitions": 2, "completed_repetitions": 2,
                "requested_points_per_repetition": 1,
                "reproduced_control_signatures": signatures,
                "identical_fresh_instance_observations": True,
                "semantic_correctness": "NOT ESTABLISHED",
                "release_approved": False
            }
        report = execute(self.module.parents[2], self.host, self.root / "p74",
                         onboarding=lambda *_a, **_kw: onboard,
                         explore_unknown_gui=True, exploration_points="160,90",
                         exploration_repeats=2, repeatability_runner=repeated)
        self.assertEqual(report["status"], "INVENTORY_WITH_EXPLORATORY_OBSERVATIONS")
        self.assertEqual(report["unknown_gui_repeatability"], "REPRODUCIBLE_OBSERVATIONS")
        self.assertEqual(report["unknown_gui_completed_repetitions"], 2)
        self.assertEqual(report["exploratory_clicks_performed"], 2)
        self.assertEqual(report["gui_clicks_automatically_authorized"], 0)
        self.assertEqual(called[0]["repeats"], 2)

    def test_p74_rejects_replay_without_full_sham_proof(self):
        onboard = onboard_for(self.plan, self.host)
        onboard["gui_editor_status"] = "EDITOR_OBSERVED"
        onboard["reviewable_gui_click_coordinates"] = []
        forged = {
            "schema": "125a-repeatable-gui-observation-v1",
            "status": "REPRODUCIBLE_OBSERVATIONS",
            "verified_module_sha256": digest(self.module),
            "verified_gui_host_sha256": digest(self.host),
            "requested_repetitions": 2, "completed_repetitions": 1,
            "requested_points_per_repetition": 1,
            "reproduced_control_signatures": [],
            "identical_fresh_instance_observations": True,
            "semantic_correctness": "NOT ESTABLISHED",
            "release_approved": False
        }
        report = execute(self.module.parents[2], self.host, self.root / "bad",
                         onboarding=lambda *_a, **_kw: onboard,
                         explore_unknown_gui=True, exploration_points="160,90",
                         exploration_repeats=2,
                         repeatability_runner=lambda *_a, **_kw: forged)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["unknown_gui_repeatability"], "NOT RUN")


if __name__ == "__main__":
    unittest.main()
