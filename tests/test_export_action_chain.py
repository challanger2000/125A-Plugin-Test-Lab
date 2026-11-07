#!/usr/bin/env python3
"""P77 contract/dispatch regression; mocked I/O is NOT a real plugin-export test."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_export_action_chain as p77


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class P77Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.module = self.root / "fake.vst3"
        self.host = self.root / "host.exe"
        self.module.write_bytes(b"module")
        self.host.write_bytes(b"host")
        self.output = self.root / "fresh.wav"
        self.workflow = {"schema": "placeholder"}
        self.contract = {"schema": "placeholder"}
        self.chain = {"schema": p77.SCHEMA, "workflow": self.workflow, "export": self.contract}
        self.gui_patch = patch.object(p77, "validate_gui", return_value=(
            self.host, self.root, self.module, [], [{"id": "click"}]))
        self.export_patch = patch.object(p77, "validate_export", return_value=[
            {"path": str(self.output)}])
        self.gui_patch.start()
        self.export_patch.start()
        self.addCleanup(self.gui_patch.stop)
        self.addCleanup(self.export_patch.stop)

    def gui_result(self):
        return dict(status="TECHNICAL_PASS", verified_module_sha256=sha(self.module),
                    gui_host_sha256=sha(self.host), declared_actions=1,
                    verified_actions=1, release_approved=False)

    def artifact_result(self):
        return dict(status="ARTIFACT_PASS", verified_module_sha256=sha(self.module),
                    declared_actions=1, verified_actions=1, release_approved=False,
                    outputs=[{"status": "PASS"}])

    def test_fresh_success(self):
        def gui(_workflow, _out, timeout):
            self.output.write_bytes(b"newly created")
            return self.gui_result()
        result = p77.run(self.chain, self.root / "report",
                         gui_runner=gui,
                         export_verifier=lambda *_args, **_kw: self.artifact_result())
        self.assertEqual(result["status"], "ACTION_AND_ARTIFACT_PASS")
        self.assertFalse(result["actual_plugin_export_tested"])
        self.assertEqual(result["export_origin"], "UNATTRIBUTED_AFTER_NATIVE_GUI_ACTION")
        self.assertFalse(result["provenance_verified"])
        self.assertFalse(result["release_approved"])

    def test_stale_file_rejected_before_action(self):
        self.output.write_bytes(b"stale")
        with self.assertRaisesRegex(ValueError, "occupied"):
            p77.run(self.chain, self.root / "report",
                    gui_runner=lambda *_a, **_k: self.fail("must not run"))

    def test_stale_timestamp_fails_even_if_file_appears_after_action(self):
        def gui(_workflow, _out, timeout):
            self.output.write_bytes(b"stale contents")
            os.utime(self.output, ns=(1_000_000_000, 1_000_000_000))
            return self.gui_result()
        result = p77.run(self.chain, self.root / "report",
                         gui_runner=gui,
                         export_verifier=lambda *_a, **_k: self.fail("must not verify"))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("predates", result["faults"][0])

    def test_broken_symlink_rejected_before_action(self):
        try:
            self.output.symlink_to(self.root / "missing.wav")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this Windows runner")
        with self.assertRaisesRegex(ValueError, "occupied"):
            p77.validate(self.chain)

    def test_hardlink_export_rejected(self):
        original = self.root / "other.bin"
        original.write_bytes(b"hardlinked bytes")
        def gui(_workflow, _out, timeout):
            os.link(original, self.output)
            return self.gui_result()
        result = p77.run(self.chain, self.root / "report",
                         gui_runner=gui,
                         export_verifier=lambda *_a, **_k: self.fail("must not verify"))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("nonlinked", result["faults"][0])

    def test_missing_output_fails(self):
        result = p77.run(self.chain, self.root / "report",
                         gui_runner=lambda *_a, **_k: self.gui_result())
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["verified_outputs"], 0)

    def test_wrong_hash_fails(self):
        def gui(_workflow, _out, timeout):
            self.output.write_bytes(b"bad")
            return self.gui_result()
        evidence = self.artifact_result()
        evidence["status"] = "ARTIFACT_FAIL"
        result = p77.run(self.chain, self.root / "report",
                         gui_runner=gui, export_verifier=lambda *_a, **_k: evidence)
        self.assertEqual(result["status"], "FAIL")

    def test_bad_native_actions_prevent_oracle(self):
        native = self.gui_result()
        native["verified_actions"] = 0
        result = p77.run(self.chain, self.root / "report",
                         gui_runner=lambda *_a, **_k: native,
                         export_verifier=lambda *_a, **_k: self.fail("no oracle"))
        self.assertEqual(result["status"], "FAIL")

    def test_bad_schema(self):
        self.chain["schema"] = "unknown"
        with self.assertRaises(ValueError):
            p77.validate(self.chain)


if __name__ == "__main__":
    unittest.main()
