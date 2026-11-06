#!/usr/bin/env python3
"""P50 adaptive follow-up of genuinely observed P49 GUI click candidates.

This probes neighboring *coordinates*, not the semantics of any control.
All new clicks retain P42 sham evidence and separate fresh processes.
"""
import argparse
import json
from pathlib import Path
import subprocess

from run_gui_coverage_scan import scan as base_scan
from run_gui_exploration import digest, run as explore

SCHEMA = "125a-adaptive-gui-probing-v1"
CLASSES = {"VISUAL_CHANGE", "PARAMETER_CHANGE", "PARAMETER_AND_VISUAL_CHANGE"}
VALID = CLASSES | {"UNSTABLE_CONTROL", "NO_OBSERVED_CHANGE"}


def neighbors(candidate, width, height, columns, rows):
    if not (1 <= columns <= 16 and 1 <= rows <= 16):
        raise ValueError("invalid tile dimensions")
    x, y = candidate["x"], candidate["y"]
    if type(x) is not int or type(y) is not int or not (0 <= x < width and 0 <= y < height):
        raise ValueError("invalid candidate coordinate")
    dx = max(1, width // (columns * 4))
    dy = max(1, height // (rows * 4))
    return [(a, b) for a, b in
            ((x - dx, y), (x + dx, y), (x, y - dy), (x, y + dy),
             (x - dx, y - dy), (x + dx, y - dy),
             (x - dx, y + dy), (x + dx, y + dy))
            if 0 <= a < width and 0 <= b < height and (a, b) != (x, y)]


def run(plugin, host, out, *, columns=8, rows=8, max_candidates=4,
        acknowledge=False, timeout=25, sampler=base_scan,
        explorer=explore, runner=subprocess.run):
    if acknowledge is not True:
        raise ValueError("P50 requires explicit opt-in for arbitrary native GUI clicks")
    if type(max_candidates) is not int or not 1 <= max_candidates <= 4:
        raise ValueError("P50 supports 1-4 follow-up candidates")
    if type(columns) is not int or type(rows) is not int or not (1 <= columns <= 16 and 1 <= rows <= 16):
        raise ValueError("invalid GUI grid")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("invalid native timeout")
    plugin = Path(plugin).resolve(strict=True)
    host = Path(host).resolve(strict=True)
    modules = [p for p in plugin.rglob("*.vst3") if p.is_file()]
    if plugin.suffix.lower() != ".vst3" or len(modules) != 1 or not host.is_file():
        raise ValueError("invalid native plugin or GUI host")
    module_hash, host_hash = digest(modules[0]), digest(host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    destination = out / "ADAPTIVE-GUI-REPORT.json"
    destination.unlink(missing_ok=True)
    result = {"schema": SCHEMA, "status": "FAIL",
              "verified_module_sha256": module_hash,
              "verified_gui_host_sha256": host_hash,
              "follow_up_points": 0, "confirmed_neighbors": 0,
              "candidates_revisited": 0, "batches": [],
              "observations": [], "faults": [],
              "automatic_control_inventory": "NOT COVERED",
              "independent_product_semantics": "NOT COVERED",
              "commercial_daw_integration": "NOT COVERED",
              "release_approved": False}
    try:
        baseline = sampler(plugin, host, out / "baseline",
                           columns=columns, rows=rows, acknowledge=True,
                           timeout=timeout, runner=runner)
        if (baseline.get("status") != "OBSERVATIONS_COMPLETE"
                or baseline.get("verified_module_sha256") != module_hash
                or baseline.get("verified_gui_host_sha256") != host_hash
                or baseline.get("completed_points") != columns * rows
                or baseline.get("planned_points") != columns * rows):
            raise ValueError("baseline P49 native sham evidence incomplete or mismatched")
        dimensions = baseline.get("editor_dimensions")
        if not isinstance(dimensions, list) or len(dimensions) != 2 or any(type(v) is not int or v < 1 for v in dimensions):
            raise ValueError("missing genuine editor dimensions")
        width, height = dimensions
        original = {(c, r) for c, r in __import__("run_gui_coverage_scan").sample_points(width, height, columns, rows)}
        selected = baseline.get("candidates")
        if not isinstance(selected, list) or baseline.get("candidate_points") != len(selected):
            raise ValueError("P49 candidate inventory mismatch")
        chosen = selected[:max_candidates]
        point_sources = {}
        for candidate in chosen:
            if candidate.get("observation") not in CLASSES or (candidate.get("x"), candidate.get("y")) not in original:
                raise ValueError("P49 candidate not validated against physical sampling")
            for point in neighbors(candidate, width, height, columns, rows):
                if point not in original:
                    point_sources.setdefault(point, []).append([candidate["x"], candidate["y"]])
        points = list(point_sources)
        if len(points) > 32:
            raise ValueError("adaptive probing exceeds strict safety bound")
        result["candidates_revisited"] = len(chosen)
        result["follow_up_points"] = len(points)
        for start in range(0, len(points), 16):
            if digest(modules[0]) != module_hash or digest(host) != host_hash:
                raise ValueError("plugin or host modified during adaptive exploration")
            chunk = points[start:start + 16]
            folder = out / ("follow-up-%02d" % (start // 16 + 1))
            record = explorer(plugin, host, folder,
                              points=";".join("%d,%d" % p for p in chunk),
                              acknowledge=True, timeout=timeout, runner=runner)
            if (record.get("status") != "OBSERVATIONS_COMPLETE"
                    or record.get("schema") != "125a-gui-exploration-result-v1"
                    or record.get("sham_control") != "COMPLETE"
                    or record.get("sham_verified_points") != len(chunk)
                    or record.get("completed_points") != len(chunk)
                    or record.get("verified_module_sha256") != module_hash
                    or record.get("verified_gui_host_sha256") != host_hash
                    or not isinstance(record.get("probes"), list)
                    or len(record["probes"]) != len(chunk)):
                raise ValueError("adaptive native sham evidence incomplete or forged")
            for point, probe in zip(chunk, record["probes"]):
                if (probe.get("x"), probe.get("y")) != point or probe.get("classification") not in VALID:
                    raise ValueError("misattributed adaptive probe")
                state = probe["classification"]
                if state in CLASSES:
                    result["confirmed_neighbors"] += 1
                result["observations"].append({
                    "x": point[0], "y": point[1], "classification": state,
                    "neighbor_of": point_sources[point]})
            result["batches"].append({"path": folder.name + "/GUI-EXPLORATION-RESULT.json",
                                      "points": len(chunk)})
        if digest(modules[0]) != module_hash or digest(host) != host_hash:
            raise ValueError("plugin or host modified after exploration")
        result["status"] = "OBSERVATIONS_COMPLETE"
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        result["faults"].append(str(exc))
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--gui-host", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=8)
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--acknowledge-ui-clicks", action="store_true")
    args = parser.parse_args()
    try:
        report = run(args.plugin, args.gui_host, args.out, columns=args.columns,
                     rows=args.rows, max_candidates=args.max_candidates,
                     timeout=args.timeout, acknowledge=args.acknowledge_ui_clicks)
    except (OSError, ValueError, TypeError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        report = {"schema": SCHEMA, "status": "FAIL", "faults": [str(exc)],
                  "release_approved": False}
        (args.out / "ADAPTIVE-GUI-REPORT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "OBSERVATIONS_COMPLETE" else 1)


if __name__ == "__main__":
    main()
