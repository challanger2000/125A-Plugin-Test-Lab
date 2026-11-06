#!/usr/bin/env python3
"""P61 refuses fabricated child-button clicks or missing popup dismissals."""
import unittest
from run_gui_owned_dialog import validate_native


GOOD = ("format\t125A-OWNED-DIALOG-v1\n"
        "baseline\t0\nafter\t1\n"
        "dialog\t0\t#32770\tvisible\towned\n"
        "button\t43061\tButton\tactioned\tdialog_closed\n"
        "end\tCOMPLETE\n")


class DialogButtonContract(unittest.TestCase):
    def test_native_button_action_and_dialog_dismissal(self):
        self.assertEqual(validate_native(GOOD, expect_button=True), 1)

    def test_missing_or_forged_native_button_fails(self):
        bad = [
            GOOD.replace("button\t43061\tButton\tactioned\tdialog_closed\n", ""),
            GOOD.replace("43061", "43062"),
            GOOD.replace("dialog_closed", "still_open"),
            GOOD.replace("\tButton\t", "\tEdit\t"),
            GOOD.replace("actioned", "guessed"),
            GOOD.replace("end\tCOMPLETE", "end\tPASS"),
        ]
        for evidence in bad:
            with self.subTest(evidence=evidence[-80:]), self.assertRaises(ValueError):
                validate_native(evidence, expect_button=True)

    def test_button_evidence_not_misread_as_generic_p60(self):
        with self.assertRaises(ValueError):
            validate_native(GOOD, expect_button=False)


if __name__ == "__main__":
    unittest.main()
