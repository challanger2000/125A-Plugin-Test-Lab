#!/usr/bin/env python3
"""P92 regression: explicit MIDI/no-note REAPER plans and independent PCM oracle."""
import copy
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from run_reaper_daw_qa import verify_plan, generate_script, check_pcm, digest, SCHEMA


class ReaperMidiRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = self.root / "reaper.exe"
        self.dll = self.root / "test.vst3"
        self.exe.write_bytes(b"fixture executable")
        self.dll.write_bytes(b"fixture module")
        self.plan = {
            "schema": SCHEMA,
            "reaper": {"exe": str(self.exe), "sha256": digest(self.exe)},
            "plugin": {"module": str(self.dll), "sha256": digest(self.dll),
                       "reaper_fx_name": "VST3: 125A QA REAPER MIDI Audible"},
            "test": {"sample_rate": 44100, "tempo_bpm": 120,
                     "note": 36, "velocity": 102, "seconds": 2,
                     "expect_audio": True, "minimum_rms": .01,
                     "insert_note": True}
        }

    def write_pcm(self, name, audible):
        path = self.root / name
        with wave.open(str(path), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(44100)
            data = []
            for i in range(88200):
                v = int(6000 * ((i % 101) / 50.5 - 1)) if audible else 0
                data += [v, v]
            f.writeframes(struct.pack("<%dh" % len(data), *data))
        return path

    def test_note_and_no_note_plans_generate_distinct_lua(self):
        verify_plan(self.plan)
        script = generate_script(
            Path(__file__).with_name("reaper_qa_driver.lua"),
            self.plan, self.root, self.root/"status", self.root/"project.RPP", "setup")
        self.assertIn("local TEST_INSERT_NOTE = true", script.read_text())
        negative = copy.deepcopy(self.plan)
        negative["test"].update(insert_note=False, expect_audio=False,
                                expect_silence=True)
        verify_plan(negative)
        script = generate_script(
            Path(__file__).with_name("reaper_qa_driver.lua"),
            negative, self.root, self.root/"status", self.root/"project.RPP", "setup")
        self.assertIn("local TEST_INSERT_NOTE = false", script.read_text())

    def test_real_pcm_oracle_rejects_false_tone_or_false_silence(self):
        audible = self.write_pcm("audible.wav", True)
        silent = self.write_pcm("silent.wav", False)
        self.assertTrue(check_pcm(audible, 44100, 2, .01, True)["audible_in_render"])
        self.assertFalse(check_pcm(silent, 44100, 2, .01, False, True)["audible_in_render"])
        with self.assertRaises(ValueError):
            check_pcm(silent, 44100, 2, .01, True)
        with self.assertRaises(ValueError):
            check_pcm(audible, 44100, 2, .01, False, True)

    def test_invalid_positive_without_note_and_double_oracle_blocked(self):
        wrong = copy.deepcopy(self.plan)
        wrong["test"].update(insert_note=False)
        with self.assertRaises(ValueError):
            verify_plan(wrong)
        wrong = copy.deepcopy(self.plan)
        wrong["test"].update(expect_silence=True)
        with self.assertRaises(ValueError):
            verify_plan(wrong)
        wrong = copy.deepcopy(self.plan)
        wrong["test"].update(insert_note="false")
        with self.assertRaises(ValueError):
            verify_plan(wrong)


if __name__ == "__main__":
    unittest.main()
