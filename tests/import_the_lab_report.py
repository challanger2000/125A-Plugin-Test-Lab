#!/usr/bin/env python3
"""Import a manually exported THE_LAB JSON/CSV as untrusted external QA evidence.

Does not launch THE_LAB, infer its version, trust vendor verdicts, check DSP
measurements against an oracle, or approve a 125A plugin release.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

SCHEMA = "125a-external-the-lab-report-import-v1"
MAX_BYTES = 4_000_000
HEX = re.compile(r"^[0-9a-f]{64}$")


def digest_bytes(content):
    return hashlib.sha256(content).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def approved_sha(value, label):
    if type(value) is not str or not HEX.fullmatch(value):
        raise ValueError("THE_LAB invalid independently pinned " + label)
    return value


def reject_constant(value):
    raise ValueError("THE_LAB nonfinite JSON numeric constant: " + value)


def finite_float(value):
    out = float(value)
    if not math.isfinite(out):
        raise ValueError("THE_LAB JSON numeric literal exceeds finite range")
    return out


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("THE_LAB duplicate JSON key: " + key)
        result[key] = value
    return result


def inspect_export(content, suffix):
    if not content or b"\x00" in content:
        raise ValueError("THE_LAB empty or binary export")
    try:
        source = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("THE_LAB export is not UTF-8 text") from exc
    if not source.strip():
        raise ValueError("THE_LAB empty export")
    if suffix == ".json":
        try:
            obj = json.loads(source, parse_constant=reject_constant,
                             parse_float=finite_float,
                             object_pairs_hook=unique_keys)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("THE_LAB malformed JSON export") from exc
        if not isinstance(obj, (dict, list)) or not obj:
            raise ValueError("THE_LAB JSON export must contain an object or list")
        return {"format": "JSON", "top_level_type": type(obj).__name__}
    if suffix == ".csv":
        try:
            # A semicolon or tab is common in international CSV exports.
            try:
                dialect = csv.Sniffer().sniff(source[:4096], delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = csv.reader(io.StringIO(source, newline=""), dialect)
            header = next(rows)
            if not 1 <= len(header) <= 128 or any(not x.strip() for x in header):
                raise ValueError("THE_LAB invalid CSV headers")
            if len(set(header)) != len(header):
                raise ValueError("THE_LAB ambiguous duplicate CSV header")
            n = 0
            for row in rows:
                n += 1
                if n > 100_000 or len(row) != len(header):
                    raise ValueError("THE_LAB unbounded or ragged CSV rows")
            if n == 0:
                raise ValueError("THE_LAB CSV has no measurement rows")
        except (csv.Error, StopIteration) as exc:
            raise ValueError("THE_LAB malformed CSV export") from exc
        return {"format": "CSV", "columns": len(header), "rows": n}
    raise ValueError("THE_LAB only manual .json or .csv measurement exports accepted")


def import_report(module, module_sha256, report, report_sha256, out,
                  *, declared_version="NOT VERIFIED"):
    module = Path(module).resolve(strict=True)
    report = Path(report).resolve(strict=True)
    expected_module = approved_sha(module_sha256, "VST3 binary SHA256")
    expected_report = approved_sha(report_sha256, "THE_LAB export SHA256")
    if not module.is_file() or not report.is_file() or module == report:
        raise ValueError("THE_LAB distinct existing module and exported report required")
    if not (type(declared_version) is str and 1 <= len(declared_version) <= 40):
        raise ValueError("THE_LAB invalid version metadata")
    if digest(module) != expected_module:
        raise ValueError("THE_LAB VST3 binary does not match pinned SHA256")
    size = report.stat().st_size
    if size <= 0 or size > MAX_BYTES:
        raise ValueError("THE_LAB export size outside bounded range")
    content = report.read_bytes()
    if len(content) != size or digest_bytes(content) != expected_report:
        raise ValueError("THE_LAB export differs from pinned SHA256")
    parsed = inspect_export(content, report.suffix.lower())
    out = Path(out).resolve()
    evidence_file = out / "THE-LAB-EXTERNAL-OBSERVATION.json"
    copy_file = out / ("THE-LAB-ORIGINAL" + report.suffix.lower())
    if evidence_file in (module, report) or copy_file in (module, report):
        raise ValueError("THE_LAB output would overwrite input")
    out.mkdir(parents=True, exist_ok=True)
    # Remove any prior success artifact before attempting to write new evidence.
    evidence_file.unlink(missing_ok=True)
    copy_file.write_bytes(content)
    if digest(copy_file) != expected_report or digest(report) != expected_report:
        copy_file.unlink(missing_ok=True)
        raise ValueError("THE_LAB copied or source report changed during import")
    if digest(module) != expected_module:
        copy_file.unlink(missing_ok=True)
        raise ValueError("THE_LAB module changed during report import")
    result = {
        "schema": SCHEMA,
        "status": "EXTERNAL_REPORT_IMPORTED_SOURCE_UNATTESTED",
        "source": "USER_SUPPLIED_EXPORT",
        "software": "Phil Speiser THE_LAB",
        "software_version": declared_version,
        "software_version_provenance": "USER_DECLARED_NOT_ATTESTED",
        "verified_module_sha256": expected_module,
        "verified_export_sha256": expected_report,
        "imported_export": copy_file.name,
        "export_bytes": size,
        "structure": parsed,
        "original_application_execution": "NOT RUN",
        "original_measurements_verified": False,
        "vendor_report_authenticity_verified": False,
        "vendor_verdict": "NOT INTERPRETED",
        "independent_dsp_oracle": "NOT RUN",
        "physical_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "product_feature_coverage": "NOT VERIFIED",
        "release_approved": False,
    }
    evidence_file.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                             encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, required=True,
                        help="Exact VST3 module binary (inside a .vst3 bundle if needed)")
    parser.add_argument("--module-sha256", required=True,
                        help="Independently approved actual VST3 module digest")
    parser.add_argument("--report", type=Path, required=True,
                        help="Manually exported original THE_LAB JSON or CSV")
    parser.add_argument("--report-sha256", required=True,
                        help="Independently captured export digest")
    parser.add_argument("--the-lab-version", default="NOT VERIFIED",
                        help="User-declared app version, never independently attested")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = import_report(args.module, args.module_sha256, args.report,
                               args.report_sha256, args.out,
                               declared_version=args.the_lab_version)
    except (ValueError, OSError, TypeError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        target = args.out / "THE-LAB-EXTERNAL-OBSERVATION.json"
        target.unlink(missing_ok=True)
        for extension in (".json", ".csv"):
            (args.out / ("THE-LAB-ORIGINAL" + extension)).unlink(missing_ok=True)
        failure = {"schema": SCHEMA, "status": "FAIL",
                   "error": str(exc), "release_approved": False,
                   "original_measurements_verified": False}
        target.write_text(json.dumps(failure, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(failure, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
