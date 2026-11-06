#!/usr/bin/env python3
"""P51 positive and adversarial gesture contract regression tests."""
import json
from pathlib import Path
import tempfile
import unittest

from run_gui_gesture_sweep import compile_contract, run


def contract():
    return {
        "schema": "125a-gui-gesture-sweep-v1",
        "product": {"binary": "C:/QA/Plugin.vst3/Contents/x86_64-win/Plugin.vst3",
                    "sha256": "a" * 64},
        "gui_host": "C:/QA/GUI.exe",
        "param_id": 9001,
        "initial_normalized": 0,
        "checkpoints": [
            {"start_x": 100, "start_y": 70, "end_x": 140, "end_y": 90,
             "expected_normalized": .5},
            {"start_x": 140, "start_y": 90, "end_x": 180, "end_y": 90,
             "expected_normalized": 1.0},
            {"start_x": 180, "start_y": 90, "end_x": 100, "end_y": 70,
             "expected_normalized": 0}
        ]
    }


class GestureSweepTests(unittest.TestCase):
    def test_compiles_persistent_window_native_actions(self):
        wf = compile_contract(contract())
        self.assertEqual(len(wf["steps"]), 3)
        self.assertEqual([s["before_normalized"] for s in wf["steps"]], [0, .5, 1])
        self.assertEqual([s["expected_normalized"] for s in wf["steps"]], [.5, 1, 0])
        self.assertTrue(all(s["action"] == "drag" for s in wf["steps"]))
        self.assertEqual(len(wf["initial"]), 1)

    def test_adversarial_invalid_oracles_rejected(self):
        for variant in range(8):
            c = contract()
            if variant == 0:
                c["checkpoints"][0]["expected_normalized"] = float("nan")
            elif variant == 1:
                c["checkpoints"][2]["expected_normalized"] = 1.1
            elif variant == 2:
                c["checkpoints"][2]["expected_normalized"] = 1.0
            elif variant == 3:
                c["checkpoints"][0]["end_x"] = 100
                c["checkpoints"][0]["end_y"] = 70
            elif variant == 4:
                c["checkpoints"] = c["checkpoints"][:1]
            elif variant == 5:
                c["checkpoints"][1]["expected_normalized"] = .5
            elif variant == 6:
                c["checkpoints"][0]["start_x"] = True
            else:
                c["checkpoints"][0]["bogus"] = 5
            with self.subTest(variant=variant):
                with self.assertRaises(ValueError):
                    compile_contract(c)

    def test_wrapper_rejects_forged_workflow(self):
        with tempfile.TemporaryDirectory() as t:
            seen = []
            def ok(wf, path, **kwargs):
                seen.append(wf)
                return {"status": "TECHNICAL_PASS", "declared_actions": 3,
                        "verified_actions": 3, "controller_action_chain": "PASS"}
            good = run(contract(), Path(t) / "good", workflow_runner=ok)
            self.assertEqual(good["status"], "CONTRACT_PASS")
            self.assertFalse(good["release_approved"])
            self.assertEqual(len(seen[0]["steps"]), 3)
            def forged(*args, **kwargs):
                return {"status": "TECHNICAL_PASS", "declared_actions": 3,
                        "verified_actions": 2, "controller_action_chain": "PASS"}
            bad = run(contract(), Path(t) / "bad", workflow_runner=forged)
            self.assertEqual(bad["status"], "FAIL")
            self.assertEqual(bad["verified_checkpoints"], 0)
            self.assertFalse(json.loads((Path(t) / "bad/GUI-GESTURE-SWEEP-RESULT.json")
                                        .read_text())["release_approved"])


if __name__ == "__main__":
    unittest.main()
