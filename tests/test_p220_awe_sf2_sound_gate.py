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
    BANK_SHA,VXD_SHA,PROGRAMS,SCHEMA,LEVEL_TOLERANCE_DB,DRY_SCHEMA,TRACE_SCHEMA,DRY_VERSION,
    dry_compare,evaluate_dry,
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
        require(positive["screen_status"]=="PASS" and positive["status"]=="BLOCKED" and
            positive["sample_exact_dry"]["status"]=="BLOCKED" and
            positive["passed_presets"]==77 and
            positive["passed_scenarios"]==154 and
            positive["release_approved"] is False,
            "synthetic positive test must exercise 154 comparisons without approving release")
        from run_unified_qa_gaps import awe77_sound_report
        require(awe77_sound_report(positive,"c"*64)=="BLOCKED",
                "P89 blocks legacy screen without actual event-bounded dry evidence")
        old_report=copy.deepcopy(positive)
        old_report.pop("audio_comparison_version")
        require(awe77_sound_report(old_report,"c"*64)=="BLOCKED",
                "P89 must block cached mono-only report even with green counters")
        missing_stereo=copy.deepcopy(positive)
        missing_stereo["status"]="PASS"  # Adversarial forged top-level green.
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

def dry_regressions(root,evidence_out=None,*,compare_baseline=False,fixtures_out=None):
    """Existing P220 WAV/comparator path; no real ROM, driver or VST3 used.

    Faults have fresh matching WAV/trace/approved-fixture hashes, so semantic
    failures cannot be attributed to stale receipts. The source gate stays
    BLOCKED even for every acoustically positive synthetic control.
    """
    import struct
    baseline=None;baseline_sources={}
    baseline_sha="f96213b20f234eef2c6fadf8d0706818cc5681dd"
    if compare_baseline:
        import subprocess,types
        previous=sys.modules.get("run_external_daw_capture_check")
        try:
            modules=[]
            for name in ("run_external_daw_capture_check","p220_awe_sf2_sound_gate"):
                raw=subprocess.check_output(["git","show",baseline_sha+":tests/"+name+".py"],cwd=Path(__file__).resolve().parent)
                baseline_sources[name]=hashlib.sha256(raw).hexdigest()
                module=types.ModuleType("_p220_before_"+name)
                exec(compile(raw,baseline_sha+":"+name,"exec"),module.__dict__)
                modules.append(module)
                if len(modules)==1:sys.modules["run_external_daw_capture_check"]=module
            baseline=modules[-1]
        finally:
            if previous is None:sys.modules.pop("run_external_daw_capture_check",None)
            else:sys.modules["run_external_daw_capture_check"]=previous
    n=132300;pre=4410;off=pre+44100
    reference=[]
    for i in range(n):
        t=(i-pre)/44100
        envelope=0 if t<0 else min(1,t/.008)*(.55+.45*math.exp(-2*t))
        if i>=off:envelope*=math.exp(-8*(i-off)/44100)
        reference.append(tuple(round(envelope*amplitude*(math.sin(2*math.pi*hz*t)+
            .13*math.sin(2*math.pi*(hz*2.71)*t))) for amplitude,hz in ((7000,233),(4200,397))))

    def midi_frame(event,frame,blocks):
        b=next(b for b in blocks if b["start_frame"]<=frame<b["start_frame"]+b["frames"])
        event.update(frame=frame,block_start=b["start_frame"],sample_offset=frame-b["start_frame"])

    def fixture(folder,mutate=None,*,prefix=211,block=512,style="stereo",daw=False,lsb=1):
        spec={"schema":DRY_SCHEMA,"rom_sha256":"d"*64,"bank_sha256":BANK_SHA,
              "sample_rate":44100,"channels":["L","R"],"pre_note_frames":pre,
              "note_length_frames":44100,"window_frames":n,"vst3_module_sha256":"c"*64,
              "vst3_capture_kind":"WINDOWS_DAW_VST3" if daw else "WINDOWS_VST3","captures":{"P000-DRY":{}}}
        f=base()[0]["scenarios"][0]
        state={"spec":spec,"fixture":f,"traces":{},"pcm":{},"receipts":{},"rates":{}}
        for backend,prefix_frames,quantum in (("creative",37,128),("vst3",prefix,block)):
            pcm=reference
            if style=="hard_left":pcm=[(l,0) for l,r in reference]
            if style=="antiphase":pcm=[(l,-l) for l,r in reference]
            if style=="silent_release":pcm=[(l,r) if i<off else (0,0) for i,(l,r) in enumerate(reference)]
            if backend=="vst3":pcm=[(l+lsb if l else 0,r-lsb if r else 0) for l,r in pcm]
            frames=math.ceil((prefix_frames+n)/quantum)*quantum
            pcm=[(0,0)]*prefix_frames+pcm+[(0,0)]*(frames-prefix_frames-n)
            blocks=[{"start_frame":i,"frames":min(quantum,frames-i)} for i in range(0,frames,quantum)]
            on=prefix_frames+pre;end=on+44100
            events=[{"sequence":0,"kind":"bank_program","channel":0,"bank":1,"program":0},
                    {"sequence":1,"kind":"note_on","channel":0,"note":48,"velocity":64},
                    {"sequence":2,"kind":"note_off","channel":0,"note":48,"velocity":0}]
            for event,frame in zip(events,(0,on,end)):midi_frame(event,frame,blocks)
            trace={"schema":TRACE_SCHEMA,"backend":backend,"capture_kind":"SYNTHETIC_FIXTURE",
                   "audio_tap":"86box_emu8000_stereo_output" if backend=="creative" else
                      "windows_daw_post_plugin_output" if daw else "windows_vst3_process_output",
                   "channel_map":["L","R"],"rom_sha256":"d"*64,"bank_sha256":BANK_SHA,
                   "sample_rate":44100,"program":0,"bank":1,"channel":0,"note":48,"velocity":64,
                   "driver_sha256":VXD_SHA,"module_sha256":"c"*64,"audio_frames":frames,
                   "process_blocks":blocks,"midi_events":events,"voices":[0],
                   "sample_events":[{"kind":kind,"frame":frame,"sample_counter":frame+11,"midi_sequence":i}
                                    for kind,frame,i in (("voice_start",on,1),("voice_release",end,2))],
                   "register_events":[{"voice":0,"kind":kind,"frame":frame,"midi_sequence":i}
                                      for kind,frame,i in (("voice_start",on,1),("voice_release",end,2))],
                   "window":{"start_frame":prefix_frames,"frames":n,
                             "discarded_prefix_frames":prefix_frames,"discarded_suffix_frames":frames-prefix_frames-n},
                   "effects":{"requested_percent":{"reverb":0,"chorus":0},
                              "control_origin":"CREATIVE_CONTROL" if backend=="creative" else "PLUGIN_GUI",
                              "control_events":[{"control":control,"origin":"CREATIVE_CONTROL" if backend=="creative" else "PLUGIN_GUI",
                                  "frame":0,"display_percent":0,"controller_value":0,"processor_value":0}
                                  for control in ("reverb","chorus")],
                              "observed_start_frame":0,"observed_frames":frames,"complete_write_history":True,
                              "initial_voice_sends":[{"voice":i,"reverb":0,"chorus":0} for i in range(32)],
                              "final_voice_sends":[{"voice":i,"reverb":0,"chorus":0} for i in range(32)],
                              "send_writes":[],"return_mute":{"reverb":True,"chorus":True}}}
            if daw:trace["daw_session"]={"name":"SYNTHETIC_DAW_FIXTURE","version":"test-only",
                "insert_effect_count":0,"track_gain_db":0,"master_gain_db":0,"normalized":False}
            spec["captures"][f["id"]][backend]={"sample_to_audio_offset_frames":-11,
                         "midi_to_sample_on_frames":0,"midi_to_sample_off_frames":0}
            state["traces"][backend]=trace;state["pcm"][backend]=pcm;state["rates"][backend]=44100
            state["receipts"][backend]={"audio_frames":frames,"event_trace":f["id"]+".events.json"}
        if mutate:mutate(state)
        for backend in ("creative","vst3"):
            d=folder/backend;d.mkdir(parents=True)
            path=d/(f["id"]+".wav")
            with wave.open(str(path),"wb") as wf:
                wf.setparams((2,2,state["rates"][backend],0,"NONE","not compressed"))
                wf.writeframes(b"".join(struct.pack("<hh",l,r) for l,r in state["pcm"][backend]))
            h=hashlib.sha256(path.read_bytes()).hexdigest()
            trace=state["traces"][backend];trace["wav_sha256"]=h
            trace_bytes=(json.dumps(trace,sort_keys=True)+"\n").encode()
            (d/(f["id"]+".events.json")).write_bytes(trace_bytes)
            th=hashlib.sha256(trace_bytes).hexdigest()
            state["receipts"][backend].update(wav_sha256=h,event_trace_sha256=th)
            spec["captures"][f["id"]][backend].update(wav_sha256=h,trace_sha256=th)
        return state

    def change_note_off(s):
        t=s["traces"]["vst3"];midi_frame(t["midi_events"][2],t["midi_events"][2]["frame"]+1,t["process_blocks"])
    def change_register_off(s):
        t=s["traces"]["vst3"];t["sample_events"][1]["frame"]+=1;t["sample_events"][1]["sample_counter"]+=1
        t["register_events"][1]["frame"]+=1
    def change_pcm(s,which):
        t=s["traces"]["vst3"];start=t["window"]["start_frame"]
        pcm=s["pcm"]["vst3"]
        if which=="swap":s["pcm"]["vst3"]=[(r,l) for l,r in pcm]
        elif which=="gain":s["pcm"]["vst3"]=[(round(l*10**(.5/20)),round(r*10**(.5/20))) for l,r in pcm]
        elif which=="onset":s["pcm"]["vst3"]=[(0,0)]+pcm[:-1]
        elif which=="release":
            for i in range(start+off,start+off+441):pcm[i]=pcm[i-441]
        elif which=="wet":
            for i in range(start+n-400,start+n):
                l,r=pcm[i];pcm[i]=(l+round(120*math.sin(i*.17)),r)
        elif which=="single_frame":
            i=start+n-2;l,r=pcm[i];pcm[i]=(l,r+23)
        elif which=="short":s["pcm"]["vst3"]=pcm[:-1]

    def tr(s):return s["traces"]["vst3"]
    def early_audio(s):
        for backend in ("creative","vst3"):
            index=s["traces"][backend]["window"]["start_frame"]+100
            s["pcm"][backend][index]=(100,100)
    cases=[
        ("independent_1lsb",None,"PASS",{}),
        ("independent_2lsb_budget",None,"PASS",{"lsb":2}),
        ("different_partitions_and_transport_offset",None,"PASS",{"prefix":997,"block":17}),
        ("matching_hard_left",None,"PASS",{"style":"hard_left"}),
        ("matching_antiphase",None,"PASS",{"style":"antiphase"}),
        ("matching_silent_release",None,"PASS",{"style":"silent_release"}),
        ("neutral_daw_contract_fixture",None,"PASS",{"daw":True}),
        ("shifted_midi_note_off",change_note_off,"FAIL",{}),
        ("shifted_register_note_off",change_register_off,"FAIL",{}),
        ("shifted_audible_release",lambda s:change_pcm(s,"release"),"FAIL",{}),
        ("extra_dsp_block_in_window",lambda s:tr(s)["window"].update(frames=n+512),"FAIL",{}),
        ("window_start_not_event_bound",lambda s:tr(s)["window"].update(start_frame=212),"FAIL",{}),
        ("wav_one_frame_short",lambda s:change_pcm(s,"short"),"FAIL",{}),
        ("nonzero_final_hardware_send",lambda s:tr(s)["effects"]["final_voice_sends"][31].update(chorus=1),"FAIL",{}),
        ("transient_send_on_other_voice",lambda s:tr(s)["effects"]["send_writes"].append(
            {"frame":7000,"voice":31,"chorus":1,"reverb":0}),"FAIL",{}),
        ("wet_return_not_muted",lambda s:tr(s)["effects"]["return_mute"].update(reverb=False),"FAIL",{}),
        ("gui_not_zero",lambda s:tr(s)["effects"]["requested_percent"].update(chorus=1),"FAIL",{}),
        ("gui_zero_processor_not_zero",lambda s:tr(s)["effects"]["control_events"][0].update(processor_value=.01),"FAIL",{}),
        ("gui_zero_controller_not_zero",lambda s:tr(s)["effects"]["control_events"][0].update(controller_value=.01),"FAIL",{}),
        ("incomplete_send_history",lambda s:tr(s)["effects"].update(complete_write_history=False),"FAIL",{}),
        ("hidden_wet_pcm_despite_zero_metadata",lambda s:change_pcm(s,"wet"),"FAIL",{}),
        ("one_late_sample_fault",lambda s:change_pcm(s,"single_frame"),"FAIL",{}),
        ("gain_half_db_must_not_be_normalized",lambda s:change_pcm(s,"gain"),"FAIL",{}),
        ("shifted_pcm_cannot_be_realigned",lambda s:change_pcm(s,"onset"),"FAIL",{}),
        ("audio_before_note_on_in_both_sources",early_audio,"FAIL",{}),
        ("wrong_audio_tap",lambda s:tr(s).update(audio_tap="native_engine_diagnostic_output"),"FAIL",{}),
        ("wrong_channel_metadata",lambda s:tr(s).update(channel_map=["R","L"]),"FAIL",{}),
        ("swapped_actual_stereo",lambda s:change_pcm(s,"swap"),"FAIL",{}),
        ("wrong_rom_hash",lambda s:tr(s).update(rom_sha256="e"*64),"FAIL",{}),
        ("wrong_bank_hash",lambda s:tr(s).update(bank_sha256="e"*64),"FAIL",{}),
        ("wrong_program",lambda s:tr(s).update(program=1),"FAIL",{}),
        ("wrong_velocity",lambda s:tr(s).update(velocity=65),"FAIL",{}),
        ("wrong_note",lambda s:tr(s).update(note=49),"FAIL",{}),
        ("wrong_wav_samplerate",lambda s:s["rates"].update(vst3=48000),"FAIL",{}),
        ("wrong_trace_samplerate",lambda s:tr(s).update(sample_rate=48000),"FAIL",{}),
        ("wrong_vst3_module",lambda s:tr(s).update(module_sha256="f"*64),"FAIL",{}),
        ("wrong_clock_calibration",lambda s:s["spec"]["captures"]["P000-DRY"]["vst3"].update(sample_to_audio_offset_frames=-10),"FAIL",{}),
        ("midi_event_outside_process_block",lambda s:tr(s)["midi_events"][1].update(sample_offset=8192),"FAIL",{}),
        ("process_block_gap",lambda s:tr(s)["process_blocks"][1].update(start_frame=513),"FAIL",{}),
        ("native_diagnostic_is_not_vst3",lambda s:tr(s).update(capture_kind="NATIVE_ENGINE_DIAGNOSTIC"),"BLOCKED",{}),
        ("synthetic_is_not_original_capture",None,"BLOCKED",{"production":True}),
        ("daw_gain_not_neutral",lambda s:tr(s)["daw_session"].update(track_gain_db=.5),"FAIL",{"daw":True}),
    ]
    report={"test_version":"p220-dry-regression-v1","comparison_version":DRY_VERSION,
            "scope":"SYNTHETIC_TEST_OF_EXISTING_P220_P90_NOT_REAL_CAPTURE",
            "release_approved":False,"original_creative_audio":"NOT RUN","actual_windows_vst3_audio":"NOT RUN",
            "github_source_sha":os.environ.get("GITHUB_SHA"),"cases":[],
            "self_challenge":"same-agent historical-source negative control, not independent review",
            "baseline_commit":baseline_sha if baseline else None,"baseline_source_sha256":baseline_sources,
            "source_sha256":{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("p220_awe_sf2_sound_gate.py","run_external_daw_capture_check.py",Path(__file__).name)}}
    for index,(name,mutate,expected,options) in enumerate(cases):
        folder=root/f"dry-{index:02d}-{name}";options=dict(options);production=options.pop("production",False)
        state=fixture(folder,mutate,**options)
        result=dry_compare(state["spec"],state["fixture"],state["receipts"]["creative"],state["receipts"]["vst3"],
                           folder/"creative",folder/"vst3",allow_synthetic=not production)
        observed="PASS" if result["comparison_status"]=="PASS" else result["status"]
        require(observed==expected,name+": expected "+expected+" observed "+observed+" "+str(result.get("reason")))
        require(result["release_approved"] is False and result["status"]!="PASS",name+" cannot approve synthetic sound")
        row={"id":name,"expected":expected,"actual":observed,"result":result}
        if baseline and name in ("independent_1lsb","shifted_midi_note_off","extra_dsp_block_in_window",
                                 "hidden_wet_pcm_despite_zero_metadata","one_late_sample_fault",
                                 "gain_half_db_must_not_be_normalized","shifted_pcm_cannot_be_realigned"):
            a,b=[baseline.exact_wav(folder/backend,"P000-DRY.wav",state["receipts"][backend]["wav_sha256"],n)
                 for backend in ("creative","vst3")]
            old=baseline.compare(a,b,"DRY")
            require(old["status"]=="PASS",name+": historical comparator control must actually PASS")
            row["historical_comparator"]={"commit":baseline_sha,"status":old["status"],
                                           "measured_audio_frames":old["measured_audio_frames"]}
        if fixtures_out and name in ("independent_1lsb","shifted_midi_note_off",
                                    "extra_dsp_block_in_window","hidden_wet_pcm_despite_zero_metadata"):
            import shutil
            target=fixtures_out/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(folder,target)
            (target/"SYNTHETIC-INPUTS.json").write_text(json.dumps({
                "scope":"SYNTHETIC_ONLY_NOT_CREATIVE_OR_VST3","spec":state["spec"],
                "fixture":state["fixture"],"receipts":state["receipts"]},indent=2)+"\n",encoding="utf-8")
        report["cases"].append(row)
        print("P220_DRY",name,"expected="+expected,"observed="+observed,flush=True)
    report["assertions"]=len(cases);report["passed_assertions"]=len(report["cases"])
    if evidence_out:
        evidence_out.parent.mkdir(parents=True,exist_ok=True)
        evidence_out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("P220_DRY_REGRESSION",len(cases),"/",len(cases),"synthetic only; real sound BLOCKED",flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stereo-only",action="store_true")
    parser.add_argument("--stereo-evidence",type=Path)
    parser.add_argument("--dry-only",action="store_true")
    parser.add_argument("--dry-evidence",type=Path)
    parser.add_argument("--compare-baseline",action="store_true")
    parser.add_argument("--dry-fixtures-out",type=Path)
    args=parser.parse_args()
    if not args.dry_only:
        with tempfile.TemporaryDirectory(prefix="p220-stereo-unit-only-") as temp:
            stereo_regressions(Path(temp),args.stereo_evidence)
    if args.dry_only or args.dry_evidence:
        with tempfile.TemporaryDirectory(prefix="p220-dry-unit-only-") as temp:
            dry_regressions(Path(temp),args.dry_evidence,compare_baseline=args.compare_baseline,
                            fixtures_out=args.dry_fixtures_out)
    if not args.stereo_only and not args.dry_only:
        run()
