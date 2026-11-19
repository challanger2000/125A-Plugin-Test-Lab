#!/usr/bin/env python3
"""Positive, boundary and adversarial tests of manually supplied THE_LAB exports."""
import json
from pathlib import Path
import tempfile
import unittest

from import_the_lab_report import digest, import_report, main, SCHEMA


class TheLabImporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root / "125A Precision Filter.vst3"
        self.module.write_bytes(b"distinct fake test-only VST3 binary fixture")
        self.export = self.root / "measurement.json"
        self.export.write_text(json.dumps({
            "status": "PASS", "measurements": [{"frequency_hz": 1000,
                                                  "magnitude_db": -3.0}]})+"\n")

    def run_import(self):
        return import_report(self.module, digest(self.module), self.export,
                             digest(self.export), self.root / "out",
                             declared_version="1.3.4")

    def test_positive_json_import_does_not_promote_vendor_pass(self):
        result = self.run_import()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["status"], "EXTERNAL_REPORT_IMPORTED_SOURCE_UNATTESTED")
        self.assertEqual(result["vendor_verdict"], "NOT INTERPRETED")
        self.assertFalse(result["original_measurements_verified"])
        self.assertFalse(result["release_approved"])
        self.assertEqual((self.root/"out"/"THE-LAB-ORIGINAL.json").read_bytes(),
                         self.export.read_bytes())

    def test_csv_semicolon_report(self):
        self.export = self.root / "measurement.csv"
        self.export.write_text("hz;db\n20;-24.1\n1000;-.2\n", encoding="utf-8")
        result = self.run_import()
        self.assertEqual(result["structure"]["rows"], 2)
        self.assertEqual(result["structure"]["columns"], 2)
        self.assertFalse(result["release_approved"])

    def test_stale_module_and_export_hash_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "VST3 binary.*pinned"):
            import_report(self.module, "0"*64, self.export, digest(self.export), self.root/"a")
        with self.assertRaisesRegex(ValueError, "export differs"):
            import_report(self.module, digest(self.module), self.export, "0"*64, self.root/"b")

    def test_nonfinite_and_duplicate_key_json_rejected(self):
        for content in ('{"frequency": NaN}', '{"a": 1, "a": 2}',
                        '{"x": Infinity}', '{"x": -Infinity}', '{"x": 1e999}'):
            with self.subTest(content=content):
                self.export.write_text(content)
                with self.assertRaises(ValueError):
                    self.run_import()

    def test_invalid_csv_and_binary_disguised_as_json_rejected(self):
        self.export = self.root/"measurement.csv"
        for text in ("hz,db\n20\n", "hz,db\n", "hz,hz\n20,30\n"):
            with self.subTest(text=text):
                self.export.write_text(text)
                with self.assertRaises(ValueError):
                    self.run_import()
        self.export = self.root/"forged.json"
        self.export.write_bytes(b"MZ\0not an export")
        with self.assertRaises(ValueError):
            self.run_import()

    def test_oversized_report_and_unknown_extension_rejected(self):
        self.export.write_bytes(b"x"*4_000_001)
        with self.assertRaises(ValueError):
            self.run_import()
        self.export = self.root/"installer.exe"
        self.export.write_bytes(b"not an export")
        with self.assertRaisesRegex(ValueError, "only manual"):
            self.run_import()

    def test_failed_cli_clears_stale_success_artifact(self):
        self.run_import()
        self.assertEqual(main(["--module", str(self.module), "--module-sha256", "0"*64,
                               "--report", str(self.export), "--report-sha256",
                               digest(self.export), "--out", str(self.root/"out")]), 1)
        result=json.loads((self.root/"out"/"THE-LAB-EXTERNAL-OBSERVATION.json").read_text())
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(result["release_approved"])


if __name__ == "__main__":
    unittest.main()
