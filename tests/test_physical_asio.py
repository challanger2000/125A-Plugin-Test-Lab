#!/usr/bin/env python3
"""P56 ASIO plans: strict refusal, replay/mismatch rejection and acceptance tests.

A synthetic callback record here is test DATA, not a physical ASIO run.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from run_physical_asio import (SCHEMA, EVIDENCE, RESULT, check_evidence,
                               validate, run, CLSID)


CL = "{12345678-1234-1234-1234-123456789abc}"


def fixture(root):
    dll = root / "Synth.vst3"
    dll.write_bytes(b"exact-plugin")
    exe = root / "asio-probe.exe"
    exe.write_bytes(b"exact-executor")
    m = hashlib.sha256(dll.read_bytes()).hexdigest()
    h = hashlib.sha256(exe.read_bytes()).hexdigest()
    plan = {
        "schema": SCHEMA,
        "product": {"path": str(dll), "sha256": m},
        "executor": {"path": str(exe), "sha256": h},
        "asio_driver": {"name": "Lab Fixture ASIO", "clsid": CL},
        "scenarios": [{"sample_rate": 44100, "buffer_frames": 128, "callbacks": 100}]
    }
    return plan


def record(plan, nonce, *, failures=0, callbacks=100):
    item = plan["scenarios"][0]
    return {
        "schema": EVIDENCE, "nonce": nonce,
        "product_sha256": plan["product"]["sha256"],
        "executor_sha256": plan["executor"]["sha256"],
        "asio_driver_name": plan["asio_driver"]["name"],
        "asio_driver_clsid": plan["asio_driver"]["clsid"],
        "sample_rate": item["sample_rate"],
        "buffer_frames": item["buffer_frames"],
        "completed_callbacks": callbacks,
        "asio_callbacks": callbacks,
        "deadline_misses": failures, "xruns": 0,
        "process_failures": 0, "error_code": 0
    }


class FakeExit:
    returncode = 0
    stdout = "Synthetic unit fixture only"
    stderr = ""


class AsioTests(unittest.TestCase):
    def test_registry_clsid_and_strict_contract(self):
        self.assertTrue(CLSID.fullmatch(CL))
        self.assertFalse(CLSID.fullmatch("fake"))
        with tempfile.TemporaryDirectory() as f:
            plan = fixture(Path(f))
            validate(plan)
            plan["scenarios"][0]["callbacks"] = True
            with self.assertRaises(ValueError):
                validate(plan)

    def test_non_hardware_ci_never_passes(self):
        with tempfile.TemporaryDirectory() as f:
            p = Path(f)
            plan = fixture(p)
            result = run(plan, p / "no", platform="linux", acknowledge=True)
            self.assertEqual(result["status"], "NOT_RUN")
            self.assertEqual(result["hardware_asio"], "NOT_RUN")
            self.assertFalse(result["release_approved"])
            result = run(plan, p / "not-opted-in", platform="win32")
            self.assertEqual(result["status"], "NOT_RUN")

    def test_missing_physical_driver_never_executes(self):
        with tempfile.TemporaryDirectory() as f:
            p = Path(f)
            called = []
            def fake(*args, **kwargs):
                called.append(args)
                return FakeExit()
            r = run(fixture(p), p / "missing", platform="win32",
                    acknowledge=True, runner=fake,
                    registry_reader=lambda name, clsid: False)
            self.assertEqual(r["status"], "NOT_RUN")
            self.assertEqual(called, [])

    def test_native_evidence_rejects_replay_wrong_driver_and_xruns(self):
        with tempfile.TemporaryDirectory() as f:
            plan = fixture(Path(f))
            obj = record(plan, "fresh")
            opts = {"nonce": "fresh", "product_sha": plan["product"]["sha256"],
                    "executor_sha": plan["executor"]["sha256"],
                    "driver": plan["asio_driver"], "scenario": plan["scenarios"][0]}
            self.assertTrue(check_evidence(obj, **opts))
            for key, value in (("nonce", "replayed"), ("asio_driver_name", "wrong"),
                               ("deadline_misses", 1), ("xruns", 2),
                               ("process_failures", 1), ("asio_callbacks", 0),
                               ("sample_rate", 96000), ("error_code", 1)):
                altered = {**obj, key: value}
                with self.subTest(key=key):
                    with self.assertRaises(ValueError):
                        check_evidence(altered, **opts)
            with self.assertRaises(ValueError):
                check_evidence({**obj, "claims_release_approved": True}, **opts)

    def test_synthetic_executor_contract_accepted_but_no_daw_release(self):
        with tempfile.TemporaryDirectory() as f:
            root = Path(f)
            plan = fixture(root)
            def fake(cmd, **kwargs):
                nonce = cmd[cmd.index("--nonce") + 1]
                output = Path(cmd[cmd.index("--out") + 1])
                output.write_text(json.dumps(record(plan, nonce)), encoding="utf-8")
                return FakeExit()
            r = run(plan, root / "simulated", platform="win32", acknowledge=True,
                    registry_reader=lambda name, clsid: True, runner=fake)
            self.assertEqual(r["status"], "EVIDENCE_ACCEPTED")
            self.assertEqual(r["hardware_asio"], "EXTERNAL_EXECUTOR_EVIDENCE_ACCEPTED")
            self.assertEqual(r["commercial_daw_session"], "NOT_RUN")
            self.assertFalse(r["release_approved"])
            self.assertEqual(len(r["scenarios"]), 1)
            def forged(cmd, **kwargs):
                output = Path(cmd[cmd.index("--out") + 1])
                output.write_text(json.dumps(record(plan, "stale-nonce")), encoding="utf-8")
                return FakeExit()
            bad = run(plan, root / "forged", platform="win32", acknowledge=True,
                      registry_reader=lambda name, clsid: True, runner=forged)
            self.assertNotEqual(bad["status"], "EVIDENCE_ACCEPTED")
            self.assertFalse(bad["release_approved"])


if __name__ == "__main__":
    unittest.main()
