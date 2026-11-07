#!/usr/bin/env python3
"""P86: bounded dense Win32 VST3 GUI observation audit.

Grid centers are sampled in fresh sham/click VST3 instances. A complete
sampled grid is not a complete inventory of all controls; semantics are never
inferred. Opt-in may activate unsafe plugin actions: use disposable VM only.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
import subprocess

from run_gui_exploration import run as explore, digest, read_bmp
from run_gui_probe_repeatability import run as repeat, fingerprint

SCHEMA = "125a-dense-gui-audit-v1"


def grid_coordinates(width, height, side):
    if side not in (3, 5):
        raise ValueError("P86 grid side supports only 3 or 5")
    if not 0 < width <= 4096 or not 0 < height <= 4096:
        raise ValueError("P86 invalid native GUI dimensions")
    return [(min(width-1, (width*(x*2+1))//(side*2)),
             min(height-1, (height*(y*2+1))//(side*2)))
            for y in range(side) for x in range(side)]


def run(bundle, gui_host, out, *, side=3, repeats=2, timeout=35,
        snapshot_runner=subprocess.run, explorer=explore, repeater=repeat):
    if type(side) is not int or side not in (3, 5):
        raise ValueError("P86 supported grid side: 3 or 5")
    if type(repeats) is not int or repeats not in (1, 2):
        raise ValueError("P86 bounded repeat count: 1 or 2")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("P86 bounded native host timeout: 5..90")
    bundle, host = Path(bundle).resolve(strict=True), Path(gui_host).resolve(strict=True)
    if not bundle.is_dir() or bundle.suffix.lower() != ".vst3" or not host.is_file():
        raise ValueError("P86 real VST3 bundle/GUI host required")
    modules = [p for p in bundle.rglob("*.vst3") if p.is_file()]
    if len(modules) != 1:
        raise ValueError("P86 exactly one native VST3 module required")
    module = modules[0].resolve(strict=True)
    module_sha, host_sha = digest(module), digest(host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "DENSE-GUI-AUDIT-RESULT.json"
    report_path.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_sha,
        "verified_gui_host_sha256": host_sha,
        "grid_side": side, "repeat_count": repeats,
        "planned_points": side*side, "completed_points": 0,
        "sham_click_pairs": 0, "distinct_observed_candidates": 0,
        "observed_parameter_ids": [],
        "visual_only_candidate_points": 0,
        "no_observed_change_points": 0,
        "observations": [],
        "control_semantics": "NOT ESTABLISHED",
        "all_controls_discovered": False, "all_product_features_tested": False,
        "safe_to_run_on_unknown_untrusted_plugin": False,
        "release_approved": False, "faults": []
    }
    try:
        if side == 5:
            # 5x5 requires two batches since the P42 native protocol accepts
            # at most 16 coordinates. Never silently truncate the last 9.
            assert side*side == 25
        untouched = out / "untouched-editor.bmp"
        untouched.unlink(missing_ok=True)
        native = snapshot_runner([str(host), "--snapshot-editor", str(bundle), str(untouched)],
                                 capture_output=True, text=True, check=False,
                                 errors="replace", timeout=timeout)
        if native.returncode != 0 or not untouched.is_file():
            raise ValueError("P86 failed to measure actual VST3 editor")
        width, height, _ = read_bmp(untouched)
        positions = grid_coordinates(width, height, side)
        if len(set(positions)) != len(positions):
            raise ValueError("P86 small editor causes ambiguous overlapping probes")
        result["editor_dimensions"] = [width, height]
        observed_ids = set()
        classifications = Counter()
        for offset in range(0, len(positions), 16):
            batch = positions[offset:offset+16]
            coordinates = ";".join("%d,%d" % point for point in batch)
            group = out / ("grid-%02d" % (offset//16+1))
            if digest(module) != module_sha or digest(host) != host_sha:
                raise ValueError("P86 native executables changed between shards")
            if repeats == 2:
                evidence = repeater(bundle, host, group, points=coordinates,
                                    max_points=len(batch), repeats=2, timeout=timeout)
                if (not isinstance(evidence, dict)
                        or evidence.get("schema") != "125a-repeatable-gui-observation-v1"
                        or evidence.get("status") != "REPRODUCIBLE_OBSERVATIONS"
                        or evidence.get("verified_module_sha256") != module_sha
                        or evidence.get("verified_gui_host_sha256") != host_sha
                        or evidence.get("completed_repetitions") != 2
                        or evidence.get("requested_points_per_repetition") != len(batch)
                        or evidence.get("identical_fresh_instance_observations") is not True
                        or evidence.get("semantic_correctness") != "NOT ESTABLISHED"
                        or evidence.get("release_approved") is not False):
                    raise ValueError("P86 native repeated grid shard incomplete")
                signatures = evidence.get("reproduced_control_signatures")
            else:
                evidence = explorer(bundle, host, group, points=coordinates,
                                    max_points=len(batch), acknowledge=True,
                                    timeout=timeout)
                if (not isinstance(evidence, dict)
                        or evidence.get("schema") != "125a-gui-exploration-result-v1"
                        or evidence.get("status") != "OBSERVATIONS_COMPLETE"
                        or evidence.get("verified_module_sha256") != module_sha
                        or evidence.get("verified_gui_host_sha256") != host_sha
                        or evidence.get("completed_points") != len(batch)
                        or evidence.get("sham_verified_points") != len(batch)
                        or evidence.get("sham_control") != "COMPLETE"
                        or evidence.get("release_approved") is not False):
                    raise ValueError("P86 native grid shard missing sham evidence")
                signatures = fingerprint(evidence)
            if not isinstance(signatures, list) or len(signatures) != len(batch):
                raise ValueError("P86 native result missed grid coordinates")
            for (x,y), entry in zip(batch, signatures):
                if (not isinstance(entry, dict) or
                        entry.get("x") != x or entry.get("y") != y or
                        entry.get("classification") not in (
                            "PARAMETER_CHANGE", "PARAMETER_AND_VISUAL_CHANGE",
                            "VISUAL_CHANGE", "NO_OBSERVED_CHANGE") or
                        not isinstance(entry.get("parameter_transitions"), list)):
                    raise ValueError("P86 mismatched or malformed candidate coordinate")
                classifications[entry["classification"]] += 1
                for parameter in entry["parameter_transitions"]:
                    if not isinstance(parameter, (tuple, list)) or len(parameter) != 3:
                        raise ValueError("P86 missing native parameter change")
                    if type(parameter[0]) is not int:
                        raise ValueError("P86 invalid native parameter identifier")
                    observed_ids.add(parameter[0])
                result["observations"].append(entry)
                result["completed_points"] += 1
                result["sham_click_pairs"] += repeats
        if digest(module) != module_sha or digest(host) != host_sha:
            raise ValueError("P86 binary identity changed during grid observation")
        if result["completed_points"] != side*side:
            raise ValueError("P86 not all native grid points observed")
        result.update(
            status="SAMPLED_GRID_COMPLETE",
            observed_parameter_ids=sorted(observed_ids),
            distinct_observed_candidates=side*side-classifications["NO_OBSERVED_CHANGE"],
            visual_only_candidate_points=classifications["VISUAL_CHANGE"],
            no_observed_change_points=classifications["NO_OBSERVED_CHANGE"]
        )
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            subprocess.TimeoutExpired) as exc:
        result["faults"].append(str(exc))
    report_path.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--gui-host", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--grid-side", type=int, choices=(3,5), default=3)
    p.add_argument("--repeats", type=int, choices=(1,2), default=2)
    a = p.parse_args()
    report = run(a.plugin, a.gui_host, a.out, side=a.grid_side,
                 repeats=a.repeats)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "SAMPLED_GRID_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
