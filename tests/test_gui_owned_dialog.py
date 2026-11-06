#!/usr/bin/env python3
"""P60 independent popup ownership and falsified observation regressions."""
import tempfile
from pathlib import Path
import hashlib
import unittest

from run_gui_owned_dialog import validate_native, run


def evidence(count):
    return ("format\t125A-OWNED-DIALOG-v1\nbaseline\t0\n"
            f"after\t{count}\n"
            + "".join(f"dialog\t{i}\t#32770\tvisible\towned\n"
                      for i in range(count)) + "end\tCOMPLETE\n")


class DialogTests(unittest.TestCase):
    def test_real_owned_dialog_contract(self):
        self.assertEqual(validate_native(evidence(1)), 1)
        self.assertEqual(validate_native(evidence(0)), 0)

    def test_malformed_or_fake_evidence(self):
        wrong = [
            evidence(1).replace("baseline\t0", "baseline\t1"),
            evidence(1).replace("after\t1", "after\t2"),
            evidence(1).replace("#32770", "BUTTON"),
            evidence(1).replace("owned", "foreign"),
            evidence(1).replace("visible", "hidden"),
            evidence(1).replace("end\tCOMPLETE", "end\tPASS"),
            evidence(1).replace("dialog\t0", "dialog\t1"),
            evidence(1)[:-12],
            evidence(0).replace("after\t0", "after\t-1"),
        ]
        for text in wrong:
            with self.subTest(source=text[:48]), self.assertRaises(ValueError):
                validate_native(text)

    def test_real_wrapper_positive_and_deliberate_missing_popup(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plugin = root / "Fixture.vst3"
            dll = plugin / "Contents/x86_64-win/Fixture.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"binary")
            host = root / "GUI.exe"
            host.write_bytes(b"exe")
            class Done:
                returncode = 0
                stdout = "native host finished"
                stderr = ""
            def native(count):
                def invoke(argv, **kwargs):
                    self.assertEqual(argv[1], "--observe-owned-dialog")
                    Path(argv[-1]).write_text(evidence(count), encoding="utf-8")
                    return Done()
                return invoke
            good = run(plugin, host, root / "good", acknowledge=True,
                       runner=native(1))
            self.assertEqual(good["status"], "CONTRACT_PASS")
            self.assertFalse(good["release_approved"])
            bad = run(plugin, host, root / "bad", acknowledge=True,
                      runner=native(0))
            self.assertEqual(bad["status"], "FAIL")
            self.assertEqual(bad["observed_owned_dialogs"], 0)
            self.assertFalse(bad["release_approved"])
            with self.assertRaises(ValueError):
                run(plugin, host, root / "unapproved", runner=native(1))


if __name__ == "__main__":
    unittest.main()
