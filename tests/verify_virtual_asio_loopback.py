#!/usr/bin/env python3
"""P95: independently verify real ASIO input against simultaneously emitted output.

Native stream consists of actual ASIO4ALL callback samples, not a generated
virtual recording. A green pure-Python unit test is NEVER a driver session.
"""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

MAGIC = b"125ALB01"
HEADER = struct.Struct("<8sIIII")
SCHEMA = "125a-virtual-asio-pcm-return-v1"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_native_trace(path):
    path = Path(path)
    if not path.is_file() or not 1000 < path.stat().st_size <= 20_000_024:
        raise ValueError("P95 native 2-in/2-out PCM trace absent or out of bounds")
    with path.open("rb") as handle:
        blob = handle.read()
    if len(blob) < HEADER.size:
        raise ValueError("P95 native PCM trace truncated")
    magic, rate, frames, block, channels = HEADER.unpack_from(blob)
    if (magic != MAGIC or channels != 4
            or rate not in (44100, 48000, 96000)
            or block not in (64, 128, 256, 512, 1024)
            or frames < block * 200 or frames > block * 1032
            or len(blob) != HEADER.size + frames * 4 * 4):
        raise ValueError("P95 inconsistent native ASIO trace header or sample length")
    samples = array("f")
    samples.frombytes(blob[HEADER.size:])
    # Native Windows x64 is little-endian. Rejecting other byte ordering is
    # preferable to accidentally passing malformed or fabricated metadata.
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) != frames * 4 or any(not math.isfinite(v) for v in samples):
        raise ValueError("P95 non-finite/truncated ASIO playback or capture PCM")
    return {"rate": rate, "frames": frames, "block": block,
            "channels": channels, "samples": samples}


def envelope(samples, channel, frames, window=256):
    values = []
    for start in range(0, frames - window + 1, window):
        total = 0.
        for n in range(start, start + window):
            v = samples[4 * n + channel]
            total += v * v
        values.append(math.sqrt(total / window))
    return values


def normalized_correlation(a, b, lag):
    # a is earlier ASIO output. b is later ASIO input. Lag is nonnegative.
    if lag <= 0 or lag >= len(a) or len(a) != len(b):
        return -1.
    n = len(a) - lag
    av = a[:n]
    bv = b[lag:]
    mean_a = sum(av) / n
    mean_b = sum(bv) / n
    power_a = sum((x - mean_a) ** 2 for x in av)
    power_b = sum((x - mean_b) ** 2 for x in bv)
    if power_a < 1e-9 or power_b < 1e-9:
        return -1.
    cross = sum((x - mean_a) * (y - mean_b) for x, y in zip(av, bv))
    return cross / math.sqrt(power_a * power_b)


def analyze(trace):
    rate, frames, s = trace["rate"], trace["frames"], trace["samples"]
    env = [envelope(s, ch, frames) for ch in range(4)]
    if len(env[0]) < 250:
        raise ValueError("P95 too little true ASIO audio for reliable loopback")
    rms = [math.sqrt(sum(v*v for v in e) / len(e)) for e in env]
    if min(rms[:2]) < .008:
        raise ValueError("P95 source VST3 generated no sufficiently audible stereo signature")
    if min(rms[2:]) < .003:
        raise ValueError("P95 VB-CABLE did not return meaningful signal on both input channels")
    # Coarse timing evidence: loopback must follow output by at least one 256
    # frame window. Maximum alignment lag one second, no fixed ASIO latency.
    longest = min(len(env[0]) // 3, int(rate / 256))
    searches = []
    for expected, captured in ((0, 2), (1, 3), (0, 3), (1, 2)):
        scores = [(normalized_correlation(env[expected], env[captured], lag),
                   lag) for lag in range(1, longest + 1)]
        searches.append(max(scores))
    (corr_l, lag_l), (corr_r, lag_r), (wrong_l, _), (wrong_r, _) = searches
    if min(corr_l, corr_r) < .75:
        raise ValueError("P95 actual virtual audio return differs from VST3 emitted channels")
    if max(abs(lag_l - lag_r), 0) > 3:
        raise ValueError("P95 left and right channel latencies diverge")
    if corr_l < wrong_r + .15 or corr_r < wrong_l + .15:
        raise ValueError("P95 swapped or ambiguous VB-CABLE stereo routing")
    return {
        "sample_rate": rate, "frames": frames, "buffer_frames": trace["block"],
        "output_rms_l": round(rms[0], 7),
        "output_rms_r": round(rms[1], 7),
        "input_rms_l": round(rms[2], 7),
        "input_rms_r": round(rms[3], 7),
        "left_correlation": round(corr_l, 5),
        "right_correlation": round(corr_r, 5),
        "wrong_channel_max_correlation": round(max(wrong_l, wrong_r), 5),
        "latency_frames_estimate": round((lag_l + lag_r) * 256 / 2),
        "latency_ms_estimate": round((lag_l + lag_r) * 256 * 500. / rate, 3),
        "latency_measurement_resolution_frames": 256,
        "pass": True
    }


def verify_pcm(trace_path, native_evidence_path, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema": SCHEMA, "status": "FAIL",
              "virtual_loopback_verified": False,
              "physical_asio_hardware_verified": False,
              "commercial_daw_verified": False,
              "release_approved": False, "faults": []}
    try:
        evidence = json.loads(Path(native_evidence_path).read_text(encoding="utf-8"))
        expected = {
            "schema", "nonce", "product_sha256", "executor_sha256",
            "asio_driver_name", "asio_driver_clsid", "sample_rate",
            "buffer_frames", "completed_callbacks", "asio_callbacks",
            "deadline_misses", "xruns", "process_failures", "error_code"
        }
        if set(evidence) != expected or evidence["schema"] != (
                "125a-physical-asio-native-evidence-v1"):
            raise ValueError("P95 wrong native signed-session schema")
        if (not str(evidence["asio_driver_name"]).lower().startswith("asio4all")
                or not isinstance(evidence["nonce"], str)
                or len(evidence["nonce"]) != 48
                or any(x != 0 for x in (
                    evidence["deadline_misses"], evidence["xruns"],
                    evidence["process_failures"], evidence["error_code"]))
                or evidence["asio_callbacks"] != evidence["completed_callbacks"]
                or evidence["asio_callbacks"] < 200):
            raise ValueError("P95 native ASIO4ALL callback evidence invalid")
        trace = parse_native_trace(trace_path)
        if (evidence["sample_rate"] != trace["rate"]
                or evidence["buffer_frames"] != trace["block"]
                or evidence["completed_callbacks"] * trace["block"] != trace["frames"]):
            raise ValueError("P95 native callback count and PCM sample count differ")
        report["metrics"] = analyze(trace)
        report["trace_sha256"] = digest(trace_path)
        report["native_evidence_sha256"] = digest(native_evidence_path)
        report["plugin_sha256"] = evidence["product_sha256"]
        report["executor_sha256"] = evidence["executor_sha256"]
        report["status"] = "VIRTUAL_ASIO_PCM_LOOPBACK_PASS"
        report["virtual_loopback_verified"] = True
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            struct.error, json.JSONDecodeError, OverflowError) as error:
        report["faults"].append(str(error))
    (out / "P95-PCM-LOOPBACK.json").write_text(json.dumps(report, indent=2)+"\n",
                                               encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trace", type=Path, required=True)
    p.add_argument("--native-evidence", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = verify_pcm(args.trace, args.native_evidence, args.out)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "VIRTUAL_ASIO_PCM_LOOPBACK_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
