#!/usr/bin/env python3
"""P71: one universal GUI discovery for native HWND and painted VST3 editors.

Read-only by default. A separately acknowledged isolated probing mode submits
one deduplicated bounded set to existing P42 sham-controlled native tests.
An apparent pixel island is never treated as a confirmed semantic control.
"""
import argparse
import json
from pathlib import Path
import subprocess

from run_gui_hwnd_guided import run as hwnd_run, digest
from run_gui_painted_candidates import run as painted_run
from run_gui_exploration import run as probe_run

SCHEMA = "125a-unified-gui-discovery-v1"


def merge_candidates(hwnd, painted, *, max_points=9):
    if type(max_points) is not int or not 1 <= max_points <= 16:
        raise ValueError("P71 invalid candidate budget")
    if (not isinstance(hwnd, dict) or not isinstance(painted, dict)
            or hwnd.get("schema") != "125a-gui-hwnd-guided-discovery-v1"
            or painted.get("schema") != "125a-painted-gui-visual-candidates-v1"
            or hwnd.get("status") != "CANDIDATES_COMPLETE"
            or painted.get("status") != "CANDIDATES_COMPLETE"
            or hwnd.get("verified_module_sha256") != painted.get("verified_module_sha256")
            or hwnd.get("verified_gui_host_sha256") != painted.get("verified_gui_host_sha256")
            or hwnd.get("release_approved") is not False
            or painted.get("release_approved") is not False
            or hwnd.get("actual_exploration_status") != "NOT RUN"
            or painted.get("exploration") != "NOT RUN"):
        raise ValueError("P71 cannot combine stale, fake, or already-clicked detection evidence")
    native = hwnd.get("proposed_candidates")
    visual = painted.get("visual_candidates")
    if not isinstance(native, list) or not isinstance(visual, list):
        raise ValueError("P71 missing actual detector candidate records")
    if len(native) > 16 or len(visual) > 16:
        raise ValueError("P71 unbounded detector candidate enumeration")
    merged, ignored = [], []
    native_boxes = []
    tree_path = hwnd.get("_native_hwnd_tree")
    # Use the native detector's actual inventory from this scan, never an
    # invented fixture geometry or an editable user-provided hitbox.
    if not isinstance(tree_path, dict):
        raise ValueError("P71 native HWND child rectangles were not supplied")
    nodes = tree_path.get("nodes")
    if (not isinstance(nodes, list) or
            len(nodes) != tree_path.get("native_hwnd_count") or
            tree_path.get("status") != "OBSERVATIONS_COMPLETE"):
        raise ValueError("P71 malformed original native HWND node geometry")
    node_map = {n.get("index"): n for n in nodes if isinstance(n, dict)}
    if len(node_map) != len(nodes):
        raise ValueError("P71 duplicate native HWND node indices")
    seen = set()
    for candidate in native:
        if (not isinstance(candidate, dict) or
                candidate.get("source") != "NATIVE_HWND_GEOMETRY" or
                candidate.get("interaction") != "PROPOSED_ONLY" or
                type(candidate.get("x")) is not int or
                type(candidate.get("y")) is not int or
                type(candidate.get("node_index")) is not int):
            raise ValueError("P71 unsupported native candidate")
        node = node_map.get(candidate["node_index"])
        if (node is None or node.get("control_id") != candidate.get("control_id")
                or node.get("class_name") != candidate.get("class_name")
                or node.get("visible") is not True
                or node.get("enabled") is not True
                or node.get("class_name", "").lower() not in
                ("button", "checkbox", "radiobutton")):
            raise ValueError("P71 candidate not confirmed by the actual native tree")
        rect = node.get("rectangle")
        if (not isinstance(rect, list) or len(rect) != 4
                or any(type(v) is not int for v in rect)
                or (candidate["x"], candidate["y"]) !=
                ((rect[0]+rect[2])//2, (rect[1]+rect[3])//2)):
            raise ValueError("P71 candidate center disagrees with native HWND bounds")
        point = (candidate["x"], candidate["y"])
        if point in seen:
            raise ValueError("P71 duplicated native candidate")
        seen.add(point)
        native_boxes.append(rect)
        merged.append({"x": point[0], "y": point[1], "source": "NATIVE_HWND",
                       "confidence": "OBSERVED_GEOMETRY_NOT_FUNCTION",
                       "control_id": candidate["control_id"],
                       "semantics": "UNKNOWN", "approved_to_click": False})
    for candidate in visual:
        if (not isinstance(candidate, dict) or
                candidate.get("origin") != "NATIVE_STATIC_PIXEL_ISLAND"
                or candidate.get("approved_to_click") is not False
                or candidate.get("control_semantics") != "UNKNOWN"
                or type(candidate.get("x")) is not int
                or type(candidate.get("y")) is not int):
            raise ValueError("P71 invalid painted candidate")
        x, y = candidate["x"], candidate["y"]
        bbox = candidate.get("bbox_xyxy")
        if (not isinstance(bbox, list) or len(bbox) != 4
                or any(type(v) is not int for v in bbox)
                or not 0 <= bbox[0] < bbox[2] <= 4096
                or not 0 <= bbox[1] < bbox[3] <= 4096
                or not bbox[0] <= x < bbox[2] or not bbox[1] <= y < bbox[3]):
            raise ValueError("P71 painted bitmap bounding box invalid")
        if (x, y) in seen or any(
                rect[0] <= x < rect[2] and rect[1] <= y < rect[3]
                for rect in native_boxes):
            ignored.append({"x": x, "y": y, "reason": "COVERED_BY_NATIVE_BUTTON"})
            continue
        seen.add((x, y))
        merged.append({"x": x, "y": y, "source": "PAINTED_VISUAL_REGION",
                       "confidence": "VISUAL_GUESS_UNVERIFIED",
                       "bbox_xyxy": bbox, "semantics": "UNKNOWN",
                       "approved_to_click": False})
    # Prefer real Win32 control geometry to guessed foreground artwork,
    # then stable top-to-bottom spatial order.
    merged.sort(key=lambda c: (0 if c["source"] == "NATIVE_HWND" else 1,
                               c["y"], c["x"]))
    for entry in merged[max_points:]:
        ignored.append({"x": entry["x"], "y": entry["y"],
                        "reason": "BOUNDED_CANDIDATE_LIMIT"})
    return merged[:max_points], ignored


def run(plugin, gui_host, out, *, acknowledge=False, max_points=9, timeout=40,
        native_detector=hwnd_run, painted_detector=painted_run,
        explorer=probe_run):
    if type(acknowledge) is not bool:
        raise ValueError("P71 acknowledgement must be explicitly boolean")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("P71 invalid bounded native timeout")
    if type(max_points) is not int or not 1 <= max_points <= 16:
        raise ValueError("P71 invalid candidate limit")
    plugin = Path(plugin).resolve(strict=True)
    gui_host = Path(gui_host).resolve(strict=True)
    if not plugin.is_dir() or plugin.suffix.lower() != ".vst3" or not gui_host.is_file():
        raise ValueError("P71 actual native Windows VST3/host required")
    binaries = [p for p in plugin.rglob("*.vst3") if p.is_file()]
    if len(binaries) != 1:
        raise ValueError("P71 ambiguous VST3 processor DLL")
    dll = binaries[0]
    module_sha, host_sha = digest(dll), digest(gui_host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "UNIFIED-GUI-DISCOVERY.json"
    report_path.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_sha,
        "verified_gui_host_sha256": host_sha,
        "mode": "EXPLICIT_OPT_IN" if acknowledge else "READ_ONLY",
        "native_candidates": 0, "painted_candidates": 0,
        "proposed_candidates": [], "ignored_candidates": [],
        "verified_click_probes": 0, "click_observation": "NOT RUN",
        "complete_gui_coverage": "NOT COVERED",
        "independent_plugin_semantics": "NOT COVERED",
        "review_required": True, "release_approved": False,
        "faults": []
    }
    try:
        native = native_detector(plugin, gui_host, out / "native",
                                 acknowledge=False, max_points=16, timeout=timeout)
        if native.get("status") != "CANDIDATES_COMPLETE":
            raise ValueError("P71 native detector failed")
        painted = painted_detector(plugin, gui_host, out / "painted",
                                   acknowledge=False, max_points=16, timeout=timeout)
        if painted.get("status") != "CANDIDATES_COMPLETE":
            raise ValueError("P71 painted detector failed")
        if (native.get("verified_module_sha256") != module_sha or
                painted.get("verified_module_sha256") != module_sha or
                native.get("verified_gui_host_sha256") != host_sha or
                painted.get("verified_gui_host_sha256") != host_sha):
            raise ValueError("P71 native/visual evidence belongs to another plugin or host")
        tree_path = out / "native" / "hwnd-tree" / "HWND-CONTROL-TREE.json"
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
        if (tree.get("verified_module_sha256") != module_sha or
                tree.get("verified_gui_host_sha256") != host_sha):
            raise ValueError("P71 stale or substituted native child HWND inventory")
        native["_native_hwnd_tree"] = tree
        proposals, ignored = merge_candidates(native, painted, max_points=max_points)
        result["native_candidates"] = len(native["proposed_candidates"])
        result["painted_candidates"] = len(painted["visual_candidates"])
        result["proposed_candidates"] = proposals
        result["ignored_candidates"] = ignored
        if digest(dll) != module_sha or digest(gui_host) != host_sha:
            raise ValueError("P71 binary or host changed while preparing unified scan")
        if acknowledge and proposals:
            points = ";".join(f"{p['x']},{p['y']}" for p in proposals)
            observed = explorer(plugin, gui_host, out / "isolated-probes",
                                points=points, max_points=len(proposals),
                                acknowledge=True, timeout=timeout)
            if (not isinstance(observed, dict) or
                    observed.get("status") != "OBSERVATIONS_COMPLETE"
                    or observed.get("verified_module_sha256") != module_sha
                    or observed.get("verified_gui_host_sha256") != host_sha
                    or observed.get("requested_points") != len(proposals)
                    or observed.get("completed_points") != len(proposals)
                    or observed.get("sham_verified_points") != len(proposals)
                    or observed.get("release_approved") is not False):
                raise ValueError("P71 independently sham-controlled click evidence incomplete")
            if digest(dll) != module_sha or digest(gui_host) != host_sha:
                raise ValueError("P71 plugin or host modified while clicking")
            result["verified_click_probes"] = len(proposals)
            result["click_observation"] = "OBSERVATIONS_COMPLETE"
        result["status"] = "CANDIDATES_COMPLETE"
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired,
            json.JSONDecodeError) as exc:
        result["faults"].append(str(exc))
        if acknowledge:
            result["click_observation"] = "FAIL"
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", required=True, type=Path)
    p.add_argument("--gui-host", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--timeout", type=int, default=40)
    p.add_argument("--max-points", type=int, default=9)
    p.add_argument("--acknowledge-ui-clicks", action="store_true")
    a = p.parse_args()
    try:
        result = run(a.plugin, a.gui_host, a.out, timeout=a.timeout,
                     max_points=a.max_points, acknowledge=a.acknowledge_ui_clicks)
    except (OSError, ValueError, TypeError) as exc:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL", "faults": [str(exc)],
                  "complete_gui_coverage": "NOT COVERED", "release_approved": False}
        (a.out / "UNIFIED-GUI-DISCOVERY.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "CANDIDATES_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
