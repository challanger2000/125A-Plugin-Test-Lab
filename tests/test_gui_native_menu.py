#!/usr/bin/env python3
"""P62 independent Win32 native menu contract and forgery rejections."""
import unittest
from run_gui_owned_dialog import validate_native

BASE = ("format\t125A-OWNED-DIALOG-v1\n"
        "baseline\t0\nafter\t1\n"
        "dialog\t0\t#32770\tvisible\towned\n")
GOOD = (BASE + "menu\t43062\tApply Preset\tenabled\tcommand_dispatched\tdialog_closed\n"
        + "end\tCOMPLETE\n")


class NativeMenuTests(unittest.TestCase):
    def test_one_real_menu_command_contract(self):
        self.assertEqual(validate_native(GOOD, expect_menu=True), 1)

    def test_rejects_missing_wrong_or_fake_menu(self):
        variants = [
            BASE + "end\tCOMPLETE\n",
            GOOD.replace("43062", "43063"),
            GOOD.replace("Apply Preset", "Wrong Item"),
            GOOD.replace("enabled", "disabled"),
            GOOD.replace("command_dispatched", "command_not_sent"),
            GOOD.replace("dialog_closed", "dialog_still_open"),
            GOOD.replace("#32770", "Button"),
            GOOD.replace("owned", "other_process"),
            GOOD.replace("end\tCOMPLETE", "end\tINCOMPLETE"),
        ]
        for item in variants:
            with self.subTest(text=item[-85:]), self.assertRaises(ValueError):
                validate_native(item, expect_menu=True)

    def test_older_p60_or_p61_cannot_claim_menu(self):
        with self.assertRaises(ValueError):
            validate_native(GOOD)
        with self.assertRaises(ValueError):
            validate_native(GOOD, expect_button=True, expect_menu=True)


if __name__ == "__main__":
    unittest.main()
