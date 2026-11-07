#!/usr/bin/env python3
"""P75: independent, crash-isolated batch QA for any Windows x64 VST3s.

Every plugin gets its own bounded Python/native process tree and evidence
directory; a crash, timeout or broken VST3 cannot turn other plugins into
unverified PASS. Default is read-only universal inventory, never automatic
interactive clicks or commercial release certification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from run_vst3_auto_discovery import verify_bundle, digest
from run_universal_qa import preflight as preflight_product

SCHEMA = "125a-vst3-batch-selection-v1"
RESULT = "125a-vst3-batch-report-v1"
ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
MAX_PLUGINS = 32
ALLOWED = {"INVENTORY_COMPLETE", "TECHNICAL_BASELINE_PASS"}


def load_selection(selection=None, root=None, *, technical_all=False):
    if (selection is None) == (root is None):
        raise ValueError("P75 specify exactly one selection manifest or plugin root")
    if selection is not None:
        obj = json.loads(Path(selection).read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or set(obj) != {"schema", "plugins"} or obj["schema"] != SCHEMA:
            raise ValueError("P75 exact versioned batch-selection schema required")
        items = obj["plugins"]
        if not isinstance(items, list) or not 1 <= len(items) <= MAX_PLUGINS:
            raise ValueError("P75 manifest must select 1..32 VST3 plugins")
        if technical_all:
            raise ValueError("P75 per-plugin manifest controls technical enablement")
    else:
        root = Path(root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("P75 root must be an existing directory")
        found = sorted((p for p in root.rglob("*.vst3") if p.is_dir()),
                       key=lambda p: str(p).lower())
        if not 1 <= len(found) <= MAX_PLUGINS:
            raise ValueError("P75 root scan must contain 1..32 VST3 bundles")
        items = [{
            "id": ("plugin_%02d" % index),
            "bundle": str(bundle), "run_technical_baseline": technical_all
        } for index, bundle in enumerate(found, 1)]
    selected, ids, paths = [], set(), set()
    for item in items:
        if not isinstance(item, dict) or not {"id", "bundle", "run_technical_baseline"} <= set(item) or (
                set(item) - {"id", "bundle", "run_technical_baseline", "approved_plan", "feature_matrix"}):
            raise ValueError("P75 unsupported plugin batch selection fields")
        ident = item["id"]
        if type(ident) is not str or not ID.fullmatch(ident) or ident in ids:
            raise ValueError("P75 invalid or duplicate plugin id")
        if type(item["run_technical_baseline"]) is not bool:
            raise ValueError("P75 technical option must be an explicit boolean")
        if ("approved_plan" in item) != ("feature_matrix" in item):
            raise ValueError("P80 approved plan and matrix must be paired")
        if "approved_plan" in item and (
                type(item["approved_plan"]) is not str or
                type(item["feature_matrix"]) is not str or
                not item["approved_plan"] or not item["feature_matrix"]):
            raise ValueError("P80 invalid approved plan/matrix reference")
        bundle, module = verify_bundle(item["bundle"])
        if bundle in paths:
            raise ValueError("P75 duplicate VST3 bundle in selection")
        paths.add(bundle)
        ids.add(ident)
        selected.append({
            "id": ident, "bundle": bundle, "module": module,
            "sha256": digest(module), "run_technical_baseline":
                item["run_technical_baseline"],
            **({"approved_plan": str(Path(item["approved_plan"]).resolve(strict=True)),
                "feature_matrix": str(Path(item["feature_matrix"]).resolve(strict=True))}
               if "approved_plan" in item else {})
        })
    return selected


def run(selected, gui_host, out, *, audio_host=None, stress_host=None,
        per_plugin_timeout=600, native_timeout=110,
        runner=subprocess.run):
    if type(per_plugin_timeout) is not int or not 45 <= per_plugin_timeout <= 1800:
        raise ValueError("P75 invalid bounded per-plugin process timeout")
    if type(native_timeout) is not int or not 5 <= native_timeout <= 120:
        raise ValueError("P75 invalid native operation timeout")
    if not isinstance(selected, list) or not 1 <= len(selected) <= MAX_PLUGINS:
        raise ValueError("P75 empty/oversized selection")
    gui = Path(gui_host).resolve(strict=True)
    if not gui.is_file():
        raise ValueError("P75 native VST3 GUI host required")
    if (audio_host is None) != (stress_host is None):
        raise ValueError("P75 audio/state stress hosts must be supplied together")
    audio = Path(audio_host).resolve(strict=True) if audio_host else None
    stress = Path(stress_host).resolve(strict=True) if stress_host else None
    if audio is not None and (not audio.is_file() or not stress.is_file()):
        raise ValueError("P75 missing real audio/stress host")
    if any(s["run_technical_baseline"] for s in selected) and audio is None:
        raise ValueError("P75 technical selected without audio/state hosts")
    identities = {gui: digest(gui)}
    if audio is not None:
        identities[audio] = digest(audio)
        identities[stress] = digest(stress)
    observed_ids, observed_paths = set(), set()
    for entry in selected:
        if (not isinstance(entry, dict) or
                not {"id", "bundle", "module", "sha256",
                     "run_technical_baseline"} <= set(entry) or
                set(entry) - {"id", "bundle", "module", "sha256",
                              "run_technical_baseline", "approved_plan",
                              "feature_matrix"} or
                ("approved_plan" in entry) != ("feature_matrix" in entry) or
                type(entry["id"]) is not str or not ID.fullmatch(entry["id"]) or
                entry["id"] in observed_ids or
                type(entry["run_technical_baseline"]) is not bool):
            raise ValueError("P75 invalid duplicated selected plugin record")
        bundle, module = verify_bundle(entry["bundle"])
        if bundle in observed_paths or module != entry["module"] or (
                digest(module) != entry["sha256"]):
            raise ValueError("P75 plugin selection changed before test execution")
        observed_ids.add(entry["id"])
        observed_paths.add(bundle)
    # Validate all reviewed product plans before any VST3 execution.
    pinned_contracts = {}
    for entry in selected:
        if "approved_plan" not in entry:
            continue
        plan_path = Path(entry["approved_plan"]).resolve(strict=True)
        matrix_path = Path(entry["feature_matrix"]).resolve(strict=True)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        preflight_product(plan, matrix, entry["module"], gui, audio, stress)
        pinned_contracts[entry["id"]] = (
            plan_path, matrix_path, digest(plan_path), digest(matrix_path))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "BATCH-QA-REPORT.json"
    target.unlink(missing_ok=True)
    report = {
        "schema": RESULT, "status": "FAIL", "declared_plugins": len(selected),
        "passed_plugins": 0, "failed_plugins": 0,
        "plugins": [], "gui_clicks_automatically_authorized": 0,
        "full_product_coverage": "NOT ESTABLISHED",
        "physical_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False
    }
    script = Path(__file__).with_name("run_universal_qa.py").resolve()
    for index, entry in enumerate(selected):
        ident = entry["id"]
        folder = out / ("%02d-%s" % (index+1, ident))
        folder.mkdir(parents=True, exist_ok=True)
        row = {"id": ident, "bundle": str(entry["bundle"]),
               "verified_module_sha256": entry["sha256"],
               "status": "FAIL", "technical_requested":
                   entry["run_technical_baseline"], "faults": []}
        try:
            if (digest(entry["module"]) != entry["sha256"] or
                    any(digest(path) != value for path, value in identities.items())):
                raise ValueError("P75 native binaries changed before child process")
            cmd = [sys.executable, str(script), "--plugin", str(entry["bundle"]),
                   "--gui-host", str(gui), "--out", str(folder),
                   "--timeout", str(native_timeout)]
            if audio is not None:
                cmd += ["--audio-host", str(audio), "--stress-host", str(stress)]
            if entry["run_technical_baseline"]:
                cmd += ["--run-technical-baseline"]
            if ident in pinned_contracts:
                pp, mp, ph, mh = pinned_contracts[ident]
                if digest(pp) != ph or digest(mp) != mh:
                    raise ValueError("P80 reviewed product plan changed before run")
                cmd += ["--approved-plan", str(pp), "--feature-matrix", str(mp)]
            process = runner(cmd, capture_output=True, text=True,
                             errors="replace", check=False,
                             timeout=per_plugin_timeout)
            (folder / "batch-child.log").write_text(
                (process.stdout or "")[-32000:] + "\n" +
                (process.stderr or "")[-32000:], encoding="utf-8")
            result_path = folder / "UNIVERSAL-QA-RESULT.json"
            if not result_path.is_file() or result_path.stat().st_size > 2_000_000:
                raise ValueError("P75 child did not produce bounded trustworthy JSON evidence")
            outcome = json.loads(result_path.read_text(encoding="utf-8"))
            expected = ("DECLARED_COVERAGE_PASS" if ident in pinned_contracts else
                        "TECHNICAL_BASELINE_PASS" if
                        entry["run_technical_baseline"] else "INVENTORY_COMPLETE")
            if (process.returncode != 0 or
                    not isinstance(outcome, dict) or
                    outcome.get("schema") != "125a-universal-vst3-qa-pipeline-v1" or
                    outcome.get("status") != expected or
                    outcome.get("verified_module_sha256") != entry["sha256"] or
                    outcome.get("verified_gui_host_sha256") != identities[gui] or
                    outcome.get("discovery") != "PASS" or
                    outcome.get("gui_clicks_automatically_authorized") != 0 or
                    outcome.get("release_approved") is not False or
                    outcome.get("required_feature_coverage") != (
                        "REQUIRED_COVERAGE_COMPLETE" if ident in pinned_contracts
                        else "NOT DECLARED") or
                    (ident in pinned_contracts and
                     outcome.get("approved_product_cases") != "CONTRACT_PASS") or
                    (entry["run_technical_baseline"] and
                     outcome.get("native_technical") != "PASS")):
                raise ValueError("P75 child failed or returned forged/incomplete actual VST3 QA")
            if digest(entry["module"]) != entry["sha256"] or any(
                    digest(path) != value for path, value in identities.items()):
                raise ValueError("P75 native binaries were changed by child process")
            if ident in pinned_contracts:
                pp, mp, ph, mh = pinned_contracts[ident]
                if digest(pp) != ph or digest(mp) != mh:
                    raise ValueError("P80 reviewed product plan changed during run")
            row["status"] = "PASS"
            row["verified_stage"] = expected
            row["required_feature_coverage"] = outcome["required_feature_coverage"]
        except (OSError, ValueError, TypeError, KeyError,
                json.JSONDecodeError, subprocess.TimeoutExpired) as error:
            row["faults"].append(str(error))
        report["plugins"].append(row)
    report["passed_plugins"] = sum(x["status"] == "PASS" for x in report["plugins"])
    report["failed_plugins"] = sum(x["status"] == "FAIL" for x in report["plugins"])
    if report["passed_plugins"] == report["declared_plugins"]:
        report["status"] = ("BATCH_DECLARED_COVERAGE_PASS" if
                            pinned_contracts else "BATCH_TECHNICAL_PASS")
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--selection", type=Path)
    group.add_argument("--plugins-root", type=Path)
    p.add_argument("--gui-host", type=Path, required=True)
    p.add_argument("--audio-host", type=Path)
    p.add_argument("--stress-host", type=Path)
    p.add_argument("--run-technical-baseline", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--per-plugin-timeout", type=int, default=600)
    p.add_argument("--native-timeout", type=int, default=110)
    args = p.parse_args()
    try:
        selected = load_selection(
            args.selection, args.plugins_root,
            technical_all=args.run_technical_baseline)
        report = run(selected, args.gui_host, args.out,
                     audio_host=args.audio_host, stress_host=args.stress_host,
                     per_plugin_timeout=args.per_plugin_timeout,
                     native_timeout=args.native_timeout)
    except (OSError, ValueError, TypeError, KeyError,
            json.JSONDecodeError) as error:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": RESULT, "status": "FAIL",
                  "faults": [str(error)], "release_approved": False}
        (args.out / "BATCH-QA-REPORT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] in (
        "BATCH_TECHNICAL_PASS", "BATCH_DECLARED_COVERAGE_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
