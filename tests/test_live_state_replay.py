#!/usr/bin/env python3
"""Negative controls: stale or forged real VST3 state-replay outcomes are FAIL."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile

spec=importlib.util.spec_from_file_location(
    "live",Path(__file__).with_name("run_live_state_replay.py"))
live=importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    bundle=root/"Fixture.vst3"
    processor=bundle/"Contents"/"x86_64-win"/"Fixture.vst3"
    processor.parent.mkdir(parents=True)
    processor.write_bytes(b"test module binary exact identity")
    host=root/"stress.exe"
    host.write_bytes(b"native host identity")
    out=root/"out"
    mode={"current":"good"}

    def mock_native(cmd, **kwargs):
        assert cmd[1]=="--stress" and cmd[7]=="none"
        assert cmd[-1]=="--replay-valid-state"
        path=Path(cmd[3])
        rate=int(cmd[4]);block=int(cmd[5])
        if mode["current"]=="missing":
            return subprocess.CompletedProcess(cmd,0,"[PASS] universal VST3 live process/set/get","")
        if mode["current"]=="changed_module":
            processor.write_bytes(b"modified plugin after initial identity check")
        elif mode["current"]=="changed_host":
            host.write_bytes(b"modified host after initial identity check")
        values={
            "format":"125A-P25-v1", "plugin":cmd[2],
            "sample_rate":rate, "block_size":block,"iterations":2500,
            "callbacks":2500,"process_failures":0,"set_failures":0,
            "set_success":500,"sets_during_playback":280,
            "save_failures":0,"save_success":500,"saves_during_playback":300,
            "torn_snapshots":0,"callback_max_ns":30000,
            "callback_overruns":0,"callback_p95_ns":10000,"callback_p99_ns":20000,
            "callback_deadline_ns":max(1000,1000000000*block//rate),
            "strict_realtime":0, "oracle":"none","scenario":"replay-genuine-state",
            "classes":1,"rate_sample":-1,"result":"PASS",
            "domain_correctness":"NOT_COVERED",
            "timing_certification":"PASS","reason":""
        }
        if mode["current"]=="stale":
            values["scenario"]="playback-save-no-writes"
        elif mode["current"]=="zero":
            values["sets_during_playback"]=0
        elif mode["current"]=="missing_sets":
            values.pop("set_success")
        elif mode["current"]=="other_plugin":
            values["plugin"]="C:/completely-different-plugin.vst3"
        elif mode["current"]=="failed_calls":
            values["set_success"]=499
            values["set_failures"]=1
        elif mode["current"]=="false_domain":
            values["domain_correctness"]="PASS"
        elif mode["current"]=="wrong_rate":
            values["sample_rate"]=96000 if rate!=96000 else 44100
        path.write_text("".join(f"{k}\t{v}\n" for k,v in values.items()),
                        encoding="utf-8")
        return subprocess.CompletedProcess(cmd,0,
             "[PASS] universal VST3 live process/set/get, snapshots and elapsed time","")

    good=live.run(bundle,host,out,runner=mock_native)
    assert good["status"]=="TECHNICAL_PASS"
    assert good["verified_module_sha256"]==hashlib.sha256(processor.read_bytes()).hexdigest()
    assert len(good["cases"])==6
    assert sum(x["sets_during_playback"] for x in good["cases"])==6*280
    assert good["release_approved"] is False
    assert good["bank_program_correctness"]=="NOT COVERED"
    for label in ("missing","stale","zero","missing_sets","other_plugin",
                  "failed_calls","false_domain","wrong_rate"):
        mode["current"]=label
        failed=live.run(bundle,host,out,runner=mock_native)
        assert failed["status"]=="FAIL",label
        assert len(failed["cases"])==6,label
        assert all(x["status"]=="FAIL" for x in failed["cases"]),label
        assert failed["release_approved"] is False,label

    # An apparently successful host must not certify another module or
    # executable that replaced the SHA-256-pinned input during a test run.
    original_module = b"test module binary exact identity"
    original_host = b"native host identity"
    for label in ("changed_module", "changed_host"):
        processor.write_bytes(original_module)
        host.write_bytes(original_host)
        mode["current"] = label
        failed = live.run(bundle, host, out, runner=mock_native)
        assert failed["status"] == "FAIL", label
        assert all(case["status"] == "FAIL" for case in failed["cases"]), label
        assert "changed during replay" in failed["cases"][0]["reason"], label
    processor.write_bytes(original_module)
    host.write_bytes(original_host)

print("[PASS] replay accepts only immutable binaries and 6 fresh 500-state/500-save/2500-audio proofs")
