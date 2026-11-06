#!/usr/bin/env python3
"""Real native CI fixture input states and independent isolation oracle mutations."""
import argparse
import importlib.util
from pathlib import Path
import tempfile

spec=importlib.util.spec_from_file_location(
    "oracle",Path(__file__).with_name("verify_instance_isolation.py"))
oracle=importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def create_states(folder):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"A.bin").write_bytes(oracle.approved(11,22))
    (folder/"B.bin").write_bytes(oracle.approved(33,44))


def synthetic_evidence(folder, global_leak=False):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"A-after.bin").write_bytes(
        oracle.approved(33,44) if global_leak else oracle.approved(11,22))
    (folder/"B-after.bin").write_bytes(oracle.approved(33,44))
    a=0.125 if global_leak else 0.25
    (folder/"MULTI-INSTANCE.tsv").write_text(
        "format\t125A-DUAL-INSTANCE-v1\n"
        "same_process_instances\t2\nprocess_callbacks\t4\n"
        f"A_first_pcm\t{a}\nB_first_pcm\t0.125\n"
        f"B_second_pcm\t0.125\nA_second_pcm\t{a}\n",encoding="utf-8")


def mutations():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        create_states(root)
        good=root/"good"
        synthetic_evidence(good)
        assert oracle.audit(good,expect="good")["status"]=="PASS"
        assert oracle.audit(good,expect="broken")["status"]=="FAIL"

        bad=root/"bad"
        synthetic_evidence(bad,True)
        broken=oracle.audit(bad,expect="broken")
        assert broken["status"]=="PASS" and broken["state_isolation"]=="FAIL"
        assert oracle.audit(bad,expect="good")["status"]=="FAIL"

        # Successful API callbacks must not hide a silently corrupt saved
        # bank, nor the wrong audio output from a global-state collision.
        (good/"A-after.bin").write_bytes(oracle.approved(33,44))
        assert oracle.audit(good,expect="good")["status"]=="FAIL"
        synthetic_evidence(good)
        (good/"MULTI-INSTANCE.tsv").write_text(
            (good/"MULTI-INSTANCE.tsv").read_text().replace(
                "A_first_pcm\t0.25","A_first_pcm\t0.125"),encoding="utf-8")
        assert oracle.audit(good,expect="good")["status"]=="FAIL"
        synthetic_evidence(good)
        with (good/"MULTI-INSTANCE.tsv").open("a",encoding="utf-8") as out:
            out.write("A_first_pcm\t0.25\n")
        try:
            oracle.audit(good,expect="good")
        except ValueError as ex:
            assert "duplicate" in str(ex)
        else:
            raise AssertionError("duplicated native PCM proof accepted")
        (good/"A-after.bin").unlink()
        try:
            oracle.audit(good,expect="good")
        except OSError:
            pass
        else:
            raise AssertionError("missing state accepted")
    print("[PASS] same-process two-instance independent state/PCM mutation controls")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--make-states",type=Path)
    args=p.parse_args()
    if args.make_states:
        create_states(args.make_states)
    mutations()
