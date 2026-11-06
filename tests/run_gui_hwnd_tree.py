#!/usr/bin/env python3
"""P54 independent read-only native Win32 editor control-tree verifier."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "125a-hwnd-control-tree-v1"
CLASS = re.compile(r"^[^\t\r\n]{1,255}$")
INT = re.compile(r"^-?[0-9]{1,10}$")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_tree(raw):
    lines = raw.splitlines()
    if len(lines) < 4 or lines[0] != "format\t125A-HWND-TREE-v1" or lines[-1] != "end\tCOMPLETE":
        raise ValueError("native HWND inventory is incomplete or invalid")
    size = lines[1].split("\t")
    if len(size) != 2 or size[0] != "count" or not size[1].isascii() or not size[1].isdecimal():
        raise ValueError("native HWND count invalid")
    count = int(size[1])
    if not 1 <= count <= 512 or len(lines) != count + 3:
        raise ValueError("native HWND inventory node count mismatch")
    nodes = []
    for i, line in enumerate(lines[2:-1]):
        parts = line.split("\t")
        if len(parts) != 11 or parts[0] != "node" or parts[1] != str(i):
            raise ValueError("native HWND node missing, duplicated or reordered")
        parent_s, cls, vis, enabled, *numbers = parts[2:]
        if not CLASS.fullmatch(cls) or vis not in ("0", "1") or enabled not in ("0", "1"):
            raise ValueError("invalid native class or visible/enabled flags")
        if any(not INT.fullmatch(x) for x in [parent_s, *numbers]):
            raise ValueError("invalid native HWND coordinate/control identifier")
        parent = int(parent_s)
        if parent != (-1 if i == 0 else parent) or (i > 0 and not 0 <= parent < i):
            # The HWND root must have -1, every later node must have a
            # previously enumerated parent (parent order is not guaranteed
            # by EnumChildWindows, so native inventory canonicalizes it).
            raise ValueError("invalid HWND hierarchy")
        left, top, right, bottom, control_id = map(int, numbers)
        if not -32768 <= left < right <= 32768 or not -32768 <= top < bottom <= 32768:
            raise ValueError("invalid HWND bounding rectangle")
        nodes.append({
            "index": i, "parent": parent, "class_name": cls,
            "visible": vis == "1", "enabled": enabled == "1",
            "rectangle": [left, top, right, bottom],
            "control_id": control_id
        })
    return nodes


def run(plugin, host, out, *, timeout=35, runner=subprocess.run):
    plugin, host, out = Path(plugin).resolve(strict=True), Path(host).resolve(strict=True), Path(out)
    modules = [p for p in plugin.rglob("*.vst3") if p.is_file()]
    if plugin.suffix.lower() != ".vst3" or len(modules) != 1 or not host.is_file():
        raise ValueError("require exactly one actual native VST3 DLL and host")
    if type(timeout) is not int or not 5 <= timeout <= 120:
        raise ValueError("native bounded timeout invalid")
    module_sha, host_sha = digest(modules[0]), digest(host)
    out.mkdir(parents=True, exist_ok=True)
    native = out / "native-hwnd-tree.tsv"
    native.unlink(missing_ok=True)
    report_file = out / "HWND-CONTROL-TREE.json"
    report_file.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": module_sha, "verified_gui_host_sha256": host_sha,
        "native_hwnd_count": 0, "nodes": [], "faults": [],
        "custom_painted_controls": "NOT COVERED",
        "complete_product_gui_controls": "NOT COVERED",
        "independent_product_semantics": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
        "release_approved": False
    }
    try:
        result = runner([str(host), "--inventory-hwnd-tree", str(plugin), str(native)],
                        capture_output=True, text=True, check=False,
                        errors="replace", timeout=timeout)
        (out / "native.log").write_text(
            (result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8")
        if result.returncode != 0 or not native.is_file():
            raise ValueError("actual Win32 GUI host did not produce HWND tree")
        if digest(modules[0]) != module_sha or digest(host) != host_sha:
            raise ValueError("host or plugin modified during native inventory")
        nodes = parse_tree(native.read_text(encoding="utf-8"))
        report["nodes"] = nodes
        report["native_hwnd_count"] = len(nodes)
        report["status"] = "OBSERVATIONS_COMPLETE"
    except (OSError, UnicodeError, ValueError, TypeError, subprocess.TimeoutExpired) as e:
        report["faults"].append(str(e))
    report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--gui-host", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=35)
    a = p.parse_args()
    try:
        result = run(a.plugin, a.gui_host, a.out, timeout=a.timeout)
    except (OSError, ValueError, TypeError) as e:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL", "faults": [str(e)],
                  "release_approved": False}
        (a.out / "HWND-CONTROL-TREE.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "OBSERVATIONS_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
