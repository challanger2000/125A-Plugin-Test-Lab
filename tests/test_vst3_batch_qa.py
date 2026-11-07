#!/usr/bin/env python3
"""P75 batch QA positive/negative, timeout isolation and fail-closed evidence."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from run_vst3_batch_qa import load_selection, run, SCHEMA, RESULT
from run_vst3_auto_discovery import digest


def setup(root):
    for name in ("A", "B"):
        bundle = root / (name + ".vst3")
        dll = bundle / "Contents" / "x86_64-win" / (name + ".vst3")
        dll.parent.mkdir(parents=True, exist_ok=True)
        dll.write_bytes(b"native module " + name.encode())
    gui = root / "GUI.exe"
    gui.write_bytes(b"native GUI host")
    selection = root / "selection.json"
    selection.write_text(json.dumps({
        "schema": SCHEMA, "plugins": [
            {"id":"plugin_a","bundle":str(root/"A.vst3"),
             "run_technical_baseline":False},
            {"id":"plugin_b","bundle":str(root/"B.vst3"),
             "run_technical_baseline":False}
        ]
    }))
    return selection, gui


class FakeResult:
    def __init__(self, code=0):
        self.returncode=code
        self.stdout="child report"
        self.stderr=""


def successful_child(cmd, **kwargs):
    args = dict(zip(cmd[2::2],cmd[3::2]))
    bundle=Path(args["--plugin"])
    folder=Path(args["--out"])
    dll=next(x for x in bundle.rglob("*.vst3") if x.is_file())
    expected = ("TECHNICAL_BASELINE_PASS" if
                "--run-technical-baseline" in cmd else "INVENTORY_COMPLETE")
    output = {
        "schema": "125a-universal-vst3-qa-pipeline-v1",
        "status": expected,
        "verified_module_sha256": digest(dll),
        "verified_gui_host_sha256": digest(Path(args["--gui-host"])),
        "discovery": "PASS", "native_technical": (
            "PASS" if expected == "TECHNICAL_BASELINE_PASS" else "NOT RUN"),
        "gui_clicks_automatically_authorized": 0,
        "required_feature_coverage": "NOT DECLARED",
        "release_approved": False
    }
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"UNIVERSAL-QA-RESULT.json").write_text(json.dumps(output))
    return FakeResult()


class BatchTests(unittest.TestCase):
    def test_auto_detects_real_bundle_directory_without_manual_per_plugin_code(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            selection,gui=setup(root)
            items=load_selection(root=root)
            self.assertEqual([x["id"] for x in items],["plugin_01","plugin_02"])
            self.assertEqual(len({x["sha256"] for x in items}),2)
            report=run(items,gui,root/"scanned",runner=successful_child)
            self.assertEqual(report["status"],"BATCH_TECHNICAL_PASS")
            self.assertEqual(report["passed_plugins"],2)
            self.assertEqual(report["failed_plugins"],0)
            self.assertFalse(report["release_approved"])
            self.assertEqual(report["gui_clicks_automatically_authorized"],0)

    def test_selected_batch_isolation_continues_after_crash_or_timeout(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            selection,gui=setup(root)
            items=load_selection(selection=selection)
            calls=[]
            def crashed_first(cmd,**kw):
                calls.append(cmd)
                if len(calls)==1:
                    raise subprocess.TimeoutExpired(cmd, kw["timeout"])
                return successful_child(cmd,**kw)
            report=run(items,gui,root/"crash",runner=crashed_first)
            self.assertEqual(report["status"],"FAIL")
            self.assertEqual(report["passed_plugins"],1)
            self.assertEqual(report["failed_plugins"],1)
            self.assertEqual([p["status"] for p in report["plugins"]],
                             ["FAIL","PASS"])
            self.assertEqual(len(calls),2)
            self.assertFalse(report["release_approved"])

    def test_forged_success_or_corrupted_module_cannot_pass(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            selection,gui=setup(root)
            items=load_selection(selection=selection)
            def fake(cmd,**kwargs):
                response=successful_child(cmd,**kwargs)
                d=Path(cmd[cmd.index("--out")+1])/"UNIVERSAL-QA-RESULT.json"
                obj=json.loads(d.read_text())
                obj["required_feature_coverage"]="REQUIRED_COVERAGE_COMPLETE"
                d.write_text(json.dumps(obj))
                return response
            report=run(items,gui,root/"forged",runner=fake)
            self.assertEqual(report["failed_plugins"],2)
            self.assertEqual(report["status"],"FAIL")
            def tamper(cmd,**kwargs):
                response=successful_child(cmd,**kwargs)
                bundle=Path(cmd[cmd.index("--plugin")+1])
                dll=next(x for x in bundle.rglob("*.vst3") if x.is_file())
                dll.write_bytes(b"wrong DLL during run")
                return response
            report=run(items,gui,root/"tamper",runner=tamper)
            self.assertEqual(report["status"],"FAIL")
            self.assertEqual(report["failed_plugins"],2)

    def test_strict_manifest_duplicated_or_invalid_selection_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            selection,gui=setup(root)
            manifest=json.loads(selection.read_text())
            candidates=[]
            x=copy.deepcopy(manifest)
            x["plugins"][1]["id"]="plugin_a"
            candidates.append(x)
            x=copy.deepcopy(manifest)
            x["plugins"][1]["bundle"]=x["plugins"][0]["bundle"]
            candidates.append(x)
            x=copy.deepcopy(manifest)
            x["plugins"][0]["run_technical_baseline"]="true"
            candidates.append(x)
            x=copy.deepcopy(manifest)
            x["plugins"][0]["unexpected"]="shell"
            candidates.append(x)
            x=copy.deepcopy(manifest)
            x["schema"]="v999"
            candidates.append(x)
            x=copy.deepcopy(manifest)
            x["plugins"]=[]
            candidates.append(x)
            for i,candidate in enumerate(candidates):
                with self.subTest(i=i):
                    selection.write_text(json.dumps(candidate))
                    with self.assertRaises(ValueError):
                        load_selection(selection=selection)

    def test_technical_requires_hosts_and_overlong_budget_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            selection,gui=setup(root)
            items=load_selection(root=root,technical_all=True)
            with self.assertRaises(ValueError):
                run(items,gui,root/"missing",runner=successful_child)
            with self.assertRaises(ValueError):
                run(items,gui,root/"too_long",per_plugin_timeout=5000,
                    runner=successful_child)
            audio=root/"audio.exe"
            stress=root/"stress.exe"
            audio.write_bytes(b"audio")
            stress.write_bytes(b"stress")
            report=run(items,gui,root/"technical",audio_host=audio,
                       stress_host=stress,runner=successful_child)
            self.assertEqual(report["status"],"BATCH_TECHNICAL_PASS")
            self.assertEqual(report["passed_plugins"],2)


if __name__=="__main__":
    unittest.main()
