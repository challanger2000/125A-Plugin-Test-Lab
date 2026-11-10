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

if __name__=="__main__":
    unittest.main()
