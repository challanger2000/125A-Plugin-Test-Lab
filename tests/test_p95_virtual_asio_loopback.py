#!/usr/bin/env python3
"""P95 only: adversarial and known-correct synthetic PCM oracle regression.

These fixtures deliberately DO NOT represent real ASIO driver execution.
"""
from array import array
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

from verify_virtual_asio_loopback import analyze, verify_pcm, parse_native_trace
from run_virtual_asio_loopback import run as execute
from run_virtual_asio4all import generate

MAGIC = b"125ALB01"
CLSID = "{01234567-89AB-CDEF-ABCD-0123456789AB}"


class P95VirtualLoopback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rate = 44100
        self.block = 512
        self.frames = 200 * self.block
        self.plugin = self.root / "qa.vst3"
        self.exe = self.root / "125A_Test_Lab_Virtual_ASIO_Loopback.exe"
        self.plugin.write_bytes(b"synthetic fixture not a native VST3")
        self.exe.write_bytes(b"synthetic fixture not a real ASIO host")
        self.plan = generate(
            self.plugin, self.exe, "ASIO4ALL v2", rate=44100,
            frames=512, callbacks=200, platform="win32",
            registry_reader=lambda name: CLSID)
        self.evidence = {
            "schema": "125a-physical-asio-native-evidence-v1",
            "nonce": "a" * 48,
            "product_sha256": self.plan["product"]["sha256"],
            "executor_sha256": self.plan["executor"]["sha256"],
            "asio_driver_name": "ASIO4ALL v2",
            "asio_driver_clsid": CLSID,
            "sample_rate": self.rate,
            "buffer_frames": self.block,
            "completed_callbacks": 200,
            "asio_callbacks": 200,
            "deadline_misses": 0, "xruns": 0,
            "process_failures": 0, "error_code": 0
        }
        self.proof = self.root / "native.json"
        self.proof.write_text(json.dumps(self.evidence), encoding="utf-8")

    def make_trace(self, *, silence=False, swap=False, delay=3072):
        frames, rate = self.frames, self.rate
        # same independently regenerated VST3 behavior as 125A QA fixture.
        outputs = [[0.] * frames for _ in range(2)]
        for t in range(frames):
            clock = t / rate
            ml = ((0x6d4e92b5 >> (int(clock / .061) % 32)) & 1)
            mr = ((0xb39a4d27 >> (int(clock / .083) % 32)) & 1)
            outputs[0][t] = .040 * ml * math.sin(2*math.pi*317*clock)
            outputs[1][t] = .055 * mr * math.sin(2*math.pi*557*clock)
        result = array("f")
        for t in range(frames):
            inp_l = 0. if silence or t < delay else outputs[int(swap)][t-delay] * .84
            inp_r = 0. if silence or t < delay else outputs[1-int(swap)][t-delay] * .72
            result.extend([outputs[0][t], outputs[1][t], inp_l, inp_r])
        path = self.root / "trace.f32"
        path.write_bytes(struct.pack("<8sIIII", MAGIC, rate, frames,
                                     self.block, 4) + result.tobytes())
        return path

    def test_realistic_delayed_stereo_PCM_passes_virtual_only(self):
        path = self.make_trace()
        report = verify_pcm(path, self.proof, self.root / "positive")
        self.assertEqual(report["status"], "VIRTUAL_ASIO_PCM_LOOPBACK_PASS",
                         report["faults"])
        self.assertGreater(report["metrics"]["left_correlation"], .8)
        self.assertGreater(report["metrics"]["right_correlation"], .8)
        self.assertTrue(report["pcm_content_verified"])
        self.assertFalse(report["driver_execution_verified"])
        self.assertFalse(report["virtual_loopback_verified"])
        self.assertFalse(report["physical_asio_hardware_verified"])
        self.assertFalse(report["commercial_daw_verified"])
        self.assertFalse(report["release_approved"])

    def test_deliberately_wrong_oscillator_frequency_must_fail(self):
        # Do not mistake a valid return of WRONG source music for a good
        # QA oscillator. Change only original output + its returned input.
        from array import array
        frames, rate, delay = self.frames, self.rate, 3072
        signals = ([], [])
        for n in range(frames):
            t = n / rate
            gates = (((0x6d4e92b5 >> (int(t/.061) % 32)) & 1),
                     ((0xb39a4d27 >> (int(t/.083) % 32)) & 1))
            signals[0].append(.040*gates[0]*math.sin(2*math.pi*911*t))
            signals[1].append(.055*gates[1]*math.sin(2*math.pi*1277*t))
        values = array("f")
        for n in range(frames):
            values.extend((signals[0][n], signals[1][n],
                           signals[0][n-delay]*.84 if n >= delay else 0.,
                           signals[1][n-delay]*.72 if n >= delay else 0.))
        path = self.root / "wrong-source.f32"
        path.write_bytes(struct.pack("<8sIIII", MAGIC, rate, frames,
                                     self.block, 4)+values.tobytes())
        report = verify_pcm(path, self.proof, self.root/"wrong-source-result")
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("source PCM differs", " ".join(report["faults"]))

    def test_fourfold_input_gain_is_rejected(self):
        path = self.make_trace()
        values = array("f")
        raw = path.read_bytes()
        values.frombytes(raw[24:])
        for n in range(self.frames):
            values[4*n+2] *= 4
            values[4*n+3] *= 4
        path.write_bytes(raw[:24]+values.tobytes())
        report = verify_pcm(path, self.proof, self.root/"gain-result")
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("return gain", " ".join(report["faults"]))

    def test_full_wave_rectified_input_cannot_pass_as_transparent_audio(self):
        # Full-wave rectification preserves every input RMS envelope window,
        # thus it defeated the previous unsigned envelope-only oracle.
        path = self.make_trace()
        raw = path.read_bytes()
        values = array("f")
        values.frombytes(raw[24:])
        for n in range(self.frames):
            values[4*n+2] = abs(values[4*n+2])
            values[4*n+3] = abs(values[4*n+3])
        path.write_bytes(raw[:24] + values.tobytes())
        result = verify_pcm(path, self.proof, self.root / "rectified-return")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("DC offset", " ".join(result["faults"]))
        self.assertFalse(result["pcm_content_verified"])
        self.assertFalse(result["driver_execution_verified"])

    def test_inverted_return_polarity_cannot_pass(self):
        # A negative waveform is not equivalent to the actual signed PCM,
        # although its RMS envelope and transfer gain are unchanged.
        for channels in ((2,), (2, 3)):
            with self.subTest(channels=channels):
                path = self.make_trace()
                raw = path.read_bytes()
                values = array("f")
                values.frombytes(raw[24:])
                for n in range(self.frames):
                    for channel in channels:
                        values[4*n + channel] = -values[4*n + channel]
                path.write_bytes(raw[:24] + values.tobytes())
                out = self.root / ("polarity-" + "-".join(map(str, channels)))
                result = verify_pcm(path, self.proof, out)
                self.assertEqual(result["status"], "FAIL", result)
                self.assertIn("signed stereo PCM", " ".join(result["faults"]))
                self.assertFalse(result["driver_execution_verified"])

    def test_between_decimated_samples_polarity_corruption_fails(self):
        # P104: old P103 signed match inspects just n % 32 == 0.
        # Invert the other 31 of 32 captured frames while preserving
        # exact energy, DC~0, every 256-frame RMS envelope and the
        # emitted output reference. The verifier MUST reject it.
        path = self.make_trace()
        raw = path.read_bytes()
        values = array("f")
        values.frombytes(raw[24:])
        delay = 3072
        for n in range(delay, self.frames):
            if (n - delay) % 32 != 0:
                values[4*n + 2] = -values[4*n + 2]
                values[4*n + 3] = -values[4*n + 3]
        path.write_bytes(raw[:24] + values.tobytes())
        result = verify_pcm(path, self.proof, self.root / "interstitial-polarity")
        self.assertEqual(result["status"], "FAIL", result)
        self.assertIn("full-resolution", " ".join(result["faults"]))
        self.assertFalse(result["pcm_content_verified"])

    def test_sample_accurate_common_lag_not_multiple_of_256(self):
        # A valid ASIO return may have non-256-aligned endpoint latency.
        # The signed comparison must not falsely fail such a clean trace.
        path = self.make_trace(delay=3073)
        report = verify_pcm(path, self.proof, self.root / "odd-sample-lag")
        self.assertEqual(report["status"], "VIRTUAL_ASIO_PCM_LOOPBACK_PASS",
                         report["faults"])
        self.assertEqual(report["metrics"]["signed_pcm_common_lag_frames"], 3073)
        self.assertGreater(report["metrics"]["signed_pcm_l"], 0.99)
        self.assertGreater(report["metrics"]["signed_pcm_r"], 0.99)
        self.assertFalse(report["driver_execution_verified"])

    def test_zero_frame_delay_is_measured_as_zero(self):
        path = self.make_trace(delay=0)
        report = verify_pcm(path, self.proof, self.root/"zero-delay")
        self.assertEqual(report["status"], "VIRTUAL_ASIO_PCM_LOOPBACK_PASS",
                         report["faults"])
        self.assertEqual(report["metrics"]["latency_frames_estimate"], 0)

    def test_silence_is_not_a_loopback(self):
        path = self.make_trace(silence=True)
        report = verify_pcm(path, self.proof, self.root / "silent")
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["virtual_loopback_verified"])

    def test_swapped_stereo_channels_are_rejected(self):
        path = self.make_trace(swap=True)
        report = verify_pcm(path, self.proof, self.root / "swapped")
        self.assertEqual(report["status"], "FAIL")

    def test_truncated_capture_is_not_a_driver_pass(self):
        path = self.make_trace()
        path.write_bytes(path.read_bytes()[:-200])
        with self.assertRaises(ValueError):
            parse_native_trace(path)

    def test_missing_capture_cannot_pass(self):
        report = verify_pcm(self.root / "missing.f32", self.proof, self.root/"missing")
        self.assertEqual(report["status"], "FAIL")

    def test_nonce_and_hash_identity_required_by_driver_orchestrator(self):
        report = execute(
            self.plan, self.root/"no-permission", platform="win32",
            acknowledge=False, endpoint_reader=lambda: {
                "playback": ["CABLE Input (VB-Audio)"],
                "recording": ["CABLE Output (VB-Audio)"]},
            registry_reader=lambda name: CLSID)
        self.assertEqual(report["status"], "NOT_RUN")
        self.assertFalse(report["physical_asio_hardware_verified"])

    def test_wrong_sample_rate_in_native_evidence_is_rejected(self):
        path = self.make_trace()
        e = dict(self.evidence, sample_rate=48000)
        self.proof.write_text(json.dumps(e), encoding="utf-8")
        report = verify_pcm(path, self.proof, self.root/"wrong-rate")
        self.assertEqual(report["status"], "FAIL")

    def test_wrong_callback_count_rejected(self):
        path = self.make_trace()
        e = dict(self.evidence, completed_callbacks=250, asio_callbacks=250)
        self.proof.write_text(json.dumps(e), encoding="utf-8")
        report = verify_pcm(path, self.proof, self.root/"wrong-count")
        self.assertEqual(report["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
