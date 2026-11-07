#!/usr/bin/env python3
"""P90 positive/negative PCM comparisons and forged ASIO evidence rejection."""
import copy
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from run_external_daw_capture_check import run, digest, SCHEMA


def save_wav(path, values, sample_rate=44100, channels=1):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        interleaved = []
        for sample in values:
            value = max(-32000, min(32000, int(sample*32768)))
            interleaved.extend([value]*channels)
        handle.writeframes(struct.pack("<%dh" % len(interleaved), *interleaved))


class ExternalCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dll = self.root / "Test.vst3"
        self.dll.write_bytes(b"source defined native fixture binary")
        self.ref = self.root / "reference.wav"
        self.recording = self.root / "recorded.wav"
        # deterministic broadband signal, aperiodic so delay is identifiable
        seed = 1234567
        self.samples = []
        previous = 0.0
        for _ in range(22050):
            seed = (1103515245*seed+12345) % (2**31)
            raw = ((seed % 65536)/32768.0-1.0)*.3
            previous = .7*previous + .3*raw
            self.samples.append(previous)
        save_wav(self.ref, self.samples)
        save_wav(self.recording, [0.0]*21 + [x*.88 for x in self.samples])
        self.contract = {
            "schema": SCHEMA,
            "plugin": {"binary":str(self.dll), "sha256":digest(self.dll)},
            "session": {
                "daw_name": "Offline CI test host (NOT real DAW)",
                "daw_version": "fixture",
                "asio_driver": "Declared-only mock metadata",
                "audio_interface": "No physical interface",
                "rate": 44100, "buffer_size": 128,
                "recorded_at_utc": "2026-11-07T14:00:00Z"
            },
            "reference": {"wav":str(self.ref), "sha256":digest(self.ref)},
            "capture": {"wav":str(self.recording), "sha256":digest(self.recording)},
            "oracle": {"min_correlation": .98, "max_lag_frames": 32}
        }

    def fresh(self):
        self.contract["capture"]["sha256"] = digest(self.recording)

    def test_good_offset_amplitude_variance_validates_pcm_but_not_asio(self):
        observed=run(self.contract, self.root/"good")
        self.assertEqual(observed["status"], "AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED")
        self.assertGreaterEqual(observed["comparison"]["correlation"], .98)
        self.assertEqual(observed["comparison"]["lag_frames"], 21)
        self.assertFalse(observed["hardware_asio_verified"])
        self.assertFalse(observed["daw_session_verified"])
        self.assertFalse(observed["release_approved"])

    def test_silence_is_never_valid_evidence(self):
        save_wav(self.recording, [0.0]*22050)
        self.fresh()
        result=run(self.contract, self.root/"silence")
        self.assertEqual(result["status"],"FAIL")

    def test_unrelated_non_silent_pcm_fails(self):
        save_wav(self.recording, list(reversed(self.samples)))
        self.fresh()
        result=run(self.contract,self.root/"wrong")
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(result["comparison"]["matches_reference"])

    def test_clipping_is_rejected(self):
        save_wav(self.recording,[.999999]*22050)
        self.fresh()
        result=run(self.contract,self.root/"clip")
        self.assertEqual(result["status"],"FAIL")

    def test_checksum_identity_is_pinned(self):
        self.contract["capture"]["sha256"]="0"*64
        result=run(self.contract,self.root/"forged")
        self.assertEqual(result["status"],"FAIL")
        self.assertTrue(any("SHA256" in fault for fault in result["faults"]))

    def test_fake_hardware_metadata_cannot_upgrade_provenance(self):
        self.contract["session"]["asio_driver"] = "Super Verified ASIO Driver"
        self.contract["session"]["daw_name"] = "Verified Real DAW"
        result=run(self.contract,self.root/"claim")
        self.assertEqual(result["status"],"AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED")
        self.assertFalse(result["hardware_asio_verified"])
        self.assertFalse(result["daw_session_verified"])

    def test_mismatched_rate_rejected(self):
        save_wav(self.recording,self.samples,sample_rate=48000)
        self.fresh()
        result=run(self.contract,self.root/"rate")
        self.assertEqual(result["status"],"FAIL")

    def test_same_reference_as_capture_is_not_independent(self):
        self.contract["capture"] = dict(self.contract["reference"])
        with self.assertRaises(ValueError):
            run(self.contract,self.root/"same")

    def test_missing_or_forged_manifest_fields_rejected(self):
        for key in ("reference", "capture", "session", "oracle"):
            with self.subTest(key=key):
                c=copy.deepcopy(self.contract)
                c.pop(key)
                with self.assertRaises(ValueError):
                    run(c,self.root/("missing_"+key))


if __name__ == "__main__":
    unittest.main()
