#!/usr/bin/env python3
"""P66 independent assertions for technical quickcheck inside common product plans."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from run_product_test_plan import validate, execute, SCHEMA


def digest(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def fixture(root):
    dll = root / "Real.vst3" / "Contents" / "x86_64-win" / "Real.vst3"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"real-native-vst3")
    hosts = {}
    for name in ("gui", "audio", "stress"):
        path = root / (name + ".exe")
        path.write_bytes(name.encode())
        hosts[name] = {"path": str(path), "sha256": digest(path)}
    plan = {
        "schema": SCHEMA,
        "product": {"id": "plugin_qa", "module": str(dll),
                    "sha256": digest(dll)},
        "hosts": hosts,
        "cases": [{"id": "audio_recall", "kind": "technical_quickcheck",
                   "contract": {"required_coverage": [
                       "api_playback_save", "sample_rate_buffer_matrix",
                       "native_audio_state_capture"]}}]
    }
    return plan


def evidence(plan):
    return {
        "schema": "125a-quickcheck-result-v1",
        "status": "TECHNICAL_PASS", "release_approved": False,
        "verified_module_sha256": plan["product"]["sha256"],
        "coverage": {
            "api_playback_save": "PASS",
            "sample_rate_buffer_matrix": "PASS",
            "native_audio_state_capture": "PASS",
            "fresh_process_project_recall": "PASS",
            "physical_asio_hardware": "NOT RUN",
            "real_commercial_daw_session": "NOT RUN"
        }
    }


class TechnicalQuickcheckAdapterTests(unittest.TestCase):
    def test_pinned_native_quickcheck_adapter_positive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = fixture(root)
            assert len(validate(plan)[2]) == 1
            calls = []
            def quick(bundle, host, stress, out, timeout):
                calls.append((bundle, host, stress))
                return evidence(plan)
            report = execute(plan, root / "positive", quick_runner=quick)
            self.assertEqual(report["status"], "CONTRACT_PASS")
            self.assertEqual(report["passed_cases"], 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0].suffix, ".vst3")
            self.assertFalse(report["release_approved"])
            self.assertEqual(report["physical_asio_hardware"], "NOT RUN")

    def test_false_coverage_and_wrong_module_never_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = fixture(root)
            cases = []
            for field, replacement in (
                    ("api_playback_save", "NOT COVERED"),
                    ("sample_rate_buffer_matrix", "FAIL"),
                    ("physical_asio_hardware", "PASS"),
                    ("real_commercial_daw_session", "PASS")):
                r = evidence(plan)
                r["coverage"][field] = replacement
                cases.append(r)
            r = evidence(plan)
            r["verified_module_sha256"] = "0" * 64
            cases.append(r)
            r = evidence(plan)
            r["release_approved"] = True
            cases.append(r)
            for i, result in enumerate(cases):
                with self.subTest(i=i):
                    report = execute(plan, root / ("bad%d" % i),
                                     quick_runner=lambda *a, output=result, **kw: output)
                    self.assertEqual(report["status"], "FAIL")
                    self.assertEqual(report["failed_cases"], 1)
                    self.assertFalse(report["release_approved"])

    def test_rejects_incomplete_hosts_unsafe_coverage_or_changed_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = fixture(root)
            plan = fixture(root)
            del plan["hosts"]["stress"]
            with self.assertRaises(ValueError):
                validate(plan)
            for coverage in (
                [], ["midi_wav_export"], ["api_playback_save", "api_playback_save"],
                [True], [".__class__"]
            ):
                plan = fixture(root)
                plan["cases"][0]["contract"]["required_coverage"] = coverage
                with self.subTest(coverage=coverage), self.assertRaises(ValueError):
                    validate(plan)
            plan = fixture(root)
            audio = Path(plan["hosts"]["audio"]["path"])
            audio.write_bytes(b"altered-native-host")
            with self.assertRaises(ValueError):
                validate(plan)
            self.assertEqual(base["schema"], SCHEMA)


if __name__ == "__main__":
    unittest.main()
