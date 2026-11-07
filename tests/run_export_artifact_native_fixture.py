#!/usr/bin/env python3
"""P76 CI: pin a real source-built VST3 to independent exported test assets.

This is an oracle-integration test, not a claim that this QA fixture
itself can export MIDI/WAV files.
"""
import argparse
import json
from pathlib import Path

from run_export_artifact_oracle import verify
from run_product_test_plan import execute
from run_vst3_auto_discovery import verify_bundle, digest
from test_export_artifact_oracle import contract


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin",type=Path,required=True)
    p.add_argument("--gui-host",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    bundle,module=verify_bundle(a.plugin)
    host=a.gui_host.resolve(strict=True)
    a.out.mkdir(parents=True,exist_ok=True)
    checks=contract(a.out,digest(module))
    plan={
        "schema":"125a-product-test-plan-v1",
        "product":{"id":"generic_export_fixture","module":str(module),
                   "sha256":digest(module)},
        "hosts":{"gui":{"path":str(host),"sha256":digest(host)}},
        "cases":[{"id":"independent_wav_midi_files","kind":"export_artifact",
                  "contract":checks}]
    }
    matrix={
        "schema":"125a-product-feature-matrix-v1",
        "product_id":"generic_export_fixture",
        "module_sha256":digest(module),
        "features":[{
            "id":"approved_fixture_output",
            "title":"Independently prepared WAV and SMF format oracle",
            "criticality":"required",
            "case_ids":["independent_wav_midi_files"],
            "waiver":None
        }]
    }
    (a.out/"approved-plan.json").write_text(json.dumps(plan,indent=2))
    (a.out/"independent-matrix.json").write_text(json.dumps(matrix,indent=2))
    result=execute(plan,a.out/"positive",coverage_matrix=matrix)
    if (result["status"]!="CONTRACT_PASS" or
            result["required_feature_coverage"]!="REQUIRED_COVERAGE_COMPLETE" or
            result["release_approved"] is not False):
        raise RuntimeError("P76 approved independent export oracle integration failed")
    wav=Path(checks["outputs"][0]["path"])
    b=bytearray(wav.read_bytes())
    b[-1]^=1
    wav.write_bytes(b)
    failed=execute(plan,a.out/"corrupt",coverage_matrix=matrix)
    if (failed["status"]!="FAIL" or failed["failed_cases"]!=1 or
            failed["required_feature_coverage"]!="REQUIRED_COVERAGE_INCOMPLETE" or
            failed["release_approved"] is not False):
        raise RuntimeError("P76 tampered PCM export falsely passed its approved P67 requirement")
    (a.out/"INDEPENDENT-EXPORT-DEMO.json").write_text(
        json.dumps({"schema":"125a-export-oracle-integration-v1",
                    "status":"POSITIVE_AND_NEGATIVE_CONFIRMED",
                    "verified_real_module_sha256":digest(module),
                    "export_files_origin":"INDEPENDENT_FIXTURE_NOT_PLUGIN_GENERATED",
                    "actual_plugin_export_tested":False,
                    "release_approved":False},indent=2)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
