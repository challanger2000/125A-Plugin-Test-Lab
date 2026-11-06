#!/usr/bin/env python3
"""P59 registry selection, exact product/ASIO-host hashes and invalid plan tests."""
import tempfile
from pathlib import Path
import unittest

from generate_physical_asio_plan import generate
from run_physical_asio import validate


class PhysicalPlanGeneratorTests(unittest.TestCase):
    def test_real_binary_hash_and_approved_registry_driver(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            dll = root / "Real.vst3"
            exe = root / "125A_Test_Lab_Physical_ASIO.exe"
            dll.write_bytes(b"real-vst3-binary-test-identity")
            exe.write_bytes(b"real-executor-binary-test-identity")
            registry_calls = []
            def driver(name):
                registry_calls.append(name)
                return "{12345678-1234-1234-1234-123456789abc}"
            plan = generate(dll, exe, "Audient ASIO", platform="win32",
                            registry_reader=driver)
            self.assertEqual(registry_calls, ["Audient ASIO"])
            self.assertEqual(plan["scenarios"][0],
                             {"sample_rate": 44100, "buffer_frames": 128,
                              "callbacks": 12000})
            self.assertEqual(plan["schema"], "125a-physical-asio-plan-v1")
            validate(plan)
            self.assertNotEqual(plan["product"]["sha256"],
                                plan["executor"]["sha256"])
            dll.write_bytes(b"modified after approved plan")
            with self.assertRaises(ValueError):
                validate(plan)

    def test_rejects_platform_driver_injection_and_unavailable_device(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            dll = root / "Real.vst3"
            exe = root / "Host.exe"
            dll.write_bytes(b"fixture")
            exe.write_bytes(b"binary")
            good = lambda name: "{12345678-1234-1234-1234-123456789abc}"
            with self.assertRaises(ValueError):
                generate(dll, exe, "Driver", platform="linux",
                         registry_reader=good)
            for name in ("", "foo\\bar", "foo/bar", "bad\nname"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    generate(dll, exe, name, platform="win32", registry_reader=good)
            for clsid in ("", "fake", "{00000000}"):
                with self.subTest(clsid=clsid), self.assertRaises(ValueError):
                    generate(dll, exe, "Driver", platform="win32",
                             registry_reader=lambda name, value=clsid: value)
            for rate, frames, count in ((100000, 128, 12000),
                                        (44100, 129, 12000),
                                        (44100, 128, 2),
                                        (True, 128, 100)):
                with self.subTest(rate=rate, frames=frames, count=count), self.assertRaises(ValueError):
                    generate(dll, exe, "Driver", platform="win32",
                             registry_reader=good, rate=rate, frames=frames,
                             callbacks=count)


if __name__ == "__main__":
    unittest.main()
