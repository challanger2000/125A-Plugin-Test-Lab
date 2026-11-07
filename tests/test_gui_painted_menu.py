#!/usr/bin/env python3
"""P64 independent custom-painted VST3 menu geometry and evidence regressions."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from run_gui_painted_menu import bmp_pixels, changed_bbox, fixture_manifest, run


def write_bmp(path, width, height, pixels):
    data = b"".join(bytes((b, g, r, 0)) for r, g, b in pixels)
    assert len(data) == width * height * 4
    header = b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, width, -height,
                       1, 32, 0, len(data), 0, 0, 0, 0)
    Path(path).write_bytes(header + info + data)


class PaintedMenuTests(unittest.TestCase):
    def test_independent_bmp_geometry_and_visual_localization(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            a = [(30, 36, 48)] * 12
            b = a.copy()
            b[1*4+1] = (210, 136, 44)
            b[1*4+2] = (210, 136, 44)
            write_bmp(root / "before.bmp", 4, 3, a)
            write_bmp(root / "after.bmp", 4, 3, b)
            self.assertEqual(changed_bbox(root / "before.bmp",
                                          root / "after.bmp"),
                             ([1, 1, 3, 2], 2))
            self.assertEqual(changed_bbox(root / "before.bmp",
                                          root / "before.bmp"),
                             (None, 0))
            self.assertEqual(bmp_pixels(root / "after.bmp")[:2], (4, 3))
            with self.assertRaises(ValueError):
                changed_bbox(root / "before.bmp", root / "after.bmp", threshold=61)
            (root / "after.bmp").write_bytes((root / "after.bmp").read_bytes()[:-4])
            with self.assertRaises(ValueError):
                changed_bbox(root / "before.bmp", root / "after.bmp")

    def test_manifest_approved_workflow_three_steps(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            dll = p / "Product.vst3"
            dll.write_bytes(b"unit")
            host = p / "Host.exe"
            host.write_bytes(b"host")
            manifest = fixture_manifest(dll, host)
            self.assertEqual(len(manifest["steps"]), 3)
            self.assertEqual(manifest["steps"][0]["visual_oracle"]["after_rgb"],
                             [210, 136, 44])
            self.assertEqual(manifest["steps"][1]["expected_normalized"], 1.0)
            self.assertIn("visual_oracle", manifest["steps"][2])

    def test_no_forged_workflow_pass_without_native_bmp(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            bundle = root / "Unit.vst3"
            module = bundle / "Contents/x86_64-win/Unit.vst3"
            module.parent.mkdir(parents=True)
            module.write_bytes(b"vst3-binary")
            exe = root / "GUI.exe"
            exe.write_bytes(b"real-gui")
            m = hashlib.sha256(module.read_bytes()).hexdigest()
            h = hashlib.sha256(exe.read_bytes()).hexdigest()
            def inventory(*a, **kw):
                return {
                    "status": "OBSERVATIONS_COMPLETE",
                    "verified_module_sha256": m,
                    "verified_gui_host_sha256": h,
                    "native_hwnd_count": 1,
                    "nodes": [{"index": 0}]}
            def forged_workflow(*a, **kw):
                return {
                    "status": "TECHNICAL_PASS", "verified_actions": 3,
                    "verified_visual_only_actions": 2,
                    "controller_action_chain": "PASS",
                    "verified_module_sha256": m,
                    "gui_host_sha256": h}
            report = run(bundle, exe, root / "fake", workflow=forged_workflow,
                         inventory=inventory)
            self.assertEqual(report["status"], "FAIL")
            self.assertFalse(report["release_approved"])
            self.assertEqual(report["verified_clicks"], 0)

    def test_missing_single_hwnd_fails_before_click(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            module = root / "Fixture.vst3/Contents/x86_64-win/Fixture.vst3"
            module.parent.mkdir(parents=True)
            module.write_bytes(b"fixture")
            host = root / "gui.exe"
            host.write_bytes(b"native-host")
            seen = []
            def bad_inventory(*args, **kwargs):
                return {"status": "OBSERVATIONS_COMPLETE",
                        "native_hwnd_count": 2}
            def never_workflow(*args, **kwargs):
                seen.append("called")
                return {}
            report = run(module.parents[2], host, root / "missing",
                         inventory=bad_inventory, workflow=never_workflow)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
