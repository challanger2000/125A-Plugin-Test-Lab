#!/usr/bin/env python3
"""Release-evidence audit: a generic green log is never product acceptance."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location(
    "release", Path(__file__).with_name("build_release_report.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

sha = "a" * 40
with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    for gate, rel in release.CASES.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        times = release.COUNTS.get(gate, 1)
        body = "\n".join(marker for marker in release.REQUIRED[gate]
                         for _ in range(times)) + "\n"
        p.write_text(body, encoding="utf-8")
    output = Path("evidence.json")
    assert release.make_report(sha, output), "complete domain-specific evidence failed"
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["summary"] == "PASS"
    assert all(x["status"] == "PASS" for x in result["checked_gates"].values())

    # Only a generic success token is a dangerously false release proof.
    gate = "P08_wav_export"
    file = Path(release.CASES[gate])
    good = file.read_text(encoding="utf-8")
    file.write_text("[PASS] setup passed but music never validated\n", encoding="utf-8")
    assert not release.make_report(sha, output), "irrelevant PASS approved WAV domain"
    assert json.loads(output.read_text(encoding="utf-8"))["checked_gates"][gate]["status"] == "FAIL"
    file.write_text(good)

    # A separately marked negative-control observation must not be green.
    file.write_text(good + "[FAIL] PCM reference wrong\n", encoding="utf-8")
    assert not release.make_report(sha, output), "explicit FAIL ignored"
    file.write_text(good)

    # Three independent new-process restores are required, not one.
    gate = "P18_fresh_process_recall"
    recall = Path(release.CASES[gate])
    previous = recall.read_text(encoding="utf-8")
    recall.write_text("\n".join(release.REQUIRED[gate]) + "\n", encoding="utf-8")
    assert not release.make_report(sha, output), "one restore approved three-restore gate"
    recall.write_text(previous)

    # Do not allow copying the expected success marker a second time.
    file.write_text(good + good, encoding="utf-8")
    assert not release.make_report(sha, output), "duplicate success proof accepted"
    file.write_text(good)

    # Missing evidence must be an explicit NO-GO.
    file.unlink()
    assert not release.make_report(sha, output), "missing oracle evidence accepted"
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["summary"] == "FAIL"
    assert result["checked_gates"]["P08_wav_export"]["status"] == "FAIL"

print("[PASS] release report refuses wrong, repeated, missing or incomplete domain evidence")
