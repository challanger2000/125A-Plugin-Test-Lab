#!/usr/bin/env python3
"""P49 pure sampling and fake-host adversarial regression tests."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_gui_coverage_scan import sample_points, scan


class FakeProcess:
    returncode = 0


class CoverageTests(unittest.TestCase):
    def test_unique_deterministic_tile_centers(self):
        p = sample_points(801, 401, 8, 8)
        self.assertEqual(len(p), 64)
        self.assertEqual(len(set(p)), 64)
        self.assertTrue(all(0 <= x < 801 and 0 <= y < 401 for x, y in p))
        self.assertEqual(p, sample_points(801, 401, 8, 8))

    def test_small_or_invalid_geometry_fails(self):
        for args in ((4, 4, 8, 8), (100, 100, 0, 2),
                     (100, 100, 17, 2), (100, 100, 2, 17)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    sample_points(*args)

    def test_no_opt_in_fails_before_click(self):
        with self.assertRaises(ValueError):
            scan("missing.vst3", "missing.exe", "out", acknowledge=False)

    def make_fixture(self, root):
        plugin = root / "Synth.vst3"
        dll = plugin / "Contents" / "x86_64-win" / "Synth.vst3"
        dll.parent.mkdir(parents=True)
        dll.write_bytes(b"native fixture identity")
        host = root / "GUI.exe"
        host.write_bytes(b"native gui host identity")
        return plugin, host

    def fake_runner(self, cmd, **kwargs):
        # 8x8 32-bit top-down BMP, matching existing P42 parser.
        import struct
        if cmd[1] != "--snapshot-editor":
            raise AssertionError("unexpected runner call")
        width, height = 80, 80
        data = bytes(width * height * 4)
        header = (b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54)
                  + struct.pack("<IiiHHIIiiII", 40, width, -height,
                                1, 32, 0, len(data), 0, 0, 0, 0))
        Path(cmd[3]).write_bytes(header + data)
        return FakeProcess()

    def test_64_points_four_batches_and_fail_closed_forgery(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plugin, host = self.make_fixture(root)
            calls = []
            def explorer(plugin_, host_, output, *, points, **kwargs):
                coords = [tuple(map(int, q.split(","))) for q in points.split(";")]
                calls.append(coords)
                m = hashlib.sha256(next(plugin_.rglob("*.vst3")).read_bytes()).hexdigest()
                h = hashlib.sha256(host_.read_bytes()).hexdigest()
                return {
                    "schema": "125a-gui-exploration-result-v1",
                    "status": "OBSERVATIONS_COMPLETE", "sham_control": "COMPLETE",
                    "verified_module_sha256": m, "verified_gui_host_sha256": h,
                    "completed_points": len(coords), "sham_verified_points": len(coords),
                    "probes": [{"x": x, "y": y, "classification": "NO_OBSERVED_CHANGE"}
                               for x, y in coords],
                }
            result = scan(plugin, host, root / "out", acknowledge=True,
                          runner=self.fake_runner, explorer=explorer)
            self.assertEqual(result["status"], "OBSERVATIONS_COMPLETE")
            self.assertEqual([len(batch) for batch in calls], [16] * 4)
            self.assertEqual(result["completed_points"], 64)
            self.assertEqual(result["candidate_points"], 0)
            self.assertFalse(result["release_approved"])
            self.assertEqual(result["product_gui_controls"], "NOT COVERED")
            self.assertEqual(json.loads((root / "out/GUI-COVERAGE-SCAN.json")
                                        .read_text())["status"], "OBSERVATIONS_COMPLETE")
            def forged(*args, **kwargs):
                record = explorer(*args, **kwargs)
                record["sham_verified_points"] -= 1
                return record
            failed = scan(plugin, host, root / "bad", acknowledge=True,
                          runner=self.fake_runner, explorer=forged)
            self.assertEqual(failed["status"], "FAIL")
            self.assertFalse(failed["release_approved"])

    def test_candidate_and_unstable_are_not_certified(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plugin, host = self.make_fixture(root)
            def explorer(plugin_, host_, output, *, points, **kwargs):
                coords = [tuple(map(int, p.split(","))) for p in points.split(";")]
                m = hashlib.sha256(next(plugin_.rglob("*.vst3")).read_bytes()).hexdigest()
                h = hashlib.sha256(host_.read_bytes()).hexdigest()
                return {
                    "schema": "125a-gui-exploration-result-v1",
                    "status": "OBSERVATIONS_COMPLETE", "sham_control": "COMPLETE",
                    "verified_module_sha256": m, "verified_gui_host_sha256": h,
                    "completed_points": len(coords), "sham_verified_points": len(coords),
                    "probes": [
                        {"x": x, "y": y, "classification":
                         ("VISUAL_CHANGE" if i == 0 else
                          "UNSTABLE_CONTROL" if i == 1 else "NO_OBSERVED_CHANGE")}
                        for i, (x, y) in enumerate(coords)]
                }
            result = scan(plugin, host, root / "result", columns=2, rows=2,
                          acknowledge=True, runner=self.fake_runner, explorer=explorer)
            self.assertEqual(result["candidate_points"], 1)
            self.assertEqual(result["unstable_points"], 1)
            self.assertEqual(result["independent_product_semantics"], "NOT COVERED")
            self.assertFalse(result["release_approved"])


if __name__ == "__main__":
    unittest.main()
