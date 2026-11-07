#!/usr/bin/env python3
"""P76 format-aware, plugin-independent WAV/MIDI export evidence oracle.

Only tests already-produced files; does not claim the plugin itself was
exercised unless an earlier approved test actually generated the outputs.
All expected SHA-256 and musical/event/frame expectations must be
independently specified before verification. No product-specific code.
"""
import hashlib
import json
from pathlib import Path
import re
import wave

SCHEMA = "125a-export-artifact-oracle-v1"
ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_SIZE = 67108864


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def validate(contract, module_sha):
    if (not isinstance(contract, dict) or
            set(contract) != {"schema", "module_sha256", "outputs"} or
            contract["schema"] != SCHEMA or
            contract["module_sha256"] != module_sha or
            type(module_sha) is not str or not SHA.fullmatch(module_sha)):
        raise ValueError("P76 requires independently pinned exact VST3 export contract")
    outputs = contract["outputs"]
    if not isinstance(outputs, list) or not 1 <= len(outputs) <= 16:
        raise ValueError("P76 1..16 exported artifacts required")
    ids, paths = set(), set()
    for entry in outputs:
        if (not isinstance(entry, dict) or
                set(entry) != {"id", "path", "kind", "expected_sha256",
                               "format_expectations"}):
            raise ValueError("P76 invalid artifact declaration keys")
        ident = entry["id"]
        if type(ident) is not str or not ID.fullmatch(ident) or ident in ids:
            raise ValueError("P76 missing or duplicate artifact ID")
        ids.add(ident)
        if (type(entry["path"]) is not str or not entry["path"] or
                len(entry["path"]) > 2048 or
                not Path(entry["path"]).is_absolute() or
                entry["path"] in paths):
            raise ValueError("P76 artifact requires unique absolute destination")
        paths.add(entry["path"])
        if type(entry["expected_sha256"]) is not str or not SHA.fullmatch(
                entry["expected_sha256"]):
            raise ValueError("P76 missing independent output byte oracle")
        kind, expected = entry["kind"], entry["format_expectations"]
        if not isinstance(expected, dict):
            raise ValueError("P76 invalid format-specific oracle")
        if kind == "wav":
            if set(expected) != {"channels","sample_rate","sample_width_bytes","frames"}:
                raise ValueError("P76 WAV must specify PCM channels/rate/bytes/frames")
            for name, minimum, maximum in [
                ("channels",1,32),("sample_rate",8000,384000),
                ("sample_width_bytes",1,4),("frames",0,100000000)
            ]:
                value=expected[name]
                if type(value) is not int or not minimum <= value <= maximum:
                    raise ValueError("P76 invalid WAV " + name)
        elif kind == "midi":
            if set(expected) != {"format","tracks","ppq","note_ons"}:
                raise ValueError("P76 MIDI requires SMF format/tracks/PPQ/expected note-ons")
            for name, lo, hi in [("format",0,1),("tracks",1,128),("ppq",1,32767)]:
                if type(expected[name]) is not int or not lo <= expected[name] <= hi:
                    raise ValueError("P76 invalid MIDI " + name)
            if expected["format"] == 0 and expected["tracks"] != 1:
                raise ValueError("P76 SMF format zero has exactly one track")
            notes=expected["note_ons"]
            if not isinstance(notes,list) or len(notes)>8192:
                raise ValueError("P76 MIDI note-on oracle count invalid")
            for note in notes:
                if not isinstance(note,dict) or set(note)!={
                        "track","tick","channel","note","velocity"}:
                    raise ValueError("P76 invalid MIDI note-on oracle structure")
                for name,lo,hi in [
                    ("track",0,expected["tracks"]-1),
                    ("tick",0,2147483647),("channel",0,15),
                    ("note",0,127),("velocity",1,127)
                ]:
                    if type(note[name]) is not int or not lo <= note[name] <= hi:
                        raise ValueError("P76 invalid independent MIDI " + name)
            if notes != sorted(notes,key=lambda x:(x["track"],x["tick"])):
                raise ValueError("P76 MIDI reference note-on list must be track/time ordered")
        else:
            raise ValueError("P76 only WAV/SMF MIDI exports are supported")
    return outputs


def vlq(data, pos):
    value=0
    for _ in range(4):
        if pos>=len(data):
            raise ValueError("P76 truncated MIDI variable-length value")
        part=data[pos]
        pos+=1
        value=(value<<7)|(part&0x7f)
        if part < 128:
            return value,pos
    raise ValueError("P76 MIDI VLQ exceeds 4 bytes")


def parse_midi(raw):
    if len(raw)<14 or raw[:4]!=b"MThd" or int.from_bytes(raw[4:8],"big")!=6:
        raise ValueError("P76 invalid SMF MIDI header")
    fmt=int.from_bytes(raw[8:10],"big")
    tracks=int.from_bytes(raw[10:12],"big")
    division=int.from_bytes(raw[12:14],"big")
    if fmt not in (0,1) or not 1<=tracks<=128 or (fmt==0 and tracks!=1) or not 1<=division<32768:
        raise ValueError("P76 unsupported MIDI format, SMPTE or malformed PPQ")
    result=[]
    pos=14
    for track in range(tracks):
        if pos+8>len(raw) or raw[pos:pos+4]!=b"MTrk":
            raise ValueError("P76 missing MIDI track")
        size=int.from_bytes(raw[pos+4:pos+8],"big")
        pos+=8
        if pos+size>len(raw):
            raise ValueError("P76 truncated MIDI track data")
        chunk=raw[pos:pos+size]
        pos+=size
        j,tick,running,events=0,0,None,0
        ended=False
        while j<len(chunk):
            events+=1
            if events>100000:
                raise ValueError("P76 excessive MIDI event count")
            delta,j=vlq(chunk,j)
            tick+=delta
            if tick>2147483647 or j>=len(chunk):
                raise ValueError("P76 overflowing/truncated MIDI event")
            status=chunk[j]
            if status>=128:
                j+=1
                if 0x80<=status<=0xef:
                    running=status
                else:
                    running=None
            elif running is not None:
                status=running
            else:
                raise ValueError("P76 MIDI data byte without running status")
            if 0x80<=status<=0xef:
                count=1 if status>>4 in (0xc,0xd) else 2
                if j+count>len(chunk) or any(v>=128 for v in chunk[j:j+count]):
                    raise ValueError("P76 truncated/invalid MIDI channel data")
                data=chunk[j:j+count]
                j+=count
                if status>>4==0x9 and data[1]!=0:
                    result.append({"track":track,"tick":tick,
                                   "channel":status&15,"note":data[0],
                                   "velocity":data[1]})
            elif status==0xff:
                if j>=len(chunk):
                    raise ValueError("P76 missing MIDI meta type")
                meta=chunk[j]
                j+=1
                count,j=vlq(chunk,j)
                if j+count>len(chunk):
                    raise ValueError("P76 truncated MIDI meta event")
                if meta==0x2f:
                    if count!=0 or j+count!=len(chunk):
                        raise ValueError("P76 malformed/non-final MIDI end-of-track")
                    ended=True
                j+=count
            elif status in (0xf0,0xf7):
                count,j=vlq(chunk,j)
                if j+count>len(chunk):
                    raise ValueError("P76 truncated MIDI SysEx")
                j+=count
            else:
                raise ValueError("P76 invalid MIDI system event in SMF")
        if not ended:
            raise ValueError("P76 MIDI track lacks a final end-of-track")
    if pos!=len(raw):
        raise ValueError("P76 unexpected unverified trailing MIDI bytes")
    return {"format":fmt,"tracks":tracks,"ppq":division,
            "note_ons":result}


def verify(contract, out, *, module_sha):
    outputs=validate(contract,module_sha)
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    report_path=out/"EXPORT-ARTIFACT-RESULT.json"
    report_path.unlink(missing_ok=True)
    report={"schema":"125a-export-artifact-result-v1",
            "status":"FAIL",
            "verified_module_sha256":module_sha,
            "declared_actions":len(outputs),"verified_actions":0,
            "outputs":[],"release_approved":False}
    for entry in outputs:
        item={"id":entry["id"],"kind":entry["kind"],"status":"FAIL"}
        try:
            filename=Path(entry["path"]).resolve(strict=True)
            if (not filename.is_file() or filename.stat().st_size>MAX_SIZE or
                    filename.stat().st_size==0):
                raise ValueError("P76 export artifact missing, empty or excessive size")
            if digest(filename)!=entry["expected_sha256"]:
                raise ValueError("P76 exported bytes differ from independent SHA-256 oracle")
            if entry["kind"]=="wav":
                try:
                    with wave.open(str(filename),"rb") as stream:
                        fmt={
                            "channels":stream.getnchannels(),
                            "sample_rate":stream.getframerate(),
                            "sample_width_bytes":stream.getsampwidth(),
                            "frames":stream.getnframes()
                        }
                        if stream.getcomptype()!="NONE":
                            raise ValueError("P76 non-PCM WAV unsupported")
                except (wave.Error,EOFError) as exc:
                    raise ValueError("P76 invalid or truncated PCM WAV") from exc
            else:
                fmt=parse_midi(filename.read_bytes())
            if fmt!=entry["format_expectations"]:
                raise ValueError("P76 exported WAV/MIDI semantics differ from independent oracle")
            item["status"]="PASS"
            item["actual_sha256"]=entry["expected_sha256"]
            report["verified_actions"]+=1
        except (OSError,ValueError,TypeError,IndexError) as exc:
            item["fault"]=str(exc)
        report["outputs"].append(item)
    if report["verified_actions"]==len(outputs):
        report["status"]="ARTIFACT_PASS"
    report_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report
