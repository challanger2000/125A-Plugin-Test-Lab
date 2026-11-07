#!/usr/bin/env python3
"""P72 independent consistency and read-only product onboarding tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from run_plugin_onboarding import combine, run, SCHEMA
from run_gui_hwnd_guided import digest


def evidence(root, module_sha, host_sha):
    abi={"schema":"125a-vst3-discovery-v1","status":"DISCOVERY_COMPLETE",
         "verified_module_sha256":module_sha,
         "verified_gui_host_sha256":host_sha,
         "release_approved":False,"parameter_count":2,"bus_count":2}
    gui={"schema":"125a-unified-gui-discovery-v1","status":"CANDIDATES_COMPLETE",
         "verified_module_sha256":module_sha,
         "verified_gui_host_sha256":host_sha,
         "mode":"READ_ONLY","click_observation":"NOT RUN",
         "native_candidates":1,"painted_candidates":1,
         "release_approved":False,
         "proposed_candidates":[{"source":"PAINTED_VISUAL_REGION","x":160,"y":90,
                                  "approved_to_click":False,"semantics":"UNKNOWN"}]}
    draft={"schema":"125a-vst3-test-plan-draft-v1",
           "product":{"id":"generic_plugin","module":str(root/"a.vst3"),
                      "sha256":module_sha},
           "hosts":{"gui":{"sha256":host_sha}},
           "executable_p65_plan":False,"release_approved":False,
           "required_feature_inventory":"NOT DECLARED",
           "proposed_cases":[{"id":"technical_baseline","approval":"REQUIRES PRODUCT OWNER REVIEW"}]}
    return abi,gui,draft


class FullProductOnboardingTests(unittest.TestCase):
    def test_combined_review_is_never_runnable_or_release_approved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            a,b,d=evidence(root,"a"*64,"b"*64)
            result=combine(a,b,d,"a"*64,"b"*64)
            self.assertEqual(result["schema"],SCHEMA)
            self.assertEqual(result["status"],"REVIEW_PACK_COMPLETE")
            self.assertEqual(result["clicks_performed"],0)
            self.assertEqual(result["required_feature_coverage"],"NOT DECLARED")
            self.assertFalse(result["release_approved"])
            self.assertFalse(result["executable_p65_plan"])
            self.assertEqual(len(result["owner_tasks"]),5)
            self.assertEqual(result["reviewable_gui_click_coordinates"][0]["semantics"],
                             "UNKNOWN")

    def test_untrusted_identity_or_invented_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            a,b,d=evidence(root,"a"*64,"b"*64)
            bads=[]
            z=copy.deepcopy(a);z["verified_module_sha256"]="f"*64
            bads.append((z,b,d))
            z=copy.deepcopy(b);z["click_observation"]="OBSERVATIONS_COMPLETE"
            bads.append((a,z,d))
            z=copy.deepcopy(d);z["executable_p65_plan"]=True
            bads.append((a,b,z))
            z=copy.deepcopy(b);z["proposed_candidates"][0]["approved_to_click"]=True
            bads.append((a,z,d))
            z=copy.deepcopy(b);z["proposed_candidates"]*=2
            bads.append((a,z,d))
            z=copy.deepcopy(a);z["status"]="FAIL"
            bads.append((z,b,d))
            for case in bads:
                with self.subTest(case=case),self.assertRaises(ValueError):
                    combine(*case,"a"*64,"b"*64)

    def test_only_read_only_detection_dispatch_and_real_hash_binding(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            dll=root/"Plugin.vst3"/"Contents"/"x86_64-win"/"Plugin.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"vst3")
            host=root/"GUI.exe"
            host.write_bytes(b"host")
            sha,hsha=digest(dll),digest(host)
            a,b,d=evidence(root,sha,hsha)
            calls=[]
            def inventory(plugin,gui,out,**kwargs):
                calls.append("ABI")
                out.mkdir(parents=True,exist_ok=True)
                (out/"PROPOSED-TEST-PLAN.json").write_text(json.dumps(d))
                return a
            def scan(plugin,gui,out,**kwargs):
                self.assertFalse(kwargs["acknowledge"])
                calls.append("GUI")
                return b
            result=run(dll.parents[2],host,root/"one-command",
                       inventory=inventory,gui=scan)
            self.assertEqual(result["status"],"REVIEW_PACK_COMPLETE")
            self.assertEqual(calls,["ABI","GUI"])
            self.assertEqual(result["clicks_performed"],0)
            self.assertFalse(result["release_approved"])
            def modified(plugin,gui,out,**kwargs):
                dll.write_bytes(b"changed while running")
                return b
            altered=run(dll.parents[2],host,root/"modified",
                        inventory=inventory,gui=modified)
            self.assertEqual(altered["status"],"FAIL")
            self.assertFalse(altered["release_approved"])


if __name__=="__main__":
    unittest.main()
