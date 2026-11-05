#!/usr/bin/env python3
"""Regression: successful host exit must not allow old P32 evidence to pass."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("p32", Path(__file__).with_name("run_product_adapter.py"))
p32 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p32)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    bundle = root / "Synthetic.vst3"
    binary = bundle / "Contents" / "x86_64-win" / "Synthetic.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"synthetic module identity only")
    host = root / "unused-host.exe"
    host.write_bytes(b"mocked host invocation")
    out = root / "results"
    out.mkdir()
    stale = out / "playback_44100.tsv"
    stale.write_text(
        "format\t125A-P25-v1\nresult\tPASS\nsave_success\t500\n"
        "save_failures\t0\nprocess_failures\t0\n"
        "domain_correctness\tNOT_COVERED\n"
        "sample_rate\t44100\nblock_size\t64\niterations\t2500\n",
        encoding="utf-8")
    manifest = {
        "schema": "125a-p32-adapter-v1",
        "product": {"name": "Synthetic", "version": "test",
                    "commit_sha": "0" * 40, "binary": str(binary),
                    "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
        "host": str(host),
        "cases": [{"id": "playback_44100", "rate": 44100, "block": 64,
                   "iterations": 2500, "mode": "save-only",
                   "assertions": {"result": {"eq": "PASS"},
                                  "save_failures": {"eq": 0},
                                  "process_failures": {"eq": 0},
                                  "domain_correctness": {"eq": "NOT_COVERED"}}}]
    }
    adapter = root / "adapter.json"
    adapter.write_text(json.dumps(manifest), encoding="utf-8")
    with patch.object(p32.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
        rc = p32.run(adapter, out, 20)
    report = json.loads((out / "ADAPTER-RESULT.json").read_text(encoding="utf-8"))
    assert rc == 1, f"unexpected exit code {rc}"
    assert report["status"] == "FAIL", report
    assert "native result missing" in report["cases"][0]["faults"], report
    assert not stale.exists(), "stale case report still exists"
print("[PASS] P32 stale evidence rejected after zero-exit host without fresh report")
