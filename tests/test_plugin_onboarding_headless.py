#!/usr/bin/env python3
"""P73 headless VST3 and opt-in automated technical baseline regression."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from run_plugin_onboarding import run, combine
from run_gui_hwnd_guided import digest


def fixture(root, editor=False):
    dll = root / "Module.vst3" / "Contents" / "x86_64-win" / "Module.vst3"
    dll.parent.mkdir(parents=True, exist_ok=True)
    dll.write_bytes(b"real VST3")
    gui = root / "GUI.exe"
    gui.write_bytes(b"GUI Host")
    audio = root / "Host.exe"
    audio.write_bytes(b"Audio Host")
    stress = root / "Stress.exe"
    stress.write_bytes(b"Stress Host")
    fp, hp = digest(dll), digest(gui)
    abi = {
        "schema": "125a-vst3-discovery-v1", "status": "DISCOVERY_COMPLETE",
        "verified_module_sha256": fp, "verified_gui_host_sha256": hp,
        "parameter_count": 2, "bus_count": 1,
        "reported_editor_available": editor, "release_approved": False
    }
    draft = {
        "schema": "125a-vst3-test-plan-draft-v1",
        "product": {"id":"module","module":str(dll), "sha256":fp},
        "hosts": {"gui": {"path":str(gui),"sha256":hp}},
        "executable_p65_plan": False, "required_feature_inventory": "NOT DECLARED",
        "proposed_cases": [], "release_approved": False
    }
    return dll, gui, audio, stress, abi, draft


def mocked_abi(abi, draft):
    def inventory(module, gui_host, out, **kwargs):
        out.mkdir(parents=True, exist_ok=True)
        (out/"PROPOSED-TEST-PLAN.json").write_text(json.dumps(draft))
        return abi
    return inventory


class HeadlessOnboardingTests(unittest.TestCase):
    def test_no_editor_detected_without_launching_gui(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dll,host,audio,stress,abi,draft=fixture(root)
            def no_gui(*args,**kwargs):
                raise AssertionError("P73 attempted GUI inspection on headless VST3")
            report=run(dll.parents[2],host,root/"headless",gui=no_gui,
                       inventory=mocked_abi(abi,draft))
            self.assertEqual(report["status"],"REVIEW_PACK_COMPLETE")
            self.assertEqual(report["gui_editor_status"],"VST3_NO_EDITOR_EXPOSED")
            self.assertEqual(report["reviewable_gui_click_coordinates"],[])
            self.assertEqual(report["native_gui_candidates"],0)
            self.assertEqual(report["owner_tasks"][2]["status"],"NOT APPLICABLE")
            self.assertEqual(report["native_technical_status"],"NOT RUN")
            self.assertFalse(report["release_approved"])

    def test_independent_technical_baseline_requires_real_coverage_and_optin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dll,host,audio,stress,abi,draft=fixture(root)
            called=[]
            def good(*args,**kwargs):
                called.append(args)
                return {
                    "schema":"125a-quickcheck-result-v1",
                    "status":"TECHNICAL_PASS", "release_approved":False,
                    "verified_module_sha256":digest(dll),
                    "coverage":{"api_playback_save":"PASS",
                                "sample_rate_buffer_matrix":"PASS",
                                "native_audio_state_capture":"PASS",
                                "physical_asio_hardware":"NOT RUN",
                                "real_commercial_daw_session":"NOT RUN"}
                }
            report=run(dll.parents[2],host,root/"native",
                       inventory=mocked_abi(abi,draft),
                       gui=lambda *args,**kwargs:self.fail("must not open headless editor"),
                       audio_host=audio,stress_host=stress,
                       run_technical=True,technical=good)
            self.assertEqual(report["status"],"REVIEW_PACK_COMPLETE")
            self.assertEqual(report["native_technical_status"],"TECHNICAL_PASS")
            self.assertEqual(len(report["native_technical_verified_coverage"]),3)
            self.assertEqual(len(called),1)
            self.assertEqual(report["required_feature_coverage"],"NOT DECLARED")
            self.assertFalse(report["release_approved"])
            def bad(*args,**kwargs):
                result=good(*args,**kwargs)
                result["coverage"]["sample_rate_buffer_matrix"]="NOT EXECUTED"
                return result
            failed=run(dll.parents[2],host,root/"bad",
                       inventory=mocked_abi(abi,draft),audio_host=audio,
                       stress_host=stress,run_technical=True,technical=bad)
            self.assertEqual(failed["status"],"FAIL")
            self.assertFalse(failed["release_approved"])

    def test_headless_cannot_forge_native_ui_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dll,host,audio,stress,abi,draft=fixture(root)
            fake={"schema":"125a-unified-gui-discovery-v1",
                  "status":"CANDIDATES_COMPLETE","release_approved":False,
                  "verified_module_sha256":digest(dll),
                  "verified_gui_host_sha256":digest(host),
                  "proposed_candidates":[]}
            with self.assertRaises(ValueError):
                combine(abi,fake,draft,digest(dll),digest(host))
            changed=copy.deepcopy(abi)
            changed["reported_editor_available"]="false"
            with self.assertRaises(ValueError):
                combine(changed,None,draft,digest(dll),digest(host))
            with self.assertRaises(ValueError):
                run(dll.parents[2],host,root/"missing",
                    inventory=mocked_abi(abi,draft),run_technical=True)


if __name__=="__main__":
    unittest.main()
