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
from run_external_daw_capture_check import _compare as compare_existing_pcm

SCHEMA = "125a-awe-sf2-77-audio-contract-v1"
RESULT_SCHEMA = "125a-testlab-awe-sf2-77-sonic-gate-v1"
COMPARISON_VERSION = "p220-stereo-v2"
DRY_VERSION = "p220-sample-exact-dry-v1"
DRY_SCHEMA = "125a-p220-sample-exact-dry-contract-v1"
TRACE_SCHEMA = "125a-p220-midi-register-sample-trace-v1"
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
STEREO_CORRELATION_DELTA_MAX = 0.10
SIDE_ENERGY_FRACTION_DELTA_MAX = 0.05
PCM_CORRELATION_MIN = 0.90
# After the existing 10-ms onset-bin alignment, retain ONE common fine
# offset for both channels. Never repair a faulty channel with its own lag.
PCM_FINE_LAG_MAX_FRAMES = 441
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
                frames==expected_frames,
                "INVALID_CAPTURE_DURATION_OR_MIDI_TIMELINE:"+fname)
        samples = wf.readframes(frames)
    require(len(samples)==frames*4,"TRUNCATED_PCM:"+fname)
    # Unpack stereo little-endian signed 16-bit without external dependencies.
    vals = struct.unpack("<"+str(frames*2)+"h",samples)
    channels = [[v/32768.0 for v in vals[ch::2]] for ch in range(2)]
    mono = [(l+r)*.5 for l,r in zip(*channels)]
    stereo_peak = max(abs(v) for v in vals)/32768.0
    require(stereo_peak < 0.99997, "CLIPPED_PCM:"+fname)
    # Stereo energy, not the mono sum: authentic anti-phase stereo is
    # audible, while a silent/missing channel must stay observable.
    total_rms = math.sqrt(sum(sum(x*x for x in ch) for ch in channels)/(frames*2))
    require(total_rms >= MIN_RMS,"SILENT_AUDIO:"+fname)
    block = 441
    e = [math.sqrt(sum(sum(x*x for x in ch[i:i+block]) for ch in channels)/(block*2))
         for i in range(0,frames-block+1,block)]
    onset_threshold = max(MIN_RMS, max(e)*0.08)
    eligible = [i for i,a in enumerate(e) if a >= onset_threshold]
    require(eligible,"NO_AUDIBLE_ONSET:"+fname)
    onset = eligible[0]
    return {"sha256":sha256(raw),"frames":frames,"mono":mono,"channels":channels,
            "envelope":e,"onset_bin":onset,"rms":total_rms,
            "peak":stereo_peak}

def band_spectrum(mono, start,*,relative=True):
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
    if relative:
        return [10*math.log10(v/whole) for v in power]
    # Hann coherent-gain calibration to full-scale peak amplitude. This is
    # a fixed analysis-window correction, never a capture level adjustment.
    coherent_gain=sum(0.5-0.5*math.cos(2*math.pi*j/(N-1)) for j in range(N))
    return [10*math.log10(4*v/(coherent_gain*coherent_gain)) for v in power]

def corr(a,b):
    require(len(a)==len(b) and len(a)>10,"INVALID_ENVELOPE_ALIGNMENT")
    aa = [math.log10(max(x,1e-6)) for x in a]
    bb = [math.log10(max(x,1e-6)) for x in b]
    am=sum(aa)/len(aa);bm=sum(bb)/len(bb)
    num=sum((x-am)*(y-bm) for x,y in zip(aa,bb))
    den=math.sqrt(sum((x-am)**2 for x in aa)*sum((y-bm)**2 for y in bb))
    return num/den if den>1e-12 else 0.0

def signal_rms(samples):
    return math.sqrt(sum(v*v for v in samples)/len(samples))

def channel_comparison(a,b,channel,*,full_window=False,spectral_start=1000):
    ra,rb=signal_rms(a),signal_rms(b)
    pa,pb=max(abs(v) for v in a),max(abs(v) for v in b)
    row={"channel":channel,"reference_rms":ra,"capture_rms":rb,
         "reference_peak":pa,"capture_peak":pb,"status":"FAIL"}
    if min(ra,rb)<MIN_RMS:
        # Legitimate hard pan is not a missing-channel failure when the
        # independently captured reference has that same quiet channel.
        row.update(status="PASS" if max(ra,rb)<MIN_RMS else "FAIL",
                   activity="QUIET_IN_BOTH" if max(ra,rb)<MIN_RMS else "CHANNEL_ACTIVITY_MISMATCH")
        return row
    gain_db=20*math.log10(rb/ra);peak_db=20*math.log10(pb/pa)
    env=lambda s:[signal_rms(s[i:i+441]) for i in range(
        0,(len(s) if full_window else min(len(s),441*150))-440,441)]
    ea,eb=env(a),env(b)
    envelope_corr=corr(ea,eb)
    # A flat, matching envelope is a valid steady tone, not an undefined
    # failed correlation. Level is still tested independently above.
    if max(ea)-min(ea)<1e-10 and max(eb)-min(eb)<1e-10:
        envelope_corr=1.0
    sa,sb=(band_spectrum(s,spectral_start,relative=not full_window) for s in (a,b))
    if full_window:
        row.update(spectrum_reference_dbfs=sa,spectrum_capture_dbfs=sb,
                   spectrum_start_frame=spectral_start)
    differences=[y-x for x,y in zip(sa,sb)]
    audible=[abs(d) for d,x,y in zip(differences,sa,sb) if max(x,y)>-42]
    require(audible,"NO_USABLE_CHANNEL_SPECTRAL_ENERGY")
    maximum=max(audible)
    row.update(activity="ACTIVE",rms_delta_db=gain_db,peak_delta_db=peak_db,
        log_envelope_correlation=envelope_corr,
        spectral_difference_db_8_centers=differences,
        max_abs_spectral_difference_db=maximum,
        status="PASS" if abs(gain_db)<=LEVEL_TOLERANCE_DB and
            abs(peak_db)<=LEVEL_TOLERANCE_DB and envelope_corr>=ENVELOPE_CORR_MIN and
            maximum<=SPECTRAL_DIFF_DB_MAX else "FAIL")
    return row

def stereo_structure(channels):
    left,right=channels
    ll=sum(x*x for x in left);rr=sum(x*x for x in right)
    lr=sum(x*y for x,y in zip(left,right))
    mid=max(0.,(ll+rr+2*lr)/4)
    side=max(0.,(ll+rr-2*lr)/4)
    return {"lr_correlation":lr/math.sqrt(ll*rr) if ll>0 and rr>0 else None,
            "mid_rms":math.sqrt(mid/len(left)),"side_rms":math.sqrt(side/len(left)),
            "side_energy_fraction":side/(mid+side) if mid+side>0 else 0.}

def compare(a,b,kind,*,sample_exact=False,allow_silent=False,spectral_start=1000):
    if sample_exact:
        require(a["frames"]==b["frames"],"DRY_WINDOW_LENGTH_MISMATCH")
        frames=a["frames"];lag_ms=0
        aa=a["channels"];bb=b["channels"]
    else:
        lag_ms=abs(a["onset_bin"]-b["onset_bin"])*10
        require(lag_ms<=ONSET_LAG_MAX_MS,"UNBOUNDED_CAPTURE_ONSET_LAG")
        frames=min(a["frames"]-a["onset_bin"]*441,
                   b["frames"]-b["onset_bin"]*441,FRAME_RATE*2)
        aa=[s[a["onset_bin"]*441:a["onset_bin"]*441+frames] for s in a["channels"]]
        bb=[s[b["onset_bin"]*441:b["onset_bin"]*441+frames] for s in b["channels"]]
    require(frames>=FRAME_RATE//2,"INSUFFICIENT_ACTIVE_PCM")
    active=[i for i,s in enumerate(aa) if signal_rms(s)>=MIN_RMS]
    require(active or (sample_exact and allow_silent),"NO_PLAYABLE_NOTE_AUDIO")
    # Reuse the existing P90 signed PCM oracle. It estimates one common
    # lag and requires every active channel to agree at that SAME lag.
    # Positive gain and residual checks detect polarity/delay faults even
    # when channel spectra and RMS magnitudes alone are unchanged.
    try:
        if active:
            pcm=compare_existing_pcm({"samples_by_channel":[aa[i] for i in active]},
                {"samples_by_channel":[bb[i] for i in active]},
                0 if sample_exact else PCM_FINE_LAG_MAX_FRAMES,PCM_CORRELATION_MIN,
                sample_exact=sample_exact)
        else:
            pcm={"matches_reference":True,"lag_frames":0,"channel_results":[],
                 "compared_frames":frames,"sample_exact":True,"gain_normalized":False,
                 "activity":"QUIET_REFERENCE_RELEASE"}
        pcm["status"]="PASS" if pcm["matches_reference"] else "FAIL"
        for row,index in zip(pcm["channel_results"],active):row["channel"]=index+1
    except ValueError as exc:
        pcm={"status":"FAIL","lag_frames":0,"reason":str(exc)}
    offset=pcm["lag_frames"]
    start_a,start_b=max(0,-offset),max(0,offset)
    frames-=abs(offset)
    aa=[s[start_a:start_a+frames] for s in aa]
    bb=[s[start_b:start_b+frames] for s in bb]
    channels=[channel_comparison(x,y,i+1,full_window=sample_exact,spectral_start=spectral_start)
              for i,(x,y) in enumerate(zip(aa,bb))]
    if sample_exact:
        for row,x,y in zip(channels,aa,bb):
            row["max_absolute_sample_error"]=max(abs(u-v) for u,v in zip(x,y))
            if row["max_absolute_sample_error"]>2/32768.0:
                row["status"]="FAIL"
    sa,sb=stereo_structure(aa),stereo_structure(bb)
    correlation_delta=(abs(sa["lr_correlation"]-sb["lr_correlation"])
        if all(x.get("activity")=="ACTIVE" for x in channels) else None)
    side_delta=abs(sa["side_energy_fraction"]-sb["side_energy_fraction"])
    stereo_pass=(pcm["status"]=="PASS" and
        all(x["status"]=="PASS" for x in channels) and
        (correlation_delta is None or correlation_delta<=STEREO_CORRELATION_DELTA_MAX) and
        side_delta<=SIDE_ENERGY_FRACTION_DELTA_MAX)
    energy_a=math.sqrt(sum(x["reference_rms"]**2 for x in channels)/2)
    energy_b=math.sqrt(sum(x["capture_rms"]**2 for x in channels)/2)
    require(min(energy_a,energy_b)>=MIN_RMS or
            (sample_exact and allow_silent),"NO_PLAYABLE_NOTE_AUDIO")
    active_rows=[x for x in channels if x.get("activity")=="ACTIVE"]
    max_spec=max((x["max_abs_spectral_difference_db"] for x in active_rows),default=0.)
    worst_bands=[max((x["spectral_difference_db_8_centers"][i] for x in active_rows),
                     key=abs,default=0.) for i in range(8)]
    return {"status":"PASS" if stereo_pass else "FAIL",
        "audio_comparison_version":COMPARISON_VERSION,
        "rms_level_native_minus_creative_db":round(20*math.log10(energy_b/energy_a),3)
            if min(energy_a,energy_b)>0 else None,
        "log_envelope_correlation":round(min((x["log_envelope_correlation"] for x in active_rows),default=0.),5),
        "onset_lag_ms":lag_ms,"channel_results":channels,
        "stereo_comparison":{"status":"PASS" if stereo_pass else "FAIL",
            "reference":sa,"capture":sb,"lr_correlation_delta":correlation_delta,
            "side_energy_fraction_delta":side_delta,"signed_pcm":pcm},
        "spectrum_native_minus_creative_db_8_centers":worst_bands,
        "max_abs_spectral_difference_db":round(max_spec,3),
        "center_frequencies_hz":[110,220,440,880,1760,3520,7040,11000],
        "measured_audio_frames":frames,
        "sample_exact":sample_exact,"gain_normalized":False if sample_exact else None,
        "scope":"emulated EMU8000 original Win95 driver vs real VST3; NOT physical AWE64"}

def load_json(path):
    if path is None or not Path(path).is_file():
        return None
    path=Path(path)
    require(0 < path.stat().st_size <= MAX_BYTES,"MISSING_OR_OVERSIZED_JSON:"+path.name)
    return json.loads(path.read_text(encoding="utf-8"))

def dry_integer(value, minimum, maximum, label):
    require(type(value) is int and minimum<=value<=maximum,"DRY_INVALID_"+label)
    return value

def dry_trace(spec,fixture,receipt,root,backend,*,allow_synthetic=False):
    """Validate supplied raw observations, not attest who actually recorded them.

    The independently approved contract pins BOTH WAV and event-file hashes.
    Native diagnostics and synthetic fixtures cannot become real capture proof.
    """
    label=fixture["id"]
    require(spec.get("schema")==DRY_SCHEMA,"MISSING_SAMPLE_EXACT_DRY_CONTRACT")
    require(SHA.fullmatch(str(spec.get("rom_sha256",""))) and
            spec.get("bank_sha256")==BANK_SHA and
            spec.get("sample_rate")==FRAME_RATE and
            spec.get("channels")==["L","R"],"DRY_SOURCE_IDENTITY_CONTRACT")
    pre=dry_integer(spec.get("pre_note_frames"),441,FRAME_RATE,"PRE_NOTE_FRAMES")
    duration=dry_integer(spec.get("note_length_frames"),1,FRAME_RATE*4,"NOTE_LENGTH")
    count=dry_integer(spec.get("window_frames"),FRAME_RATE,FRAME_RATE*8,"WINDOW_FRAMES")
    require(duration==fixture["note_off_ms"]*FRAME_RATE//1000 and
            count==fixture["record_ms"]*FRAME_RATE//1000 and
            count-pre-duration>=FRAME_RATE//2,"DRY_APPROVED_EVENT_WINDOW")
    pin=spec.get("captures",{}).get(label,{}).get(backend,{})
    name=label+".events.json"
    require(receipt.get("event_trace")==name and
            SHA.fullmatch(str(pin.get("trace_sha256",""))) and
            receipt.get("event_trace_sha256")==pin["trace_sha256"] and
            receipt.get("wav_sha256")==pin.get("wav_sha256"),"DRY_UNPINNED_WAV_OR_EVENT_TRACE")
    path=Path(root)/name
    require(path.is_file() and 0<path.stat().st_size<=MAX_BYTES,"DRY_MISSING_EVENT_TRACE")
    raw=path.read_bytes()
    require(sha256(raw)==pin["trace_sha256"],"DRY_STALE_EVENT_TRACE_SHA")
    trace=json.loads(raw.decode("utf-8"))
    require(isinstance(trace,dict) and trace.get("schema")==TRACE_SCHEMA and
            trace.get("backend")==backend,"DRY_INVALID_EVENT_TRACE_SCHEMA")
    kind=trace.get("capture_kind")
    expected_kind=("ORIGINAL_CREATIVE_86BOX" if backend=="creative" else
                   spec.get("vst3_capture_kind"))
    allowed=(kind==expected_kind and expected_kind in
             ("ORIGINAL_CREATIVE_86BOX","WINDOWS_VST3","WINDOWS_DAW_VST3"))
    synthetic=kind=="SYNTHETIC_FIXTURE"
    require(allowed or (allow_synthetic and synthetic),"DRY_NON_REAL_CAPTURE:"+str(kind))
    tap=("86box_emu8000_stereo_output" if backend=="creative" else
         "windows_daw_post_plugin_output" if expected_kind=="WINDOWS_DAW_VST3" else
         "windows_vst3_process_output")
    require(trace.get("audio_tap")==tap and trace.get("channel_map")==["L","R"],
            "DRY_WRONG_AUDIO_TAP_OR_CHANNEL_MAP")
    require(trace.get("rom_sha256")==spec["rom_sha256"] and
            trace.get("bank_sha256")==BANK_SHA and
            trace.get("sample_rate")==FRAME_RATE and
            trace.get("wav_sha256")==pin.get("wav_sha256") and
            trace.get("program")==fixture["program"] and
            trace.get("bank")==fixture["user_bank"] and
            trace.get("channel")==fixture["channel"] and
            trace.get("note")==fixture["note"] and
            trace.get("velocity")==fixture["velocity"],"DRY_CAPTURE_IDENTITY_MISMATCH")
    identity="driver_sha256" if backend=="creative" else "module_sha256"
    approved=VXD_SHA if backend=="creative" else spec.get("vst3_module_sha256")
    require(SHA.fullmatch(str(approved)) and trace.get(identity)==approved,
            "DRY_WRONG_DRIVER_OR_VST3_MODULE")
    if expected_kind=="WINDOWS_DAW_VST3":
        daw=trace.get("daw_session",{})
        require(all(isinstance(daw.get(k),str) and daw[k].strip() for k in ("name","version")) and
                daw.get("insert_effect_count")==0 and daw.get("track_gain_db")==0 and
                daw.get("master_gain_db")==0 and daw.get("normalized") is False,
                "DRY_DAW_SIGNAL_CHAIN_NOT_NEUTRAL")
    frames=dry_integer(trace.get("audio_frames"),FRAME_RATE//2,FRAME_RATE*8,"AUDIO_FRAMES")
    require(receipt.get("audio_frames")==frames,"DRY_RECEIPT_FRAME_COUNT")
    blocks=trace.get("process_blocks")
    require(isinstance(blocks,list) and 0<len(blocks)<=32768,"DRY_MISSING_PROCESS_BLOCKS")
    cursor=0;starts={}
    for block in blocks:
        require(isinstance(block,dict) and block.get("start_frame")==cursor,
                "DRY_PROCESS_BLOCK_GAP_OR_OVERLAP")
        length=dry_integer(block.get("frames"),1,8192,"PROCESS_BLOCK_LENGTH")
        starts[cursor]=length;cursor+=length
    require(cursor==frames,"DRY_PROCESS_BLOCKS_DO_NOT_COVER_PCM")
    events=trace.get("midi_events")
    require(isinstance(events,list) and len(events)==3,"DRY_UNEXPECTED_MIDI_EVENTS")
    for index,(event,event_kind) in enumerate(zip(events,("bank_program","note_on","note_off"))):
        require(isinstance(event,dict) and event.get("kind")==event_kind and
                event.get("sequence")==index and event.get("channel")==fixture["channel"],
                "DRY_MIDI_EVENT_IDENTITY")
        start=event.get("block_start");offset=event.get("sample_offset")
        require(type(start) is int and start in starts and type(offset) is int and
                0<=offset<starts[start] and event.get("frame")==start+offset,
                "DRY_MIDI_SAMPLE_OFFSET_NOT_ACTUAL_BLOCK_EVENT")
        if index==0:
            require(event.get("bank")==fixture["user_bank"] and
                    event.get("program")==fixture["program"],"DRY_MIDI_BANK_PROGRAM")
        else:
            require(event.get("note")==fixture["note"] and
                    event.get("velocity")== (fixture["velocity"] if index==1 else 0),
                    "DRY_MIDI_NOTE_OR_VELOCITY")
    require(events[0]["frame"]<=events[1]["frame"] and
            events[2]["frame"]-events[1]["frame"]==duration,"DRY_MIDI_NOTE_OFF_SHIFT")
    samples=trace.get("sample_events")
    require(isinstance(samples,list) and len(samples)==2,"DRY_MISSING_SAMPLE_BOUNDARIES")
    clock_offset=dry_integer(pin.get("sample_to_audio_offset_frames"),-FRAME_RATE,FRAME_RATE,"CLOCK_OFFSET")
    for index,(event,event_kind) in enumerate(zip(samples,("voice_start","voice_release")),1):
        require(isinstance(event,dict) and event.get("kind")==event_kind and
                event.get("midi_sequence")==index,"DRY_SAMPLE_EVENT_TRIGGER")
        counter=dry_integer(event.get("sample_counter"),0,2**53,"SAMPLE_COUNTER")
        frame=dry_integer(event.get("frame"),0,frames-1,"SAMPLE_FRAME")
        latency=dry_integer(pin.get("midi_to_sample_"+("on" if index==1 else "off")+"_frames"),
                            0,FRAME_RATE,"MIDI_TO_SAMPLE_LATENCY")
        require(frame==counter+clock_offset and frame==events[index]["frame"]+latency,
                "DRY_UNPROVED_MIDI_REGISTER_SAMPLE_ALIGNMENT")
    onset,off=[x["frame"] for x in samples]
    require(off-onset==duration,"DRY_REGISTER_NOTE_OFF_SHIFT")
    voices=trace.get("voices")
    require(isinstance(voices,list) and 1<=len(voices)<=32 and
            all(type(v) is int and 0<=v<32 for v in voices) and len(set(voices))==len(voices),
            "DRY_INVALID_ACTIVE_VOICES")
    registers=trace.get("register_events")
    expected={(voice,kind,index,frame) for voice in voices
              for kind,index,frame in (("voice_start",1,onset),("voice_release",2,off))}
    require(isinstance(registers,list) and len(registers)==len(expected) and
            all(isinstance(r,dict) for r in registers) and
            {(r.get("voice"),r.get("kind"),r.get("midi_sequence"),r.get("frame")) for r in registers}==expected,
            "DRY_MISSING_OR_SHIFTED_REGISTER_EVENTS")
    window=trace.get("window",{})
    start=onset-pre
    require(start>=0 and window.get("start_frame")==start and window.get("frames")==count and
            start+count<=frames and window.get("discarded_prefix_frames")==start and
            window.get("discarded_suffix_frames")==frames-start-count,
            "DRY_WINDOW_NOT_EXACT_EVENT_BOUNDED")
    fx=trace.get("effects",{})
    require(isinstance(fx,dict) and fx.get("requested_percent")=={"reverb":0,"chorus":0} and
            fx.get("control_origin")== ("CREATIVE_CONTROL" if backend=="creative" else "PLUGIN_GUI") and
            fx.get("observed_start_frame")==0 and fx.get("observed_frames")==frames and
            fx.get("complete_write_history") is True,"DRY_EFFECT_CONTROL_OR_OBSERVATION_MISSING")
    controls=fx.get("control_events")
    require(isinstance(controls,list) and 2<=len(controls)<=128 and
            all(isinstance(e,dict) for e in controls) and
            {e.get("control") for e in controls}=={"reverb","chorus"},
            "DRY_MISSING_GUI_TO_PROCESSOR_OBSERVATIONS")
    for control in controls:
        require(control.get("origin")==fx["control_origin"] and
                type(control.get("frame")) is int and 0<=control["frame"]<=onset and
                all(type(control.get(k)) in (int,float) and control[k]==0 for k in
                    ("display_percent","controller_value","processor_value")),
                "DRY_GUI_CONTROLLER_PROCESSOR_ZERO_MISMATCH")
    for field in ("initial_voice_sends","final_voice_sends"):
        sends=fx.get(field)
        require(isinstance(sends,list) and len(sends)==32 and
                all(isinstance(v,dict) for v in sends) and
                [v.get("voice") for v in sends]==list(range(32)) and
                all(type(v.get(k)) is int and v[k]==0 for v in sends for k in ("reverb","chorus")),
                "DRY_NONZERO_OR_UNOBSERVED_HARDWARE_SENDS")
    writes=fx.get("send_writes")
    require(isinstance(writes,list) and len(writes)<=32768,"DRY_MISSING_SEND_WRITE_HISTORY")
    for write in writes:
        require(isinstance(write,dict) and type(write.get("frame")) is int and
                0<=write["frame"]<frames and type(write.get("voice")) is int and
                0<=write["voice"]<32 and
                all(type(write.get(k)) is int and write[k]==0 for k in ("reverb","chorus")),
                "DRY_ACTIVE_EFFECT_SEND_WRITE")
    require(fx.get("return_mute")=={"reverb":True,"chorus":True},"DRY_EFFECT_RETURN_NOT_MUTED")
    wav=exact_wav(Path(root),fixture[backend+"_wav"],pin["wav_sha256"],frames)
    return wav,trace,{"capture_kind":kind,"audio_tap":tap,"trace_sha256":pin["trace_sha256"],
                      "wav_sha256":pin["wav_sha256"],"window_start":start,"window_frames":count,
                      "discarded_prefix_frames":start,"discarded_suffix_frames":frames-start-count,
                      "note_on_frame_in_window":pre,"note_off_frame_in_window":pre+duration,
                      "all_32_voice_sends_zero":True,"complete_send_write_history":True,
                      "gui_controller_processor_zero":True,
                      "rom_sha256":trace["rom_sha256"],"bank_sha256":trace["bank_sha256"],
                      "sample_rate":FRAME_RATE,
                      "synthetic":synthetic}

def dry_compare(spec,fixture,cr,vr,creative_dir,vst3_dir,*,allow_synthetic=False):
    result={"id":fixture["id"],"comparison_version":DRY_VERSION,"status":"BLOCKED",
            "comparison_status":"NOT RUN","release_approved":False,
            "provenance":"HASH_PINNED_SUPPLIED_OBSERVATIONS_NOT_INDEPENDENT_CAPTURE_ATTESTATION"}
    try:
        require(fixture.get("variant")=="DRY","NOT_A_DRY_SCENARIO")
        decoded=[];observations=[]
        for receipt,root,backend in ((cr,creative_dir,"creative"),(vr,vst3_dir,"vst3")):
            wav,trace,observed=dry_trace(spec,fixture,receipt,root,backend,allow_synthetic=allow_synthetic)
            observed["backend"]=backend;observations.append(observed)
            start=observed["window_start"];count=observed["window_frames"]
            window=[s[start:start+count] for s in wav["channels"]]
            require(max(abs(v) for ch in window for v in ch[:spec["pre_note_frames"]])<=2/32768.0,
                    "DRY_AUDIO_BEFORE_ACTUAL_NOTE_ON")
            decoded.append({"frames":count,"channels":window})
        result["observations"]=observations
        require(observations[0]["wav_sha256"]!=observations[1]["wav_sha256"],
                "SAME_WAV_BYTES_REUSED_AS_INDEPENDENT_CREATIVE_AND_VST3")
        result["window_comparison"]=compare(*decoded,"DRY",sample_exact=True,
                                            spectral_start=spec["pre_note_frames"]+1000)
        release_start=spec["pre_note_frames"]+spec["note_length_frames"]
        release=[{"frames":d["frames"]-release_start,
                  "channels":[s[release_start:] for s in d["channels"]]} for d in decoded]
        result["release_comparison"]=compare(*release,"DRY",sample_exact=True,allow_silent=True)
        ok=all(result[k]["status"]=="PASS" for k in ("window_comparison","release_comparison"))
        result["comparison_status"]="PASS" if ok else "FAIL"
        synthetic=any(x["synthetic"] for x in observations)
        result["source_scope"]="SYNTHETIC_FIXTURE_ONLY" if synthetic else "SUPPLIED_REAL_CAPTURE_RECEIPTS"
        result["status"]=("BLOCKED" if synthetic else "PASS") if ok else "FAIL"
    except (EvidenceError,ValueError,KeyError,TypeError,OSError,EOFError,wave.Error,OverflowError) as exc:
        result["reason"]=str(exc)
        result["status"]="BLOCKED" if str(exc).startswith(("MISSING_","DRY_MISSING_","DRY_NON_REAL_CAPTURE")) else "FAIL"
        result["comparison_status"]="NOT RUN"
    return result

def evaluate_dry(contract,creative,vst3,creative_dir,vst3_dir):
    scenarios=[x for x in validate_contract(contract) if x["variant"]=="DRY"]
    report={"schema":"125a-p220-sample-exact-dry-result-v1","comparison_version":DRY_VERSION,
            "status":"BLOCKED","release_approved":False,"expected_cases":77,"passed_cases":0,
            "cases":[{"id":x["id"],"status":"BLOCKED","comparison_status":"NOT RUN",
                      "reason":"NO_APPROVED_EVENT_BOUNDED_CAPTURE_PAIR"} for x in scenarios],
            "capture_producer_execution":"NOT RUN_BY_THIS_COMPARATOR",
            "physical_awe64":"NOT RUN","daw_asio_verification":"NOT RUN"}
    spec=contract.get("sample_exact_dry")
    if not isinstance(spec,dict) or creative is None or vst3 is None:
        report["reason"]="MISSING_SAMPLE_EXACT_DRY_CONTRACT_OR_REAL_CAPTURES"
        return report
    report.update(rom_sha256=spec.get("rom_sha256"),bank_sha256=spec.get("bank_sha256"),
                  vst3_module_sha256=spec.get("vst3_module_sha256"),sample_rate=spec.get("sample_rate"))
    try:
        require(set(spec.get("captures",{}))=={x["id"] for x in scenarios},"DRY_NOT_EXACTLY_77_CAPTURE_PAIRS")
        sources=[]
        for source in (creative,vst3):
            require(isinstance(source,dict),"DRY_INVALID_RECEIPTS")
            selected=[x for x in source.get("trials",[]) if isinstance(x,dict) and x.get("id") in spec["captures"]]
            sources.append({**source,"trials":selected})
        check_provenance(*sources,scenarios)
        require(vst3.get("module_sha256")==spec.get("vst3_module_sha256"),"DRY_MODULE_RECEIPT_MISMATCH")
        report["cases"]=[dry_compare(spec,f,cr,vr,creative_dir,vst3_dir)
                         for f,cr,vr in zip(scenarios,sources[0]["trials"],sources[1]["trials"])]
        report["status"]=("PASS" if all(x["status"]=="PASS" for x in report["cases"]) else
                          "FAIL" if any(x["status"]=="FAIL" for x in report["cases"]) else "BLOCKED")
        report["passed_cases"]=sum(x["status"]=="PASS" for x in report["cases"])
    except (EvidenceError,ValueError,TypeError,KeyError) as exc:
        report.update(status="FAIL",reason=str(exc))
    return report

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
                cr.get("original_sample_start_register_written") is True,
                "CREATIVE_PROGRAM_FALLBACK_OR_NO_SAMPLE_USED:"+label)
        require(vr.get("vst3_program_selected")==fixture["program"] and
                type(vr.get("vst3_note_on_count")) is int and
                vr["vst3_note_on_count"]>0 and
                vr.get("vst3_bank_selection_acknowledged") is True,
                "VST3_WRONG_PRESET_OR_MISSING_AUDIO_PROCESS:"+label)

def evaluate(contract,creative,vst3,creative_dir,vst3_dir):
    scenarios=validate_contract(contract)
    report={"schema":RESULT_SCHEMA,
        "audio_comparison_version":COMPARISON_VERSION,
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
    dry_report=evaluate_dry(contract,creative,vst3,creative_dir,vst3_dir)
    dry_by_id={x["id"]:x for x in dry_report["cases"]}
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
            if fixture["variant"]=="DRY" and isinstance(contract.get("sample_exact_dry"),dict):
                dry=dry_by_id[fixture["id"]]
                entry.update(dry.get("window_comparison",{}))
                entry.update(status=dry["status"],sample_exact_dry={
                    "id":fixture["id"],"status":dry["status"],"comparison_version":DRY_VERSION,
                    "detail_location":"sample_exact_dry.cases"})
                if dry.get("reason"):entry["reason"]=dry["reason"]
                if dry.get("observations"):
                    entry["creative_wav_sha256"]=dry["observations"][0]["wav_sha256"]
                    entry["vst3_wav_sha256"]=dry["observations"][1]["wav_sha256"]
            else:
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
            row["status"]="FAIL" if entry["status"]=="FAIL" or row["status"]=="FAIL" else "BLOCKED"
            all_good=False
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
    report["screen_status"]=report["status"]
    report["sample_exact_dry"]=dry_report
    if report["status"]=="PASS" and report["sample_exact_dry"]["status"]!="PASS":
        report["status"]=report["sample_exact_dry"]["status"]
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-only",action="store_true",
                    help="Use the same P220 gate for the 77 event-bounded DRY pairs only")
    for flag in ("contract","creative_receipts","vst3_receipts","creative_audio_dir",
                 "vst3_audio_dir","out"):
        ap.add_argument("--"+flag.replace("_","-"),dest=flag,type=Path,required=(flag in ("contract","out")))
    a=ap.parse_args()
    report={"schema":"125a-p220-sample-exact-dry-result-v1" if a.dry_only else RESULT_SCHEMA,
            "status":"BLOCKED","release_approved":False,
            "errors":[],"presets":[{"program":p,"status":"BLOCKED",
                          "reason":"NO_CAPTURE_CONTRACT"} for p in PROGRAMS]}
    try:
        contract=load_json(a.contract)
        require(contract is not None,"MISSING_CAPTURE_CONTRACT")
        report=(evaluate_dry if a.dry_only else evaluate)(contract,load_json(a.creative_receipts),
                        load_json(a.vst3_receipts),a.creative_audio_dir,
                        a.vst3_audio_dir)
    except (EvidenceError,ValueError,KeyError,TypeError,OSError,OverflowError) as exc:
        report["status"]="FAIL"
        report["errors"].append(str(exc))
    a.out.parent.mkdir(exist_ok=True,parents=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    if a.dry_only:
        print("P220 sample-exact dry capture evidence:",report["status"],
              "PASS",report.get("passed_cases",0),"/77; release_approved=False")
    else:
        print("P220 original Creative 77-preset sound evidence:",
              report["status"],"PASS",report.get("passed_presets",0),"/77",
              "scenarios",report.get("passed_scenarios",0),"/154",
              "release_approved=False")
    if report["status"]!="PASS":
        raise SystemExit(1)

if __name__=="__main__":
    main()
