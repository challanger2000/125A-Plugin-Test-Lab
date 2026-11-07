#!/usr/bin/env python3
"""P76 universal independent PCM WAV / SMF MIDI artifact oracle tests."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from run_export_artifact_oracle import validate, verify, parse_midi, SCHEMA
from run_product_test_plan import execute
from test_product_test_plan import make_plan


def sha(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def make_midi(path, *, note=36):
    track0 = bytes.fromhex("00 ff 51 03 07 a1 20 00 ff 2f 00")
    track1 = b"\x00\x99" + bytes([note,100]) + bytes.fromhex(
        "83 60 89") + bytes([note,0]) + bytes.fromhex("00 ff 2f 00")
    data=(b"MThd"+struct.pack(">IHHH",6,1,2,960)
          +b"MTrk"+struct.pack(">I",len(track0))+track0
          +b"MTrk"+struct.pack(">I",len(track1))+track1)
    Path(path).write_bytes(data)
    return data


def contract(root, module_sha):
    wav = root/"export.wav"
    mid = root/"export.mid"
    with wave.open(str(wav),"wb") as f:
        f.setnchannels(2)
        f.setframerate(48000)
        f.setsampwidth(3)
        f.writeframes(b"\x00\x00\x00" * 2 * 960)
    make_midi(mid)
    return {
        "schema": SCHEMA, "module_sha256": module_sha,
        "outputs": [
            {"id":"rendered_wav","path":str(wav),"kind":"wav",
             "expected_sha256":sha(wav),
             "format_expectations":{"channels":2,"sample_rate":48000,
                                    "sample_width_bytes":3,"frames":960}},
            {"id":"exported_midi","path":str(mid),"kind":"midi",
             "expected_sha256":sha(mid),
             "format_expectations":{
                 "format":1,"tracks":2,"ppq":960,
                 "note_ons":[{"track":1,"tick":0,"channel":9,"note":36,"velocity":100}]}}
        ]
    }


class GenericArtifactOracleTests(unittest.TestCase):
    def test_exact_pcm_and_midi_export_pass_only_expected_reference(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            expectation=contract(root,"a"*64)
            self.assertEqual(len(validate(expectation,"a"*64)),2)
            outcome=verify(expectation,root/"evidence",module_sha="a"*64)
            self.assertEqual(outcome["status"],"ARTIFACT_PASS")
            self.assertEqual(outcome["verified_actions"],2)
            self.assertEqual([o["status"] for o in outcome["outputs"]],["PASS","PASS"])
            self.assertFalse(outcome["release_approved"])

    def test_one_incorrect_wav_sample_blocks_entire_artifact_test(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            expectation=contract(root,"a"*64)
            wav=Path(expectation["outputs"][0]["path"])
            data=bytearray(wav.read_bytes())
            data[-1]^=0xff
            wav.write_bytes(data)
            failed=verify(expectation,root/"wav-defect",module_sha="a"*64)
            self.assertEqual(failed["status"],"FAIL")
            self.assertEqual(failed["verified_actions"],1)
            self.assertEqual(failed["outputs"][0]["status"],"FAIL")
            self.assertEqual(failed["outputs"][1]["status"],"PASS")

    def test_midi_wrong_note_timing_or_corrupt_data_never_pass(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            expectation=contract(root,"a"*64)
            actual=Path(expectation["outputs"][1]["path"])
            make_midi(actual,note=38)
            # Update byte oracle to isolate the separate semantic timing note oracle.
            expectation["outputs"][1]["expected_sha256"]=sha(actual)
            result=verify(expectation,root/"wrong-note",module_sha="a"*64)
            self.assertEqual(result["status"],"FAIL")
            self.assertEqual(result["verified_actions"],1)
            with self.assertRaises(ValueError):
                parse_midi(actual.read_bytes()[:-1])
            with self.assertRaises(ValueError):
                parse_midi(b"MThd"+b"\x00"*12)

    def test_preflight_rejects_unbounded_or_unknown_contract_without_touching_files(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            base=contract(root,"a"*64)
            variants=[]
            v=copy.deepcopy(base)
            v["module_sha256"]="b"*64
            variants.append(v)
            v=copy.deepcopy(base)
            v["outputs"][1]["id"]="rendered_wav"
            variants.append(v)
            v=copy.deepcopy(base)
            v["outputs"][0]["kind"]="exe"
            variants.append(v)
            v=copy.deepcopy(base)
            v["outputs"][0]["path"]="relative-output.wav"
            variants.append(v)
            v=copy.deepcopy(base)
            v["outputs"][1]["format_expectations"]["note_ons"][0]["velocity"]=0
            variants.append(v)
            v=copy.deepcopy(base)
            v["outputs"][0]["format_expectations"]["channels"]=0
            variants.append(v)
            v=copy.deepcopy(base)
            v["outputs"][0]["unknown"]="shell"
            variants.append(v)
            for bad in variants:
                with self.subTest(bad=bad),self.assertRaises(ValueError):
                    validate(bad,"a"*64)

    def test_generic_p65_case_with_independent_p67_coverage_gate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            plan,module,host=make_plan(root)
            artifact=contract(root,plan["product"]["sha256"])
            plan["cases"]=[{"id":"export_validation","kind":"export_artifact",
                            "contract":artifact}]
            matrix={
                "schema":"125a-product-feature-matrix-v1",
                "product_id":plan["product"]["id"],
                "module_sha256":plan["product"]["sha256"],
                "features":[
                    {"id":"wav_export","title":"Independent WAV export byte and frame oracle",
                     "criticality":"required","case_ids":["export_validation"],
                     "waiver":None},
                    {"id":"midi_export","title":"Independent SMF export note events and tempo",
                     "criticality":"required","case_ids":["export_validation"],
                     "waiver":None}
                ]
            }
            report=execute(plan,root/"approved-exports",coverage_matrix=matrix)
            self.assertEqual(report["status"],"CONTRACT_PASS")
            self.assertEqual(report["required_feature_coverage"],
                             "REQUIRED_COVERAGE_COMPLETE")
            self.assertFalse(report["release_approved"])
            # The *same plan* immediately detects a single corrupt WAV byte.
            wav=Path(artifact["outputs"][0]["path"])
            data=bytearray(wav.read_bytes())
            data[-2]^=0x10
            wav.write_bytes(data)
            failed=execute(plan,root/"reject-exports",coverage_matrix=matrix)
            self.assertEqual(failed["status"],"FAIL")
            self.assertEqual(failed["failed_cases"],1)
            self.assertEqual(failed["required_feature_coverage"],
                             "REQUIRED_COVERAGE_INCOMPLETE")


if __name__=="__main__":
    unittest.main()
