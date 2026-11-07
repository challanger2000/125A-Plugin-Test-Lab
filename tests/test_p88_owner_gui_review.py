#!/usr/bin/env python3
"""P88 review queue never promotes observation into approved product testing."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from run_gui_owner_review_queue import generate


class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cap, self.par, self.dense = (self.root / x for x in
                                           ("cap.tsv", "params.tsv", "dense.json"))
        self.cap.write_text(
            "format\t125A-VST3-CAPABILITIES-v1\n"
            "audio_classes\t1\nparameter_count\t2\n"
            "editable_parameters\t2\nreadonly_parameters\t0\n"
            "bypass_parameters\t0\nprogram_parameters\t0\n"
            "editor_available\t1\neditor_win32_hwnd\t1\n"
            "bus_count\t0\nend\tCOMPLETE\n", encoding="utf-8")
        self.par.write_text(
            "format\t125A-GUI-PARAMS-v1\nparam_count\t2\n"
            "param\t0\t9001\t0\t0\t0\t0\n"
            "param\t1\t9002\t0\t0\t0\t0\n", encoding="utf-8")
        self.audit = {
            "schema":"125a-dense-gui-audit-v1",
            "status":"SAMPLED_GRID_COMPLETE",
            "verified_module_sha256":"a"*64,
            "verified_gui_host_sha256":"b"*64,
            "grid_side":3,"repeat_count":1,
            "planned_points":9,"completed_points":9,
            "observed_parameter_ids":[9001],
            "observations":[
                {"x": i, "y": i, "classification":(
                    "PARAMETER_AND_VISUAL_CHANGE" if i==4
                    else "NO_OBSERVED_CHANGE"),
                 "parameter_transitions":([[9001,0.0,1.0]] if i==4 else [])}
                for i in range(9)],
            "control_semantics":"NOT ESTABLISHED",
            "all_controls_discovered":False,
            "all_product_features_tested":False,
            "release_approved":False}
        self.dense.write_text(json.dumps(self.audit), encoding="utf-8")

    def make(self):
        return generate(self.cap,self.par,self.dense,self.root/"review")

    def test_review_queue_preserves_native_ids_without_semantic_fabrication(self):
        result=self.make()
        self.assertEqual(result["status"],"REVIEW_PACKAGE_COMPLETE")
        self.assertEqual(result["native_parameter_count"],2)
        self.assertEqual(result["observed_parameter_count"],1)
        self.assertEqual(result["unobserved_parameter_count"],1)
        one,two=result["parameter_review_queue"]
        self.assertEqual(one["param_id"],9001)
        self.assertEqual(one["observations"][0]["position"],{"x":4,"y":4})
        self.assertEqual(two["param_id"],9002)
        self.assertFalse(two["observed_at_grid_sample"])
        self.assertTrue(all(p["requires_owner_approval"] and
                            not p["approved_to_execute"] and
                            p["proposed_product_control_name"] is None
                            for p in result["parameter_review_queue"]))
        self.assertFalse(result["executable_p65_plan_generated"])
        self.assertFalse(result["complete_ui_inventory"])
        self.assertFalse(result["release_approved"])

    def test_unknown_parameter_and_missing_transition_reject(self):
        for mutation in ("unknown","missing","duplicate","incomplete"):
            with self.subTest(mutation=mutation):
                obj=copy.deepcopy(self.audit)
                if mutation=="unknown":
                    obj["observations"][4]["parameter_transitions"]=[[9999,0.0,1.0]]
                    obj["observed_parameter_ids"]=[9999]
                elif mutation=="missing":
                    obj["observations"][4]["parameter_transitions"]=[]
                elif mutation=="duplicate":
                    obj["observed_parameter_ids"]=[9001,9001]
                else:
                    obj["completed_points"]=8
                self.dense.write_text(json.dumps(obj),encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.make()

    def test_unapproved_visual_only_control_is_not_executable(self):
        obj=copy.deepcopy(self.audit)
        obj["observations"][0]["classification"]="VISUAL_CHANGE"
        self.dense.write_text(json.dumps(obj),encoding="utf-8")
        result=self.make()
        self.assertEqual(len(result["visual_only_review_candidates"]),1)
        self.assertEqual(result["visual_only_review_candidates"][0]["status"],
                         "REQUIRES_INDEPENDENT_PRODUCT_ORACLE")
        self.assertFalse(result["executable_p65_plan_generated"])


if __name__=="__main__":
    unittest.main()
