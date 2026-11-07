#!/usr/bin/env python3
"""P86 dense native GUI exploration: sharding, completeness and fail-closed report."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from run_gui_dense_audit import grid_coordinates, run, SCHEMA
from run_universal_qa import execute
from test_product_test_plan import make_plan
from test_universal_qa import onboard_for
from run_gui_exploration import digest
import struct


def bmp(path, color, width=320, height=180):
    pixels = bytes((color[2], color[1], color[0], 255)) * (width*height)
    header = struct.pack('<HIHHI', 0x4D42, 54+len(pixels), 0, 0, 54)
    dib = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32,
                      0, len(pixels), 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + dib + pixels)



class DenseAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan, self.module, self.host = make_plan(self.root)
        self.bundle = self.module.parents[2]

    def snapshot(self, argv, **kwargs):
        self.assertEqual(argv[1], "--snapshot-editor")
        bmp(Path(argv[3]), (30, 36, 48))
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    def example_signature(self, x, y):
        active = x == 160 and y == 90
        return {"x": x, "y": y,
                "classification": "PARAMETER_AND_VISUAL_CHANGE" if active
                                  else "NO_OBSERVED_CHANGE",
                "native_child_depth": 0,
                "visual_observed": active,
                "parameter_transitions": [[9001, 0.0, 1.0]] if active else []}

    def fake_repeat(self, bundle, host, folder, *, points, repeats, **kwargs):
        self.assertEqual(repeats, 2)
        positions = [tuple(map(int, p.split(","))) for p in points.split(";")]
        return {
            "schema": "125a-repeatable-gui-observation-v1",
            "status": "REPRODUCIBLE_OBSERVATIONS",
            "verified_module_sha256": digest(self.module),
            "verified_gui_host_sha256": digest(self.host),
            "completed_repetitions": repeats,
            "requested_points_per_repetition": len(positions),
            "identical_fresh_instance_observations": True,
            "semantic_correctness": "NOT ESTABLISHED",
            "release_approved": False,
            "reproduced_control_signatures": [
                self.example_signature(x, y) for x, y in positions]
        }

    def test_three_by_three_real_center_and_observed_effect(self):
        result = run(self.bundle, self.host, self.root / "audit",
                     side=3, repeats=2, snapshot_runner=self.snapshot,
                     repeater=self.fake_repeat)
        self.assertEqual(result["status"], "SAMPLED_GRID_COMPLETE")
        self.assertEqual(result["planned_points"], 9)
        self.assertEqual(result["sham_click_pairs"], 18)
        self.assertEqual(result["distinct_observed_candidates"], 1)
        self.assertEqual(result["observed_parameter_ids"], [9001])
        self.assertFalse(result["all_product_features_tested"])
        self.assertFalse(result["release_approved"])

    def test_five_grid_shards_exactly_16_plus_9_without_truncation(self):
        observed_batch_lengths = []
        def fake(*args, **kwargs):
            observed_batch_lengths.append(len(kwargs["points"].split(";")))
            return self.fake_repeat(*args, **kwargs)
        result = run(self.bundle, self.host, self.root / "full",
                     side=5, repeats=2, snapshot_runner=self.snapshot,
                     repeater=fake)
        self.assertEqual(result["status"], "SAMPLED_GRID_COMPLETE")
        self.assertEqual(observed_batch_lengths, [16, 9])
        self.assertEqual(result["completed_points"], 25)
        self.assertEqual(result["sham_click_pairs"], 50)
        self.assertEqual(result["distinct_observed_candidates"], 1)

    def test_missing_shard_denies_full_sweep_evidence(self):
        def truncated(*args, **kwargs):
            report = self.fake_repeat(*args, **kwargs)
            if len(kwargs["points"].split(";")) == 9:
                report["reproduced_control_signatures"].pop()
            return report
        result = run(self.bundle, self.host, self.root / "wrong",
                     side=5, snapshot_runner=self.snapshot, repeater=truncated)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["completed_points"], 16)
        self.assertEqual(result["sham_click_pairs"], 32)
        self.assertFalse(result["all_controls_discovered"])

    def test_coordinate_mismatch_rejected(self):
        def wrong(*args, **kwargs):
            report = self.fake_repeat(*args, **kwargs)
            report["reproduced_control_signatures"][0]["x"] = 1
            return report
        result = run(self.bundle, self.host, self.root / "wrong-coordinate",
                     snapshot_runner=self.snapshot, repeater=wrong)
        self.assertEqual(result["status"], "FAIL")

    def test_grid_preflight_rejects_invalid_budget(self):
        for side, repeats in ((4, 2), (7, 2), (3, 3), (True, 2)):
            with self.subTest(side=side, repeats=repeats):
                with self.assertRaises(ValueError):
                    run(self.bundle, self.host, self.root / "no",
                        side=side, repeats=repeats)
        self.assertEqual(grid_coordinates(320, 180, 3)[4], (160, 90))

    def test_p74_native_dense_dispatch_and_no_release_credit(self):
        onboard = onboard_for(self.plan, self.host)
        onboard["gui_editor_status"] = "EDITOR_OBSERVED"
        onboard["reviewable_gui_click_coordinates"] = []
        calls = []
        def dense(*args, **kw):
            calls.append(kw)
            return run(self.bundle, self.host, self.root / "nested",
                       side=kw["side"], repeats=kw["repeats"],
                       snapshot_runner=self.snapshot, repeater=self.fake_repeat)
        report = execute(self.bundle, self.host, self.root / "p74",
                         onboarding=lambda *_a, **_kw: onboard,
                         explore_unknown_gui=True, dense_grid=3,
                         exploration_repeats=2, dense_runner=dense)
        self.assertEqual(report["status"], "INVENTORY_WITH_EXPLORATORY_OBSERVATIONS")
        self.assertEqual(report["unknown_gui_dense_grid"], 3)
        self.assertEqual(report["exploratory_clicks_performed"], 18)
        self.assertEqual(report["unknown_gui_grid_coverage"], "SAMPLED POINTS ONLY")
        self.assertEqual(report["gui_clicks_automatically_authorized"], 0)
        self.assertFalse(report["release_approved"])
        self.assertEqual(len(calls), 1)

    def test_p74_rejects_wrong_dense_metadata_and_missing_opt_in(self):
        with self.assertRaises(ValueError):
            execute(self.bundle, self.host, self.root / "bad",
                    dense_grid=3)
        with self.assertRaises(ValueError):
            execute(self.bundle, self.host, self.root / "bad2",
                    explore_unknown_gui=True, dense_grid=4)
        with self.assertRaises(ValueError):
            execute(self.bundle, self.host, self.root / "bad3",
                    explore_unknown_gui=True, dense_grid=3,
                    exploration_points="160,90")


if __name__ == "__main__":
    unittest.main()
