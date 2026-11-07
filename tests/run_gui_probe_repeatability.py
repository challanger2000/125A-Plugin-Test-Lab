#!/usr/bin/env python3
"""P84: repeated fresh-instance sham-controlled observation of unknown GUI controls.

An observation that is reproduced is still not an independent functional
oracle. This tests stability, not product semantics or safety.
"""
import argparse
import json
from pathlib import Path

from run_gui_exploration import run as explore, digest

SCHEMA = "125a-repeatable-gui-observation-v1"


def fingerprint(observed):
    if not isinstance(observed, dict) or not isinstance(observed.get("probes"), list):
        raise ValueError("P84 malformed native probe evidence")
    result = []
    for probe in observed["probes"]:
        if not isinstance(probe, dict):
            raise ValueError("P84 missing native probe")
        if probe.get("sham_control_attribution") != "SUPPORTED":
            raise ValueError("P84 unstable sham control")
        changes = probe.get("changed_parameters")
        if not isinstance(changes, list):
            raise ValueError("P84 missing parameter transitions")
        effects = []
        for item in changes:
            if not isinstance(item, dict) or set(item) != {
                    "param_id", "before_normalized", "after_normalized"}:
                raise ValueError("P84 invalid observed native parameter transition")
            effects.append((item["param_id"], item["before_normalized"],
                            item["after_normalized"]))
        effects.sort()
        signature = {
            "x": probe.get("x"), "y": probe.get("y"),
            "classification": probe.get("classification"),
            "native_child_depth": probe.get("native_child_depth"),
            "parameter_transitions": effects,
            # Painted pixels may fluctuate due to rendering, even when the
            # same button genuinely works. Compare visual category only.
            "visual_observed": probe.get("painted_visual_observation") == "OBSERVED"
        }
        if signature["classification"] not in (
                "PARAMETER_CHANGE", "PARAMETER_AND_VISUAL_CHANGE",
                "VISUAL_CHANGE", "NO_OBSERVED_CHANGE"):
            raise ValueError("P84 unusable native classification")
        result.append(signature)
    return result


def run(bundle, gui_host, out, *, points=None, max_points=4, repeats=2,
        timeout=30, explorer=explore):
    if type(repeats) is not int or not 2 <= repeats <= 5:
        raise ValueError("P84 requires 2..5 independent VST3 probe repetitions")
    if type(max_points) is not int or not 1 <= max_points <= 16:
        raise ValueError("P84 requires bounded point count")
    bundle = Path(bundle).resolve(strict=True)
    host = Path(gui_host).resolve(strict=True)
    modules = [p for p in bundle.rglob("*.vst3") if p.is_file()]
    if len(modules) != 1:
        raise ValueError("P84 expects one native VST3 module")
    module = modules[0].resolve(strict=True)
    module_sha, host_sha = digest(module), digest(host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    evidence_path = out / "GUI-REPEATABILITY-RESULT.json"
    evidence_path.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_sha,
        "verified_gui_host_sha256": host_sha,
        "requested_repetitions": repeats, "completed_repetitions": 0,
        "requested_points_per_repetition": None,
        "reproduced_control_signatures": [],
        "identical_fresh_instance_observations": False,
        "semantic_correctness": "NOT ESTABLISHED",
        "release_approved": False, "faults": []
    }
    baseline = None
    try:
        for i in range(repeats):
            if digest(module) != module_sha or digest(host) != host_sha:
                raise ValueError("P84 VST3 or native host changed during repeatability test")
            observed = explorer(
                bundle, host, out / ("repeat-%02d" % (i+1)),
                points=points, max_points=max_points,
                acknowledge=True, timeout=timeout)
            if (not isinstance(observed, dict)
                    or observed.get("schema") != "125a-gui-exploration-result-v1"
                    or observed.get("status") != "OBSERVATIONS_COMPLETE"
                    or observed.get("verified_module_sha256") != module_sha
                    or observed.get("verified_gui_host_sha256") != host_sha
                    or observed.get("sham_control") != "COMPLETE"
                    or observed.get("gui_control_discovery") != "OBSERVATIONS_ONLY"
                    or observed.get("product_gui_controls") != "NOT COVERED"
                    or observed.get("release_approved") is not False
                    or type(observed.get("requested_points")) is not int
                    or observed.get("requested_points") != observed.get("completed_points")
                    or observed.get("requested_points") != observed.get("sham_verified_points")):
                raise ValueError("P84 incomplete or untrusted native sham observation")
            signatures = fingerprint(observed)
            if len(signatures) != observed["requested_points"]:
                raise ValueError("P84 missing native probe signatures")
            if baseline is None:
                baseline = signatures
                report["requested_points_per_repetition"] = len(signatures)
            elif signatures != baseline:
                raise ValueError("P84 fresh VST3 instances disagree about GUI behavior")
            report["completed_repetitions"] += 1
        if digest(module) != module_sha or digest(host) != host_sha:
            raise ValueError("P84 VST3 or native host changed after native probes")
        report.update(status="REPRODUCIBLE_OBSERVATIONS",
                      reproduced_control_signatures=baseline,
                      identical_fresh_instance_observations=True)
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        report["faults"].append(str(exc))
    evidence_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--gui-host", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--points", type=str)
    parser.add_argument("--max-points", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=2)
    a = parser.parse_args()
    report = run(a.plugin, a.gui_host, a.out, points=a.points,
                 max_points=a.max_points, repeats=a.repeats)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "REPRODUCIBLE_OBSERVATIONS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
