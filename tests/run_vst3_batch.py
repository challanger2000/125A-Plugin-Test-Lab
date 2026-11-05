#!/usr/bin/env python3
"""P23: isolate and inspect EVERY VST3 bundle in a directory tree.

Each module is loaded in a separate subprocess with a hard timeout.
No audio, state or GUI PASS is implied by capability discovery.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import subprocess
import sys
import time

from verify_universal_discovery import check


def discover(root: pathlib.Path) -> list[pathlib.Path]:
    assert root.is_dir(), "plugin scan root is not a directory"
    paths = []
    for path in root.rglob("*"):
        if path.suffix.lower() != ".vst3":
            continue
        if any(p.suffix.lower() == ".vst3" for p in path.parents):
            continue
        if path.is_dir() or path.is_file():
            paths.append(path)
    return sorted(paths, key=lambda p: str(p).lower())


def scan(host: pathlib.Path, root: pathlib.Path, out: pathlib.Path,
         timeout: int) -> bool:
    assert host.is_file(), "universal test host executable missing"
    assert 1 <= timeout <= 300, "invalid timeout range"
    plugins = discover(root)
    assert plugins, "no .vst3 modules in root"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for i, plugin in enumerate(plugins, 1):
        record = {"relative_path": str(plugin.relative_to(root)), "status": "FAIL"}
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [str(host.resolve()), "--inspect", str(plugin.resolve())],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, check=False,
            )
            log = (proc.stdout or "") + "\n" + (proc.stderr or "")
            (out / f"module-{i:03d}.log").write_text(log, encoding="utf-8")
            record["exit_code"] = proc.returncode
            if proc.returncode == 0:
                capabilities = check(proc.stdout)
                record["status"] = "PASS"
                record["classes"] = capabilities["classes"]
            else:
                record["reason"] = "host exited nonzero (load, interface or runtime error)"
        except subprocess.TimeoutExpired:
            record["reason"] = f"host exceeded {timeout}s timeout"
        except (OSError, AssertionError, ValueError) as err:
            record["reason"] = str(err)
        record["elapsed_ms"] = round((time.monotonic() - start) * 1000)
        results.append(record)
        print(f"[{record['status']}] P23 {record['relative_path']}")
    passed = all(item["status"] == "PASS" for item in results)
    report = {
        "schema": "125a-universal-vst3-batch-v1",
        "status": "PASS" if passed else "FAIL",
        "discovered": len(results),
        "passed": sum(item["status"] == "PASS" for item in results),
        "failed": sum(item["status"] == "FAIL" for item in results),
        "modules": results,
        "coverage": {"capability_discovery": "EXECUTED",
                     "audio_rendering": "NOT_EXECUTED",
                     "gui_interaction": "NOT_EXECUTED",
                     "state_recall": "NOT_EXECUTED"}
    }
    (out / "BATCH-RESULT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[{report['status']}] P23 batch {report['passed']}/{report['discovered']} modules")
    return passed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", type=pathlib.Path, required=True)
    p.add_argument("--root", type=pathlib.Path, required=True)
    p.add_argument("--out", type=pathlib.Path, required=True)
    p.add_argument("--timeout", type=int, default=30)
    args = p.parse_args()
    try:
        if not scan(args.host, args.root, args.out, args.timeout):
            sys.exit(1)
    except (AssertionError, OSError, ValueError) as error:
        print(f"[FAIL] P23 scan: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
