#!/usr/bin/env python3
"""P100: pinned original-Creative Win95 -> real Windows VST3 -> exact EMU8000 OUT+PCM.
An opt-in Test Lab product adapter. Private Creative assets stay owner-local.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct, subprocess, sys, wave
from pathlib import Path

SCHEMA="125A-P100-ORIGINAL-VST3-PARITY-1"
REQUIRED=("vst3","native_host","rom","sf2","ram_ports","ram_pcm","vxd_pack",
          "note_ports","reference_wav","session_manifest","guest_log",
          "original_trace","original_full_wav")
GROUPS=("C4_ON","C4_OFF","D4_ON","D4_OFF")
HEADER=b"# INDEPENDENT_NATIVE_P002_PORT_WRITES_ONLY\n"
CLOCK=b"# CLOCK=HOST_44100_SAMPLE_FRAMES; ORIGIN=ACTIVATION\n"

def demand(ok,msg):
    if not ok: raise ValueError(msg)

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def source(plan_path):
    p=json.loads(plan_path.read_text(encoding="utf-8-sig"))
    demand(p.get("schema")==SCHEMA,"P100 plan schema")
    demand(p.get("sample_rate")==44100,"44.1kHz original clock required")
    timings=p.get("midi_sample_frames",[])
    demand(len(timings)==4 and all(type(x)==int for x in timings) and
           0<timings[0]<timings[1]<timings[2]<timings[3]<p.get("native_total_frames",0)
           <=44100*30,"explicit four-event original MIDI schedule invalid")
    w=p.get("pcm_window",{})
    demand(all(type(w.get(k))==int and w[k]>=0
               for k in ("original_start_frame","native_start_frame","frames")) and
           w["frames"]>=256 and w["native_start_frame"]==timings[0] and
           w["native_start_frame"]+w["frames"]<=p["native_total_frames"],
           "explicit original/native PCM window invalid")
    demand(type(p.get("reference_first_note_frame"))==int and
           p["reference_first_note_frame"]>=0,"original note clock missing")
    items=p.get("files",{})
    demand(all(k in items for k in REQUIRED),"missing SHA-pinned private source")
    paths={}
    for key in REQUIRED:
        obj=items[key]
        demand(set(obj)=={"path","sha256"} and
               bool(re.fullmatch("[0-9a-f]{64}",obj["sha256"])),
               key+": missing SHA256 contract")
        relative=Path(obj["path"])
        f=(plan_path.parent/relative).resolve()
        demand(f.is_file() and f.stat().st_size<=96000000,key+": absent/oversize")
        demand(digest(f)==obj["sha256"],key+": SHA256 not pinned")
        paths[key]=f
    demand(len(set(paths.values()))==len(paths),"private inputs alias")
    manifest=json.loads(paths["session_manifest"].read_text(encoding="utf-8-sig"))
    demand(digest(paths["session_manifest"])==p.get("source_session_sha256"),
           "source session manifest digest mismatch")
    demand(manifest.get("schema")=="P002_ORIGINAL_WIN95_REAL_BOOT_CAPTURE_V1" and
           manifest.get("original_session_kind")=="PRIVATE_CALIBRATED_86BOX_WIN95_CREATIVE_CC0_1" and
           manifest.get("sample_rate")==44100 and manifest.get("sample_bits")==16 and
           manifest.get("guest_log_from_same_private_fat16_disk") is True and
           manifest.get("original_source_sf2_ram_words_bit_equal")==260921,
           "not independently boot-attested original Win95 source")
    for field,key in (
        ("original_emu8k_trace_sha256","original_trace"),
        ("original_guest_log_sha256","guest_log"),
        ("original_win95_precard_wav_sha256","original_full_wav"),
        ("original_owner_sf2_sha256","sf2"),("original_rom_sha256","rom")):
        demand(manifest.get(field)==digest(paths[key]),
               "Win95 source provenance mismatch: "+field)
    # Independently prove cropped reference is BYTE-IDENTICAL to the
    # unchanged original 44.1kHz PCM16 guest WAV at the source note origin.
    with wave.open(str(paths["original_full_wav"])) as full, \
         wave.open(str(paths["reference_wav"])) as crop:
        for f in (full,crop):
            demand(f.getnchannels()==2 and f.getsampwidth()==2 and
                   f.getframerate()==44100 and f.getcomptype()=="NONE",
                   "original reference is not PCM16 44.1kHz stereo")
        start=p["reference_first_note_frame"];n=w["frames"]
        demand(start+n<=full.getnframes() and
               w["original_start_frame"]+n<=crop.getnframes(),
               "original reference crop exceeds Win95 recording")
        full.setpos(start);crop.setpos(w["original_start_frame"])
        a=hashlib.sha256();b=hashlib.sha256()
        for off in range(0,n,4096):
            k=min(n-off,4096)
            a.update(full.readframes(k));b.update(crop.readframes(k))
        demand(a.digest()==b.digest(),"original reference crop is not authentic")
    demand(manifest["original_emu8k_trace_sha256"].encode() in
           paths["note_ports"].read_bytes()[:600],
           "C4/D4 port fixture not tied to this Win95 trace")
    return p,paths

def ref_ports(path):
    result={};section=None
    for line in path.read_text(encoding="ascii").splitlines():
        line=line.strip()
        if not line:continue
        if line.startswith("#"):
            key=line.lstrip("# ")
            if key in GROUPS:
                demand(key not in result,"duplicate original note group")
                result[key]=[];section=key
            continue
        demand(section is not None,"orphan original note event")
        v=line.split()
        demand(len(v)==3,"original port record invalid")
        result[section].append((int(v[0]),int(v[1],16),int(v[2],16)))
    demand(tuple(result)==GROUPS and all(result.values()),
           "incomplete original C4/D4 NoteOn/Off")
    for group in result.values():
        demand(all(group[i][0]<=group[i+1][0] for i in range(len(group)-1)),
               "original clock not monotonic")
    return result

def native_ports(path):
    with path.open("rb") as f:
        demand(f.readline()==HEADER and f.readline()==CLOCK,
               "native trace lacks genuine 125A EMU8000 capture header")
        lines=f.read().decode("ascii").splitlines()
    out=[]
    for line in lines:
        if not line.strip():continue
        fields=line.split()
        demand(len(fields)==3,"native trace malformed")
        event=(int(fields[0]),int(fields[1],16),int(fields[2],16))
        demand(0<=event[0]<=44100*30 and
               all(0<=x<=65535 for x in event[1:]) and
               (not out or event[0]>=out[-1][0]),"native trace clock/port invalid")
        out.append(event)
    demand(bool(out),"native trace empty")
    return out

def compare_ports(source_file,native_file,times,first_frame):
    original=ref_ports(source_file)
    demand(original["C4_ON"][0][0]==first_frame,
           "source first C4 timing changed")
    native=native_ports(native_file)
    groups=[]
    for key,native_on in zip(GROUPS,times):
        ref=original[key]
        origin=ref[0][0]
        demand(ref[-1][0]-origin<=15,"original note port interval too broad")
        a=[(frame-origin,port,value) for frame,port,value in ref]
        b=[(frame-native_on,port,value) for frame,port,value in native
           if native_on<=frame<native_on+16]
        mismatch=None
        for i in range(max(len(a),len(b))):
            x=a[i] if i<len(a) else None
            y=b[i] if i<len(b) else None
            if x!=y:
                difference="count" if x is None or y is None else \
                    next(name for name,xx,yy in zip(("frame","port","value"),x,y) if xx!=yy)
                mismatch={"event_index":i,"field":difference,"original":x,"native":y,
                          "original_absolute_frame":origin+(x[0] if x else 0),
                          "native_absolute_frame":native_on+(y[0] if y else 0)}
                break
        groups.append({"note":key,"original_writes":len(a),"native_writes":len(b),
                       "equal":mismatch is None,"first_difference":mismatch})
    return {"equal":all(x["equal"] for x in groups),"groups":groups,
            "auto_time_alignment":False,"source_trace_sha256":digest(source_file),
            "native_trace_sha256":digest(native_file)}

def compare_pcm(source_file,native_file,window):
    start=window["original_start_frame"];position=window["native_start_frame"]
    count=window["frames"];first=None;mismatch=0;nonzero=[0,0];maxdelta=0
    with wave.open(str(source_file)) as a,wave.open(str(native_file)) as b:
        for item in (a,b):
            demand(item.getframerate()==44100 and item.getnchannels()==2 and
                   item.getsampwidth()==2 and item.getcomptype()=="NONE",
                   "not original EMU8000 stereo 44100Hz PCM16")
        demand(start+count<=a.getnframes() and position+count<=b.getnframes(),
               "PCM window out of bounds")
        a.setpos(start);b.setpos(position)
        for offset in range(0,count,4096):
            n=min(4096,count-offset)
            aa=a.readframes(n);bb=b.readframes(n)
            demand(len(aa)==len(bb)==n*4,"truncated PCM comparison")
            for j in range(0,len(aa),2):
                v=struct.unpack_from("<h",aa,j)[0]
                w=struct.unpack_from("<h",bb,j)[0]
                nonzero[0]+=v!=0;nonzero[1]+=w!=0
                if v!=w:
                    mismatch+=1;maxdelta=max(maxdelta,abs(v-w))
                    if first is None:
                        f=offset+j//4
                        first={"relative_frame":f,"original_absolute_frame":start+f,
                               "native_absolute_frame":position+f,"channel":(j//2)%2,
                               "original_s16":v,"native_s16":w}
    demand(min(nonzero)>=64,"silent source or silent native PCM is not parity")
    return {"equal":mismatch==0,"mismatched_channel_samples":mismatch,
            "compared_channel_samples":2*count,"first_difference":first,
            "max_abs_difference_lsb":maxdelta,"gain_normalization":False,
            "automatic_alignment":False}

def run_host(host,args,out,label,timeout):
    stdout=out/(label+".stdout.txt");stderr=out/(label+".stderr.txt")
    try:
        with stdout.open("wb") as a,stderr.open("wb") as b:
            p=subprocess.run([str(host)]+[str(x) for x in args],
                             stdin=subprocess.DEVNULL,stdout=a,stderr=b,
                             timeout=timeout,check=False)
        return {"exit_code":p.returncode,"stdout":stdout.name,"stderr":stderr.name}
    except subprocess.TimeoutExpired:
        return {"exit_code":None,"timeout":True,"stdout":stdout.name,"stderr":stderr.name}
    except OSError as error:
        stderr.write_text(str(error),encoding="utf8")
        return {"exit_code":None,"launch_error":str(error),
                "stdout":stdout.name,"stderr":stderr.name}

def execute(plan_path,out,timeout=120):
    demand(not out.exists(),"P100 output folder must be new")
    out.mkdir(parents=True)
    result={"schema":"125A-P100-ORIGINAL-VST3-RESULT-1","status":"NO_GO",
            "release_approved":False,"asio":"NOT_RUN","commercial_daw":"NOT_RUN"}
    def save():
        (out/"P100-RESULT.json").write_text(
            json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf8")
    try:
        plan,files=source(plan_path)
        result["original_session_and_all_source_sha_verified"]=True
        result["original_session_sha256"]=plan["source_session_sha256"]
        result["native_module_sha256"]=digest(files["vst3"])
        t=plan["midi_sample_frames"]
        prefix=[files[k] for k in ("vst3","rom","sf2","ram_ports","ram_pcm","vxd_pack")]
        def case(label,clocked):
            out_file=out/(label+".out.txt")
            pcm_file=out/(label+".wav")
            sha_file=out/(label+".clock.json")
            arguments=[*prefix,out_file,pcm_file,*t,plan["native_total_frames"],sha_file]
            if clocked:arguments.append(files["note_ports"])
            result[label+"_native_host"]=run_host(files["native_host"],arguments,out,label,timeout)
            return out_file,pcm_file,sha_file
        case("independent",False)
        if result["independent_native_host"].get("exit_code")!=0:
            result["status"]="INDEPENDENT_NATIVE_HOST_FAILED"
            save();return result
        ports,pcm,clock=case("source_clocked",True)
        if result["source_clocked_native_host"].get("exit_code")!=0:
            result["status"]="SOURCE_CLOCKED_NATIVE_HOST_FAILED"
            save();return result
        timing=json.loads(clock.read_text(encoding="utf-8-sig"))
        demand(timing.get("schema")=="P002_NATIVE_REAL_VST3_HOST_CLOCKS_V1",
               "native clock manifest schema invalid")
        for key,val in zip(("note_c4_on_frame","note_c4_off_frame",
                             "note_d4_on_frame","note_d4_off_frame"),t):
            demand(timing.get(key)==val,"native MIDI clock mismatched: "+key)
        demand(timing.get("pcm_frames")==plan["native_total_frames"],
               "native frame count does not match")
        for key,path in (("native_chip_out_trace_sha256",ports),
                         ("native_precard_wav_sha256",pcm),
                         ("original_vxd_pack_sha256",files["vxd_pack"]),
                         ("exported_vst3_sha256",files["vst3"])):
            demand(timing.get(key)==digest(path),"native evidence hash changed: "+key)
        result["registers"]=compare_ports(files["note_ports"],ports,t,
                                           plan["reference_first_note_frame"])
        result["pcm16"]=compare_pcm(files["reference_wav"],pcm,plan["pcm_window"])
        result["status"]=("BIT_EXACT_C4_D4_PASS" if
                          result["registers"]["equal"] and result["pcm16"]["equal"]
                          else "ORIGINAL_NATIVE_MISMATCH")
    except (ValueError,KeyError,TypeError,OSError,UnicodeError,json.JSONDecodeError,wave.Error) as error:
        result["status"]="INVALID_EVIDENCE_OR_TEST_CONFIGURATION"
        result["error"]=str(error)
    save();return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--host-timeout",type=int,default=120)
    a=p.parse_args(argv)
    result=execute(a.plan.resolve(),a.out.resolve(),a.host_timeout)
    print("P100",result["status"],"result",a.out/"P100-RESULT.json")
    return 0 if result["status"]=="BIT_EXACT_C4_D4_PASS" else 10

if __name__=="__main__":sys.exit(main())
