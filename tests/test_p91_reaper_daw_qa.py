#!/usr/bin/env python3
"""P91 strict REAPER DAW driver regressions; mocked process is NOT real REAPER."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from run_reaper_daw_qa import (
    SCHEMA, digest, confined_lua, verify_plan, execute, check_pcm
)


def good_pcm(path, frames=88200):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        pattern = [int(7000 * ((i % 200) / 100.0 - 1.0))
                   for i in range(frames)]
        values = [sample for v in pattern for sample in (v, v)]
        wav.writeframes(struct.pack("<%dh" % len(values), *values))


class ReaperQATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reaper = self.root / "reaper.exe"
        self.module = self.root / "Test.vst3"
        self.reaper.write_bytes(b"MOCK test binary, NOT real REAPER")
        self.module.write_bytes(b"MOCK test module, NOT real VST3")
        self.plan = {
            "schema": SCHEMA,
            "reaper": {"exe": str(self.reaper), "sha256": digest(self.reaper)},
            "plugin": {"module": str(self.module),
                       "sha256": digest(self.module),
                       "reaper_fx_name": "VST3: 125A QA Synth (125A)"},
            "test": {"sample_rate": 44100, "tempo_bpm": 120,
                     "note": 60, "velocity": 100, "seconds": 2,
                     "expect_audio": True, "minimum_rms": .01}
        }
        self.test_template = Path(__file__).with_name("reaper_qa_driver.lua")

    def test_exact_binary_and_fx_name_required(self):
        verify_plan(self.plan)
        for key, value in (("sha256","0"*64),):
            altered=copy.deepcopy(self.plan)
            altered["reaper"][key]=value
            with self.assertRaises(ValueError):
                verify_plan(altered)
        altered=copy.deepcopy(self.plan)
        altered["plugin"]["reaper_fx_name"] = "VST2: wrong"
        with self.assertRaises(ValueError):
            verify_plan(altered)
        altered=copy.deepcopy(self.plan)
        altered["test"]["note"] = 999
        with self.assertRaises(ValueError):
            verify_plan(altered)

    def test_lua_sanitizes_bracket_escape_and_rejects_multiline(self):
        self.assertEqual(confined_lua("a]b"), "[[a]b]]")
        self.assertEqual(confined_lua("a]]b"), "[=[a]]b]=]")
        with self.assertRaises(ValueError):
            confined_lua("bad\nsource")

    def test_real_adapter_pipeline_protocol_without_pretending_live_daw(self):
        issued=[]
        def fake_process(command, status_file, timeout):
            issued.append((command,status_file,timeout))
            if status_file is None:
                good_pcm(self.root/"pass"/"125A_Reaper_Render.wav")
                return {"exit_code":0}
            if status_file.name == "setup.status":
                (self.root/"pass"/"125A_Reaper_Project.RPP").write_text(
                    "<REAPER_PROJECT 0.1\n>",encoding="utf-8")
                return {"phase":"setup","note_count":"1",
                        "fx_name":"VST3: 125A QA Synth","reaper_version":"7.x"}
            return {"phase":"reload","note_count":"1",
                    "fx_name":"VST3: 125A QA Synth",
                    "pitch":"60","velocity":"100"}
        result=execute(self.plan,self.root/"pass",
                       script_template=self.test_template,
                       process_runner=fake_process)
        self.assertEqual(result["status"],"REAL_REAPER_DAW_PIPELINE_PASS")
        self.assertEqual(len(issued),3)
        self.assertEqual(issued[0][0][1:4],["-newinst","-nosplash","-new"])
        self.assertEqual(issued[1][0][1],"-newinst")
        self.assertEqual(issued[2][0][1:3],["-nosplash","-renderproject"])
        self.assertEqual(result["render"]["channels"],2)
        self.assertFalse(result["release_approved"])
        self.assertEqual(result["physical_asio_hardware"],"NOT RUN")
        # Crucial: this is an adapter fixture ONLY, not evidence of a
        # genuine REAPER process on the Windows test runner.
        self.assertEqual(self.reaper.read_bytes(),
                         b"MOCK test binary, NOT real REAPER")

    def test_missing_render_or_fake_fx_rejected(self):
        def fake_process(command, status_file, timeout):
            if status_file and status_file.name=="setup.status":
                (self.root/"fail"/"125A_Reaper_Project.RPP").write_text("RPP")
                return {"phase":"setup","note_count":"1",
                        "fx_name":"Simulated","reaper_version":"mock"}
            if status_file:
                return {"phase":"reload","note_count":"1",
                        "fx_name":"Simulated","pitch":"60","velocity":"100"}
            return {"exit_code":0}
        result=execute(self.plan,self.root/"fail",process_runner=fake_process)
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(result["rendered_by_reaper_process"])

    def test_wrong_reloaded_note_rejected_before_render(self):
        issued=[]
        def fake(command,status_file,timeout):
            issued.append(command)
            if status_file.name=="setup.status":
                (self.root/"badreload"/"125A_Reaper_Project.RPP").write_text("RPP")
                return {"phase":"setup","note_count":"1",
                        "fx_name":"VST3: QA","reaper_version":"7.x"}
            return {"phase":"reload","note_count":"1",
                    "fx_name":"VST3: QA","pitch":"70","velocity":"100"}
        result=execute(self.plan,self.root/"badreload",process_runner=fake)
        self.assertEqual(result["status"],"FAIL")
        self.assertEqual(len(issued),2)

    def test_nonempty_evidence_dir_rejected(self):
        out=self.root/"occupied"
        out.mkdir()
        (out/"old.txt").write_text("stale")
        with self.assertRaises(ValueError):
            execute(self.plan,out)

    def test_pcm_needs_genuine_nonsilent_output(self):
        path=self.root/"valid.wav"
        good_pcm(path)
        info=check_pcm(path,44100,2,.01,True)
        self.assertGreater(info["rms"],.01)
        with self.assertRaises(ValueError):
            check_pcm(path,48000,2,.01,True)
        with self.assertRaises(ValueError):
            check_pcm(path,44100,3,.01,True)


if __name__=="__main__":
    unittest.main()
