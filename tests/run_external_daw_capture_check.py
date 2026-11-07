#!/usr/bin/env python3
"""P90: independently compare a *supplied* external DAW capture to reference PCM.

This program has no ASIO driver, DAW process, or capture-device access.
A metadata claim that an ASIO device was used is NOT hardware provenance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import wave

SCHEMA = "125a-external-daw-asio-capture-v1"
RESULT = "125a-external-daw-capture-comparison-v1"
MAX_BYTES = 16_000_000
RATES = {44100, 48000, 88200, 96000, 176400, 192000}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def _int(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("P90 invalid " + name)
    return value


def _hex(value, name):
    if type(value) is not str or len(value) != 64 or any(
            c not in "0123456789abcdef" for c in value):
        raise ValueError("P90 invalid " + name)
    return value


def _name(value, name):
    if type(value) is not str or not 1 <= len(value.strip()) <= 160:
        raise ValueError("P90 invalid " + name)
    return value


def _pcm(path, declared_hash):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or not 46 <= path.stat().st_size <= MAX_BYTES:
        raise ValueError("P90 WAV capture/reference missing or size outside bounds")
    if digest(path) != _hex(declared_hash, "PCM SHA256"):
        raise ValueError("P90 supplied PCM differs from independently pinned SHA256")
    try:
        with wave.open(str(path), "rb") as wav:
            nch = wav.getnchannels()
            rate = wav.getframerate()
            width = wav.getsampwidth()
            count = wav.getnframes()
            fmt = wav.getcomptype()
            if (fmt != "NONE" or nch not in (1, 2) or rate not in RATES
                    or width not in (2, 3, 4)
                    or not rate // 4 <= count <= rate * 10):
                raise ValueError("P90 unsupported real PCM capture properties")
            raw = wav.readframes(count)
            if len(raw) != count * nch * width:
                raise ValueError("P90 truncated PCM audio")
    except (wave.Error, EOFError, struct.error) as exc:
        raise ValueError("P90 WAV parse failed") from exc
    if width == 2:
        values = struct.unpack("<%dh" % (count*nch), raw)
        scale = 32768.0
    elif width == 4:
        values = struct.unpack("<%di" % (count*nch), raw)
        scale = 2147483648.0
    else:
        values = [
            int.from_bytes(raw[i:i+3], "little", signed=True)
            for i in range(0, len(raw), 3)]
        scale = 8388608.0
    streams = [[v/scale for v in values[ch::nch]] for ch in range(nch)]
    peaks = [max(abs(v) for v in samples) for samples in streams]
    if any(peak < .005 for peak in peaks):
        raise ValueError("P90 silent reference/capture channel invalid")
    if any(peak >= .99999 for peak in peaks):
        raise ValueError("P90 clipped waveform channel cannot prove PCM integrity")
    return {"samples_by_channel": streams, "rate": rate, "frames": count,
            "channels": nch, "bits": width*8, "peaks": peaks,
            "sha256": declared_hash}


def _compare(ref, capture, max_offset, threshold):
    # The common lag is estimated with channel one, then ALL real channels
    # must independently pass the exact same lag, gain and PCM residual
    # requirements. A good left channel cannot conceal a broken right.
    a, b = ref["samples_by_channel"][0], capture["samples_by_channel"][0]
    window = min(8192, len(a)//3, len(b)//3)
    if window < 1000:
        raise ValueError("P90 insufficient signal for independent comparison")
    stride = max(1, window//1024)
    best = (-math.inf, 0)
    for offset in range(-max_offset, max_offset+1):
        start_a, start_b = max(0, -offset), max(0, offset)
        pairs = min(window, len(a)-start_a, len(b)-start_b)
        if pairs < 1000:
            continue
        aa = [a[start_a+i] for i in range(0, pairs, stride)]
        bb = [b[start_b+i] for i in range(0, pairs, stride)]
        xy = sum(x*y for x,y in zip(aa,bb))
        xx = sum(x*x for x in aa)
        yy = sum(y*y for y in bb)
        corr = xy/math.sqrt(xx*yy) if xx > 1e-10 and yy > 1e-10 else -1.
        if corr > best[0]:
            best = (corr, offset)
    offset = best[1]
    start_a, start_b = max(0, -offset), max(0, offset)
    overlap = min(len(a)-start_a, len(b)-start_b)
    if overlap < int(.75 * min(len(a), len(b))):
        raise ValueError("P90 captured waveform overlaps too little")
    stride = max(1, overlap//40000)
    comparisons = []
    for channel, (ref_stream, recorded_stream) in enumerate(zip(
            ref["samples_by_channel"], capture["samples_by_channel"]), start=1):
        aa = ref_stream[start_a:start_a+overlap:stride]
        bb = recorded_stream[start_b:start_b+overlap:stride]
        xx = sum(x*x for x in aa)
        yy = sum(y*y for y in bb)
        xy = sum(x*y for x,y in zip(aa,bb))
        if xx < 1e-6 or yy < 1e-6:
            raise ValueError("P90 channel has insufficient captured signal energy")
        gain = xy/xx
        corr = xy/math.sqrt(xx*yy)
        nrmse = math.sqrt(max(0, yy-2*gain*xy+gain*gain*xx)/yy)
        valid_channel = corr >= threshold and .2 <= gain <= 5.0 and nrmse <= .18
        comparisons.append({
            "channel": channel, "correlation": round(corr, 7),
            "relative_rms_error": round(nrmse, 7),
            "estimated_gain": round(gain, 7),
            "matches_reference": valid_channel
        })
    valid = (all(x["matches_reference"] for x in comparisons)
             and abs(len(a)-len(b)) <= max_offset)
    return {
        "lag_frames": offset,
        "correlation": min(x["correlation"] for x in comparisons),
        "relative_rms_error": max(x["relative_rms_error"] for x in comparisons),
        "estimated_gain": comparisons[0]["estimated_gain"],
        "channel_results": comparisons,
        "channels_compared": len(comparisons),
        "compared_frames": overlap,
        "matches_reference": valid
    }


def run(contract, out):
    if not isinstance(contract, dict) or set(contract) != {
            "schema", "plugin", "session", "reference", "capture", "oracle"} or (
            contract["schema"] != SCHEMA):
        raise ValueError("P90 exact versioned DAW capture contract required")
    plugin = contract["plugin"]
    session = contract["session"]
    expected = contract["reference"]
    capture_spec = contract["capture"]
    oracle = contract["oracle"]
    if (not isinstance(plugin, dict) or set(plugin) != {"binary", "sha256"}
            or not isinstance(session, dict) or set(session) != {
                "daw_name", "daw_version", "asio_driver", "audio_interface",
                "rate", "buffer_size", "recorded_at_utc"}
            or not isinstance(expected, dict) or set(expected) != {"wav", "sha256"}
            or not isinstance(capture_spec, dict) or set(capture_spec) != {
                "wav", "sha256"}
            or not isinstance(oracle, dict) or set(oracle) != {
                "min_correlation", "max_lag_frames"}):
        raise ValueError("P90 malformed expected external source specification")
    binary = Path(plugin["binary"]).resolve(strict=True)
    binary_sha = _hex(plugin["sha256"], "module SHA256")
    if digest(binary) != binary_sha:
        raise ValueError("P90 source VST3 binary changed since reference was approved")
    for field in ("daw_name", "daw_version", "asio_driver",
                  "audio_interface", "recorded_at_utc"):
        _name(session[field], field)
    if _int(session["rate"], 44100, 192000, "rate") not in RATES:
        raise ValueError("P90 unsupported rate")
    _int(session["buffer_size"], 16, 8192, "buffer size")
    if type(oracle["min_correlation"]) not in (int,float) or not (
            .90 <= oracle["min_correlation"] <= .9999):
        raise ValueError("P90 invalid minimum correlation requirement")
    lag = _int(oracle["max_lag_frames"], 0, 1024, "latency/lag budget")
    expected_path = Path(expected["wav"]).resolve(strict=True)
    captured_path = Path(capture_spec["wav"]).resolve(strict=True)
    if expected_path == captured_path or expected["sha256"] == capture_spec["sha256"]:
        raise ValueError("P90 capture must be a distinct independently recorded WAV")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": RESULT, "status": "FAIL",
        "verified_module_sha256": binary_sha,
        "comparison": None, "faults": [],
        "session_metadata_source": "USER_DECLARATION_ONLY",
        "hardware_asio_verified": False,
        "daw_session_verified": False,
        "product_function_semantics_verified": False,
        "release_approved": False
    }
    try:
        ref = _pcm(expected_path, expected["sha256"])
        mic = _pcm(captured_path, capture_spec["sha256"])
        if ref["rate"] != mic["rate"] or ref["rate"] != session["rate"]:
            raise ValueError("P90 capture/reference declared sample rates disagree")
        if ref["channels"] != mic["channels"]:
            raise ValueError("P90 capture/reference channel counts disagree")
        result = _compare(ref, mic, lag, oracle["min_correlation"])
        report["comparison"] = result
        report["reference"] = {k:v for k,v in ref.items() if k != "samples_by_channel"}
        report["capture"] = {k:v for k,v in mic.items() if k != "samples"}
        report["status"] = ("AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED"
                            if result["matches_reference"] else "FAIL")
        if not result["matches_reference"]:
            report["faults"].append("P90 actual PCM fails independent reference oracle")
        if digest(binary) != binary_sha or digest(expected_path) != expected["sha256"] or (
                digest(captured_path) != capture_spec["sha256"]):
            raise ValueError("P90 source assets changed while testing")
    except (OSError, ValueError, TypeError, wave.Error, OverflowError) as exc:
        report["status"] = "FAIL"
        report["faults"].append(str(exc))
    (out / "EXTERNAL-CAPTURE-COMPARISON.json").write_text(
        json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        result = run(json.loads(a.contract.read_text(encoding="utf-8")), a.out)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as err:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": RESULT, "status": "FAIL", "faults": [str(err)],
                  "hardware_asio_verified": False,
                  "daw_session_verified": False, "release_approved": False}
        (a.out / "EXTERNAL-CAPTURE-COMPARISON.json").write_text(
            json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "AUDIO_COMPARISON_PASS_SOURCE_UNATTESTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
