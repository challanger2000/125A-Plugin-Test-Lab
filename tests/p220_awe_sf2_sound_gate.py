#!/usr/bin/env python3
"""P220 original Creative Win95 -> 86Box EMU8000 vs real Windows VST3 SF2 audio.

FAIL CLOSED. 77-program audio-domain release gate, not an audio generator.
Only original independently captured WAV and real VST3 WAV count. Synthetic
fixtures validate fault detection, NEVER count as original driver testing.
No physical Creative hardware identity is inferred from a common 86Box chip.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
import wave
from pathlib import Path

SCHEMA = "125a-awe-sf2-77-audio-contract-v1"
RESULT_SCHEMA = "125a-testlab-awe-sf2-77-sonic-gate-v1"
BANK_SHA = "d5b99ec38fddf59f53f66b90921e170d207bf3bbd73960f6e4175c39ef68349b"
VXD_SHA = "d343f2428ab3e593c9e42a668cf521b7801e1239792eaf7f2b11b5f179bc7c9a"
PROGRAMS = tuple(p for p in range(78) if p != 63)
SHA = re.compile(r"^[0-9a-f]{64}$")
FID = re.compile(r"^P(\d{3})-(DRY|MODFX)$")
FRAME_RATE = 44100
# These are conservative **screening** tolerances for emulator-A/B only,
# NOT measured physical AWE64 or a claim of perceptual equivalence.
LEVEL_TOLERANCE_DB = 1.0
ENVELOPE_CORR_MIN = 0.90
SPECTRAL_DIFF_DB_MAX = 4.0
ONSET_LAG_MAX_MS = 250
MIN_RMS = 0.00015
MAX_BYTES = 8 * 1024 * 1024
MAX_WAV_BYTES = 20 * 1024 * 1024

class EvidenceError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise EvidenceError(message)

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def exact_wav(root, fname, expected_sha, expected_frames):
    require(isinstance(fname, str) and re.fullmatch(r"P\d{3}-(DRY|MODFX)\.wav",fname),
            "UNSAFE_OR_MISMATCHED_FILENAME")
    require(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha),
            "MISSING_EXACT_WAV_SHA")
    path = root / fname
    require(path.is_file(), "MISSING_AUDIO_CAPTURE:"+fname)
    require(44 <= path.stat().st_size <= MAX_WAV_BYTES,
            "EMPTY_OR_OVERSIZED_WAV:"+fname)
    raw = path.read_bytes()
    require(sha256(raw) == expected_sha, "STALE_OR_SWAPPED_AUDIO_SHA:"+fname)
    with wave.open(str(path),"rb") as wf:
        params = (wf.getnchannels(),wf.getsampwidth(),wf.getframerate(),wf.getcomptype())
        require(params == (2,2,FRAME_RATE,"NONE"),
                "INVALID_FORMAT:"+fname+":"+str(params))
        frames = wf.getnframes()
        require(FRAME_RATE // 2 <= frames <= FRAME_RATE * 8 and
                type(expected_frames) is int and
                abs(frames-expected_frames)<=FRAME_RATE//5,
                "INVALID_CAPTURE_DURATION_OR_MIDI_TIMELINE:"+fname)
        samples = wf.readframes(frames)
    require(len(samples)==frames*4,"TRUNCATED_PCM:"+fname)
    # Unpack stereo little-endian signed 16-bit without external dependencies.
    vals = struct.unpack("<"+str(frames*2)+"h",samples)
    mono = [(vals[i]+vals[i+1])/65536.0 for i in range(0,len(vals),2)]
    stereo_peak = max(abs(v) for v in vals)/32768.0
    require(stereo_peak < 0.99997, "CLIPPED_PCM:"+fname)
    total_rms = math.sqrt(sum(x*x for x in mono)/len(mono))
    require(total_rms >= MIN_RMS,"SILENT_AUDIO:"+fname)
    block = 441
    e = [math.sqrt(sum(x*x for x in mono[i:i+block])/block)
         for i in range(0,len(mono)-block+1,block)]
    onset_threshold = max(MIN_RMS, max(e)*0.08)
    eligible = [i for i,a in enumerate(e) if a >= onset_threshold]
    require(eligible,"NO_AUDIBLE_ONSET:"+fname)
    onset = eligible[0]
    return {"sha256":sha256(raw),"frames":frames,"mono":mono,
            "envelope":e,"onset_bin":onset,"rms":total_rms,
            "peak":stereo_peak}

def band_spectrum(mono, start):
    # Audio spectrum in 8 fixed Goertzel bands, per stable 1024-frame window.
    # This is an independent *diagnostic screening* metric; waveform-level
    # filter shape, full loop identity and actual physical chip need more.
    N = 1024
    centers = (110,220,440,880,1760,3520,7040,11000)
    start = max(0,min(len(mono)-N,start))
    window = [mono[start+j]*(0.5-0.5*math.cos(2*math.pi*j/(N-1)))
              for j in range(N)]
    power = []
    for hz in centers:
        k = max(1,round(hz*N/FRAME_RATE))
        coeff = 2*math.cos(2*math.pi*k/N)
        a=b=0.0
        for x in window:
            nxt = x+coeff*a-b
            b=a;a=nxt
        power.append(max(a*a+b*b-coeff*a*b,1e-20))
    whole=sum(power)
    return [10*math.log10(v/whole) for v in power]

def corr(a,b):
    require(len(a)==len(b) and len(a)>10,"INVALID_ENVELOPE_ALIGNMENT")
    aa = [math.log10(max(x,1e-6)) for x in a]
    bb = [math.log10(max(x,1e-6)) for x in b]
    am=sum(aa)/len(aa);bm=sum(bb)/len(bb)
    num=sum((x-am)*(y-bm) for x,y in zip(aa,bb))
    den=math.sqrt(sum((x-am)**2 for x in aa)*sum((y-bm)**2 for y in bb))
    return num/den if den>1e-12 else 0.0

def compare(a,b,kind):
    # Remove *only* variable starting silence. Do not RMS-normalize first:
    # absolute level differences are an independent release-critical result.
    a_e=a["envelope"];b_e=b["envelope"]
    lag_ms=abs(a["onset_bin"]-b["onset_bin"])*10
    require(lag_ms <= ONSET_LAG_MAX_MS,"UNBOUNDED_CAPTURE_ONSET_LAG")
    x=a_e[a["onset_bin"]:];y=b_e[b["onset_bin"]:]
    window=min(len(x),len(y),150)
    require(window>=50,"INSUFFICIENT_ALIGNED_AUDIO")
    envelope_corr=corr(x[:window],y[:window])
    # Measure gain on active audio after onset, not pre-roll silence.
    frames=min(a["frames"]-a["onset_bin"]*441,
               b["frames"]-b["onset_bin"]*441,FRAME_RATE*2)
    require(frames>=FRAME_RATE//2,"INSUFFICIENT_ACTIVE_PCM")
    aa=a["mono"][a["onset_bin"]*441:a["onset_bin"]*441+frames]
    bb=b["mono"][b["onset_bin"]*441:b["onset_bin"]*441+frames]
    rms_a=math.sqrt(sum(v*v for v in aa)/frames)
    rms_b=math.sqrt(sum(v*v for v in bb)/frames)
    require(rms_a>=MIN_RMS and rms_b>=MIN_RMS,"NO_PLAYABLE_NOTE_AUDIO")
    gain_db=20*math.log10(rms_b/rms_a)
    spec_a=band_spectrum(a["mono"],a["onset_bin"]*441+1000)
    spec_b=band_spectrum(b["mono"],b["onset_bin"]*441+1000)
    spectral_differences=[round(y-x,3) for x,y in zip(spec_a,spec_b)]
    # Inaudible FFT-bin leakage must not cause a false spectral FAIL.
    # Preserve the full diagnostics but gate only bands having meaningful
    # energy in at least one backend (relative to its own measured spectrum).
    audible=[abs(d) for d,x,y in zip(spectral_differences,spec_a,spec_b)
             if max(x,y)>-42]
    require(audible,"NO_USABLE_SPECTRAL_ENERGY")
    max_abs=max(audible)
    # Tails are only measured when the recorded MIDI schedule includes
    # a verified NoteOff. Their separate loop/effect semantics are gated
    # by playback evidence rather than pretending this determines hardware.
    passed=(abs(gain_db)<=LEVEL_TOLERANCE_DB and
            envelope_corr>=ENVELOPE_CORR_MIN and
            max_abs<=SPECTRAL_DIFF_DB_MAX)
    return {"status":"PASS" if passed else "FAIL",
            "rms_level_native_minus_creative_db":round(gain_db,3),
            "log_envelope_correlation":round(envelope_corr,5),
            "onset_lag_ms":lag_ms,
            "spectrum_native_minus_creative_db_8_centers":spectral_differences,
            "max_abs_spectral_difference_db":round(max_abs,3),
            "center_frequencies_hz":[110,220,440,880,1760,3520,7040,11000],
            "measured_audio_frames":frames,
            "scope":"emulated EMU8000 original Win95 driver vs real VST3; NOT physical AWE64"}

def load_json(path):
    if path is None or not Path(path).is_file():
        return None
    path=Path(path)
    require(0 < path.stat().st_size <= MAX_BYTES,"MISSING_OR_OVERSIZED_JSON:"+path.name)
    return json.loads(path.read_text(encoding="utf-8"))

def validate_contract(c):
    require(isinstance(c,dict) and c.get("schema")==SCHEMA,"MISSING_APPROVED_CAPTURE_CONTRACT")
    require(c.get("private_sf2_sha256")==BANK_SHA,"WRONG_PRIVATE_77_BANK_SHA")
    require(c.get("programs")==list(PROGRAMS),"NOT_EXACTLY_77_PROGRAMS_NO_63")
    # The trial definition is frozen independently of whatever any backend
    # actually synthesized. No hidden ROM/fallback and no reordered phdr.
    scenarios=c.get("scenarios")
    require(isinstance(scenarios,list) and len(scenarios)==154,
            "MISSING_2_SCENARIOS_PER_77_PRESETS")
    expected=[(p,k) for p in PROGRAMS for k in ("DRY","MODFX")]
    seen=[]
    for x in scenarios:
        require(isinstance(x,dict),"INVALID_SCENARIO_OBJECT")
        p=x.get("program");k=x.get("variant")
        seen.append((p,k))
        expected_note,expected_vel=(48,64) if k=="DRY" else (72,120)
        require(x.get("id")==f"P{p:03d}-{k}" and
                x.get("note")==expected_note and x.get("velocity")==expected_vel and
                x.get("channel")==0 and x.get("user_bank")==1 and
                x.get("note_off_ms")==1000 and x.get("record_ms")==3000,
                "MIDI_SCENARIO_CHANGED_OR_SWAPPED")
        cc=x.get("controllers")
        approved=({"1":0,"7":100,"11":127,"91":0,"93":0} if k=="DRY"
                  else {"1":96,"7":100,"11":127,"91":48,"93":32})
        require(cc==approved,"UNAPPROVED_CC_OR_EFFECT_SETTINGS")
        require(x.get("creative_wav")==x["id"]+".wav" and
                x.get("vst3_wav")==x["id"]+".wav",
                "CAPTURE_NAME_IDENTITY_CHANGED")
    require(seen==expected and len(set(seen))==154,
            "PRESET_ORDER_MISSING_OR_DUPLICATE")
    return scenarios

def check_provenance(creative,vst3,scenarios):
    require(isinstance(creative,dict) and isinstance(vst3,dict),
            "MISSING_ORIGINAL_DRIVER_OR_VST3_PROVENANCE")
    require(creative.get("schema")=="125a-p220-genuine-creative-win95-77-v1" and
            creative.get("actual_win95_creative_driver") is True and
            creative.get("original_creative_winmm_endpoint_selected") is True and
            creative.get("guest_agent_executed") is True and
            creative.get("hardware")=="sbawe64_gold" and
            creative.get("chip")=="86box_emu8000" and
            creative.get("physical_creative_hardware") is False and
            creative.get("driver_sha256")==VXD_SHA and
            creative.get("original_sf2_file_sha256")==BANK_SHA and
            creative.get("creative_user_bank_loaded")==1 and
            creative.get("full_bank_sample_upload_confirmed") is True and
            type(creative.get("sample_upload_words")) is int and
            creative.get("sample_upload_words")>0,
            "ORIGINAL_CREATIVE_DRIVER_OR_FULL_BANK_LOAD_NOT_PROVED")
    require(vst3.get("schema")=="125a-p220-real-vst3-77-capture-v1" and
            vst3.get("real_windows_vst3_process") is True and
            vst3.get("native_offline_emu8000_only") is False and
            vst3.get("chip")=="86box_emu8000" and
            vst3.get("loaded_sf2_sha256")==BANK_SHA and
            type(vst3.get("process_callback_count")) is int and
            vst3["process_callback_count"]>0 and
            isinstance(vst3.get("module_sha256"),str) and
            SHA.fullmatch(vst3["module_sha256"]),
            "REAL_WINDOWS_VST3_PROCESS_AND_BANK_NOT_PROVED")
    c=creative.get("trials");v=vst3.get("trials")
    require(isinstance(c,list) and isinstance(v,list) and
            len(c)==len(v)==len(scenarios),"MISSING_INDEPENDENT_154_CAPTURE_RECEIPTS")
    for index,(fixture,cr,vr) in enumerate(zip(scenarios,c,v)):
        label=fixture["id"]
        for receipt,backend in ((cr,"CREATIVE"),(vr,"VST3")):
            require(isinstance(receipt,dict) and
                receipt.get("id")==label and
                receipt.get("program")==fixture["program"] and
                receipt.get("note")==fixture["note"] and
                receipt.get("velocity")==fixture["velocity"] and
                receipt.get("controllers")==fixture["controllers"] and
                receipt.get("note_off_observed") is True and
                type(receipt.get("audio_frames")) is int and
                receipt.get("audio_frames")>=FRAME_RATE//2 and
                isinstance(receipt.get("wav_sha256"),str) and
                SHA.fullmatch(receipt["wav_sha256"]),
                backend+"_MISSING_OR_MISMATCHED_MIDI_AUDIO_RECEIPT:"+str(index))
        require(cr.get("creative_program_change_delivered") is True and
                type(cr.get("original_emu8000_voice_write_delta")) is int and
                cr["original_emu8000_voice_write_delta"]>0 and
                cr.get("sf2_bank_program_selected")==fixture["program"] and
                cr.get("original_sample_readback_confirmed") is True,
                "CREATIVE_PROGRAM_FALLBACK_OR_NO_SAMPLE_USED:"+label)
        require(vr.get("vst3_program_selected")==fixture["program"] and
                type(vr.get("vst3_note_on_count")) is int and
                vr["vst3_note_on_count"]>0 and
                vr.get("vst3_bank_selection_acknowledged") is True,
                "VST3_WRONG_PRESET_OR_MISSING_AUDIO_PROCESS:"+label)

def evaluate(contract,creative,vst3,creative_dir,vst3_dir):
    scenarios=validate_contract(contract)
    report={"schema":RESULT_SCHEMA,
        "private_sf2_sha256":BANK_SHA,
        "original_creative_driver_sha256":VXD_SHA,
        "expected_programs":77,"expected_scenarios":154,
        "original_driver_logic":"real Creative Win95 WinMM, IF source receipt verified",
        "reference_chip":"86Box EMU8000, not a physical Creative AWE64",
        "real_physical_awe64":"NOT TESTED","Studio_One_ASIO":"NOT TESTED",
        "release_approved":False,"status":"BLOCKED","errors":[],
        "presets":[{"program":p,"status":"BLOCKED","scenario_results":[],
                    "reason":"NO_INDEPENDENT_TWO_BACKEND_PCM"} for p in PROGRAMS]}
    if creative is None or vst3 is None:
        report["errors"].append("MISSING_REAL_CREATIVE_OR_WINDOWS_VST3_CAPTURE_RECEIPTS")
        return report
    try:
        check_provenance(creative,vst3,scenarios)
    except (EvidenceError,KeyError,TypeError) as exc:
        report["status"]="FAIL"
        report["errors"].append(str(exc))
        return report
    report["vst3_module_sha256"]=vst3["module_sha256"]
    report["original_creative_full_bank_capture_verified"]=True
    report["actual_windows_vst3_audio_captured"]=True
    all_good=True
    for i,p in enumerate(PROGRAMS):
        row=report["presets"][i]
        row["status"]="PASS"
        row["reason"]=None
    for fixture,cr,vr in zip(scenarios,creative["trials"],vst3["trials"]):
        p=fixture["program"]
        row=report["presets"][PROGRAMS.index(p)]
        entry={"id":fixture["id"],"variant":fixture["variant"],
               "note":fixture["note"],"velocity":fixture["velocity"],
               "controllers":fixture["controllers"],"status":"FAIL"}
        try:
            target_frames=fixture["record_ms"]*FRAME_RATE//1000
            a=exact_wav(Path(creative_dir),fixture["creative_wav"],cr["wav_sha256"],target_frames)
            b=exact_wav(Path(vst3_dir),fixture["vst3_wav"],vr["wav_sha256"],target_frames)
            require(a["frames"]==cr["audio_frames"] and
                    b["frames"]==vr["audio_frames"],
                    "RECEIPT_FRAME_COUNT_DOES_NOT_MATCH_ACTUAL_WAV")
            require(a["sha256"]!=b["sha256"],
                    "SAME_WAV_BYTES_REUSED_AS_INDEPENDENT_CREATIVE_AND_VST3")
            entry.update(compare(a,b,fixture["variant"]))
            entry["creative_wav_sha256"]=a["sha256"]
            entry["vst3_wav_sha256"]=b["sha256"]
        except (EvidenceError,ValueError,OSError,EOFError,wave.Error) as exc:
            entry["reason"]=str(exc)
        row["scenario_results"].append(entry)
        if entry["status"]!="PASS":
            row["status"]="FAIL";all_good=False
    # A two-scenario screen cannot prove actual loop boundaries and chorus
    # algorithm identity for every possible SF2 instrument. Explicitly
    # require separately attested targeted tests before full SONIC gate PASS.
    extra=contract.get("independent_detail_gates",{})
    mandatory=("amplitude_adsr","filter_sweeps","loop_seams",
               "dry_wet_reverb_chorus","program_recall_and_reload")
    per=extra.get("per_program",{}) if isinstance(extra,dict) else {}
    for row in report["presets"]:
        key=str(row["program"])
        relevant=per.get(key,{}) if isinstance(per,dict) else {}
        incomplete=[k for k in mandatory if not
                    (isinstance(relevant.get(k),dict) and
                     relevant[k].get("status")=="PASS" and
                     relevant[k].get("original_creative_evidence_sha256") and
                     relevant[k].get("vst3_evidence_sha256"))]
        row["detail_gates"]={k:relevant.get(k,{"status":"NOT TESTED"})
                            for k in mandatory}
        if incomplete:
            row["status"]="BLOCKED" if row["status"]=="PASS" else row["status"]
            row["reason"]="MISSING_DETAILED_SONIC_EVIDENCE:"+",".join(incomplete)
            all_good=False
    report["passed_scenarios"]=sum(e["status"]=="PASS" for p in report["presets"] for e in p["scenario_results"])
    report["failed_scenarios"]=154-report["passed_scenarios"]
    report["passed_presets"]=sum(p["status"]=="PASS" for p in report["presets"])
    report["status"]="PASS" if all_good else (
        "FAIL" if any(p["status"]=="FAIL" for p in report["presets"]) else "BLOCKED")
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for flag in ("contract","creative_receipts","vst3_receipts","creative_audio_dir",
                 "vst3_audio_dir","out"):
        ap.add_argument("--"+flag.replace("_","-"),dest=flag,type=Path,required=(flag in ("contract","out")))
    a=ap.parse_args()
    report={"schema":RESULT_SCHEMA,"status":"BLOCKED","release_approved":False,
            "errors":[],"presets":[{"program":p,"status":"BLOCKED",
                          "reason":"NO_CAPTURE_CONTRACT"} for p in PROGRAMS]}
    try:
        contract=load_json(a.contract)
        require(contract is not None,"MISSING_CAPTURE_CONTRACT")
        report=evaluate(contract,load_json(a.creative_receipts),
                        load_json(a.vst3_receipts),a.creative_audio_dir,
                        a.vst3_audio_dir)
    except (EvidenceError,ValueError,KeyError,TypeError,OSError,OverflowError) as exc:
        report["status"]="FAIL"
        report["errors"].append(str(exc))
    a.out.parent.mkdir(exist_ok=True,parents=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("P220 original Creative 77-preset sound evidence:",
          report["status"],"PASS",report.get("passed_presets",0),"/77",
          "scenarios",report.get("passed_scenarios",0),"/154",
          "release_approved=False")
    if report["status"]!="PASS":
        raise SystemExit(1)

if __name__=="__main__":
    main()
