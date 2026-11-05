#!/usr/bin/env python3
"""Fresh-process VST3 recall negative controls without depending on MSVC."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import wave

spec = importlib.util.spec_from_file_location("recall", Path(__file__).with_name("run_state_reload.py"))
recall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recall)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    binary = root / "fixture.vst3" / "Contents" / "x86_64-win" / "fixture.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"synthetic module only")
    host = root / "host.exe"
    host.write_bytes(b"synthetic host only")
    state = root / "state.bin"
    state.write_bytes(b"original state data")
    product = {"schema": "125a-state-reload-v1", "product": {
        "binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
        "host": str(host), "initial_state": str(state), "deterministic_audio": True}
    calls = []

    def fake_host(cmd, **kwargs):
        calls.append(cmd)
        wav, saved = Path(cmd[4]), Path(cmd[5])
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2)
            w.setframerate(44100)
            w.setsampwidth(3)
            w.writeframes(b"\x00" * (352800 * 2 * 3))
        saved.write_bytes(b"valid persisted state")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    out = root / "positive"
    result = recall.check(product, out, runner=fake_host)
    assert result["status"] == "PASS" and result["new_process_instances"] == 2
    assert result["musical_correctness"] == "NOT COVERED"
    assert len(calls) == 2 and all(c[1] == "--render-state-save" for c in calls)

    # Exact externally supplied saved state fingerprint is checked on BOTH
    # genuine host processes, not inferred from an API success code.
    expected_state = hashlib.sha256(b"valid persisted state").hexdigest()
    product["expected_saved_state_sha256"] = expected_state
    result = recall.check(product, root / "integrity_positive", runner=fake_host)
    assert result["status"] == "PASS"
    assert result["saved_state_integrity"] == "PASS"
    product["expected_saved_state_sha256"] = "e" * 64
    result = recall.check(product, root / "integrity_wrong_reference", runner=fake_host)
    assert result["status"] == "FAIL"
    assert result["saved_state_integrity"] == "FAIL"
    assert result["fresh_process_recall"] == "FAIL"
    product["expected_saved_state_sha256"] = expected_state

    # A host that falsely returns a successful load but re-serializes the
    # wrong state must not be accepted by a known product-state oracle.
    def state_corruption(cmd, **kwargs):
        outcome = fake_host(cmd, **kwargs)
        Path(cmd[5]).write_bytes(b"different saved state")
        return outcome

    result = recall.check(product, root / "integrity_corrupt_host", runner=state_corruption)
    assert result["status"] == "FAIL"
    assert result["saved_state_integrity"] == "FAIL"
    del product["expected_saved_state_sha256"]

    product["expected_audio_sha256"] = "f" * 64
    result = recall.check(product, root / "wrong_reference", runner=fake_host)
    assert result["status"] == "FAIL" and result["musical_correctness"] == "FAIL"
    del product["expected_audio_sha256"]

    def absent(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, "", "")
    result = recall.check(product, out, runner=absent)
    assert result["status"] == "FAIL" and result["new_process_instances"] == 0
    assert not (out / "recall-1.wav").exists(), "stale audio survived"
    assert not (out / "recall-1.bin").exists(), "stale state survived"

    product["product"]["sha256"] = "0" * 64
    try:
        recall.check(product, root / "wrong_binary", runner=fake_host)
    except ValueError as e:
        assert "binary SHA-256 mismatch" in str(e)
    else:
        raise AssertionError("wrong VST3 binary accepted")
    product["product"]["sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    product["deterministic_audio"] = False
    result = recall.check(product, root / "nondeterministic", runner=fake_host)
    assert result["status"] == "PASS"
    assert result["audio_determinism"] == "NOT COVERED"
    # VST3 allows small, non-empty opaque state streams. Do not reject
    # valid one-byte states purely because our old fixtures were larger.
    state.write_bytes(b"x")
    result = recall.check(product, root / "tiny_state", runner=fake_host)
    assert result["status"] == "PASS", "valid one-byte state refused"
    state.write_bytes(b"")
    try:
        recall.check(product, root / "empty_state", runner=fake_host)
    except ValueError as e:
        assert "invalid state size" in str(e)
    else:
        raise AssertionError("empty plugin state accepted")
    # Sparse logical file exercises the upper resource bound without making a
    # 128 MiB memory allocation during unit test.
    with state.open("wb") as stream:
        stream.seek(128 * 1024 * 1024 - 1)
        stream.write(b"X")
    try:
        recall.check(product, root / "oversize_state", runner=fake_host)
    except ValueError as e:
        assert "invalid state size" in str(e)
    else:
        raise AssertionError("state at upper size limit accepted")
print("[PASS] fresh-process state-recall rejects stale outputs, wrong binary and audio reference")
