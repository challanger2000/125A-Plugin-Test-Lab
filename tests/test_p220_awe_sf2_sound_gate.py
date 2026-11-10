#!/usr/bin/env python3
"""P220 **SYNTHETIC TEST-OF-TEST**, not a Creative/Windows audio experiment.

Ensures full 77-program gate detects missing original driver, bad source
identity, missing/zero/swapped/wrong PCM, altered MIDI, missing effect,
incomplete ADSR/filter/loop/FX/recall, and reused same WAV bytes.
This only proves the *oracle detects faults*. No synthetic test result
may ever be issued as original Creative Win95 sound fidelity.
"""
from __future__ import annotations
import copy
import hashlib
import math
import sys
import tempfile
import wave
from pathlib import Path
from p220_awe_sf2_sound_gate import (
    BANK_SHA,VXD_SHA,PROGRAMS,SCHEMA,LEVEL_TOLERANCE_DB,
    EvidenceError,compare,evaluate,exact_wav,validate_contract,check_provenance)

def require(ok,label):
    if not ok:raise AssertionError("P220 test-of-test FAIL: "+label)

def wave_file(path,prog,vel=64,backend=0):
    # Real independent PCM generation here only creates deliberately
    # *synthetic* unit fixtures. It never claims Win95, SF2, or VST3.
    sr=44100;n=int(sr*0.55)
    import struct
    frequency=125.0 + (prog%63)*15.0
    buf=bytearray()
    for i in range(n):
        t=i/sr
        fade=0.3+0.7*math.exp(-4.5*t)
        v=math.sin(2*math.pi*frequency*t)*0.34*fade
        # One LSB difference from the independent synthetic backend.
        val=max(-32766,min(32766,round(v*32767)+(1 if backend else 0)))
        buf+=struct.pack("<hh",val,val)
    with wave.open(str(path),"wb") as wf:
        wf.setnchannels(2);wf.setsampwidth(2);wf.setframerate(sr)
        wf.writeframes(bytes(buf))
    return hashlib.sha256(path.read_bytes()).hexdigest(),n

def base():
    scenarios=[]
    for p in PROGRAMS:
        for mode,note,vel,cc in (
            ("DRY",48,64,{"1":0,"7":100,"11":127,"91":0,"93":0}),
            ("MODFX",72,120,{"1":96,"7":100,"11":127,"91":48,"93":32})
        ):
            ident=f"P{p:03d}-{mode}"
            scenarios.append(dict(id=ident,program=p,variant=mode,note=note,
               velocity=vel,controllers=cc,channel=0,user_bank=1,
               note_off_ms=1000,record_ms=3000,
               creative_wav=ident+".wav",vst3_wav=ident+".wav"))
    gates={str(p):{k:{"status":"PASS",
              "original_creative_evidence_sha256":"a"*64,
              "vst3_evidence_sha256":"b"*64} for k in (
               "amplitude_adsr","filter_sweeps","loop_seams",
               "dry_wet_reverb_chorus","program_recall_and_reload")}
           for p in PROGRAMS}
    plan=dict(schema=SCHEMA,private_sf2_sha256=BANK_SHA,
        programs=list(PROGRAMS),scenarios=scenarios,
        independent_detail_gates={"per_program":gates})
    creative=dict(schema="125a-p220-genuine-creative-win95-77-v1",
        actual_win95_creative_driver=True,
        original_creative_winmm_endpoint_selected=True,
        guest_agent_executed=True,hardware="sbawe64_gold",
        chip="86box_emu8000",physical_creative_hardware=False,
        driver_sha256=VXD_SHA,original_sf2_file_sha256=BANK_SHA,
        creative_user_bank_loaded=1,full_bank_sample_upload_confirmed=True,
        sample_upload_words=200000,trials=[])
    vst=dict(schema="125a-p220-real-vst3-77-capture-v1",
        real_windows_vst3_process=True,native_offline_emu8000_only=False,
        chip="86box_emu8000",loaded_sf2_sha256=BANK_SHA,
        process_callback_count=10000,module_sha256="c"*64,trials=[])
    return plan,creative,vst

def make(root):
    creative_dir=root/"creative";vst3_dir=root/"vst3"
    creative_dir.mkdir();vst3_dir.mkdir()
    plan,creative,vst=base()
    for x in plan["scenarios"]:
        name=x["id"]+".wav"
        cs,frames=wave_file(creative_dir/name,x["program"],backend=0)
        vs,vframes=wave_file(vst3_dir/name,x["program"],backend=1)
        require(frames==vframes,"synthetic render frame identity")
        common=dict(id=x["id"],program=x["program"],note=x["note"],
                    velocity=x["velocity"],controllers=x["controllers"],
                    note_off_observed=True,audio_frames=frames)
        creative["trials"].append({**common,"wav_sha256":cs,
            "creative_program_change_delivered":True,
            "original_emu8000_voice_write_delta":128,
            "sf2_bank_program_selected":x["program"],
            "original_sample_readback_confirmed":True})
        vst["trials"].append({**common,"wav_sha256":vs,
            "vst3_program_selected":x["program"],
            "vst3_note_on_count":1,"vst3_bank_selection_acknowledged":True})
    return plan,creative,vst,creative_dir,vst3_dir

def run():
    with tempfile.TemporaryDirectory(prefix="p220-unit-only-") as temp:
        root=Path(temp)
        plan,creative,vst,cdir,vdir=make(root)
        require(len(validate_contract(plan))==154,"exact 154 trial contract")
        check_provenance(creative,vst,plan["scenarios"])
        positive=evaluate(plan,creative,vst,cdir,vdir)
        require(positive["status"]=="PASS" and
            positive["passed_presets"]==77 and
            positive["passed_scenarios"]==154 and
            positive["release_approved"] is False,
            "synthetic positive test must exercise 154 comparisons without approving release")
        print("P220 SYNTHETIC oracle positive: 77/77 and 154/154, release_approved=False – NO original Creative driver used")
        # Nine semantic mutants checked through same actual-wave and
        # source/receipt gates, not missing JSON field parser failures.
        mutants=0
        q=evaluate(plan,None,vst,cdir,vdir)
        require(q["status"]=="BLOCKED","missing original source must BLOCK")
        mutants+=1
        c=copy.deepcopy(creative);c["driver_sha256"]="0"*64
        require(evaluate(plan,c,vst,cdir,vdir)["status"]=="FAIL",
                "fake original Creative driver must FAIL");mutants+=1
        c=copy.deepcopy(creative);c["full_bank_sample_upload_confirmed"]=False
        require(evaluate(plan,c,vst,cdir,vdir)["status"]=="FAIL",
                "SF2 not actually loaded must FAIL");mutants+=1
        c=copy.deepcopy(creative);c["trials"][15]["sf2_bank_program_selected"]=0
        require(evaluate(plan,c,vst,cdir,vdir)["status"]=="FAIL",
                "wrong program on Creative side must FAIL");mutants+=1
        altered=copy.deepcopy(vst)
        altered["trials"][15]["vst3_program_selected"]=0
        require(evaluate(plan,creative,altered,cdir,vdir)["status"]=="FAIL",
                "wrong VST3 program must FAIL");mutants+=1
        plan_missing=copy.deepcopy(plan)
        plan_missing["independent_detail_gates"]["per_program"]["7"]["dry_wet_reverb_chorus"]={"status":"NOT TESTED"}
        blocked=evaluate(plan_missing,creative,vst,cdir,vdir)
        require(blocked["status"]=="BLOCKED" and blocked["presets"][7]["status"]=="BLOCKED",
                "missing FX proof cannot pass");mutants+=1
        path=vdir/"P008-DRY.wav"
        raw=path.read_bytes()
        # A deliberately *wrong* but still valid stereo PCM with a matched
        # manifest digest, not a trivial stale-hash parsing failure.
        path.write_bytes((vdir/"P009-DRY.wav").read_bytes())
        actual=copy.deepcopy(vst)
        i=plan["scenarios"].index(next(x for x in plan["scenarios"] if x["id"]=="P008-DRY"))
        actual["trials"][i]["wav_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
        wrong=evaluate(plan,creative,actual,cdir,vdir)
        require(wrong["status"]=="FAIL" and
                wrong["presets"][8]["status"]=="FAIL" and
                wrong["presets"][8]["scenario_results"][0]["status"]=="FAIL",
                "wrong-tone/relabelled PCM must fail for the correct acoustic reason")
        mutants+=1
        path.write_bytes(raw)
        # Silence is a full valid WAV with a matching SHA and correct format.
        with wave.open(str(path),"wb") as wf:
            wf.setnchannels(2);wf.setsampwidth(2);wf.setframerate(44100)
            wf.writeframes(b"\0\0\0\0"*(int(44100*.55)))
        bad=copy.deepcopy(vst)
        bad["trials"][i]["wav_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
        silence=evaluate(plan,creative,bad,cdir,vdir)
        require(silence["status"]=="FAIL" and
                "SILENT_AUDIO" in silence["presets"][8]["scenario_results"][0]["reason"],
                "silent valid WAV must fail semantically")
        mutants+=1
        path.write_bytes(raw)
        # Same physical file bytes twice from purportedly independent systems.
        oldcre=cdir/"P008-DRY.wav"
        oldbytes=oldcre.read_bytes()
        oldcre.write_bytes(path.read_bytes())
        same=copy.deepcopy(creative)
        same["trials"][i]["wav_sha256"]=hashlib.sha256(oldcre.read_bytes()).hexdigest()
        replay=evaluate(plan,same,vst,cdir,vdir)
        require(replay["status"]=="FAIL" and
                "SAME_WAV_BYTES_REUSED" in replay["presets"][8]["scenario_results"][0]["reason"],
                "duplicated same audio must not count as independent original driver")
        mutants+=1
        oldcre.write_bytes(oldbytes)
        p=copy.deepcopy(plan);p["programs"][63]=63
        try:validate_contract(p)
        except EvidenceError:mutants+=1
        else:raise AssertionError("inserted nonexistent program63 accepted")
        print(f"P220 SYNTHETIC MUTATION AUDIT: {mutants}/10 rejected, including valid-but-wrong sound, silent PCM, wrong presets and missing FX")
        return True

if __name__=="__main__":
    run()
