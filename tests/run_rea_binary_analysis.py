#!/usr/bin/env python3
"""P99: explicitly requested REA/Ghidra observation, never a functional QA pass."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess

SCHEMA = "125a-rea-binary-observation-v1"
MAX_OUTPUT = 2_000_000


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def analyze(binary, out, *, node, entry, timeout=120, runner=subprocess.run):
    if type(timeout) is not int or not 30 <= timeout <= 600:
        raise ValueError("P99 timeout must be between 30 and 600 seconds")
    binary, node, entry = (Path(p).resolve(strict=True)
                           for p in (binary, node, entry))
    if any(not p.is_file() for p in (binary, node, entry)):
        raise ValueError("P99 target, Node and REA entry must be existing files")
    pinned = {p: digest(p) for p in (binary, node, entry)}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    raw_path, report_path = out / "REA-RAW-OUTPUT.json", out / "REA-RESULT.json"
    raw_path.unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA, "status": "FAIL",
        "binary_sha256": pinned[binary],
        "node_sha256": pinned[node], "rea_entry_sha256": pinned[entry],
        "rea_exit_code": None, "raw_sha256": None,
        "semantic_verification": "NOT ESTABLISHED",
        "observed_provider": None, "rea_evidence_id": None,
        "release_approved": False, "faults": [],
    }
    try:
        process = runner(
            [str(node), str(entry), "inspect", str(binary),
             "--provider", "ghidra", "--json"],
            capture_output=True, text=True, errors="replace",
            check=False, timeout=timeout)
        report["rea_exit_code"] = process.returncode
        if process.returncode != 0:
            raise ValueError("P99 REA failed: " + (process.stderr or "")[-400:])
        raw = process.stdout
        if not isinstance(raw, str) or not 0 < len(raw.encode("utf-8")) <= MAX_OUTPUT:
            raise ValueError("P99 missing or oversized JSON output")
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get("ok") is False or value.get("error"):
            raise ValueError("P99 REA returned an error rather than native Evidence")
        # REA 6.8+ publishes one canonical Evidence record per native
        # inspection. A nonempty arbitrary dict is *not* analysis evidence.
        evidence_id = value.get("evidence_id")
        subject = value.get("subject")
        provider = value.get("provider")
        observed = value.get("normalized_result")
        failures = []
        if not isinstance(evidence_id, str) or re.fullmatch(
                r"ev_[0-9a-f]{64}", evidence_id) is None:
            failures.append("evidence_id")
        if not isinstance(provider, dict) or provider.get("id") != "ghidra":
            failures.append("provider_id")
        if (not isinstance(subject, dict)
                or not isinstance(subject.get("digest"), dict)
                or subject["digest"].get("sha256") != pinned[binary]):
            failures.append("subject_digest")
        if not isinstance(observed, dict) or not observed:
            failures.append("normalized_result")
        if not isinstance(value.get("operation"), str) or not value["operation"]:
            failures.append("operation")
        if failures:
            # Report field *names only*, never private decompiled data.
            known_keys = ",".join(sorted(str(k) for k in value.keys())[:24])
            # Provider identity and field names are public metadata; only
            # those fields may appear in logs, never recovered instructions.
            provider_id = (provider.get("id") if isinstance(provider, dict)
                           else type(provider).__name__)
            profile = value.get("analysis_profile")
            profile_provider = (profile.get("provider") if isinstance(profile, dict)
                                else None)
            profile_id = (profile_provider.get("id")
                          if isinstance(profile_provider, dict) else None)
            raise ValueError(
                "P99 canonical Ghidra Evidence mismatch: " +
                ",".join(failures) + "; observed provider id: " +
                str(provider_id)[:80] + "; profile provider id: " +
                str(profile_id)[:80] + "; top-level keys: " + known_keys)
        if any(digest(p) != sha for p, sha in pinned.items()):
            raise ValueError("P99 target or REA tools mutated during analysis")
        raw_path.write_text(raw, encoding="utf-8")
        report["raw_sha256"] = digest(raw_path)
        report["observed_provider"] = provider["id"]
        report["rea_evidence_id"] = evidence_id
        report["status"] = "OBSERVATION_CAPTURED"
    except (OSError, ValueError, TypeError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as error:
        report["faults"].append(str(error)[:1200])
        raw_path.unlink(missing_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", required=True, type=Path)
    p.add_argument("--node", required=True, type=Path)
    p.add_argument("--rea-entry", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()
    try:
        result = analyze(args.binary, args.out, node=args.node,
                         entry=args.rea_entry, timeout=args.timeout)
    except (OSError, ValueError, TypeError) as error:
        args.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL", "faults": [str(error)],
                  "semantic_verification": "NOT ESTABLISHED", "release_approved": False}
        (args.out / "REA-RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "OBSERVATION_CAPTURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
