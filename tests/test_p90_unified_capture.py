#!/usr/bin/env python3
"""P90 P89 per-plugin integration: external audio is never physical ASIO proof."""
import json
from pathlib import Path
import unittest

from test_p89_unified_qa_gaps import UnifiedGapTests
from run_unified_qa_gaps import review


class P90SummaryTests(UnifiedGapTests):
    def test_good_external_capture_remains_unattested(self):
        contract = self.root / "capture.json"
        contract.write_text(json.dumps({"schema":"external-test"}),encoding="utf-8")
        calls = []
        def accepted(obj, folder):
            calls.append((obj, folder))
            return {
                "schema":"125a-external-daw-capture-comparison-v1",
                "status":"AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED",
                "verified_module_sha256":"a"*64,
                "hardware_asio_verified":False,
                "daw_session_verified":False,
                "release_approved":False
            }
        report = review(self.batch, self.root/"external",
                        capture_contracts={"reviewed":str(contract)},
                        capture_runner=accepted)
        self.assertEqual(len(calls),1)
        self.assertEqual(report["external_pcm_captures_compared"],1)
        self.assertEqual(report["external_pcm_captures_matching"],1)
        self.assertEqual(report["physical_asio_hardware"],"NOT RUN")
        self.assertEqual(report["external_audio_source_provenance"],"NOT ATTESTED")
        self.assertFalse(report["all_products_release_approved"])
        self.assertEqual(report["plugins"][1]["externally_supplied_audio_comparison"],
                         "NOT PROVIDED")

    def test_external_pcm_failure_is_explicit_not_hidden(self):
        contract = self.root / "capture.json"
        contract.write_text("{}")
        def failure(obj, folder):
            return {
                "schema":"125a-external-daw-capture-comparison-v1",
                "status":"FAIL", "verified_module_sha256":"a"*64,
                "hardware_asio_verified":False,
                "daw_session_verified":False, "release_approved":False
            }
        report = review(self.batch, self.root/"external-fail",
                        capture_contracts={"reviewed":str(contract)},
                        capture_runner=failure)
        self.assertEqual(report["external_pcm_captures_matching"],0)
        self.assertIn("EXTERNAL_PCM_CAPTURE_COMPARISON_FAILED",
                      report["plugins"][0]["unresolved_acceptance_gaps"])

    def test_forged_asio_and_module_evidence_fail_closed(self):
        contract = self.root/"claim.json"
        contract.write_text("{}")
        for attr,value in (("hardware_asio_verified",True),
                           ("daw_session_verified",True),
                           ("verified_module_sha256","b"*64),
                           ("release_approved",True)):
            with self.subTest(attribute=attr):
                reported={
                    "schema":"125a-external-daw-capture-comparison-v1",
                    "status":"AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED",
                    "verified_module_sha256":"a"*64,
                    "hardware_asio_verified":False,
                    "daw_session_verified":False, "release_approved":False
                }
                reported[attr]=value
                with self.assertRaises(ValueError):
                    review(self.batch,self.root/("forged-"+attr),
                           capture_contracts={"reviewed":str(contract)},
                           capture_runner=lambda *_a:reported)

    def test_unselected_plugin_source_is_rejected(self):
        with self.assertRaises(ValueError):
            review(self.batch,self.root/"unknown",
                   capture_contracts={"unselected":"no.json"})


if __name__=="__main__":
    unittest.main()
