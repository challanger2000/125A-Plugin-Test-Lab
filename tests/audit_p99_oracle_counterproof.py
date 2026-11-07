#!/usr/bin/env python3
"""2026-11-07 read-only adversarial proof of an existing oracle coverage gap.

This test deliberately documents an *accepted incorrect source stimulus*.
Its own CI PASS means a defect in test adequacy was reproduced, NOT that
virtual ASIO4ALL hardware or correct VST3 audio was accepted.
"""
from array import array
import json
import math
from pathlib import Path
import struct
import tempfile

from test_p95_virtual_asio_loopback import P95VirtualLoopback
from verify_virtual_asio_loopback import verify_pcm, MAGIC


def run():
    # Reuse the exact existing P95 independently generated evidence and
    # correct-return positive control before constructing a wrong-return
    # negative. No customer VST3 or source is mutated.
    f = P95VirtualLoopback(methodName="test_realistic_delayed_stereo_PCM_passes_virtual_only")
    f.setUp()
    try:
        positive = verify_pcm(f.make_trace(), f.proof, f.root / "audit-correct")
        assert positive["status"] == "VIRTUAL_ASIO_PCM_LOOPBACK_PASS", positive
        wrong = array("f")
        delay = 3072
        frames = f.frames
        rate = f.rate
        l = array("f", [0.]) * frames
        r = array("f", [0.]) * frames
        # Original P95 reference is 317 Hz L / 557 Hz R.
        # A faulty VST3 makes 911 Hz L / 1277 Hz R, while preserving
        # the published channel-specific on/off envelopes.
        for n in range(frames):
            t = n / rate
            ml = (0x6d4e92b5 >> (int(t / .061) % 32)) & 1
            mr = (0xb39a4d27 >> (int(t / .083) % 32)) & 1
            l[n] = .040 * ml * math.sin(2 * math.pi * 911 * t)
            r[n] = .055 * mr * math.sin(2 * math.pi * 1277 * t)
        for n in range(frames):
            il = l[n-delay] * .84 if n >= delay else 0.
            ir = r[n-delay] * .72 if n >= delay else 0.
            wrong.extend((l[n], r[n], il, ir))
        path = f.root / "wrong-frequency-native-trace.f32"
        path.write_bytes(
            struct.pack("<8sIIII", MAGIC, rate, frames, f.block, 4)
            + wrong.tobytes())
        # Intentionally use existing, fully valid expected session evidence.
        # The only mutation is the VST3 output waveform and its returning
        # input, not JSON nonce, header, timestamps, or callback count.
        result = verify_pcm(path, f.proof, f.root / "audit-broken")
        detected = result["status"] == "FAIL"
        report = {
            "schema": "125a-audit-p99-oracle-challenge-v1",
            "baseline_correct_status": positive["status"],
            "fault_injection": "VST3 emitted 911Hz/1277Hz instead of contract 317Hz/557Hz; real-return PCM simulated to match",
            "negative_was_rejected": detected,
            "actual_negative_status": result["status"],
            "test_adequacy_finding": "UNDETECTED_WRONG_SOURCE_FREQUENCIES" if not detected else "REJECTED_WRONG_SOURCE",
            "actual_asio4all_driver_run": "NOT RUN",
            "physical_hardware": "NOT RUN",
            "release_approved": False
        }
        dest = Path("artifacts/P99-audit")
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "ORACLE-COUNTERPROOF.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        if detected:
            raise AssertionError("P99 expected to reproduce the current uncovered frequency error; if the verifier was fixed, update the audit.")
        print("[AUDIT] Counterexample reproduced. Product/audio acceptance remains FAIL/NOT RUN.")
    finally:
        f.tearDown()
        f.doCleanups()


if __name__ == "__main__":
    run()
