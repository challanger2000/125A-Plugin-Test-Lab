#!/usr/bin/env python3
"""P220: AWE-specific real release-gate integration in P89 Test Lab summary.

Technical PASS must never silently hide an absent 77-preset original
Creative Win95 sound oracle. Non-AWE product checks remain unchanged.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run_unified_qa_gaps import review,awe77_sound_report

class SoundReleaseIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.batch=self.root/"batch"
        self.batch.mkdir()
        self.batch_report=dict(schema="125a-vst3-batch-report-v1",
          status="BATCH_TECHNICAL_PASS",declared_plugins=1,passed_plugins=1,
          failed_plugins=0,release_approved=False,
          plugins=[{"id":"awe","verified_module_sha256":"c"*64,
              "status":"PASS","verified_stage":"TECHNICAL_BASELINE_PASS",
              "required_feature_coverage":"NOT DECLARED","faults":[]}])
        self.child=dict(schema="125a-universal-vst3-qa-pipeline-v1",
          verified_module_sha256="c"*64,status="TECHNICAL_BASELINE_PASS",
          discovery="PASS",approved_product_cases="NOT DECLARED",
          required_feature_coverage="NOT DECLARED",required_feature_gaps=[],
          unknown_gui_exploration="NOT RUN",real_asio_hardware="NOT RUN",
          commercial_daw_session="NOT RUN",release_approved=False)
        d=self.batch/"01-awe";d.mkdir()
        (self.batch/"BATCH-QA-REPORT.json").write_text(json.dumps(self.batch_report))
        (d/"UNIVERSAL-QA-RESULT.json").write_text(json.dumps(self.child))

    def test_actual_technical_pass_does_not_certify_original_bank_sound(self):
        result=review(self.batch,self.root/"awe-no-sound")
        self.assertEqual(result["status"],"RECONCILED_REPORT_COMPLETE")
        self.assertEqual(result["passed_plugins"],1)
        self.assertEqual(result["awe77_required_product_count"],1)
        self.assertEqual(result["awe77_sonic_gate_blocked_or_failed"],1)
        self.assertEqual(result["plugins"][0]["required_awe_77_sonic_gate"],"BLOCKED")
        self.assertIn("REQUIRED_AWE_SF2_77_SONIC_BLOCKED",
                      result["plugins"][0]["unresolved_acceptance_gaps"])
        self.assertFalse(result["all_products_release_approved"])

    def test_explicit_release_run_exits_nonzero_despite_technical_pass(self):
        script=Path(__file__).with_name("run_unified_qa_gaps.py")
        cmd=[sys.executable,str(script),"--batch",str(self.batch),
             "--out",str(self.root/"release"),"--require-awe77-for","awe"]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=25)
        self.assertNotEqual(r.returncode,0,r.stdout)
        evidence=json.loads((self.root/"release"/"UNIFIED-QA-GAPS.json").read_text())
        self.assertEqual(evidence["awe77_sonic_gate_blocked_or_failed"],1)
        self.assertEqual(evidence["plugins"][0]["required_awe_77_sonic_gate"],"BLOCKED")

    def test_forged_meta_green_cannot_approve_77_missing_sound_files(self):
        bad={"schema":"125a-testlab-awe-sf2-77-sonic-gate-v1",
             "audio_comparison_version":"p220-stereo-v2",
             "private_sf2_sha256":"d5b99ec38fddf59f53f66b90921e170d207bf3bbd73960f6e4175c39ef68349b",
             "status":"PASS","release_approved":False,"passed_presets":77,
             "passed_scenarios":154,"failed_scenarios":0,
             "vst3_module_sha256":"c"*64,
             "original_creative_full_bank_capture_verified":True,
             "actual_windows_vst3_audio_captured":True,
             "presets":[]}
        report=self.root/"forged.json";report.write_text(json.dumps(bad))
        r=review(self.batch,self.root/"bad",awe77_reports={"awe":str(report)})
        self.assertEqual(r["plugins"][0]["required_awe_77_sonic_gate"],"FAIL")
        bad["vst3_module_sha256"]="d"*64
        report.write_text(json.dumps(bad))
        r=review(self.batch,self.root/"bad-sha",awe77_reports={"awe":str(report)})
        self.assertEqual(r["plugins"][0]["required_awe_77_sonic_gate"],"BLOCKED")

    def test_legacy_mono_reports_remain_blocked_even_with_positive_counters(self):
        legacy={"schema":"125a-testlab-awe-sf2-77-sonic-gate-v1",
             "private_sf2_sha256":"d5b99ec38fddf59f53f66b90921e170d207bf3bbd73960f6e4175c39ef68349b",
             "status":"PASS","release_approved":False,"passed_presets":77,
             "passed_scenarios":154,"failed_scenarios":0,
             "vst3_module_sha256":"c"*64,
             "original_creative_full_bank_capture_verified":True,
             "actual_windows_vst3_audio_captured":True}
        self.assertEqual(awe77_sound_report(legacy,"c"*64),"BLOCKED")

    def test_unrelated_plugin_remains_generic_technical_check(self):
        x=copy.deepcopy(self.batch_report)
        x["plugins"][0]["id"]="other"
        (self.batch/"BATCH-QA-REPORT.json").write_text(json.dumps(x))
        (self.batch/"01-awe").rename(self.batch/"01-other")
        r=review(self.batch,self.root/"other")
        self.assertEqual(r["awe77_required_product_count"],0)
        self.assertEqual(r["awe77_sonic_gate_blocked_or_failed"],0)
        self.assertEqual(r["plugins"][0]["required_awe_77_sonic_gate"],"NOT APPLICABLE")
        self.assertEqual(r["status"],"RECONCILED_REPORT_COMPLETE")

    def test_complete_cached_stereo_screen_without_dry_events_is_blocked(self):
        # Deliberately constructed REPORT-PARSER fixture, not capture proof.
        # Unlike the old empty-list mutant, this passes every old stereo-v2
        # field check and must still be stopped by the new mandatory dry gate.
        from p220_awe_sf2_sound_gate import BANK_SHA,PROGRAMS,COMPARISON_VERSION
        case={"status":"PASS","audio_comparison_version":COMPARISON_VERSION,
              "channel_results":[{"channel":i,"status":"PASS"} for i in (1,2)],
              "stereo_comparison":{"status":"PASS","signed_pcm":{"status":"PASS"}}}
        gates={k:{"status":"PASS"} for k in ("amplitude_adsr","filter_sweeps","loop_seams",
                "dry_wet_reverb_chorus","program_recall_and_reload")}
        cached={"schema":"125a-testlab-awe-sf2-77-sonic-gate-v1",
                "audio_comparison_version":COMPARISON_VERSION,"status":"PASS",
                "private_sf2_sha256":BANK_SHA,"vst3_module_sha256":"c"*64,
                "original_creative_full_bank_capture_verified":True,"actual_windows_vst3_audio_captured":True,
                "passed_presets":77,"passed_scenarios":154,"failed_scenarios":0,"release_approved":False,
                "presets":[{"program":p,"status":"PASS","scenario_results":[copy.deepcopy(case),copy.deepcopy(case)],
                            "detail_gates":copy.deepcopy(gates)} for p in PROGRAMS]}
        self.assertEqual(awe77_sound_report(cached,"c"*64),"BLOCKED")
        cached["sample_exact_dry"]={"status":"PASS"}  # No raw/numeric/event evidence.
        self.assertEqual(awe77_sound_report(cached,"c"*64),"BLOCKED")

    def test_full_gate_routes_dry_through_event_windows_without_legacy_block_crop(self):
        # A ROUTING unit test, separate from the actual-WAV dry regressions.
        # Validated dry captures may contain explicit pre/post DSP padding.
        # The legacy whole-file reader must never replace their exact window.
        from unittest.mock import patch
        import p220_awe_sf2_sound_gate as gate
        from test_p220_awe_sf2_sound_gate import base
        contract,creative,vst=base();contract["sample_exact_dry"]={"routing_fixture":True}
        for f in contract["scenarios"]:
            common={k:f[k] for k in ("id","program","note","velocity","controllers")}
            common.update(note_off_observed=True,audio_frames=132300)
            creative["trials"].append({**common,"wav_sha256":"a"*64,
                "creative_program_change_delivered":True,"original_emu8000_voice_write_delta":1,
                "sf2_bank_program_selected":f["program"],"original_sample_start_register_written":True})
            vst["trials"].append({**common,"wav_sha256":"b"*64,"vst3_program_selected":f["program"],
                "vst3_note_on_count":1,"vst3_bank_selection_acknowledged":True})
        dry={"status":"BLOCKED","cases":[{"id":f"P{p:03d}-DRY","status":"BLOCKED",
            "window_comparison":{"status":"PASS","measured_audio_frames":132300}}
            for p in gate.PROGRAMS]}
        def wet_reader(root,name,sha,frames):
            self.assertTrue(name.endswith("-MODFX.wav"),"DRY raw block padding reached legacy crop")
            return {"sha256":sha,"frames":frames}
        with patch.object(gate,"evaluate_dry",return_value=dry), \
                patch.object(gate,"exact_wav",side_effect=wet_reader) as reader, \
                patch.object(gate,"compare",return_value={"status":"PASS"}):
            result=gate.evaluate(contract,creative,vst,self.root,self.root)
        self.assertEqual(reader.call_count,154)  # Only 77 wet pairs, two files each.
        self.assertEqual(result["status"],"BLOCKED")
        self.assertTrue(all(p["scenario_results"][0]["sample_exact_dry"]["status"]=="BLOCKED"
                            for p in result["presets"]))

if __name__=="__main__":
    unittest.main()
