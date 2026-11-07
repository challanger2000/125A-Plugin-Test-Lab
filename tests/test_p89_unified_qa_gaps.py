#!/usr/bin/env python3
"""P89 independently reconcile success/failure/coverage in native batch reports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from run_unified_qa_gaps import review


class UnifiedGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.batch = self.root / "batch"
        self.batch.mkdir()
        self.source = {
            "schema":"125a-vst3-batch-report-v1", "status":"BATCH_MIXED_QA_PASS",
            "declared_plugins":2, "passed_plugins":2, "failed_plugins":0,
            "release_approved":False,
            "plugins":[
                {"id":"reviewed","verified_module_sha256":"a"*64,
                 "status":"PASS", "verified_stage":"DECLARED_COVERAGE_PASS",
                 "required_feature_coverage":"REQUIRED_COVERAGE_COMPLETE",
                 "faults":[]},
                {"id":"unknown","verified_module_sha256":"b"*64,
                 "status":"PASS", "verified_stage":"INVENTORY_COMPLETE",
                 "required_feature_coverage":"NOT DECLARED",
                 "faults":[]}
            ]
        }
        self.children = [
            {"schema":"125a-universal-vst3-qa-pipeline-v1",
             "verified_module_sha256":"a"*64,
             "status":"DECLARED_COVERAGE_PASS", "discovery":"PASS",
             "approved_product_cases":"CONTRACT_PASS",
             "required_feature_coverage":"REQUIRED_COVERAGE_COMPLETE",
             "required_feature_gaps":[],
             "unknown_gui_exploration":"NOT RUN",
             "real_asio_hardware":"NOT RUN",
             "commercial_daw_session":"NOT RUN",
             "release_approved":False},
            {"schema":"125a-universal-vst3-qa-pipeline-v1",
             "verified_module_sha256":"b"*64,
             "status":"INVENTORY_COMPLETE", "discovery":"PASS",
             "approved_product_cases":"NOT DECLARED",
             "required_feature_coverage":"NOT DECLARED",
             "required_feature_gaps":[],
             "unknown_gui_exploration":"NOT RUN",
             "real_asio_hardware":"NOT RUN",
             "commercial_daw_session":"NOT RUN",
             "release_approved":False}
        ]
        self.write()

    def write(self):
        (self.batch/"BATCH-QA-REPORT.json").write_text(json.dumps(self.source))
        for i,(name,child) in enumerate(zip(("reviewed","unknown"),self.children),1):
            directory = self.batch / ("%02d-%s" % (i,name))
            directory.mkdir(exist_ok=True)
            (directory/"UNIVERSAL-QA-RESULT.json").write_text(json.dumps(child))

    def test_truthful_mixed_batch_and_readable_summary(self):
        result=review(self.batch,self.root/"out")
        self.assertEqual(result["status"],"RECONCILED_REPORT_COMPLETE")
        self.assertEqual(result["passed_plugins"],2)
        self.assertEqual(result["product_verified_plugins"],1)
        self.assertEqual(result["plugins"][1]["required_feature_coverage"],"NOT DECLARED")
        self.assertIn("INDEPENDENT_PRODUCT_FEATURE_COVERAGE_NOT_PROVED",
                      result["plugins"][1]["unresolved_acceptance_gaps"])
        self.assertFalse(result["all_products_release_approved"])
        markdown=(self.root/"out"/"UNIFIED-QA-GAPS.md").read_text()
        self.assertIn("reviewed",markdown)
        self.assertIn("unknown",markdown)
        self.assertIn("physical ASIO",markdown)

    def test_actual_failed_child_does_not_stop_consolidated_report(self):
        self.source["status"]="FAIL"
        self.source["passed_plugins"]=1
        self.source["failed_plugins"]=1
        self.source["plugins"][0]["status"]="FAIL"
        self.source["plugins"][0].pop("verified_stage")
        self.source["plugins"][0]["faults"]=["incorrect sound"]
        self.children[0]["status"]="FAIL"
        self.children[0]["required_feature_coverage"]="REQUIRED_COVERAGE_INCOMPLETE"
        self.children[0]["required_feature_gaps"]=["export"]
        self.write()
        result=review(self.batch,self.root/"failed")
        self.assertEqual(result["status"],"RECONCILED_REPORT_COMPLETE")
        self.assertEqual(result["failed_plugins"],1)
        self.assertIn("PLUGIN_QA_FAILED",result["plugins"][0]["unresolved_acceptance_gaps"])
        self.assertIn("DECLARED_REQUIRED_FEATURE_GAPS",
                      result["plugins"][0]["unresolved_acceptance_gaps"])

    def test_forged_pass_cannot_hide_missing_child_or_wrong_sha(self):
        bad=self.batch/"01-reviewed"/"UNIVERSAL-QA-RESULT.json"
        bad.unlink()
        with self.assertRaises(ValueError):
            review(self.batch,self.root/"no")
        self.write()
        self.children[0]["verified_module_sha256"]="c"*64
        self.write()
        with self.assertRaises(ValueError):
            review(self.batch,self.root/"wrong")

    def test_false_hardware_or_release_claim_cannot_be_accepted(self):
        for field,value in (("real_asio_hardware","PASS"),
                            ("commercial_daw_session","PASS"),
                            ("release_approved",True),
                            ("required_feature_coverage","NOT DECLARED")):
            with self.subTest(field=field):
                self.children[0][field]=value
                self.write()
                with self.assertRaises(ValueError):
                    review(self.batch,self.root/field)
                self.children[0]=copy.deepcopy({
                    "schema":"125a-universal-vst3-qa-pipeline-v1",
                    "verified_module_sha256":"a"*64,
                    "status":"DECLARED_COVERAGE_PASS", "discovery":"PASS",
                    "approved_product_cases":"CONTRACT_PASS",
                    "required_feature_coverage":"REQUIRED_COVERAGE_COMPLETE",
                    "required_feature_gaps":[],
                    "unknown_gui_exploration":"NOT RUN",
                    "real_asio_hardware":"NOT RUN",
                    "commercial_daw_session":"NOT RUN", "release_approved":False
                })


if __name__=="__main__":
    unittest.main()
