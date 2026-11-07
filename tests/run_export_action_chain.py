#!/usr/bin/env python3
"""P77: approved native GUI action -> freshly generated WAV/MIDI -> P76 oracle.

This is a generic, explicitly planned workflow, not discovery of arbitrary exporters.
Outputs must be absent BEFORE any native GUI action (no deletion or stale-file reuse).
"""
import argparse
import json
import os
import stat
import time
from pathlib import Path

from run_gui_workflow import validate as validate_gui, run as run_gui, digest
from run_export_artifact_oracle import validate as validate_export, verify as verify_export

SCHEMA = "125a-export-action-chain-v1"
RESULT = "125a-export-action-chain-result-v1"


def validate(chain):
    if not isinstance(chain, dict) or set(chain) != {"schema", "workflow", "export"} or chain["schema"] != SCHEMA:
        raise ValueError("P77 exact approved action-chain schema required")
    workflow, export = chain["workflow"], chain["export"]
    host, bundle, module, _, steps = validate_gui(workflow)
    outputs = validate_export(export, digest(module))
    if not steps or not outputs:
        raise ValueError("P77 requires an approved action and independent output assertions")
    # An export action cannot be inferred from a parameter value; approval is explicit.
    # Both inputs are verified before the first click, and all output paths must be free.
    resolved = [Path(item["path"]).resolve() for item in outputs]
    if len(set(resolved)) != len(resolved):
        raise ValueError("P77 duplicate output destinations")
    # lexists includes broken symlinks, unlike Path.exists().
    if any(os.path.lexists(path) for path in resolved):
        raise ValueError("P78 output destination occupied, including symlink")
    for path in resolved:
        if path in (host, module, Path(__file__).resolve()):
            raise ValueError("P78 export path collides with executable")
        if not path.parent.is_dir():
            raise ValueError("P78 output directory must exist")
    return host, module, len(steps), resolved


def run(chain, out, *, gui_runner=run_gui, export_verifier=verify_export, timeout=90):
    # Fail closed before dispatch: no output clearing, no implicit shell commands.
    host, module, count, paths = validate(chain)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "EXPORT-ACTION-CHAIN-RESULT.json"
    report_path.unlink(missing_ok=True)
    module_hash, host_hash = digest(module), digest(host)
    report = {
        "schema": RESULT, "status": "FAIL",
        "verified_module_sha256": module_hash,
        "verified_gui_host_sha256": host_hash,
        "expected_actions": count, "verified_actions": 0,
        "expected_outputs": len(paths), "verified_outputs": 0,
        "actual_plugin_export_tested": False,
        "export_origin": "NOT ESTABLISHED",
        "provenance_verified": False,
        "release_approved": False, "faults": []
    }
    try:
        # Capture wall-clock before dispatch; freshness alone does not prove authorship.
        action_started_ns = time.time_ns()
        observed = gui_runner(chain["workflow"], out / "actions", timeout=timeout)
        if (not isinstance(observed, dict) or observed.get("status") != "TECHNICAL_PASS"
                or observed.get("verified_module_sha256") != module_hash
                or observed.get("gui_host_sha256") != host_hash
                or observed.get("declared_actions") != count
                or observed.get("verified_actions") != count
                or observed.get("release_approved") is True):
            raise ValueError("P77 native GUI action evidence incomplete")
        report["verified_actions"] = count
        if digest(module) != module_hash or digest(host) != host_hash:
            raise ValueError("P77 executable identity changed")
        for path in paths:
            st = path.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                raise ValueError("P78 export must be a regular nonlinked file")
            if st.st_mtime_ns < action_started_ns:
                raise ValueError("P78 export predates GUI action")
            if st.st_size < 1:
                raise ValueError("P78 export is empty")
        evidence = export_verifier(chain["export"], out / "artifacts", module_sha=module_hash)
        if (not isinstance(evidence, dict) or evidence.get("status") != "ARTIFACT_PASS"
                or evidence.get("verified_module_sha256") != module_hash
                or evidence.get("declared_actions") != len(paths)
                or evidence.get("verified_actions") != len(paths)
                or evidence.get("release_approved") is not False
                or not isinstance(evidence.get("outputs"), list)
                or len(evidence["outputs"]) != len(paths)
                or any(e.get("status") != "PASS" for e in evidence["outputs"])):
            raise ValueError("P77 independent WAV/MIDI oracle rejected generated output")
        if digest(module) != module_hash or digest(host) != host_hash:
            raise ValueError("P77 executable identity changed after oracle")
        # Verified new output is not proof that the plugin wrote it:
        # another process could have written matching bytes.
        report.update(status="ACTION_AND_ARTIFACT_PASS",
                      verified_outputs=len(paths),
                      actual_plugin_export_tested=False,
                      export_origin="UNATTRIBUTED_AFTER_NATIVE_GUI_ACTION",
                      provenance_verified=False)
    except (ValueError, OSError, TypeError, KeyError, IndexError) as exc:
        report["faults"].append(str(exc))
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chain", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()
    try:
        chain = json.loads(args.chain.read_text(encoding="utf-8"))
        report = run(chain, args.out, timeout=args.timeout)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "ACTION_AND_ARTIFACT_PASS" else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("P77 preflight FAIL: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
