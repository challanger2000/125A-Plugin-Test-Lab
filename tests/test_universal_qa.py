#!/usr/bin/env python3
"""P74 proof: one-command universal pipeline never converts raw discovery to QA pass."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from run_universal_qa import execute, preflight, SCHEMA
from run_vst3_auto_discovery import digest
from run_rea_binary_analysis import SCHEMA as REA_SCHEMA
from test_product_test_plan import make_plan
from test_product_feature_coverage import matrix_for


def onboard_for(plan, host, technical=False):
    return {
        "schema": "125a-plugin-onboarding-v1",
        "status": "REVIEW_PACK_COMPLETE",
        "verified_module_sha256": plan["product"]["sha256"],
        "verified_gui_host_sha256": plan["hosts"]["gui"]["sha256"],
        "release_approved": False,
        "clicks_performed": 0,
        "executable_p65_plan": False,
        "required_feature_coverage": "NOT DECLARED",
        "native_technical_status": "TECHNICAL_PASS" if technical else "NOT RUN",
        "native_technical_verified_coverage": (
            ["api_playback_save", "sample_rate_buffer_matrix",
             "native_audio_state_capture"] if technical else [])
    }


def product_result(plan, coverage="REQUIRED_COVERAGE_COMPLETE"):
    return {
        "schema": "125a-product-test-plan-result-v1",
        "status": "CONTRACT_PASS",
        "verified_module_sha256": plan["product"]["sha256"],
        "release_approved": False,
        "required_feature_coverage": coverage,
        "required_feature_gaps": [],
        "declared_cases": 2, "passed_cases": 2,
        "failed_cases": 0, "not_run_cases": 0
    }


class PipelineTests(unittest.TestCase):
    def test_default_is_inventory_only_without_clicks_or_approval(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plan, module, host = make_plan(root)
            calls = []
            def scanned(*args, **kwargs):
                calls.append(kwargs.get("run_technical"))
                return onboard_for(plan, host)
            result = execute(module.parents[2], host, root / "inventory",
                             onboarding=scanned)
            self.assertEqual(calls, [False])
            self.assertEqual(result["schema"], SCHEMA)
            self.assertEqual(result["status"], "INVENTORY_COMPLETE")
            self.assertEqual(result["approved_product_cases"], "NOT DECLARED")
            self.assertEqual(result["required_feature_coverage"], "NOT DECLARED")
            self.assertEqual(result["binary_analysis"], "NOT RUN")
            self.assertEqual(result["gui_clicks_automatically_authorized"], 0)
            self.assertFalse(result["release_approved"])

    def test_approved_cases_require_full_independent_feature_matrix(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plan, module, host = make_plan(root)
            required = matrix_for(plan, include_missing=False)
            fake = lambda *args, **kwargs: onboard_for(plan, host)
            report = execute(module.parents[2], host, root / "approved",
                             onboarding=fake, plan=plan, matrix=required,
                             product_runner=lambda *a,**kw: product_result(plan))
            self.assertEqual(report["status"], "DECLARED_COVERAGE_PASS")
            self.assertEqual(report["approved_product_cases"], "CONTRACT_PASS")
            self.assertFalse(report["release_approved"])
            gaps = matrix_for(plan, include_missing=True)
            failed = execute(module.parents[2], host, root / "uncovered",
                             onboarding=fake, plan=plan, matrix=gaps,
                             product_runner=lambda *a,**kw: product_result(
                                 plan, "REQUIRED_COVERAGE_INCOMPLETE"))
            self.assertEqual(failed["status"], "FAIL")
            self.assertIn("incomplete", failed["faults"][0])

    def test_forged_stale_or_untrusted_evidence_does_not_pass(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plan, module, host = make_plan(root)
            valid = onboard_for(plan, host)
            mutations = []
            for key,value in [
                ("verified_module_sha256", "1"*64),
                ("status", "FAIL"),
                ("clicks_performed", 3),
                ("executable_p65_plan", True),
                ("required_feature_coverage", "REQUIRED_COVERAGE_COMPLETE"),
                ("release_approved", True)
            ]:
                row=copy.deepcopy(valid)
                row[key]=value
                mutations.append(row)
            for i,row in enumerate(mutations):
                with self.subTest(i=i):
                    failed=execute(module.parents[2], host, root / ("fail"+str(i)),
                                   onboarding=lambda *a, observed=row, **kw:observed)
                    self.assertEqual(failed["status"],"FAIL")
                    self.assertFalse(failed["release_approved"])

    def test_real_technical_baseline_is_strict_and_nonrelease(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            plan,module,host=make_plan(root)
            audio=root/"Audio.exe"
            stress=root/"Stress.exe"
            audio.write_bytes(b"audio")
            stress.write_bytes(b"stress")
            normal=execute(module.parents[2],host,root/"tech",
                           audio_host=audio,stress_host=stress,
                           run_technical=True,
                           onboarding=lambda *a,**kw:onboard_for(plan,host,True))
            self.assertEqual(normal["status"],"TECHNICAL_BASELINE_PASS")
            self.assertEqual(normal["native_technical"],"PASS")
            self.assertFalse(normal["release_approved"])
            bad=onboard_for(plan,host,True)
            bad["native_technical_verified_coverage"].pop()
            rejected=execute(module.parents[2],host,root/"bad",
                             audio_host=audio,stress_host=stress,
                             run_technical=True,
                             onboarding=lambda *a,**kw:bad)
            self.assertEqual(rejected["status"],"FAIL")

    def test_rea_opt_in_observes_but_never_certifies_and_rejects_forgery(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plan, module, host = make_plan(root)
            node, entry = root / "node.exe", root / "rea.mjs"
            node.write_bytes(b"node mock")
            entry.write_bytes(b"REA mock")
            def observed(binary, out, *, node, entry, timeout):
                out.mkdir(parents=True, exist_ok=True)
                raw = out / "REA-RAW-OUTPUT.json"
                raw.write_text('{"evidence": "unreviewed"}', encoding="utf-8")
                result = {"schema": REA_SCHEMA, "status": "OBSERVATION_CAPTURED",
                          "binary_sha256": digest(binary),
                          "node_sha256": digest(node), "rea_entry_sha256": digest(entry),
                          "rea_exit_code": 0, "raw_sha256": digest(raw),
                          "semantic_verification": "NOT ESTABLISHED",
                          "release_approved": False}
                (out / "REA-RESULT.json").write_text(json.dumps(result))
                return result
            kwargs = {"onboarding": lambda *a, **kw: onboard_for(plan, host),
                      "run_rea": True, "rea_node": node, "rea_entry": entry}
            good = execute(module.parents[2], host, root / "rea-ok",
                           rea_executor=observed, **kwargs)
            self.assertEqual(good["status"], "INVENTORY_COMPLETE")
            self.assertEqual(good["binary_analysis"], "OBSERVATION_CAPTURED")
            self.assertFalse(good["release_approved"])
            def forged(binary, out, **kw):
                result = observed(binary, out, **kw)
                result["binary_sha256"] = "0" * 64
                return result
            bad = execute(module.parents[2], host, root / "rea-forged",
                          rea_executor=forged, **kwargs)
            self.assertEqual(bad["status"], "FAIL")
            self.assertEqual(bad["binary_analysis"], "NOT RUN")
            with self.assertRaises(ValueError):
                execute(module.parents[2], host, root / "no-rea-tools",
                        onboarding=kwargs["onboarding"], run_rea=True)

    def test_preflight_blocks_wrong_module_or_partial_contract_pair(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            plan,module,host=make_plan(root)
            matrix=matrix_for(plan,include_missing=False)
            with self.assertRaises(ValueError):
                preflight(plan,None,module,host)
            with self.assertRaises(ValueError):
                preflight(None,matrix,module,host)
            rogue=copy.deepcopy(plan)
            rogue["product"]["sha256"]="1"*64
            with self.assertRaises(ValueError):
                preflight(rogue,matrix,module,host)
            with self.assertRaises(ValueError):
                preflight(plan,matrix,module,root/"other.exe")
            self.assertEqual(len(preflight(plan,matrix,module,host)),2)

    def test_native_module_mutation_during_scan_is_never_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            plan,module,host=make_plan(root)
            def mutate(*args,**kwargs):
                module.write_bytes(b"altered after discovery started")
                return onboard_for(plan,host)
            rejected=execute(module.parents[2],host,root/"mutate",
                             onboarding=mutate)
            self.assertEqual(rejected["status"],"FAIL")
            self.assertFalse(rejected["release_approved"])


if __name__ == "__main__":
    unittest.main()
