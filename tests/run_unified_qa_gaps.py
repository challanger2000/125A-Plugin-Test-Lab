#!/usr/bin/env python3
"""P89: independent one-page consolidated QA result from real P75/P80/P83 batches.

Reconciles source reports; does NOT grant release approval, infer unknown
function semantics, or claim commercial DAW / physical ASIO tests occurred.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from run_external_daw_capture_check import run as compare_external_capture

SCHEMA = "125a-p89-unified-qa-review-v1"
BATCH_SCHEMA = "125a-vst3-batch-report-v1"
CHILD_SCHEMA = "125a-universal-vst3-qa-pipeline-v1"
IDENT = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 2_000_000
AWE77_IDS = frozenset(("awe","awe_synthesizer","125a_awe_synthesizer"))
P220_SHA = "d5b99ec38fddf59f53f66b90921e170d207bf3bbd73960f6e4175c39ef68349b"

def awe77_sound_report(evidence, module_sha):
    """Do not promote P74 technical PASS to private-SF2 sound acceptance."""
    if (not isinstance(evidence,dict)
            or evidence.get("schema")!="125a-testlab-awe-sf2-77-sonic-gate-v1"
            or evidence.get("status")!="PASS"
            or evidence.get("private_sf2_sha256")!=P220_SHA
            or evidence.get("vst3_module_sha256")!=module_sha
            or evidence.get("original_creative_full_bank_capture_verified") is not True
            or evidence.get("actual_windows_vst3_audio_captured") is not True
            or evidence.get("passed_presets")!=77
            or evidence.get("passed_scenarios")!=154
            or evidence.get("failed_scenarios")!=0
            or evidence.get("release_approved") is not False):
        return "BLOCKED"
    expected=[p for p in range(78) if p!=63]
    entries=evidence.get("presets",[])
    if (not isinstance(entries,list) or len(entries)!=77
            or [p.get("program") for p in entries if isinstance(p,dict)]!=expected):
        return "FAIL"
    expected_gates=("amplitude_adsr","filter_sweeps","loop_seams",
                    "dry_wet_reverb_chorus","program_recall_and_reload")
    for item in entries:
        if item.get("status")!="PASS" or len(item.get("scenario_results",[]))!=2:
            return "FAIL"
        if [case.get("status") for case in item["scenario_results"]] != ["PASS","PASS"]:
            return "FAIL"
        if set(item.get("detail_gates",{}))!=set(expected_gates):
            return "FAIL"
        if any(item["detail_gates"][g].get("status")!="PASS" for g in expected_gates):
            return "FAIL"
    return "PASS"


def load(path):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("P89 missing or oversized actual QA evidence: " + str(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("P89 native QA evidence must be an object")
    return obj


def review(batch_directory, out, *, capture_contracts=None,
           capture_runner=compare_external_capture,
           awe77_reports=None, required_awe77_ids=()):
    source = Path(batch_directory).resolve(strict=True)
    batch = load(source / "BATCH-QA-REPORT.json")
    if (batch.get("schema") != BATCH_SCHEMA
            or type(batch.get("declared_plugins")) is not int
            or not 1 <= batch["declared_plugins"] <= 32
            or not isinstance(batch.get("plugins"), list)
            or len(batch["plugins"]) != batch["declared_plugins"]
            or type(batch.get("passed_plugins")) is not int
            or type(batch.get("failed_plugins")) is not int
            or batch["passed_plugins"] + batch["failed_plugins"] !=
               batch["declared_plugins"]
            or batch.get("release_approved") is not False
            or batch.get("status") not in (
                "FAIL", "BATCH_TECHNICAL_PASS", "BATCH_MIXED_QA_PASS",
                "BATCH_DECLARED_COVERAGE_PASS",
                "BATCH_EXPLORATORY_OBSERVATIONS_COMPLETE")):
        raise ValueError("P89 corrupted/incomplete consolidated native batch report")

    capture_contracts = capture_contracts or {}
    awe77_reports = awe77_reports or {}
    if (not isinstance(awe77_reports,dict)
            or any(type(k) is not str or not IDENT.fullmatch(k)
                or type(v) is not str for k,v in awe77_reports.items())
            or any(type(v) is not str or not IDENT.fullmatch(v)
                   for v in required_awe77_ids)):
        raise ValueError("P220 invalid explicit AWE 77-sound product selection")
    required_awe77_ids = set(required_awe77_ids)
    if (not isinstance(capture_contracts, dict)
            or any(type(k) is not str or not IDENT.fullmatch(k)
                   or type(v) is not str for k,v in capture_contracts.items())):
        raise ValueError("P90 invalid plugin-to-capture contract selection")
    known_ids = {x.get("id") for x in batch["plugins"] if isinstance(x, dict)}
    if not required_awe77_ids <= known_ids or not set(awe77_reports) <= known_ids:
        raise ValueError("P220 AWE 77-audio gate references an unselected VST3")
    if not set(capture_contracts) <= known_ids:
        raise ValueError("P90 external DAW capture targets unselected plugin")
    out = Path(out)
    rows, seen_ids = [], set()
    for index, item in enumerate(batch["plugins"], 1):
        if (not isinstance(item, dict) or type(item.get("id")) is not str
                or not IDENT.fullmatch(item["id"]) or item["id"] in seen_ids
                or type(item.get("verified_module_sha256")) is not str
                or not SHA.fullmatch(item["verified_module_sha256"])
                or item.get("status") not in ("PASS", "FAIL")):
            raise ValueError("P89 ambiguous VST3 module identity or repeated ID")
        ident = item["id"]
        seen_ids.add(ident)
        child_dir = source / ("%02d-%s" % (index, ident))
        child_path = child_dir / "UNIVERSAL-QA-RESULT.json"
        source_exists = child_path.is_file()
        evidence = load(child_path) if source_exists else None
        if evidence is not None:
            if (evidence.get("schema") != CHILD_SCHEMA
                    or evidence.get("verified_module_sha256") != item["verified_module_sha256"]
                    or evidence.get("release_approved") is not False
                    or evidence.get("real_asio_hardware") != "NOT RUN"
                    or evidence.get("commercial_daw_session") != "NOT RUN"):
                raise ValueError("P89 child identity or hardware/DAW evidence claim invalid")
        if item["status"] == "PASS":
            if (evidence is None
                    or evidence.get("status") != item.get("verified_stage")
                    or evidence.get("discovery") != "PASS"
                    or item.get("verified_stage") not in (
                        "INVENTORY_COMPLETE", "TECHNICAL_BASELINE_PASS",
                        "INVENTORY_WITH_EXPLORATORY_OBSERVATIONS",
                        "DECLARED_COVERAGE_PASS")
                    or item.get("required_feature_coverage") !=
                       evidence.get("required_feature_coverage")):
                raise ValueError("P89 PASS cannot be corroborated by native child evidence")
        else:
            if not item.get("faults") and evidence is None:
                raise ValueError("P89 failed plugin has neither child evidence nor fault")

        product = (evidence.get("approved_product_cases") if evidence is not None
                   else "NOT VERIFIED")
        coverage = (evidence.get("required_feature_coverage") if evidence is not None
                    else "NOT VERIFIED")
        feature_gaps = (evidence.get("required_feature_gaps", []) if evidence is not None
                        else [])
        if not isinstance(feature_gaps, list) or len(feature_gaps) > 64:
            raise ValueError("P89 unbounded product feature gap record")
        gaps = []
        if item["status"] != "PASS":
            gaps.append("PLUGIN_QA_FAILED")
        if product != "CONTRACT_PASS" or coverage != "REQUIRED_COVERAGE_COMPLETE":
            gaps.append("INDEPENDENT_PRODUCT_FEATURE_COVERAGE_NOT_PROVED")
        awe77 = "NOT APPLICABLE"
        if ident in AWE77_IDS or ident in required_awe77_ids:
            awe77 = "BLOCKED"
            if ident in awe77_reports:
                awe77 = awe77_sound_report(
                    load(awe77_reports[ident]),item["verified_module_sha256"])
            if awe77!="PASS":
                gaps.append("REQUIRED_AWE_SF2_77_SONIC_"+awe77)
        external = "NOT PROVIDED"
        if ident in capture_contracts:
            supplied = load(capture_contracts[ident])
            recorded = capture_runner(supplied, out / "external-capture" / ident)
            if (not isinstance(recorded, dict)
                    or recorded.get("schema") != "125a-external-daw-capture-comparison-v1"
                    or recorded.get("verified_module_sha256") != item["verified_module_sha256"]
                    or recorded.get("hardware_asio_verified") is not False
                    or recorded.get("daw_session_verified") is not False
                    or recorded.get("release_approved") is not False
                    or recorded.get("status") not in (
                        "AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED", "FAIL")):
                raise ValueError("P90 foreign/forged external PCM cannot be accepted")
            external = recorded["status"]
        # P68 ABI discovery is not equivalent to complete product semantics.
        gaps.extend(("PHYSICAL_ASIO_HARDWARE_NOT_TESTED",
                     "COMMERCIAL_DAW_SESSION_NOT_TESTED",
                     "UNKNOWN_PRODUCT_FUNCTION_SEMANTICS_NOT_CERTIFIED"))
        if feature_gaps:
            gaps.append("DECLARED_REQUIRED_FEATURE_GAPS")
        if external == "FAIL":
            gaps.append("EXTERNAL_PCM_CAPTURE_COMPARISON_FAILED")
        rows.append({
            "id": ident, "module_sha256": item["verified_module_sha256"],
            "automated_qa_result": item["status"],
            "observed_stage": (evidence.get("status") if evidence is not None
                               else "NO COMPLETE CHILD REPORT"),
            "native_discovery": (evidence.get("discovery") if evidence is not None
                                 else "NOT VERIFIED"),
            "independent_product_feature_cases": product,
            "required_feature_coverage": coverage,
            "required_feature_gaps": feature_gaps,
            "unknown_gui_exploration": (evidence.get("unknown_gui_exploration")
                                        if evidence is not None else "NOT VERIFIED"),
            "failure_details": item.get("faults", []),
            "externally_supplied_audio_comparison": external,
            "required_awe_77_sonic_gate":awe77,
            "unresolved_acceptance_gaps": gaps,
            "release_approved": False
        })

    good = sum(r["automated_qa_result"] == "PASS" for r in rows)
    bad = len(rows) - good
    if good != batch["passed_plugins"] or bad != batch["failed_plugins"]:
        raise ValueError("P89 failed/complete plugin count disagrees with native batch")
    summary = {
        "schema": SCHEMA, "status": "RECONCILED_REPORT_COMPLETE",
        "source_batch_status": batch["status"],
        "declared_plugins": len(rows), "passed_plugins": good,
        "failed_plugins": bad, "product_verified_plugins": sum(
            r["independent_product_feature_cases"] == "CONTRACT_PASS"
            and r["required_feature_coverage"] == "REQUIRED_COVERAGE_COMPLETE"
            for r in rows),
        "physical_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "universal_unknown_function_semantics": "NOT PROVEN",
        "external_pcm_captures_compared": sum(
            r["externally_supplied_audio_comparison"] != "NOT PROVIDED"
            for r in rows),
        "external_pcm_captures_matching": sum(
            r["externally_supplied_audio_comparison"] ==
            "AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED" for r in rows),
        "external_audio_source_provenance": "NOT ATTESTED",
        "awe77_required_product_count":sum(r["required_awe_77_sonic_gate"]!="NOT APPLICABLE"
                                           for r in rows),
        "awe77_sonic_gate_blocked_or_failed":sum(r["required_awe_77_sonic_gate"] in ("BLOCKED","FAIL")
                                              for r in rows),
        "all_products_release_approved": False,
        "plugins": rows
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "UNIFIED-QA-GAPS.json").write_text(
        json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    lines = [
        "# 125A Test Lab — Consolidated VST3 QA",
        "",
        "Automatic batch: **%s**. %d passed, %d failed, %d submitted."
        % (batch["status"], good, bad, len(rows)), "",
        "| Plugin | Automated check | Declared functionality | External PCM | Open acceptance gaps |",
        "| --- | --- | --- | --- | ---: |"
    ]
    for row in rows:
        lines.append("| `%s` | %s | %s | %s | %d |" % (
            row["id"], row["automated_qa_result"],
            row["required_feature_coverage"],
            row["externally_supplied_audio_comparison"],
            len(row["unresolved_acceptance_gaps"])))
    lines.extend([
        "", "## What is not certified", "",
        "The native batch does not prove physical ASIO hardware, an actual commercial",
        "DAW session, or the musical correctness of unknown product functions.",
        "Even a fully green automated batch is **not** independent product release approval.",
        "", "## Actionable gaps", ""
    ])
    for row in rows:
        lines.append("- **%s:** %s" % (
            row["id"], "; ".join(row["unresolved_acceptance_gaps"])))
    (out / "UNIFIED-QA-GAPS.md").write_text(
        "\n".join(lines)+"\n", encoding="utf-8")
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--require-awe77-for",action="append",default=[],
                        metavar="PLUGIN_ID",help="Release-mode: mandatory full authentic 77-preset original Creative sound gate")
    parser.add_argument("--awe77-evidence",action="append",default=[],
                        metavar="PLUGIN_ID=REPORT_JSON",help="Verified actual two-sided P220 PCM report, exact VST3 module fingerprint")
    parser.add_argument("--external-capture", action="append", default=[],
                        metavar="PLUGIN_ID=CONTRACT_JSON",
                        help="External capture file and independent reference")
    args=parser.parse_args()
    capture_contracts = {}
    for source in args.external_capture:
        if "=" not in source:
            parser.error("--external-capture requires PLUGIN_ID=CONTRACT_JSON")
        plugin_id, file_path = source.split("=", 1)
        if plugin_id in capture_contracts:
            parser.error("duplicate external-capture plugin id")
        capture_contracts[plugin_id] = file_path
    awe77_reports={}
    for item in args.awe77_evidence:
        if "=" not in item:parser.error("--awe77-evidence requires ID=REPORT.json")
        ident,path=item.split("=",1)
        if ident in awe77_reports:parser.error("duplicate AWE sound report")
        awe77_reports[ident]=path
    try:
        report=review(args.batch,args.out,capture_contracts=capture_contracts,
                      awe77_reports=awe77_reports,required_awe77_ids=args.require_awe77_for)
    except (OSError,ValueError,TypeError,KeyError,IndexError,
            json.JSONDecodeError) as exc:
        args.out.mkdir(parents=True,exist_ok=True)
        report={"schema":SCHEMA,"status":"FAIL","faults":[str(exc)],
                "all_products_release_approved":False}
        (args.out/"UNIFIED-QA-GAPS.json").write_text(
            json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    if report["status"]!="RECONCILED_REPORT_COMPLETE":
        return 1
    # A missing original Creative driver/bank/audio is an unambiguous
    # nonzero exit for an *explicit AWE release check*. Generic technical
    # batch reconciliation remains observational for all other products.
    if args.require_awe77_for and report["awe77_sonic_gate_blocked_or_failed"]:
        print("P220 AWE ORIGINAL SF2 77-SOUND RELEASE BLOCKED",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
