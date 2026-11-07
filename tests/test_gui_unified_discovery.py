#!/usr/bin/env python3
"""P71 regression for combined native/painted discovery and click safety."""
import copy
import tempfile
import unittest
from pathlib import Path

from run_gui_unified_discovery import merge_candidates, run, SCHEMA
from run_gui_hwnd_guided import digest


def fixtures(visual="button"):
    tree = {"schema": "125a-hwnd-control-tree-v1",
            "status": "OBSERVATIONS_COMPLETE", "release_approved": False,
            "native_hwnd_count": 2,
            "nodes": [
                {"index": 0, "parent": -1, "class_name": "PluginEditor",
                 "visible": True, "enabled": True, "rectangle": [0,0,320,180],
                 "control_id":0},
                {"index": 1, "parent": 0, "class_name":"Button",
                 "visible": True, "enabled": True,
                 "rectangle":[120,65,200,115], "control_id":43001}
            ]}
    native = {"schema":"125a-gui-hwnd-guided-discovery-v1",
              "status":"CANDIDATES_COMPLETE", "release_approved":False,
              "actual_exploration_status":"NOT RUN",
              "verified_module_sha256":"1"*64,
              "verified_gui_host_sha256":"2"*64,
              "proposed_candidates":[{
                  "node_index":1,"control_id":43001,"class_name":"Button",
                  "x":160,"y":90,"source":"NATIVE_HWND_GEOMETRY",
                  "interaction":"PROPOSED_ONLY"}],
              "_native_hwnd_tree":tree}
    if visual=="button":
        regions = [(150,90,[120,65,200,115])]
    elif visual=="another":
        regions = [(250,40,[220,20,290,60])]
    else:
        regions = []
    painted = {"schema":"125a-painted-gui-visual-candidates-v1",
               "status":"CANDIDATES_COMPLETE", "release_approved":False,
               "exploration":"NOT RUN",
               "verified_module_sha256":"1"*64,
               "verified_gui_host_sha256":"2"*64,
               "visual_candidates":[
                   {"x":x, "y":y, "bbox_xyxy":rect,
                    "origin":"NATIVE_STATIC_PIXEL_ISLAND",
                    "control_semantics":"UNKNOWN", "approved_to_click":False}
                   for x,y,rect in regions]}
    return native, painted


class UnifiedGuiTests(unittest.TestCase):
    def test_deduplicates_real_hwnd_button_from_visual_artwork(self):
        native, painted = fixtures()
        candidates, ignored = merge_candidates(native, painted)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source"], "NATIVE_HWND")
        self.assertEqual((candidates[0]["x"], candidates[0]["y"]),(160,90))
        self.assertEqual(ignored[0]["reason"], "COVERED_BY_NATIVE_BUTTON")

    def test_keeps_additional_custom_painted_candidate(self):
        candidates, ignored = merge_candidates(*fixtures("another"))
        self.assertEqual([c["source"] for c in candidates],
                         ["NATIVE_HWND", "PAINTED_VISUAL_REGION"])
        self.assertEqual(len(ignored), 0)
        self.assertTrue(all(c["approved_to_click"] is False for c in candidates))
        subset, ignored = merge_candidates(*fixtures("another"), max_points=1)
        self.assertEqual(len(subset),1)
        self.assertEqual(ignored[0]["reason"],"BOUNDED_CANDIDATE_LIMIT")

    def test_mismatched_or_fake_sources_fail_closed(self):
        base_a,base_b=fixtures()
        cases=[]
        a,b=copy.deepcopy(base_a),copy.deepcopy(base_b)
        b["verified_module_sha256"]="3"*64
        cases.append((a,b))
        a,b=copy.deepcopy(base_a),copy.deepcopy(base_b)
        a["proposed_candidates"][0]["x"]=180
        cases.append((a,b))
        a,b=copy.deepcopy(base_a),copy.deepcopy(base_b)
        a["actual_exploration_status"]="OBSERVATIONS_COMPLETE"
        cases.append((a,b))
        a,b=copy.deepcopy(base_a),copy.deepcopy(base_b)
        b["visual_candidates"][0]["approved_to_click"]=True
        cases.append((a,b))
        a,b=copy.deepcopy(base_a),copy.deepcopy(base_b)
        a["_native_hwnd_tree"]["nodes"][1]["enabled"]=False
        cases.append((a,b))
        for a,b in cases:
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):
                merge_candidates(a,b)

    def test_read_only_wrapper_never_clicks_and_optin_requires_sham(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dll=root/"Synth.vst3"/"Contents"/"x86_64-win"/"Synth.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"module")
            host=root/"GUI.exe"
            host.write_bytes(b"host")
            def detector_native(*args,**kwargs):
                src,_=fixtures("another")
                src.pop("_native_hwnd_tree")
                src["verified_module_sha256"]=digest(dll)
                src["verified_gui_host_sha256"]=digest(host)
                target=args[2]/"hwnd-tree"/"HWND-CONTROL-TREE.json"
                target.parent.mkdir(parents=True,exist_ok=True)
                import json
                tree=fixtures("another")[0]["_native_hwnd_tree"]
                tree.update({"verified_module_sha256":digest(dll),
                             "verified_gui_host_sha256":digest(host)})
                target.write_text(json.dumps(tree))
                self.assertFalse(kwargs["acknowledge"])
                return src
            def detector_painted(*args,**kwargs):
                _,src=fixtures("another")
                src["verified_module_sha256"]=digest(dll)
                src["verified_gui_host_sha256"]=digest(host)
                self.assertFalse(kwargs["acknowledge"])
                return src
            calls=[]
            def click(*args,**kwargs):
                calls.append(kwargs["points"])
                return {"status":"OBSERVATIONS_COMPLETE",
                        "verified_module_sha256":digest(dll),
                        "verified_gui_host_sha256":digest(host),
                        "requested_points":2,"completed_points":2,
                        "sham_verified_points":2,"release_approved":False}
            result=run(dll.parents[2],host,root/"read",
                       native_detector=detector_native,
                       painted_detector=detector_painted,explorer=click)
            self.assertEqual(result["schema"],SCHEMA)
            self.assertEqual(result["status"],"CANDIDATES_COMPLETE")
            self.assertEqual(result["click_observation"],"NOT RUN")
            self.assertEqual(calls,[])
            self.assertFalse(result["release_approved"])
            approved=run(dll.parents[2],host,root/"active",acknowledge=True,
                         native_detector=detector_native,
                         painted_detector=detector_painted,explorer=click)
            self.assertEqual(approved["click_observation"],"OBSERVATIONS_COMPLETE")
            self.assertEqual(calls,["160,90;250,40"])

            def fake(*args,**kwargs):
                record=click(*args,**kwargs)
                record["sham_verified_points"]=0
                return record
            failed=run(dll.parents[2],host,root/"fake",acknowledge=True,
                       native_detector=detector_native,
                       painted_detector=detector_painted,explorer=fake)
            self.assertEqual(failed["status"],"FAIL")
            self.assertEqual(failed["click_observation"],"FAIL")


if __name__=="__main__":
    unittest.main()
