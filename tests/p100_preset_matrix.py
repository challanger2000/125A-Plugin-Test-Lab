#!/usr/bin/env python3
"""P100 expansion: complete SF2 preset matrix and strict offline parity audit.

An additive P100 Test Lab module, not a replacement for the live P100 host.
An audit accepts only SHA-pinned owner-private source/native captures. No
source bytes, ROM, SF2, Creative drivers, or recordings belong in public CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from run_p100_original_vst3_parity import compare_pcm, demand, digest

SCHEMA = "125A-P100-SF2-PRESET-MATRIX-V1"
EVIDENCE_SCHEMA = "125A-P100-SF2-MATRIX-EVIDENCE-V1"
SOURCE_MANIFEST_SCHEMA = "P002_ORIGINAL_WIN95_REAL_BOOT_CAPTURE_V1"
NOTES = (48, 60, 72)
VELOCITIES = (1, 64, 127)
FRAME_RATE = 44100
SAMPLE_FRAMES = 88200


def sf2_presets(path: Path):
    """Parse SF2 RIFF/pdta/phdr; do not assume programs are contiguous."""
    with path.open("rb") as f:
        raw = f.read()
    demand(len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"sfbk",
           "bank is not RIFF sfbk")
    demand(struct.unpack_from("<I", raw, 4)[0] == len(raw) - 8,
           "truncated or trailing SF2 RIFF bytes")
    phdr = None
    def chunks(begin, end):
        pos = begin
        while pos < end:
            demand(pos + 8 <= end, "truncated SF2 chunk header")
            name = raw[pos:pos + 4]
            size = struct.unpack_from("<I", raw, pos + 4)[0]
            data = pos + 8
            demand(data + size <= end, "truncated SF2 chunk")
            yield name, data, data + size
            pos = data + size + (size & 1)
        demand(pos == end, "misaligned SF2 chunk")
    for name, begin, end in chunks(12, len(raw)):
        if name != b"LIST" or end - begin < 4 or raw[begin:begin + 4] != b"pdta":
            continue
        demand(phdr is None, "multiple SF2 pdta lists")
        for subname, b, e in chunks(begin + 4, end):
            if subname == b"phdr":
                demand(phdr is None, "duplicate SF2 phdr")
                phdr = raw[b:e]
    demand(phdr is not None and len(phdr) >= 76 and len(phdr) % 38 == 0,
           "missing or malformed SF2 phdr")
    presets = []
    previous_bag = -1
    for i in range(0, len(phdr), 38):
        name, program, bank, bag, _lib, _genre, _morph = struct.unpack_from(
            "<20sHHHIII", phdr, i)
        name = name.split(b"\0", 1)[0].decode("cp1252", "replace").strip()
        demand(bag >= previous_bag, "descending SF2 preset bag index")
        previous_bag = bag
        if i == len(phdr) - 38:
            demand(name == "EOP", "missing terminal SF2 EOP preset")
        else:
            demand(0 <= program < 128 and bool(name), "invalid SF2 preset")
            presets.append({"bank": bank, "program": program, "name": name})
    keys = [(p["bank"], p["program"]) for p in presets]
    demand(len(keys) == len(set(keys)), "duplicate SF2 bank/program mapping")
    demand(bool(presets), "SF2 has no presets")
    return presets


def events(kind, note=None, velocity=None):
    if kind == "single":
        return [
            {"frame": 256, "type": "note_on", "note": note, "velocity": velocity},
            {"frame": 22306, "type": "note_off", "note": note},
            {"frame": 44100, "type": "midi_reset"},
        ]
    if kind == "chord":
        return [
            {"frame": 256, "type": "note_on", "note": n, "velocity": v}
            for n, v in ((60, 64), (64, 100), (67, 127))
        ] + [
            {"frame": 22306, "type": "note_off", "note": n}
            for n in (60, 64, 67)
        ] + [{"frame": 44100, "type": "midi_reset"}]
    if kind == "retrigger":
        return [
            {"frame": 256, "type": "note_on", "note": 60, "velocity": 64},
            {"frame": 5000, "type": "note_on", "note": 60, "velocity": 127},
            {"frame": 16000, "type": "note_off", "note": 60},
            {"frame": 22306, "type": "note_off", "note": 60},
            {"frame": 44100, "type": "midi_reset"},
        ]
    raise ValueError("unknown case kind")


def make_plan(bank_path: Path, expected_presets=77):
    presets = sf2_presets(bank_path)
    demand(len(presets) == expected_presets,
           f"preset catalog has {len(presets)}, expected {expected_presets}")
    cases = []
    for p in presets:
        prefix = f"b{p['bank']:05d}-p{p['program']:03d}"
        for note in NOTES:
            for vel in VELOCITIES:
                cases.append({"id": f"{prefix}-n{note:03d}-v{vel:03d}",
                              "bank": p["bank"], "program": p["program"],
                              "kind": "single", "events": events("single", note, vel)})
        for kind in ("chord", "retrigger"):
            cases.append({"id": f"{prefix}-{kind}",
                          "bank": p["bank"], "program": p["program"],
                          "kind": kind, "events": events(kind)})
    return {"schema": SCHEMA, "sf2_sha256": digest(bank_path),
            "sample_rate": FRAME_RATE, "total_frames_per_case": SAMPLE_FRAMES,
            "notes": list(NOTES), "velocities": list(VELOCITIES),
            "presets": presets, "cases": cases,
            "required_source": "real Creative Win95 independent per-case original OUT and PCM",
            "required_native": "real exported Windows VST3 independently generated OUT and PCM",
            "strict_pcm16": True, "auto_alignment": False,
            "release_approved": False}


def load_plan(path: Path):
    data = json.loads(path.read_text("utf-8-sig"))
    demand(data.get("schema") == SCHEMA and data.get("sample_rate") == FRAME_RATE,
           "wrong P100 matrix plan schema/clock")
    presets = data.get("presets")
    demand(isinstance(presets, list) and len(presets) > 0,
           "matrix plan missing presets")
    cases = data.get("cases")
    demand(isinstance(cases, list) and len(cases) == len(presets) * 11,
           "incomplete P100 preset matrix plan")
    keys = [(p["bank"], p["program"]) for p in presets]
    demand(len(keys) == len(set(keys)), "duplicate preset mapping")
    ids = [c["id"] for c in cases]
    demand(len(ids) == len(set(ids)), "duplicate matrix case ID")
    demand(data.get("notes") == list(NOTES) and
           data.get("velocities") == list(VELOCITIES) and
           data.get("total_frames_per_case") == SAMPLE_FRAMES and
           data.get("strict_pcm16") is True and
           data.get("auto_alignment") is False,
           "P100 matrix coverage/clock policy changed")
    expected = []
    for p in presets:
        prefix = f"b{p['bank']:05d}-p{p['program']:03d}"
        for n in NOTES:
            for v in VELOCITIES:
                expected.append((f"{prefix}-n{n:03d}-v{v:03d}", p["bank"],p["program"],
                                 "single", events("single", n, v)))
        for kind in ("chord", "retrigger"):
            expected.append((f"{prefix}-{kind}",p["bank"],p["program"],kind,events(kind)))
    for actual, expected_case in zip(cases,expected):
        demand((actual.get("id"),actual.get("bank"),actual.get("program"),
                actual.get("kind"),actual.get("events")) == expected_case,
               "P100 preset matrix missing/modified/reordered cases")
    return data


def verified_file(root: Path, descriptor: dict):
    demand(isinstance(descriptor, dict) and
           set(descriptor) == {"path", "sha256"}, "invalid SHA-pinned evidence")
    path = descriptor["path"]
    demand(isinstance(path, str) and bool(path) and
           not Path(path).is_absolute() and
           not re.match(r"^[A-Za-z]:", path) and
           "\\" not in path and ".." not in Path(path).parts,
           "unsafe evidence file path")
    fp = (root / path).resolve()
    demand(fp.is_relative_to(root.resolve()) and fp.is_file(),
           "missing evidence file")
    demand(re.fullmatch("[0-9a-f]{64}", descriptor["sha256"]) is not None and
           digest(fp) == descriptor["sha256"], "evidence SHA256 mismatch")
    return fp


def register_writes(path: Path, *, native: bool):
    lines = path.read_text("ascii").splitlines()
    if native:
        demand(len(lines) >= 3 and
               lines[0] == "# INDEPENDENT_NATIVE_P002_PORT_WRITES_ONLY" and
               lines[1] == "# CLOCK=HOST_44100_SAMPLE_FRAMES; ORIGIN=ACTIVATION" and
               lines[2] == "# SOURCE_ORIGINAL_WIN95_PROVENANCE=SEPARATELY_REQUIRED",
               "native VST3 register capture missing required headers")
        lines = lines[3:]
    else:
        demand(not any("INDEPENDENT_NATIVE_P002_PORT_WRITES_ONLY" in x
                       for x in lines[:3]),
               "native capture cannot be used as original source")
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Original 86Box traces include READ events prefixed with 'R '.
        # The genuine native VST3 OUT recorder MUST remain write-only.
        read = line.startswith("R ")
        if read:
            demand(not native, "native trace contains a READ event")
            line = line[2:]
        fields = line.split()
        demand(len(fields) == 3 and fields[0].isdigit() and
               all(re.fullmatch("[0-9A-Fa-f]{1,4}", x) for x in fields[1:]),
               "malformed physical EMU8000 register event")
        frame = int(fields[0]); port = int(fields[1],16); value = int(fields[2],16)
        demand(0 <= frame <= FRAME_RATE * 3600 and
               (not out or out[-1][0] <= frame),
               "invalid EMU8000 register clock")
        if not read:
            out.append((frame, port, value))
    demand(bool(out), "empty register capture is not proof")
    return out


def compare_registers(a: Path, b: Path, orig_origin: int, native_origin: int,
                      frames: int, *, original_cached=None):
    source = original_cached if original_cached is not None else register_writes(a,native=False)
    original = [(t-orig_origin,p,v) for t,p,v in source
                if orig_origin <= t < orig_origin+frames]
    independent = [(t-native_origin,p,v) for t,p,v in register_writes(b,native=True)
                   if native_origin <= t < native_origin+frames]
    demand(bool(original) and bool(independent),
           "source/native register events missing in requested window")
    difference = None
    for i in range(max(len(original), len(independent))):
        left = original[i] if i < len(original) else None
        right = independent[i] if i < len(independent) else None
        if left != right:
            difference = {"event_index": i, "original": left, "native": right}
            break
    return {"equal": difference is None, "original_events": len(original),
            "native_events": len(independent), "first_difference": difference}


def audit(plan_file: Path, bundle: Path):
    """Fail closed. No real PASS without complete owner-private evidence."""
    p = load_plan(plan_file)
    result_file = bundle / "P100-MATRIX-RESULT.json"
    report = {"schema": "125A-P100-SF2-MATRIX-RESULT-V1",
              "status": "INCOMPLETE_OR_MISMATCH", "release_approved": False,
              "expected_cases": len(p["cases"]), "tested_cases": 0,
              "passed_cases": 0, "failures": []}
    try:
        evidence_path = bundle / "P100-MATRIX-EVIDENCE.json"
        demand(evidence_path.is_file(), "no owner-private P100 matrix evidence bundle")
        evidence = json.loads(evidence_path.read_text("utf-8-sig"))
        demand(evidence.get("schema") == EVIDENCE_SCHEMA and
               evidence.get("plan_sha256") == digest(plan_file),
               "evidence does not belong to this exact matrix plan")
        source_manifest = verified_file(bundle, evidence["original_session_manifest"])
        original = json.loads(source_manifest.read_text("utf-8-sig"))
        demand(original.get("schema") == SOURCE_MANIFEST_SCHEMA and
               original.get("original_session_kind") ==
                    "PRIVATE_CALIBRATED_86BOX_WIN95_CREATIVE_CC0_1" and
               original.get("sample_rate") == FRAME_RATE and
               original.get("original_source_sf2_ram_words_bit_equal") == 260921 and
               original.get("original_owner_sf2_sha256") == p["sf2_sha256"] and
               original.get("guest_log_from_same_private_fat16_disk") is True,
               "not the attested original Creative Win95 SoundFont session")
        # Current C4/D4-only owner session is NOT accepted as evidence for
        # a claimed 77-preset sweep. Its private guest must actually log
        # every case in this matrix under a session-bound source attestor.
        demand(original.get("matrix_plan_sha256") == digest(plan_file) and
               original.get("matrix_case_ids") == [c["id"] for c in p["cases"]],
               "original Win95 session did not execute the complete matrix")
        # The *full* private original trace and PCM are mandatory and their
        # own SHA values must be tied to the same original session manifest.
        orig_trace = verified_file(bundle,evidence["original_trace"])
        orig_wav = verified_file(bundle,evidence["original_wav"])
        orig_log = verified_file(bundle,evidence["original_guest_log"])
        demand(original.get("original_emu8k_trace_sha256") == digest(orig_trace) and
               original.get("original_win95_precard_wav_sha256") == digest(orig_wav) and
               original.get("original_guest_log_sha256") == digest(orig_log),
               "original full Win95 source trace/PCM/guest provenance mismatch")
        native_vst3 = verified_file(bundle,evidence["native_vst3"])
        native_host = verified_file(bundle,evidence["native_host"])
        # Cache the huge original register stream; don't parse it 847 times.
        original_writes = register_writes(orig_trace,native=False)
        inputs = evidence.get("cases")
        demand(isinstance(inputs,list),"missing P100 matrix evidence cases")
        case_map = {x["id"]: x for x in inputs}
        demand(len(inputs) == len(case_map) == len(p["cases"]) and
               set(case_map) == {c["id"] for c in p["cases"]},
               "missing, duplicate or extra P100 matrix case evidence")
        distinct = set()
        for case in p["cases"]:
            sample = case_map[case["id"]]
            check = {"id": case["id"], "kind": case["kind"]}
            try:
                demand(sample.get("bank") == case["bank"] and
                       sample.get("program") == case["program"] and
                       sample.get("events") == case["events"],
                       "captured MIDI/bank/program differs from planned case")
                demand(type(sample.get("exported_windows_vst3_host_exit_code"))
                       is int and sample["exported_windows_vst3_host_exit_code"]==0,
                       "no successful exported Windows VST3 host run attested")
                frames = sample.get("frames",0)
                demand(type(frames) is int and 256 <= frames <= SAMPLE_FRAMES,
                       "invalid case PCM window")
                orig_origin = sample.get("original_start_frame")
                native_origin = sample.get("native_start_frame")
                demand(type(orig_origin) is int and orig_origin>=0 and
                       type(native_origin) is int and native_origin>=0,
                       "source/native origins not separately declared")
                native_wav = verified_file(bundle,sample["native_wav"])
                native_out = verified_file(bundle,sample["native_out"])
                clock_file = verified_file(bundle,sample["native_clock_manifest"])
                clock = json.loads(clock_file.read_text("utf-8-sig"))
                demand(clock.get("schema")=="P002_NATIVE_REAL_VST3_MATRIX_CASE_V1" and
                       clock.get("id")==case["id"] and
                       clock.get("bank")==case["bank"] and
                       clock.get("program")==case["program"] and
                       clock.get("events")==case["events"] and
                       clock.get("sample_rate")==FRAME_RATE and
                       clock.get("native_module_sha256")==digest(native_vst3) and
                       clock.get("native_host_sha256")==digest(native_host) and
                       clock.get("native_chip_out_trace_sha256")==digest(native_out) and
                       clock.get("native_precard_wav_sha256")==digest(native_wav),
                       "native per-case VST3 host/clock provenance mismatch")
                demand(native_wav!=orig_wav and native_out!=orig_trace and
                       str(native_wav) not in distinct and str(native_out) not in distinct and
                       str(clock_file) not in distinct,
                       "aliased/reused native evidence across independent test cases")
                distinct.update((str(native_wav),str(native_out),str(clock_file)))
                check["registers"] = compare_registers(
                    orig_trace,native_out,orig_origin,native_origin,frames,
                    original_cached=original_writes)
                check["pcm"] = compare_pcm(
                    orig_wav,native_wav,
                    {"original_start_frame":orig_origin,
                     "native_start_frame":native_origin,"frames":frames})
                check["pass"] = check["registers"]["equal"] and check["pcm"]["equal"]
            except (ValueError,KeyError,OSError,EOFError) as e:
                check["pass"] = False
                check["error"] = str(e)
            report["tested_cases"] += 1
            report["passed_cases"] += int(check["pass"])
            if not check["pass"]:
                report["failures"].append(check)
        if report["passed_cases"] == len(p["cases"]):
            report["status"] = "ALL_PRESET_CASES_BIT_EXACT_PASS"
    except (ValueError,KeyError,OSError,EOFError,TypeError) as e:
        report["failure_reason"] = str(e)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    gen=sub.add_parser("plan",help="enumerate every real SF2 preset, never fake missing IDs")
    gen.add_argument("--sf2",type=Path,required=True)
    gen.add_argument("--out",type=Path,required=True)
    gen.add_argument("--expected-presets",type=int,default=77)
    verify=sub.add_parser("audit",help="strict owner-private original/native captures")
    verify.add_argument("--plan",type=Path,required=True)
    verify.add_argument("--bundle",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.command == "plan":
        p=make_plan(args.sf2,args.expected_presets)
        demand(not args.out.exists(),"matrix plan output already exists")
        args.out.write_text(json.dumps(p,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
        print(f"P100_MATRIX_PLANNED presets={len(p['presets'])} cases={len(p['cases'])} "
              f"source_sha256={p['sf2_sha256']} LIVE_PARITY=NOT_RUN")
        return 0
    report=audit(args.plan,args.bundle)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["status"] == "ALL_PRESET_CASES_BIT_EXACT_PASS" else 10


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError,KeyError,OSError) as exc:
        print("P100_MATRIX_FAIL_CLOSED: "+str(exc),file=sys.stderr)
        sys.exit(10)
