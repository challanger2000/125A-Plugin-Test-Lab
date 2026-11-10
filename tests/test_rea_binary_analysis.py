#!/usr/bin/env python3
"""P99 contract regressions using synthetic REA responses, not Ghidra evidence."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from run_rea_binary_analysis import SCHEMA, analyze, digest


def canonical(target):
    return {
        "evidence_id": "ev_" + "a" * 64,
        "provider": {"id": "ghidra", "name": "Ghidra", "version": None},
        "subject": {"digest": {"sha256": digest(target)}, "format": "pe"},
        "operation": "binary_overview",
        "normalized_result": {"procedure_count": 3},
    }


class REATests(unittest.TestCase):
    def test_explicit_observation_and_attribution(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            target, node, entry = [root / n for n in ("x.vst3", "node.exe", "rea.mjs")]
            for file in (target, node, entry):
                file.write_bytes(file.name.encode())
            commands = []
            def fake(cmd, **kwargs):
                commands.append((cmd, kwargs))
                return SimpleNamespace(returncode=0, stderr="",
                                       stdout=json.dumps(canonical(target)))
            report = analyze(target, root / "good", node=node, entry=entry, runner=fake)
            self.assertEqual(report["schema"], SCHEMA)
            self.assertEqual(report["status"], "OBSERVATION_CAPTURED")
            self.assertEqual(report["binary_sha256"], digest(target))
            self.assertEqual(report["raw_sha256"], digest(root / "good" / "REA-RAW-OUTPUT.json"))
            self.assertEqual(report["observed_provider"], "ghidra")
            self.assertEqual(report["rea_evidence_id"], "ev_" + "a"*64)
            self.assertEqual(commands[0][0][2:],
                             ["inspect", str(target.resolve()), "--provider", "ghidra", "--json"])
            self.assertFalse(commands[0][1]["check"])
            self.assertEqual(report["semantic_verification"], "NOT ESTABLISHED")
            self.assertFalse(report["release_approved"])

    def test_bad_exit_json_error_timeout_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            target, node, entry = [root / n for n in ("x.vst3", "node.exe", "rea.mjs")]
            for file in (target, node, entry):
                file.write_bytes(file.name.encode())
            cases = [
                SimpleNamespace(returncode=1, stderr="no Ghidra", stdout="{}"),
                SimpleNamespace(returncode=0, stderr="", stdout="not-json"),
                SimpleNamespace(returncode=0, stderr="", stdout='{"error":"no"}'),
                SimpleNamespace(returncode=0, stderr="", stdout="{}"),
                SimpleNamespace(returncode=0, stderr="", stdout='{"ok":false}'),
                SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(
                    {**canonical(target), "provider": {"id": "placeholder"}})),
                SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(
                    {**canonical(target), "subject": {"digest": {"sha256": "0"*64}}})),
            ]
            for i, row in enumerate(cases):
                with self.subTest(index=i):
                    out = root / ("bad_" + str(i))
                    result = analyze(target, out, node=node, entry=entry,
                                     runner=lambda *args, observed=row, **kw: observed)
                    self.assertEqual(result["status"], "FAIL")
                    self.assertFalse((out / "REA-RAW-OUTPUT.json").exists())
            def raises(*args, **kwargs):
                raise subprocess.TimeoutExpired("fake", 30)
            self.assertEqual(analyze(target, root / "timeout", node=node,
                                     entry=entry, runner=raises)["status"], "FAIL")
            def mutates(*args, **kwargs):
                target.write_bytes(b"mutated")
                return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(canonical(target)))
            self.assertEqual(analyze(target, root / "mutation", node=node,
                                     entry=entry, runner=mutates)["status"], "FAIL")
            with self.assertRaises(ValueError):
                analyze(target, root / "invalid_budget", node=node, entry=entry,
                        timeout=0)


if __name__ == "__main__":
    unittest.main()
