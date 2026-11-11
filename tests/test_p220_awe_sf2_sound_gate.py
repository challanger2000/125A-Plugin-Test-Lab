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
import argparse
import hashlib
import json
import math
import os
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
    sr=44100;n=int(sr*3.0)
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
            "original_sample_start_register_written":True})
        vst["trials"].append({**common,"wav_sha256":vs,
            "vst3_program_selected":x["program"],
            "vst3_note_on_count":1,"vst3_bank_selection_acknowledged":True})
    return plan,creative,vst,creative_dir,vst3_dir

STEREO_TEST_VERSION = "p220-stereo-regression-v2"

def stereo_regressions(root, evidence_out=None):
    """Actual asymmetric PCM/WAV mutants, with fresh matching SHA receipts.

    This tests the existing comparator, not a real Creative/VST3 capture.
    Expected outcomes are fixed before invoking the comparator. Equal
    dual-mono has no observable channel-order information and must pass.
    """
    import struct
    n=44100*3
    def signal(i, channel):
        t=i/44100
        env=(.35+.65*math.exp(-2.1*t))*(.85+.15*math.cos(7*t))
        return round((6000 if channel==0 else 3500)*env*(
            math.sin(2*math.pi*(220 if channel==0 else 440)*t)+
            .19*math.sin(2*math.pi*(617 if channel==0 else 991)*t)))
    stereo=[(signal(i,0),signal(i,1)) for i in range(n)]
    dual=[(l,l) for l,r in stereo]
    anti=[(l,-l) for l,r in stereo]
    hard_left=[(l,0) for l,r in stereo]
    cases=[
        ("asymmetric_independent_lsb",stereo,[(l+1,r-1) for l,r in stereo],"PASS"),
        ("dual_mono_swap",dual,[(r,l) for l,r in dual],"PASS"),
        ("matching_antiphase",anti,[(l+1,r+1) for l,r in anti],"PASS"),
        ("matching_hard_left",hard_left,[(l+1,1) for l,r in hard_left],"PASS"),
        ("common_gain_half_db",stereo,[(round(l*10**(.5/20)),round(r*10**(.5/20))) for l,r in stereo],"PASS"),
        ("common_latency_211_frames",stereo,[(0,0)]*211+stereo[:-211],"PASS"),
        ("left_right_swap",stereo,[(r,l) for l,r in stereo],"FAIL"),
        ("right_silent",stereo,[(l,0) for l,r in stereo],"FAIL"),
        ("left_silent",stereo,[(0,r) for l,r in stereo],"FAIL"),
        ("right_gain_minus_3db",stereo,[(l,round(r*10**(-3/20))) for l,r in stereo],"FAIL"),
        ("right_polarity",stereo,[(l,-r) for l,r in stereo],"FAIL"),
        ("both_polarities",stereo,[(-l,-r) for l,r in stereo],"FAIL"),
        ("right_delay_128_frames",stereo,[(l,stereo[i-128][1] if i>=128 else 0) for i,(l,r) in enumerate(stereo)],"FAIL"),
    ]
    report={"test_version":STEREO_TEST_VERSION,
            "scope":"SYNTHETIC_STEREO_WAV_COMPARATOR_ONLY_NOT_ORIGINAL_CREATIVE_OR_VST3",
            "tool_source_sha256":hashlib.sha256(Path(__file__).with_name("p220_awe_sf2_sound_gate.py").read_bytes()).hexdigest(),
            "test_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "pcm_oracle_source_sha256":hashlib.sha256(Path(__file__).with_name("run_external_daw_capture_check.py").read_bytes()).hexdigest(),
            "github_source_sha":os.environ.get("GITHUB_SHA"),
            "release_approved":False,"cases":[]}
    for index,(name,reference,actual,expected) in enumerate(cases):
        folder=root/f"stereo-{index:02d}-{name}";folder.mkdir()
        decoded=[];hashes=[]
        for side,pcm in (("reference",reference),("capture",actual)):
            d=folder/side;d.mkdir();path=d/"P000-DRY.wav"
            with wave.open(str(path),"wb") as wav:
                wav.setparams((2,2,44100,0,"NONE","not compressed"))
                wav.writeframes(b"".join(struct.pack("<hh",l,r) for l,r in pcm))
            h=hashlib.sha256(path.read_bytes()).hexdigest();hashes.append(h)
            try:decoded.append(exact_wav(d,path.name,h,n))
            except EvidenceError as exc:decoded.append(exc)
        detail={}
        try:
            if any(isinstance(x,Exception) for x in decoded):
                raise next(x for x in decoded if isinstance(x,Exception))
            detail=compare(decoded[0],decoded[1],"DRY")
            observed=detail["status"]
        except EvidenceError as exc:
            observed="FAIL";detail={"reason":str(exc)}
        row={"id":name,"expected":expected,"actual":observed,
             "reference_wav_sha256":hashes[0],"capture_wav_sha256":hashes[1],
             "comparison":detail}
        report["cases"].append(row)
        print("P220_STEREO",name,"expected="+expected,"observed="+observed)
    report["passed_assertions"]=sum(x["expected"]==x["actual"] for x in report["cases"])
    report["assertions"]=len(cases)
    if evidence_out is not None:
        evidence_out.parent.mkdir(parents=True,exist_ok=True)
        evidence_out.write_text(json.dumps(report,indent=2)+"\n")
    require(report["passed_assertions"]==len(cases),
            "asymmetric stereo mutants and legitimate capture controls")
    print("P220_STEREO_REGRESSION",report["passed_assertions"],"/",len(cases),
          "synthetic WAV only; release_approved=False")

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
        from run_unified_qa_gaps import awe77_sound_report
        require(awe77_sound_report(positive,"c"*64)=="PASS",
                "P89 accepts actual complete synthetic stereo-v2 evidence")
        old_report=copy.deepcopy(positive)
        old_report.pop("audio_comparison_version")
        require(awe77_sound_report(old_report,"c"*64)=="BLOCKED",
                "P89 must block cached mono-only report even with green counters")
        missing_stereo=copy.deepcopy(positive)
        missing_stereo["presets"][0]["scenario_results"][0].pop("stereo_comparison")
        require(awe77_sound_report(missing_stereo,"c"*64)=="FAIL",
                "P89 rejects missing case-level stereo proof")
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
            wf.writeframes(b"\0\0\0\0"*(int(44100*3.0)))
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stereo-only",action="store_true")
    parser.add_argument("--stereo-evidence",type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="p220-stereo-unit-only-") as temp:
        stereo_regressions(Path(temp),args.stereo_evidence)
    if not args.stereo_only:
        run()
