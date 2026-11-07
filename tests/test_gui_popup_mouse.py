#!/usr/bin/env python3
"""P63 fail-closed contract tests: true popup-menu mouse selection evidence."""
import tempfile
from pathlib import Path
import unittest
from run_gui_owned_dialog import validate_native, run

BASE = ("format\t125A-OWNED-DIALOG-v1\n"
        "baseline\t0\nafter\t1\n"
        "dialog\t0\t#32770\tvisible\towned\n")
CHOICE = ("popup\t43064\tActions/Apply Preset\tmouse_input\t"
          "trackpopup_selected\tcommand_handled\tdialog_closed\n")
GOOD = BASE + CHOICE + "end\tCOMPLETE\n"


class NativePopupTests(unittest.TestCase):
    def test_real_selection_record_accepted_only_in_popup_mode(self):
        self.assertEqual(validate_native(GOOD, expect_popup=True), 1)
        for kwargs in ({}, {"expect_button": True}, {"expect_menu": True},
                       {"expect_popup": True, "expect_menu": True}):
            with self.subTest(mode=kwargs), self.assertRaises(ValueError):
                validate_native(GOOD, **kwargs)

    def test_forged_or_direct_command_never_certifies_mouse(self):
        for value in ("command_dispatched", "keyboard_guess", "mouse_failed",
                      "trackpopup_not_used", "command_not_handled",
                      "dialog_open", "direct_wm_command"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_native(
                    GOOD.replace("mouse_input", value)
                    if value != "direct_wm_command" else
                    GOOD.replace("trackpopup_selected", value),
                    expect_popup=True)
        for value in ("43065", "Unknown", "disabled", "foreign"):
            bad = GOOD.replace("43064", value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_native(bad, expect_popup=True)
        with self.assertRaises(ValueError):
            validate_native(GOOD.replace("end\tCOMPLETE", "end\tPASS"),
                            expect_popup=True)
        with self.assertRaises(ValueError):
            validate_native(BASE+"end\tCOMPLETE\n", expect_popup=True)

    def test_real_wrapper_fails_closed_on_unapproved_or_wrong_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "Plugin.vst3"
            module = plugin / "Contents/x86_64-win/Plugin.vst3"
            module.parent.mkdir(parents=True)
            module.write_bytes(b"actual-fixture-identity")
            host = root / "GUI.exe"
            host.write_bytes(b"native-GUI-identity")
            class Done:
                returncode = 0
                stdout = "fixture"
                stderr = ""
            def stub(evidence):
                def invoke(argv, **kwargs):
                    self.assertEqual(argv[1], "--select-owned-popup-mouse")
                    Path(argv[-1]).write_text(evidence, encoding="utf-8")
                    return Done()
                return invoke
            passing = run(plugin, host, root / "good", popup=True,
                          acknowledge=True, runner=stub(GOOD))
            self.assertEqual(passing["status"], "CONTRACT_PASS")
            self.assertEqual(passing["physical_menu_selection"], "MOUSE_SELECTED_OS_MENU")
            self.assertFalse(passing["release_approved"])
            bad = run(plugin, host, root / "bad", popup=True,
                      acknowledge=True,
                      runner=stub(GOOD.replace("trackpopup_selected",
                                               "direct_command")))
            self.assertEqual(bad["status"], "FAIL")
            self.assertNotEqual(bad["physical_menu_selection"], "MOUSE_SELECTED_OS_MENU")
            self.assertFalse(bad["release_approved"])
            with self.assertRaises(ValueError):
                run(plugin, host, root / "no-opt-in", popup=True,
                    runner=stub(GOOD))


if __name__ == "__main__":
    unittest.main()
