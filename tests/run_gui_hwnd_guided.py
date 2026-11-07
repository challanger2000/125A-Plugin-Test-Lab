#!/usr/bin/env python3
"""P69: automatically derive GUI probes from *real* Win32 child HWNDs.

The default is READ ONLY. A separate opt-in runs existing P42 sham-controlled
real VST3 click exploration at the observed native child centers. Owner
expected behavior, custom-painted controls and destructive action safety are
not inferred from HWND geometry.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from run_gui_hwnd_tree import run as tree_run
from run_gui_exploration import run as exploration_run

SCHEMA = "125a-gui-hwnd-guided-discovery-v1"
BUTTON_CLASSES = {"button", "checkbox", "radiobutton"}
SKIPPED_CLASSES = {"edit", "richedit", "richedit20w", "combobox",
                   "syslistview32", "systreeview32", "msctls_trackbar32"}
MAX_SUGGESTIONS = 16


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def derive_candidates(tree, *, max_points=9):
    if type(max_points) is not int or not 1 <= max_points <= MAX_SUGGESTIONS:
        raise ValueError("P69 invalid bounded candidate count")
    if (not isinstance(tree, dict) or
            tree.get("schema") != "125a-hwnd-control-tree-v1" or
            tree.get("status") != "OBSERVATIONS_COMPLETE" or
            type(tree.get("native_hwnd_count")) is not int or
            tree["native_hwnd_count"] != len(tree.get("nodes", [])) or
            not 1 <= tree["native_hwnd_count"] <= 512 or
            tree.get("release_approved") is not False):
        raise ValueError("P69 cannot trust absent or incomplete HWND tree")
    nodes = tree["nodes"]
    root = nodes[0]
    if root.get("index") != 0 or root.get("parent") != -1:
        raise ValueError("P69 missing unique root editor HWND")
    base = root.get("rectangle")
    if (not isinstance(base, list) or len(base) != 4 or
            any(type(v) is not int for v in base) or
            base[2] <= base[0] or base[3] <= base[1] or
            base[2] - base[0] > 4096 or base[3] - base[1] > 4096):
        raise ValueError("P69 invalid actual editor bounds")
    width, height = base[2] - base[0], base[3] - base[1]
    selected, skipped, seen = [], [], set()
    for index, node in enumerate(nodes):
        if (not isinstance(node, dict) or node.get("index") != index or
                type(node.get("parent")) is not int or
                (index > 0 and not 0 <= node["parent"] < index) or
                type(node.get("visible")) is not bool or
                type(node.get("enabled")) is not bool or
                type(node.get("class_name")) is not str or
                type(node.get("control_id")) is not int):
            raise ValueError("P69 corrupted, ambiguous child HWND node")
        if index == 0:
            continue
        cls = node["class_name"].lower()
        rect = node.get("rectangle")
        if (not isinstance(rect, list) or len(rect) != 4 or
                any(type(x) is not int for x in rect) or
                rect[2] <= rect[0] or rect[3] <= rect[1]):
            raise ValueError("P69 invalid child HWND geometry")
        if not node["visible"] or not node["enabled"]:
            skipped.append({"node_index": index, "reason": "HIDDEN_OR_DISABLED"})
            continue
        if cls in SKIPPED_CLASSES or cls not in BUTTON_CLASSES:
            skipped.append({"node_index": index,
                            "reason": "UNAPPROVED_OR_NON_BUTTON_CLASS"})
            continue
        x = (rect[0] + rect[2]) // 2
        y = (rect[1] + rect[3]) // 2
        if not 0 <= x < width or not 0 <= y < height:
            skipped.append({"node_index": index, "reason": "OUTSIDE_EDITOR"})
            continue
        if (x, y) in seen:
            skipped.append({"node_index": index, "reason": "DUPLICATE_TARGET"})
            continue
        seen.add((x, y))
        selected.append({"node_index": index, "control_id": node["control_id"],
                         "class_name": node["class_name"],
                         "x": x, "y": y,
                         "source": "NATIVE_HWND_GEOMETRY",
                         "interaction": "PROPOSED_ONLY"})
    selected.sort(key=lambda c: (c["y"], c["x"], c["node_index"]))
    overflow = selected[max_points:]
    for node in overflow:
        skipped.append({"node_index": node["node_index"],
                        "reason": "EXCEEDS_BOUNDED_PROBE_LIMIT"})
    return selected[:max_points], skipped


def run(plugin, host, out, *, acknowledge=False, max_points=9,
        inventory=tree_run, explore=exploration_run, timeout=40):
    if type(acknowledge) is not bool:
        raise ValueError("P69 acknowledgement must be a boolean")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("P69 unbounded timeout rejected")
    plugin = Path(plugin).resolve(strict=True)
    host = Path(host).resolve(strict=True)
    if plugin.suffix.lower() != ".vst3" or not plugin.is_dir() or not host.is_file():
        raise ValueError("P69 requires actual Windows VST3 bundle and native host")
    modules = [p for p in plugin.rglob("*.vst3") if p.is_file()]
    if len(modules) != 1:
        raise ValueError("P69 requires one uniquely pinned plugin DLL")
    dll = modules[0]
    fp, hp = digest(dll), digest(host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    file = out / "HWND-GUIDED-RESULT.json"
    file.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": fp, "verified_gui_host_sha256": hp,
        "proposed_candidates": [], "skipped_nodes": [],
        "probe_mode": "READ_ONLY" if not acknowledge else "OPT_IN_EXPLORATION",
        "actual_exploration_status": "NOT RUN",
        "product_gui_semantics": "NOT COVERED",
        "custom_painted_controls": "NOT COVERED",
        "release_approved": False, "faults": []
    }
    try:
        observations = inventory(plugin, host, out / "hwnd-tree", timeout=timeout)
        if (observations.get("verified_module_sha256") != fp or
                observations.get("verified_gui_host_sha256") != hp):
            raise ValueError("P69 stale or misattributed HWND tree evidence")
        candidates, skips = derive_candidates(observations, max_points=max_points)
        report["proposed_candidates"] = candidates
        report["skipped_nodes"] = skips
        if digest(dll) != fp or digest(host) != hp:
            raise ValueError("P69 tested DLL changed while generating candidates")
        if acknowledge and candidates:
            points = ";".join(f"{c['x']},{c['y']}" for c in candidates)
            outcome = explore(plugin, host, out / "native-probes",
                              points=points, max_points=len(candidates),
                              acknowledge=True, timeout=timeout)
            if (outcome.get("status") != "OBSERVATIONS_COMPLETE" or
                    outcome.get("verified_module_sha256") != fp or
                    outcome.get("verified_gui_host_sha256") != hp or
                    outcome.get("requested_points") != len(candidates) or
                    outcome.get("completed_points") != len(candidates) or
                    outcome.get("sham_verified_points") != len(candidates) or
                    outcome.get("release_approved") is not False):
                raise ValueError("P69 real sham-controlled HWND click probes incomplete")
            if digest(dll) != fp or digest(host) != hp:
                raise ValueError("P69 binary identity changed during GUI clicks")
            report["actual_exploration_status"] = "OBSERVATIONS_COMPLETE"
        report["status"] = "CANDIDATES_COMPLETE"
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        report["faults"].append(str(error))
        report["actual_exploration_status"] = "FAIL" if acknowledge else "NOT RUN"
    file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--gui-host", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-points", type=int, default=9)
    p.add_argument("--timeout", type=int, default=40)
    p.add_argument("--acknowledge-ui-clicks", action="store_true")
    a = p.parse_args()
    try:
        result = run(a.plugin, a.gui_host, a.out,
                     acknowledge=a.acknowledge_ui_clicks,
                     max_points=a.max_points, timeout=a.timeout)
    except (OSError, ValueError, KeyError, TypeError) as error:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL",
                  "faults": [str(error)], "release_approved": False}
        (a.out / "HWND-GUIDED-RESULT.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "CANDIDATES_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
