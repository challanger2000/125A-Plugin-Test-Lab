#!/usr/bin/env python3
"""P55 independent native button selection, opt-in and forged-evidence tests."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from run_gui_native_buttons import select_buttons, run


ROOT = {"index": 0, "parent": -1, "class_name": "NativeEditor", "visible": True,
        "enabled": True, "rectangle": [0, 0, 320, 180], "control_id": 0}
BUTTON = {"index": 1, "parent": 0, "class_name": "Button", "visible": True,
          "enabled": True, "rectangle": [120, 65, 200, 115], "control_id": 43001}


class NativeButtonTests(unittest.TestCase):
    def test_real_nested_geometry(self):
        buttons, truncated = select_buttons([ROOT, BUTTON])
        self.assertEqual(buttons[0]["center"], [160, 90])
        self.assertEqual(buttons[0]["control_id"], 43001)
        self.assertFalse(truncated)

    def test_painted_only_cannot_be_native_button(self):
        self.assertEqual(select_buttons([ROOT]), ([], False))

    def test_hidden_disabled_and_unsafe_bounds(self):
        for key in ("visible", "enabled"):
            node = {**BUTTON, key: False}
            self.assertEqual(select_buttons([ROOT, node]), ([], False))
        with self.assertRaises(ValueError):
            select_buttons([ROOT, {**BUTTON, "rectangle": [300, 30, 400, 90]}])
        with self.assertRaises(ValueError):
            select_buttons([ROOT, {**BUTTON, "rectangle": [0, 0, 0, 0]}])

    def test_no_opt_in(self):
        with self.assertRaises(ValueError):
            run("missing.vst3", "missing.exe", "out")

    def test_sham_verified_native_button_and_fake_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plugin = root / "Synth.vst3"
            dll = plugin / "Contents/x86_64-win/Synth.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"vst3-identity")
            host = root / "GUI.exe"
            host.write_bytes(b"gui-identity")
            m = hashlib.sha256(dll.read_bytes()).hexdigest()
            h = hashlib.sha256(host.read_bytes()).hexdigest()
            def inventory(*args, **kwargs):
                return {"status": "OBSERVATIONS_COMPLETE",
                        "verified_module_sha256": m, "verified_gui_host_sha256": h,
                        "native_hwnd_count": 2, "nodes": [ROOT, BUTTON]}
            def explore(*args, points, **kwargs):
                self.assertEqual(points, "160,90")
                return {"schema": "125a-gui-exploration-result-v1",
                        "status": "OBSERVATIONS_COMPLETE", "sham_control": "COMPLETE",
                        "verified_module_sha256": m, "verified_gui_host_sha256": h,
                        "completed_points": 1, "sham_verified_points": 1,
                        "probes": [{"x": 160, "y": 90, "classification":
                                    "PARAMETER_AND_VISUAL_CHANGE",
                                    "changed_parameters": [{"param_id": 9001}]}]}
            good = run(plugin, host, root / "good", acknowledge=True,
                       reader=inventory, explorer=explore)
            self.assertEqual(good["status"], "OBSERVATIONS_COMPLETE")
            self.assertEqual(good["probed_buttons"], 1)
            self.assertEqual(good["observations"][0]["changed_parameters"][0]["param_id"], 9001)
            self.assertFalse(good["release_approved"])
            def fake(*args, **kwargs):
                result = explore(*args, **kwargs)
                result["sham_verified_points"] = 0
                return result
            bad = run(plugin, host, root / "bad", acknowledge=True,
                      reader=inventory, explorer=fake)
            self.assertEqual(bad["status"], "FAIL")
            self.assertFalse(bad["release_approved"])
            def only_painted(*args, **kwargs):
                return {"status": "OBSERVATIONS_COMPLETE",
                        "verified_module_sha256": m, "verified_gui_host_sha256": h,
                        "native_hwnd_count": 1, "nodes": [ROOT]}
            empty = run(plugin, host, root / "painted", acknowledge=True,
                        reader=only_painted)
            self.assertEqual(empty["status"], "OBSERVATIONS_COMPLETE")
            self.assertEqual(empty["probed_buttons"], 0)


if __name__ == "__main__":
    unittest.main()
