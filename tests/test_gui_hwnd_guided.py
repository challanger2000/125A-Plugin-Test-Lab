#!/usr/bin/env python3
"""P69 native Win32 child-control candidate and opt-in isolation regressions."""
import tempfile
from pathlib import Path
import unittest

from run_gui_hwnd_guided import derive_candidates, run, SCHEMA


def actual_tree():
    return {
        "schema": "125a-hwnd-control-tree-v1",
        "status": "OBSERVATIONS_COMPLETE",
        "native_hwnd_count": 5,
        "release_approved": False,
        "nodes": [
            {"index": 0, "parent": -1, "class_name": "NativeRoot",
             "visible": True, "enabled": True,
             "rectangle": [0, 0, 320, 180], "control_id": 0},
            {"index": 1, "parent": 0, "class_name": "BUTTON",
             "visible": True, "enabled": True,
             "rectangle": [120, 65, 200, 115], "control_id": 43001},
            {"index": 2, "parent": 0, "class_name": "Edit",
             "visible": True, "enabled": True,
             "rectangle": [10, 10, 90, 40], "control_id": 43002},
            {"index": 3, "parent": 0, "class_name": "Button",
             "visible": False, "enabled": True,
             "rectangle": [10, 60, 80, 90], "control_id": 43003},
            {"index": 4, "parent": 0, "class_name": "STATIC",
             "visible": True, "enabled": True,
             "rectangle": [10, 100, 80, 130], "control_id": 43004}
        ]
    }


class GuidedNativeGuiTests(unittest.TestCase):
    def test_coordinates_derived_from_real_button_not_generic_grid(self):
        candidates, skipped = derive_candidates(actual_tree())
        self.assertEqual(len(candidates), 1)
        self.assertEqual((candidates[0]["x"], candidates[0]["y"]),
                         (160, 90))
        self.assertEqual(candidates[0]["control_id"], 43001)
        self.assertEqual(candidates[0]["interaction"], "PROPOSED_ONLY")
        self.assertEqual({s["reason"] for s in skipped},
                         {"HIDDEN_OR_DISABLED", "UNAPPROVED_OR_NON_BUTTON_CLASS"})

    def test_malformed_tree_outside_editor_and_duplicate_child_are_ignored_or_rejected(self):
        import copy
        broken = copy.deepcopy(actual_tree())
        broken["nodes"][1]["rectangle"] = [200, 40, 120, 60]
        with self.assertRaises(ValueError):
            derive_candidates(broken)
        broken = copy.deepcopy(actual_tree())
        broken["nodes"][1]["rectangle"] = [500, 50, 550, 80]
        chosen, excluded = derive_candidates(broken)
        self.assertEqual(chosen, [])
        self.assertEqual(excluded[0]["reason"], "OUTSIDE_EDITOR")
        broken = copy.deepcopy(actual_tree())
        broken["nodes"][1]["parent"] = 123
        with self.assertRaises(ValueError):
            derive_candidates(broken)
        broken = copy.deepcopy(actual_tree())
        broken["native_hwnd_count"] = 4
        with self.assertRaises(ValueError):
            derive_candidates(broken)
        with self.assertRaises(ValueError):
            derive_candidates(actual_tree(), max_points=0)

    def test_read_only_run_never_invokes_mouse_clicks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            dll = root / "Fixture.vst3/Contents/x86_64-win/Fixture.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"real VST3 identity")
            host = root / "native.exe"
            host.write_bytes(b"real GUI host identity")
            from run_gui_hwnd_guided import digest
            def inventory(*args, **kwargs):
                return {**actual_tree(),
                        "verified_module_sha256": digest(dll),
                        "verified_gui_host_sha256": digest(host)}
            probes = []
            def explore(*args, **kwargs):
                probes.append(args)
                return {}
            result = run(dll.parents[2], host, root / "read-only",
                         inventory=inventory, explore=explore)
            self.assertEqual(result["schema"], SCHEMA)
            self.assertEqual(result["status"], "CANDIDATES_COMPLETE")
            self.assertEqual(result["actual_exploration_status"], "NOT RUN")
            self.assertFalse(result["release_approved"])
            self.assertEqual(probes, [])

            def actual_explore(*args, **kwargs):
                self.assertEqual(kwargs["points"], "160,90")
                self.assertIs(kwargs["acknowledge"], True)
                return {"status": "OBSERVATIONS_COMPLETE",
                        "verified_module_sha256": digest(dll),
                        "verified_gui_host_sha256": digest(host),
                        "requested_points": 1, "completed_points": 1,
                        "sham_verified_points": 1, "release_approved": False}
            enabled = run(dll.parents[2], host, root / "opt-in",
                          acknowledge=True, inventory=inventory,
                          explore=actual_explore)
            self.assertEqual(enabled["status"], "CANDIDATES_COMPLETE")
            self.assertEqual(enabled["actual_exploration_status"],
                             "OBSERVATIONS_COMPLETE")

    def test_fake_click_evidence_never_qualifies(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            dll = root / "Test.vst3/Contents/x86_64-win/Test.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"vst3")
            host = root / "GUI.exe"
            host.write_bytes(b"host")
            from run_gui_hwnd_guided import digest
            def inventory(*args, **kwargs):
                return {**actual_tree(),
                        "verified_module_sha256": digest(dll),
                        "verified_gui_host_sha256": digest(host)}
            def fake(*args, **kwargs):
                return {"status": "OBSERVATIONS_COMPLETE",
                        "verified_module_sha256": digest(dll),
                        "verified_gui_host_sha256": digest(host),
                        "requested_points": 1, "completed_points": 1,
                        "sham_verified_points": 0, "release_approved": False}
            actual = run(dll.parents[2], host, root / "fake",
                         acknowledge=True, inventory=inventory,
                         explore=fake)
            self.assertEqual(actual["status"], "FAIL")
            self.assertEqual(actual["actual_exploration_status"], "FAIL")
            self.assertFalse(actual["release_approved"])


if __name__ == "__main__":
    unittest.main()
