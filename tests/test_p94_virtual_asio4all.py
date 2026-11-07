#!/usr/bin/env python3
"""P94 ASIO4ALL virtual-only classification and hostile/native evidence tests."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from run_virtual_asio4all import (
    SCHEMA, RESULT_SCHEMA, detect_live_wdm_endpoints, digest, generate, run
)

CLSID = "{01234567-89AB-CDEF-ABCD-0123456789AB}"


class VirtualASIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plugin = self.root / "exact.vst3"
        self.executor = self.root / "host.exe"
        self.plugin.write_bytes(b"TEST ONLY native fixture")
        self.executor.write_bytes(b"TEST ONLY native executor")
        self.plan = generate(
            self.plugin, self.executor, "ASIO4ALL v2", rate=44100,
            frames=128, callbacks=100,
            registry_reader=lambda name: CLSID, platform="win32")
        self.registry = lambda name: CLSID
        self.endpoints = lambda: {
            "playback": ["CABLE Input (VB-Audio Virtual Cable)"],
            "recording": ["CABLE Output (VB-Audio Virtual Cable)"]
        }
        self.native_calls = []

    def native_runner(self, command, **kwargs):
        self.native_calls.append(command)
        def arg(flag):
            return command[command.index(flag) + 1]
        proof = {
            "schema": "125a-physical-asio-native-evidence-v1",
            "nonce": arg("--nonce"),
            "product_sha256": digest(self.plugin),
            "executor_sha256": digest(self.executor),
            "asio_driver_name": "ASIO4ALL v2",
            "asio_driver_clsid": CLSID,
            "sample_rate": 44100,
            "buffer_frames": 128,
            "completed_callbacks": 100,
            "asio_callbacks": 100,
            "deadline_misses": 0, "xruns": 0,
            "process_failures": 0, "error_code": 0
        }
        Path(arg("--out")).write_text(json.dumps(proof), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "native sample fixture", "")

    def execute(self, **extra):
        options = dict(opt_in=True, platform="win32",
                       endpoint_reader=self.endpoints,
                       registry_reader=self.registry,
                       process_runner=self.native_runner)
        options.update(extra)
        return run(self.plan, self.root / "output", **options)

    def test_valid_callback_evidence_remains_explicitly_virtual(self):
        result = self.execute()
        self.assertEqual(result["status"], "VIRTUAL_ASIO_CALLBACK_PASS")
        self.assertEqual(result["actual_asio_callbacks"], 100)
        self.assertEqual(result["virtual_wdm_endpoints"], "VB_CABLE_PAIR_ACTIVE")
        self.assertFalse(result["physical_hardware_verified"])
        self.assertFalse(result["daw_session_verified"])
        self.assertFalse(result["release_approved"])
        self.assertEqual(result["physical_asio_hardware"], "NOT_TESTED")
        self.assertNotIn("hardware_asio", result)
        self.assertEqual(len(self.native_calls), 1)
        self.assertEqual(result["verified_module_sha256"], digest(self.plugin))

    def test_non_opt_in_is_not_run_and_does_not_touch_driver(self):
        result = self.execute(opt_in=False)
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertEqual(self.native_calls, [])
        self.assertFalse(result["physical_hardware_verified"])

    def test_missing_wdm_pair_fails_before_driver(self):
        result = self.execute(endpoint_reader=lambda: {
            "playback": ["CABLE Input"], "recording": []})
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertFalse(self.native_calls)

    def test_reject_real_hardware_driver_and_wrong_registration(self):
        for name in ("Focusrite USB ASIO", "Audient ASIO", "FlexASIO", ""):
            with self.subTest(name=name):
                attempt = copy.deepcopy(self.plan)
                attempt["asio_driver"]["name"] = name
                with self.assertRaises(ValueError):
                    from run_virtual_asio4all import validate
                    validate(attempt)
        result = self.execute(registry_reader=lambda n: "{11111111-1111-1111-1111-111111111111}")
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertFalse(self.native_calls)

    def test_wrong_nonce_and_xruns_are_strict_failures(self):
        def corrupt(command, **kwargs):
            response = self.native_runner(command, **kwargs)
            path = Path(command[command.index("--out") + 1])
            proof = json.loads(path.read_text(encoding="utf-8"))
            proof["nonce"] = "forged"
            path.write_text(json.dumps(proof), encoding="utf-8")
            return response
        result = self.execute(process_runner=corrupt)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["physical_asio_hardware"], "NOT_TESTED")

    def test_native_driver_error_is_never_accepted(self):
        def failing(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 1, "", "device busy")
        result = self.execute(process_runner=failing)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["actual_asio_callbacks"], 0)

    def test_module_changed_before_callback_does_not_approve(self):
        self.plugin.write_bytes(b"MODIFIED VST3")
        result = self.execute()
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertFalse(self.native_calls)

    def test_live_pnp_requires_both_active_real_vb_cable_endpoints(self):
        def fake_ok(argv, **kwargs):
            self.assertIn("Get-PnpDevice", argv[-1])
            return subprocess.CompletedProcess(
                argv, 0,
                json.dumps(["CABLE Input (VB-Audio Virtual Cable)",
                            "CABLE Output (VB-Audio Virtual Cable)"]), "")
        found = detect_live_wdm_endpoints(
            probe_runner=fake_ok, platform="win32")
        self.assertEqual(len(found["playback"]), 1)
        self.assertEqual(len(found["recording"]), 1)
        def fake_no(argv, **kwargs):
            return subprocess.CompletedProcess(
                argv, 0, json.dumps(["Speakers (Real USB)"]), "")
        with self.assertRaises(ValueError):
            detect_live_wdm_endpoints(
                probe_runner=fake_no, platform="win32")

    def test_linux_cannot_masquerade_as_live_windows_driver(self):
        result = self.execute(platform="linux")
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertEqual(self.native_calls, [])


if __name__ == "__main__":
    unittest.main()
