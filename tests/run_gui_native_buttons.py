#!/usr/bin/env python3
"""P55 discover actual native Win32 BUTTON controls, then sham-probe them.

The GUI inventory supplies positions, not product semantics. Each observed
button is probed in a new real VST3 process with a matched sham control.
No product release approval is inferred.
"""
import argparse
import json
from pathlib import Path
import subprocess

from run_gui_hwnd_tree import run as inventory, digest
from run_gui_exploration import run as explore

SCHEMA = "125a-native-button-probe-v1"
VALID = {"PARAMETER_CHANGE", "VISUAL_CHANGE", "PARAMETER_AND_VISUAL_CHANGE",
         "NO_OBSERVED_CHANGE", "UNSTABLE_CONTROL"}


def select_buttons(nodes, limit=16):
    if not isinstance(nodes, list) or len(nodes) < 1:
        raise ValueError("P55 actual HWND tree missing")
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("P55 limit must be 1..16")
    root = nodes[0]
    dimensions = root.get("rectangle")
    if (not isinstance(dimensions, list) or len(dimensions) != 4
            or any(type(x) is not int for x in dimensions)):
        raise ValueError("P55 missing root geometry")
    candidates = []
    seen = set()
    for node in nodes[1:]:
        if not isinstance(node, dict):
            raise ValueError("invalid control inventory node")
        if node.get("class_name", "").casefold() != "button":
            continue
        if node.get("visible") is not True or node.get("enabled") is not True:
            continue
        rect = node.get("rectangle")
        if not isinstance(rect, list) or len(rect) != 4 or any(type(x) is not int for x in rect):
            raise ValueError("native BUTTON rectangle missing")
        left, top, right, bottom = rect
        if not (root["rectangle"][0] <= left < right <= root["rectangle"][2]
                and root["rectangle"][1] <= top < bottom <= root["rectangle"][3]):
            raise ValueError("native BUTTON bounds escape editor")
        x, y = (left + right) // 2, (top + bottom) // 2
        if (x, y) in seen:
            raise ValueError("two native controls share the same selected point")
        seen.add((x, y))
        candidates.append({"index": node["index"], "control_id": node["control_id"],
                           "center": [x, y], "class_name": node["class_name"]})
    return candidates[:limit], len(candidates) > limit


def run(plugin, host, out, *, acknowledge=False, limit=16, timeout=25,
        reader=inventory, explorer=explore, runner=subprocess.run):
    if acknowledge is not True:
        raise ValueError("P55 native BUTTON clicks require explicit opt-in")
    plugin = Path(plugin).resolve(strict=True)
    host = Path(host).resolve(strict=True)
    modules = [p for p in plugin.rglob("*.vst3") if p.is_file()]
    if plugin.suffix.lower() != ".vst3" or len(modules) != 1 or not host.is_file():
        raise ValueError("invalid real plugin/GUI host")
    module_sha, host_sha = digest(modules[0]), digest(host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "NATIVE-BUTTON-PROBES.json"
    report_path.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_sha,
        "verified_gui_host_sha256": host_sha,
        "discovered_buttons": 0, "probed_buttons": 0,
        "unprobed_buttons_exist": False, "observations": [], "faults": [],
        "complete_product_gui_controls": "NOT COVERED",
        "independent_product_semantics": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
        "release_approved": False
    }
    try:
        measured = reader(plugin, host, out / "inventory", timeout=timeout, runner=runner)
        if (measured.get("status") != "OBSERVATIONS_COMPLETE"
                or measured.get("verified_module_sha256") != module_sha
                or measured.get("verified_gui_host_sha256") != host_sha
                or measured.get("native_hwnd_count") != len(measured.get("nodes", []))):
            raise ValueError("invalid real native HWND inventory evidence")
        buttons, truncated = select_buttons(measured["nodes"], limit)
        report["discovered_buttons"] = len(buttons)
        report["unprobed_buttons_exist"] = truncated
        if buttons:
            if digest(modules[0]) != module_sha or digest(host) != host_sha:
                raise ValueError("plugin or host changed after native inventory")
            points = ";".join("%d,%d" % tuple(button["center"]) for button in buttons)
            observed = explorer(plugin, host, out / "sham-probes", points=points,
                                acknowledge=True, timeout=timeout, runner=runner)
            if (observed.get("schema") != "125a-gui-exploration-result-v1"
                    or observed.get("status") != "OBSERVATIONS_COMPLETE"
                    or observed.get("sham_control") != "COMPLETE"
                    or observed.get("verified_module_sha256") != module_sha
                    or observed.get("verified_gui_host_sha256") != host_sha
                    or observed.get("completed_points") != len(buttons)
                    or observed.get("sham_verified_points") != len(buttons)
                    or not isinstance(observed.get("probes"), list)
                    or len(observed["probes"]) != len(buttons)):
                raise ValueError("P55 actual click/sham evidence incomplete or forged")
            for button, probe in zip(buttons, observed["probes"]):
                if ((probe.get("x"), probe.get("y")) != tuple(button["center"])
                        or probe.get("classification") not in VALID):
                    raise ValueError("P55 physical button click misattributed")
                report["observations"].append({
                    **button, "classification": probe["classification"],
                    "changed_parameters": probe.get("changed_parameters", [])
                })
            report["probed_buttons"] = len(buttons)
        if digest(modules[0]) != module_sha or digest(host) != host_sha:
            raise ValueError("plugin or host modified during native probing")
        report["status"] = "OBSERVATIONS_COMPLETE"
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        report["faults"].append(str(exc))
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--gui-host", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--acknowledge-ui-clicks", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.plugin, args.gui_host, args.out,
                     limit=args.limit, timeout=args.timeout,
                     acknowledge=args.acknowledge_ui_clicks)
    except (OSError, ValueError, TypeError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL",
                  "faults": [str(exc)], "release_approved": False}
        (args.out / "NATIVE-BUTTON-PROBES.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "OBSERVATIONS_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
