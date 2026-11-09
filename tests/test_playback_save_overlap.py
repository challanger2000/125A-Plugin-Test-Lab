#!/usr/bin/env python3
"""Prove playback-save counts cannot be certified when playback has stopped."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

root_scripts = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("adapter", root_scripts / "run_product_adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
spec2 = importlib.util.spec_from_file_location("oracle", root_scripts / "verify_state_stress.py")
oracle = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(oracle)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    binary = root / "Fixture.vst3" / "Contents" / "x86_64-win" / "Fixture.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"only a synthetic test identity")
    host = root / "native.exe"
    host.write_bytes(b"fake host for independent evidence mutation")
    manifest = {
        "schema": "125a-p32-adapter-v1",
        "product": {"name": "Fixture", "version": "test", "commit_sha": "0" * 40,
                    "binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
        "host": str(host),
        "cases": [{
            "id": "playback_44100", "rate": 44100, "block": 64, "iterations": 2500,
            "mode": "save-only",
            "assertions": {"result": {"eq": "PASS"}, "save_failures": {"eq": 0},
                           "process_failures": {"eq": 0},
                           "save_success": {"eq": 500},
                           "domain_correctness": {"eq": "NOT_COVERED"}}
        }]
    }
    m = root / "manifest.json"
    m.write_text(json.dumps(manifest), encoding="utf-8")
    evidence = {
        "format": "125A-P25-v1", "sample_rate": 44100, "block_size": 64,
        "iterations": 2500, "callbacks": 2500, "process_failures": 0,
        "set_failures": 0, "set_success": 0, "sets_during_playback": 0, "save_failures": 0, "save_success": 500,
        "saves_during_playback": 400, "torn_snapshots": 0,
        "callback_max_ns": 20000, "callback_p95_ns": 10000,
        "callback_p99_ns": 15000, "callback_deadline_ns": 1451247,
        "strict_realtime": 0, "callback_overruns": 0,
        "timing_certification": "PASS", "rate_sample": -1.0,
        "result": "PASS", "oracle": "none", "domain_correctness": "NOT_COVERED"
    }
    def simulate(argv, **kwargs):
        output = Path(argv[3])
        output.write_text("".join(f"{k}\t{v}\n" for k, v in evidence.items()), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")

    with patch.object(adapter.subprocess, "run", side_effect=simulate):
        rc = adapter.run(m, root / "good", 20)
        assert rc == 0, "real-playback overlap evidence refused"
        result = json.loads((root / "good" / "ADAPTER-RESULT.json").read_text(encoding="utf-8"))
        assert result["cases"][0]["measured_active_playback_saves"] == 400
        for name, value in (("no_overlap", 0), ("impossible", 501), ("missing", None)):
            original = evidence.pop("saves_during_playback") if value is None else evidence["saves_during_playback"]
            if value is not None:
                evidence["saves_during_playback"] = value
            rc = adapter.run(m, root / name, 20)
            result = json.loads((root / name / "ADAPTER-RESULT.json").read_text(encoding="utf-8"))
            assert rc == 1 and result["status"] == "FAIL", name
            assert any("playback" in reason or "saves_during_playback" in reason
                       for reason in result["cases"][0]["faults"]), name
            evidence["saves_during_playback"] = original
        # P98: a missing-input stereo-effect callback is rejected, not
        # misleadingly counted as a successful 100ns realtime callback.
        original_result = evidence["result"]
        original_failures = evidence["process_failures"]
        original_timing = evidence["timing_certification"]
        evidence["result"] = "FAIL"
        evidence["process_failures"] = 2368
        evidence["timing_certification"] = "NOT COVERED"
        rc = adapter.run(m, root / "invalid-callback-timing", 20)
        bad = json.loads((root / "invalid-callback-timing" / "ADAPTER-RESULT.json").read_text(encoding="utf-8"))
        assert rc == 1 and bad["status"] == "FAIL"
        assert bad["cases"][0]["realtime_certification"] == "NOT COVERED"
        assert any("process_failures" in fault for fault in bad["cases"][0]["faults"])
        assert not any("invalid timing certification" in fault
                       for fault in bad["cases"][0]["faults"])
        evidence["timing_certification"] = "PASS"
        rc = adapter.run(m, root / "forged-fast-invalid-callbacks", 20)
        forged = json.loads((root / "forged-fast-invalid-callbacks" / "ADAPTER-RESULT.json").read_text(encoding="utf-8"))
        assert rc == 1 and any("failed plugin callbacks cannot certify realtime timing" in fault
                               for fault in forged["cases"][0]["faults"])
        evidence["result"] = original_result
        evidence["process_failures"] = original_failures
        evidence["timing_certification"] = original_timing
    # A P25 host log with all 500 saves after playback is also rejected by
    # the independent TSV oracle, regardless of its recorded result=PASS.
    tsv = root / "late.tsv"
    evidence["saves_during_playback"] = 0
    tsv.write_text("".join(f"{k}\t{v}\n" for k, v in evidence.items()), encoding="utf-8")
    try:
        oracle.parse(tsv)
    except AssertionError as exc:
        assert "saves during" in str(exc), str(exc)
    else:
        raise AssertionError("independent oracle accepted post-playback-only saves")
    # A very fast real process() can take less than one steady_clock tick:
    # 0 ns at p95 is valid if p99 and maximum are ordered correctly.
    evidence["saves_during_playback"] = 300
    evidence["callback_p95_ns"] = 0
    evidence["callback_p99_ns"] = 100
    evidence["callback_max_ns"] = 400
    tsv.write_text("".join(f"{k}\t{v}\n" for k, v in evidence.items()),
                   encoding="utf-8")
    assert oracle.parse(tsv)["callback_p95_ns"] == 0
    evidence["callback_p95_ns"] = 200
    tsv.write_text("".join(f"{k}\t{v}\n" for k, v in evidence.items()),
                   encoding="utf-8")
    try:
        oracle.parse(tsv)
    except AssertionError as exc:
        assert "timing order" in str(exc), str(exc)
    else:
        raise AssertionError("inconsistent callback p95/p99 order accepted")
print("[PASS] 500 saves cannot appear green if none overlapped active VST3 playback")
