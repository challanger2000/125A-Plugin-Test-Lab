#!/usr/bin/env python3
"""P67 independent, fail-closed product feature coverage gate.

A user-approved feature inventory is NOT inferred from tests, so an omitted
feature cannot silently become "covered". Evidence is accepted only from
the current pinned VST3 execution report, never a textual PASS supplied by
a plugin developer or an external checklist.
"""
import re

SCHEMA = "125a-product-feature-matrix-v1"
ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
REQUIRED = {"required", "optional"}
VALID_WAIVER = {"not_applicable"}


def validate_matrix(matrix, plan):
    if not isinstance(matrix, dict) or set(matrix) != {
            "schema", "product_id", "module_sha256", "features"} or matrix["schema"] != SCHEMA:
        raise ValueError("P67 requires exact independent feature-matrix schema")
    product = plan["product"]
    if (matrix["product_id"] != product["id"] or
            matrix["module_sha256"] != product["sha256"] or
            not isinstance(matrix["module_sha256"], str) or
            not HEX.fullmatch(matrix["module_sha256"])):
        raise ValueError("P67 feature matrix has wrong or stale VST3 identity")
    cases = {c["id"] for c in plan["cases"]}
    features = matrix["features"]
    if not isinstance(features, list) or not 1 <= len(features) <= 256:
        raise ValueError("P67 feature matrix needs 1..256 declared features")
    ids = set()
    for feature in features:
        if not isinstance(feature, dict) or set(feature) != {
                "id", "title", "criticality", "case_ids", "waiver"}:
            raise ValueError("P67 feature matrix has missing or extra keys")
        fid, title, criticality, linked, waiver = (
            feature["id"], feature["title"], feature["criticality"],
            feature["case_ids"], feature["waiver"])
        if not isinstance(fid, str) or not ID.fullmatch(fid) or fid in ids:
            raise ValueError("P67 invalid/duplicate feature ID")
        ids.add(fid)
        if not isinstance(title, str) or not 3 <= len(title) <= 160 or not title.strip():
            raise ValueError("P67 missing meaningful feature description")
        if criticality not in REQUIRED or type(criticality) is not str:
            raise ValueError("P67 feature criticality must be required/optional")
        if (not isinstance(linked, list) or len(linked) > 32
                or any(type(cid) is not str or not ID.fullmatch(cid) for cid in linked)
                or len(set(linked)) != len(linked)):
            raise ValueError("P67 invalid/duplicate links to product test cases")
        if any(cid not in cases for cid in linked):
            raise ValueError("P67 feature references a test absent from approved plan")
        # Waivers are informational only and cannot certify a required
        # feature; they must not become a shortcut to final approval.
        if waiver is not None and (
                not isinstance(waiver, dict) or
                set(waiver) != {"reason", "disposition"} or
                waiver["disposition"] not in VALID_WAIVER or
                type(waiver["reason"]) is not str or
                not 10 <= len(waiver["reason"]) <= 500):
            raise ValueError("P67 waiver requires explicit bounded reason and disposition")
        if criticality == "required" and waiver is not None:
            raise ValueError("P67 required feature cannot be waived in a technical test plan")
        if waiver and linked:
            raise ValueError("P67 waived optional feature cannot also claim test evidence")
    if not any(f["criticality"] == "required" for f in features):
        raise ValueError("P67 needs at least one required feature")
    return features


def evaluate(matrix, plan, report):
    features = validate_matrix(matrix, plan)
    if (not isinstance(report, dict) or
            report.get("schema") != "125a-product-test-plan-result-v1" or
            report.get("product_id") != matrix["product_id"] or
            report.get("verified_module_sha256") != matrix["module_sha256"] or
            report.get("release_approved") is not False):
        raise ValueError("P67 requires matching pinned P65/P66 native execution evidence")
    cases = report.get("cases")
    plan_case_ids = {c["id"] for c in plan["cases"]}
    if (not isinstance(cases, list) or len(cases) != len(plan_case_ids)
            or {c.get("id") for c in cases if isinstance(c, dict)} != plan_case_ids):
        raise ValueError("P67 execution evidence has missing or duplicate cases")
    case_map = {}
    for case in cases:
        if (not isinstance(case, dict) or
                case.get("status") not in {"PASS", "FAIL", "NOT RUN"} or
                type(case.get("verified_actions")) is not int or
                type(case.get("expected_actions")) is not int or
                case["expected_actions"] < 1 or
                not 0 <= case["verified_actions"] <= case["expected_actions"]):
            raise ValueError("P67 malformed native per-case evidence")
        case_map[case["id"]] = case
    if (report.get("declared_cases") != len(plan_case_ids) or
            report.get("passed_cases") != sum(c["status"] == "PASS" for c in cases) or
            report.get("failed_cases") != sum(c["status"] == "FAIL" for c in cases) or
            report.get("not_run_cases") != sum(c["status"] == "NOT RUN" for c in cases)):
        raise ValueError("P67 native test counts disagree with case evidence")
    result = []
    for feature in features:
        links = feature["case_ids"]
        status = "NOT RUN"
        if feature["waiver"] is not None:
            status = "NOT APPLICABLE"
        elif not links:
            status = "NOT COVERED"
        else:
            actual = [case_map[cid] for cid in links]
            if any(c["status"] == "FAIL" for c in actual):
                status = "FAIL"
            elif all(c["status"] == "PASS" and
                     c["verified_actions"] == c["expected_actions"]
                     for c in actual):
                status = "PASS"
            else:
                status = "NOT RUN"
        result.append({
            "id": feature["id"], "title": feature["title"],
            "criticality": feature["criticality"],
            "case_ids": list(links), "status": status
        })
    required = [f for f in result if f["criticality"] == "required"]
    missing = [f["id"] for f in required if f["status"] != "PASS"]
    summary = {
        "schema": "125a-product-feature-coverage-result-v1",
        "status": "REQUIRED_COVERAGE_COMPLETE" if not missing else "REQUIRED_COVERAGE_INCOMPLETE",
        "product_id": matrix["product_id"],
        "verified_module_sha256": matrix["module_sha256"],
        "declared_features": len(result),
        "required_features": len(required),
        "required_passed": len(required) - len(missing),
        "required_unverified": missing,
        "features": result,
        "whole_product_certified": False,
        "physical_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False
    }
    return summary
