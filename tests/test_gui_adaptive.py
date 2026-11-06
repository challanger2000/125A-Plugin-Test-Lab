#!/usr/bin/env python3
"""P50 adversarial tests, using deterministic synthetic native observations."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from test_gui_coverage_scan import CoverageTests
from run_gui_adaptive import neighbors, run


class AdaptiveTests(unittest.TestCase):
    def test_neighbors_unique_and_bounded(self):
        p = neighbors({"x": 20, "y": 20}, 80, 80, 2, 2)
        self.assertEqual(len(p), 8)
        self.assertEqual(len(set(p)), 8)
        self.assertNotIn((20, 20), p)

    def test_opt_in_required(self):
        with self.assertRaises(ValueError):
            run("absent.vst3", "absent.exe", "out")

    def test_realistic_neighbor_batches_and_forged_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            fixture = CoverageTests()
            plugin, host = fixture.make_fixture(root)
            m = hashlib.sha256(next(plugin.rglob("*.vst3")).read_bytes()).hexdigest()
            h = hashlib.sha256(host.read_bytes()).hexdigest()
            def sampler(*args, **kwargs):
                return {"status": "OBSERVATIONS_COMPLETE",
                        "verified_module_sha256": m,
                        "verified_gui_host_sha256": h,
                        "editor_dimensions": [80, 80],
                        "planned_points": 4, "completed_points": 4,
                        "candidate_points": 1,
                        "candidates": [{"x": 20, "y": 20,
                                        "observation": "VISUAL_CHANGE"}]}
            def explorer(*args, points, **kwargs):
                coords = [tuple(map(int, v.split(","))) for v in points.split(";")]
                return {"schema": "125a-gui-exploration-result-v1",
                        "status": "OBSERVATIONS_COMPLETE", "sham_control": "COMPLETE",
                        "verified_module_sha256": m, "verified_gui_host_sha256": h,
                        "completed_points": len(coords), "sham_verified_points": len(coords),
                        "probes": [{"x": x, "y": y, "classification":
                                    "PARAMETER_CHANGE" if i == 0 else "NO_OBSERVED_CHANGE"}
                                   for i, (x, y) in enumerate(coords)]}
            report = run(plugin, host, root / "good", columns=2, rows=2,
                         acknowledge=True, sampler=sampler, explorer=explorer)
            self.assertEqual(report["status"], "OBSERVATIONS_COMPLETE")
            self.assertEqual(report["follow_up_points"], 8)
            self.assertEqual(report["confirmed_neighbors"], 1)
            self.assertFalse(report["release_approved"])
            self.assertEqual(report["independent_product_semantics"], "NOT COVERED")
            def forged(*args, **kwargs):
                r = explorer(*args, **kwargs)
                r["sham_verified_points"] = 0
                return r
            bad = run(plugin, host, root / "bad", columns=2, rows=2,
                      acknowledge=True, sampler=sampler, explorer=forged)
            self.assertEqual(bad["status"], "FAIL")
            self.assertFalse(bad["release_approved"])
            def no_baseline(*args, **kwargs):
                r = sampler(*args, **kwargs)
                r["completed_points"] = 3
                return r
            bad2 = run(plugin, host, root / "bad2", columns=2, rows=2,
                       acknowledge=True, sampler=no_baseline, explorer=explorer)
            self.assertEqual(bad2["status"], "FAIL")

    def test_no_baseline_candidates_is_success_not_gui_approval(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plugin, host = CoverageTests().make_fixture(root)
            m = hashlib.sha256(next(plugin.rglob("*.vst3")).read_bytes()).hexdigest()
            h = hashlib.sha256(host.read_bytes()).hexdigest()
            def sampler(*args, **kwargs):
                return {"status": "OBSERVATIONS_COMPLETE",
                        "verified_module_sha256": m, "verified_gui_host_sha256": h,
                        "editor_dimensions": [80, 80],
                        "planned_points": 4, "completed_points": 4,
                        "candidate_points": 0, "candidates": []}
            report = run(plugin, host, root / "out", columns=2, rows=2,
                         acknowledge=True, sampler=sampler)
            self.assertEqual(report["status"], "OBSERVATIONS_COMPLETE")
            self.assertEqual(report["follow_up_points"], 0)
            self.assertEqual(report["automatic_control_inventory"], "NOT COVERED")


if __name__ == "__main__":
    unittest.main()
