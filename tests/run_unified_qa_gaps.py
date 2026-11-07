#!/usr/bin/env python3
"""P89: independent one-page consolidated QA result from real P75/P80/P83 batches.

Reconciles source reports; does NOT grant release approval, infer unknown
function semantics, or claim commercial DAW / physical ASIO tests occurred.
"""
import argparse
import json
from pathlib import Path
import re

SCHEMA = "125a-p89-unified-qa-review-v1"
BATCH_SCHEMA = "125a-vst3-batch-report-v1"
CHILD_SCHEMA = "125a-universal-vst3-qa-pipeline-v1"
IDENT = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 2_000_000


def load(path):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("P89 missing or oversized actual QA evidence: " + str(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("P89 native QA evidence must be an object")
    return obj


def review(batch_directory, out):
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
        # P68 ABI discovery is not equivalent to complete product semantics.
        gaps.extend(("PHYSICAL_ASIO_HARDWARE_NOT_TESTED",
                     "COMMERCIAL_DAW_SESSION_NOT_TESTED",
                     "UNKNOWN_PRODUCT_FUNCTION_SEMANTICS_NOT_CERTIFIED"))
        if feature_gaps:
            gaps.append("DECLARED_REQUIRED_FEATURE_GAPS")
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
        "| Plugin | Automated check | Declared functionality | Open acceptance gaps |",
        "| --- | --- | --- | ---: |"
    ]
    for row in rows:
        lines.append("| `%s` | %s | %s | %d |" % (
            row["id"], row["automated_qa_result"],
            row["required_feature_coverage"],
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
    args=parser.parse_args()
    try:
        report=review(args.batch,args.out)
    except (OSError,ValueError,TypeError,KeyError,IndexError,
            json.JSONDecodeError) as exc:
        args.out.mkdir(parents=True,exist_ok=True)
        report={"schema":SCHEMA,"status":"FAIL","faults":[str(exc)],
                "all_products_release_approved":False}
        (args.out/"UNIFIED-QA-GAPS.json").write_text(
            json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["status"]=="RECONCILED_REPORT_COMPLETE" else 1


if __name__=="__main__":
    raise SystemExit(main())
