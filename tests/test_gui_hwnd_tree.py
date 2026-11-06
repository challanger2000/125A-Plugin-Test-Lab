#!/usr/bin/env python3
"""P54 rejects fabricated or malformed native window hierarchy evidence."""
import unittest
from run_gui_hwnd_tree import parse_tree


def tree(nodes):
    return ("format\t125A-HWND-TREE-v1\ncount\t%d\n" % len(nodes)
            + "\n".join(nodes) + "\nend\tCOMPLETE\n")


ROOT = "node\t0\t-1\t125A_P04_NativeClickSurface\t1\t1\t0\t0\t320\t180\t0"
BUTTON = "node\t1\t0\tButton\t1\t1\t120\t65\t200\t115\t43001"


class HwndTreeTests(unittest.TestCase):
    def test_actual_class_contract(self):
        values = parse_tree(tree([ROOT, BUTTON]))
        self.assertEqual(values[1]["parent"], 0)
        self.assertEqual(values[1]["class_name"], "Button")
        self.assertEqual(values[1]["control_id"], 43001)
        self.assertEqual(values[1]["rectangle"], [120, 65, 200, 115])

    def test_custom_painted_editor_not_mistaken_for_buttons(self):
        values = parse_tree(tree([ROOT]))
        self.assertEqual(len(values), 1)

    def test_invalid_topologies_rejected(self):
        errors = [
            tree([ROOT, BUTTON]).replace("count\t2", "count\t3"),
            tree([ROOT, BUTTON]).replace("node\t1\t0", "node\t1\t1"),
            tree([ROOT, BUTTON]).replace("node\t1\t0", "node\t1\t-1"),
            tree([ROOT, BUTTON]).replace("node\t1\t0", "node\t1\t3"),
            tree([ROOT, BUTTON]).replace("120\t65\t200\t115", "200\t65\t120\t115"),
            tree([ROOT, BUTTON]).replace("end\tCOMPLETE", "end\tPASS"),
            tree([ROOT, BUTTON]).replace("Button\t1\t1", "Button\t2\t1"),
            tree([ROOT, BUTTON]).replace("node\t0\t-1", "node\t0\t0"),
            tree([ROOT, BUTTON]).replace("node\t1\t0", "node\t0\t0"),
        ]
        for item in errors:
            with self.subTest(item=item[:90]):
                with self.assertRaises(ValueError):
                    parse_tree(item)


if __name__ == "__main__":
    unittest.main()
