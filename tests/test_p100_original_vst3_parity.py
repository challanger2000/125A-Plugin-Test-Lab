"""P100 zero-proprietary-data positive and mutation negatives."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave

MODULE=Path(__file__).with_name("run_p100_original_vst3_parity.py")
spec=importlib.util.spec_from_file_location("p100_reference",MODULE)
p100=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=p100
spec.loader.exec_module(p100)

def wav(path,values):
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<hh",*pair) for pair in values))

class OriginalVst3P100Regression(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.original=self.root/"original.wav"
        self.native=self.root/"native.wav"
        self.pcm=[(315 if i%3 else -319,412 if i%2 else -415)
                  for i in range(480)]
        wav(self.original,self.pcm)
        wav(self.native,[(0,0)]*5+self.pcm)
        self.window={"original_start_frame":0,"native_start_frame":5,"frames":480}
        self.notes=self.root/"notes.txt"
        self.ports=self.root/"port.txt"
        self.notes.write_text("# C4_ON\n100 E22 0060\n100 A20 00FF\n"
                              "# C4_OFF\n200 E22 00A0\n200 A20 8000\n"
                              "# D4_ON\n300 E22 0063\n300 A20 00FF\n"
                              "# D4_OFF\n400 E22 00A3\n400 A20 8000\n")
        self.events=["# INDEPENDENT_NATIVE_P002_PORT_WRITES_ONLY",
                     "# CLOCK=HOST_44100_SAMPLE_FRAMES; ORIGIN=ACTIVATION",
                     "# SOURCE_ORIGINAL_WIN95_PROVENANCE=SEPARATELY_REQUIRED",
                     "5 E22 0060","5 A20 00FF",
                     "25 E22 00A0","25 A20 8000",
                     "45 E22 0063","45 A20 00FF",
                     "65 E22 00A3","65 A20 8000"]
        self.ports.write_text("\n".join(self.events)+"\n")
    def tearDown(self):
        self.tmp.cleanup()
    def test_equal_original_and_independent_pcm(self):
        r=p100.compare_pcm(self.original,self.native,self.window)
        self.assertTrue(r["equal"])
        self.assertEqual(r["compared_channel_samples"],960)
    def test_one_sample_mutation_rejected_at_exact_frame_and_channel(self):
        changed=self.pcm[:]
        changed[30]=(changed[30][0],changed[30][1]+1)
        wav(self.native,[(0,0)]*5+changed)
        r=p100.compare_pcm(self.original,self.native,self.window)
        self.assertEqual(r["mismatched_channel_samples"],1)
        self.assertEqual(r["first_difference"]["relative_frame"],30)
        self.assertEqual(r["first_difference"]["channel"],1)
    def test_auto_alignment_forbidden(self):
        wrong=dict(self.window,native_start_frame=6,frames=479)
        self.assertFalse(p100.compare_pcm(self.original,self.native,wrong)["equal"])
    def test_nonzero_original_emu8000_chorus_send_disproves_dry(self):
        source={
            "C4_ON":[(100,0xe22,0x20),(100,0x622,0x0000),
                     (100,0xe22,0xe0),(100,0x622,0x7f23)],
            "D4_ON":[(300,0xe22,0x26),(300,0x622,0x0000),
                     (300,0xe22,0xe6),(300,0x622,0x7f23)]}
        r=p100.source_chip_effect_sends(source)
        self.assertFalse(r["internal_emu8000_chorus_reverb_send_zero"])
        self.assertFalse(r["pre_card_audio_is_necessarily_fx_free"])
        self.assertEqual(r["per_note"]["C4_ON"]["chorus"][0]["send"],127)
    def test_true_zero_send_proved_only_with_both_buses_observed(self):
        source={
            "C4_ON":[(100,0xe22,0x20),(100,0x622,0),
                     (100,0xe22,0xe0),(100,0x622,0x23)],
            "D4_ON":[(300,0xe22,0x26),(300,0x622,0),
                     (300,0xe22,0xe6),(300,0x622,0x23)]}
        r=p100.source_chip_effect_sends(source)
        self.assertTrue(r["internal_emu8000_chorus_reverb_send_zero"])
    def test_missing_bus_does_not_pass_zero_send(self):
        r=p100.source_chip_effect_sends({"C4_ON":[],"D4_ON":[]})
        self.assertIsNone(r["internal_emu8000_chorus_reverb_send_zero"])
        self.assertFalse(r["pre_card_audio_is_necessarily_fx_free"])
    def test_original_and_native_port_positive(self):
        self.assertTrue(p100.compare_ports(self.notes,self.ports,[5,25,45,65],100)["equal"])
    def test_register_value_mutation_rejected(self):
        self.ports.write_text("\n".join(
            s.replace("45 A20 00FF","45 A20 00FE") for s in self.events)+"\n")
        r=p100.compare_ports(self.notes,self.ports,[5,25,45,65],100)
        self.assertFalse(r["equal"])
        self.assertEqual(r["groups"][2]["first_difference"]["field"],"value")
        self.assertEqual(r["groups"][2]["first_difference"]["native_absolute_frame"],45)
    def test_missing_original_out_rejected(self):
        self.ports.write_text("\n".join(x for x in self.events if x!="45 A20 00FF")+"\n")
        self.assertFalse(p100.compare_ports(self.notes,self.ports,[5,25,45,65],100)["equal"])
    def test_fake_native_header_rejected(self):
        self.ports.write_text("5 E22 0060\n")
        with self.assertRaisesRegex(ValueError,"header"):
            p100.compare_ports(self.notes,self.ports,[5,25,45,65],100)
    def test_unexpected_native_metadata_is_rejected(self):
        self.ports.write_text("\n".join(self.events[:3]+
            ["# UNVERIFIED_DIAGNOSTIC_IS_NOT_A_PORT"]+self.events[3:])+"\n")
        with self.assertRaisesRegex(ValueError,"malformed"):
            p100.compare_ports(self.notes,self.ports,[5,25,45,65],100)
    def test_real_recording_crlf_is_accepted(self):
        self.ports.write_bytes(("\r\n".join(self.events)+"\r\n").encode("ascii"))
        self.assertTrue(p100.compare_ports(
            self.notes,self.ports,[5,25,45,65],100)["equal"])
    def test_note_origin_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,"timing"):
            p100.compare_ports(self.notes,self.ports,[5,25,45,65],101)
    def test_nonzero_source_and_native_required(self):
        wav(self.native,[(0,0)]*(5+480))
        with self.assertRaisesRegex(ValueError,"silent"):
            p100.compare_pcm(self.original,self.native,self.window)
    def test_prelude_opt_in_must_be_boolean(self):
        contract=self.root/"bad-prelude.json"
        contract.write_text('{"schema":"125A-P100-ORIGINAL-VST3-PARITY-1",'
                            '"sample_rate":44100,"replay_original_boot_prelude":"YES"}')
        with self.assertRaisesRegex(ValueError,"BOOLEAN"):
            p100.source(contract)
    def test_owner_prelude_clock_must_be_exact(self):
        contract=self.root/"wrong-prelude-clock.json"
        contract.write_text('{"schema":"125A-P100-ORIGINAL-VST3-PARITY-1",'
                            '"sample_rate":44100,"replay_original_boot_prelude":true,'
                            '"midi_sample_frames":[138,17837,46906,65088],'
                            '"native_total_frames":97000}')
        with self.assertRaisesRegex(ValueError,"frame 137"):
            p100.source(contract)
    def test_stderr_is_not_an_exception_or_a_pass(self):
        result=p100.run_host(Path(sys.executable),
            ["-c","import sys;sys.stderr.write('P002 native error\\n');sys.exit(17)"],
            self.root,"stderr-case",10)
        self.assertEqual(result["exit_code"],17)
        self.assertIn("P002 native error",
                      (self.root/"stderr-case.stderr.txt").read_text())
    def test_no_fake_success_with_missing_source_contract(self):
        contract=self.root/"invalid.json"
        contract.write_text('{"schema":"125A-P100-ORIGINAL-VST3-PARITY-1"}')
        res=p100.execute(contract,self.root/"result")
        self.assertEqual(res["status"],"INVALID_EVIDENCE_OR_TEST_CONFIGURATION")
        self.assertFalse(res["release_approved"])
        self.assertTrue((self.root/"result"/"P100-RESULT.json").exists())

if __name__=="__main__":unittest.main()
