#!/usr/bin/env python3
"""P49: Bounded multi-pass GUI observations, using the existing P42-P44 host.

Only probes physical sample points; never claims an exhaustive control
inventory, semantic correctness, or DAW/release approval.
"""
import argparse
import json
from pathlib import Path
import subprocess

from run_gui_exploration import digest, read_bmp, run as explore

SCHEMA = "125a-gui-coverage-scan-v1"


def sample_points(width, height, columns, rows):
    """Distinct deterministic interior tile centers, row-major."""
    if not (1 <= columns <= 16 and 1 <= rows <= 16):
        raise ValueError("grid dimensions must be 1..16")
    if width < columns or height < rows:
        raise ValueError("editor smaller than requested grid")
    points = [(min(width - 1, (2 * x + 1) * width // (2 * columns)),
               min(height - 1, (2 * y + 1) * height // (2 * rows)))
              for y in range(rows) for x in range(columns)]
    if len(set(points)) != len(points):
        raise ValueError("grid does not have unique physical points")
    return points


def scan(plugin, gui_host, out, *, columns=8, rows=8,
         acknowledge=False, timeout=25, runner=subprocess.run,
         explorer=explore):
    if acknowledge is not True:
        raise ValueError("explicit acknowledgment of destructive GUI actions required")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("invalid bounded timeout")
    plugin = Path(plugin).resolve(strict=True)
    gui_host = Path(gui_host).resolve(strict=True)
    if plugin.suffix.lower() != ".vst3" or not plugin.is_dir() or not gui_host.is_file():
        raise ValueError("expected real VST3 bundle and native GUI host")
    modules = list(plugin.rglob("*.vst3"))
    if len(modules) != 1 or not modules[0].is_file():
        raise ValueError("expected exactly one VST3 DLL in bundle")
    module_sha = digest(modules[0])
    host_sha = digest(gui_host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    destination = out / "GUI-COVERAGE-SCAN.json"
    destination.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_sha,
        "verified_gui_host_sha256": host_sha,
        "planned_points": columns * rows, "completed_points": 0,
        "candidate_points": 0, "unstable_points": 0,
        "batches": [], "candidates": [],
        "point_sampling": "TILE_CENTERS_NOT_EXHAUSTIVE",
        "product_gui_controls": "NOT COVERED",
        "independent_product_semantics": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
        "release_approved": False, "faults": []
    }
    try:
        snapshot = out / "overview.bmp"
        snapshot.unlink(missing_ok=True)
        proc = runner([str(gui_host), "--snapshot-editor", str(plugin), str(snapshot)],
                      capture_output=True, text=True, check=False,
                      errors="replace", timeout=timeout)
        if proc.returncode != 0 or not snapshot.is_file():
            raise ValueError("native editor snapshot failed")
        width, height, _ = read_bmp(snapshot)
        points = sample_points(width, height, columns, rows)
        result["editor_dimensions"] = [width, height]
        for start in range(0, len(points), 16):
            if digest(modules[0]) != module_sha or digest(gui_host) != host_sha:
                raise ValueError("native plugin/host identity changed")
            batch_points = points[start:start + 16]
            batch_dir = out / ("batch-%03d" % (start // 16 + 1))
            observed = explorer(
                plugin, gui_host, batch_dir,
                points=";".join("%d,%d" % point for point in batch_points),
                acknowledge=True, timeout=timeout, runner=runner)
            if (observed.get("schema") != "125a-gui-exploration-result-v1"
                    or observed.get("status") != "OBSERVATIONS_COMPLETE"
                    or observed.get("sham_control") != "COMPLETE"
                    or observed.get("verified_module_sha256") != module_sha
                    or observed.get("verified_gui_host_sha256") != host_sha
                    or observed.get("completed_points") != len(batch_points)
                    or observed.get("sham_verified_points") != len(batch_points)):
                raise ValueError("GUI batch lacked complete matched-sham evidence")
            probes = observed.get("probes")
            if not isinstance(probes, list) or len(probes) != len(batch_points):
                raise ValueError("GUI batch lost probe results")
            for offset, (point, probe) in enumerate(zip(batch_points, probes)):
                if (probe.get("x"), probe.get("y")) != point:
                    raise ValueError("GUI batch misattributed coordinates")
                state = probe.get("classification")
                if state not in ("UNSTABLE_CONTROL", "NO_OBSERVED_CHANGE",
                                 "PARAMETER_CHANGE", "VISUAL_CHANGE",
                                 "PARAMETER_AND_VISUAL_CHANGE"):
                    raise ValueError("GUI batch invalid observation class")
                if state == "UNSTABLE_CONTROL":
                    result["unstable_points"] += 1
                if state in ("PARAMETER_CHANGE", "VISUAL_CHANGE",
                             "PARAMETER_AND_VISUAL_CHANGE"):
                    result["candidates"].append({
                        "probe_index": start + offset,
                        "x": point[0], "y": point[1], "observation": state,
                        "batch": start // 16 + 1
                    })
            result["completed_points"] += len(batch_points)
            result["batches"].append({
                "path": batch_dir.name + "/GUI-EXPLORATION-RESULT.json",
                "points": len(batch_points), "status": "OBSERVATIONS_COMPLETE"
            })
        if digest(modules[0]) != module_sha or digest(gui_host) != host_sha:
            raise ValueError("plugin/host changed after scan")
        result["candidate_points"] = len(result["candidates"])
        result["status"] = "OBSERVATIONS_COMPLETE"
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        result["faults"].append(str(exc))
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True, type=Path)
    parser.add_argument("--gui-host", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=8)
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--acknowledge-ui-clicks", action="store_true")
    args = parser.parse_args()
    try:
        result = scan(args.plugin, args.gui_host, args.out,
                      columns=args.columns, rows=args.rows,
                      timeout=args.timeout,
                      acknowledge=args.acknowledge_ui_clicks)
    except (OSError, ValueError, TypeError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL",
                  "faults": [str(exc)], "release_approved": False,
                  "product_gui_controls": "NOT COVERED"}
        (args.out / "GUI-COVERAGE-SCAN.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "OBSERVATIONS_COMPLETE" else 1)


if __name__ == "__main__":
    main()
