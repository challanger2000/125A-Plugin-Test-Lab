#!/usr/bin/env python3
"""Product-independent dual-VST3 reference: good, global leak, stale and wrong SHA."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location(
    "dual", Path(__file__).with_name("run_product_dual_state.py"))
dual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dual)
spec2 = importlib.util.spec_from_file_location(
    "fixture", Path(__file__).with_name("test_instance_isolation.py"))
# Do not import fixture: test_instance_isolation.py runs a test at import.
spec3 = importlib.util.spec_from_file_location(
    "oracle", Path(__file__).with_name("verify_instance_isolation.py"))
oracle = importlib.util.module_from_spec(spec3)
spec3.loader.exec_module(oracle)


def sha(bytes_):
    return hashlib.sha256(bytes_).hexdigest()


def fixture_files(root):
    root = Path(root)
    plugin = root / "Fake.vst3" / "Contents" / "x86_64-win" / "Fake.vst3"
    plugin.parent.mkdir(parents=True, exist_ok=True)
    plugin.write_bytes(b"real host fixture identity")
    host = root / "two-instance.exe"
    host.write_bytes(b"synthetic host for manifest unit test only")
    a = root / "A.bin"
    b = root / "B.bin"
    a.write_bytes(oracle.approved(11,22))
    b.write_bytes(oracle.approved(33,44))
    manifest = {
        "schema": "125a-product-dual-state-oracle-v1",
        "product": {"binary": str(plugin), "sha256": dual.hash_file(plugin)},
        "host": str(host),
        "initial_states": {
            "A": {"path": str(a), "sha256": dual.hash_file(a)},
            "B": {"path": str(b), "sha256": dual.hash_file(b)},
        },
        "reference": {
            "expected_saved_sha256": {
                "A": sha(oracle.approved(11,22)),
                "B": sha(oracle.approved(33,44))},
            "expected_pcm": {
                "A_first_pcm": 0.25, "A_second_pcm": 0.25,
                "B_first_pcm": 0.125, "B_second_pcm": 0.125},
            "abs_tolerance": 0.000001,
        }
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


def simulate(argv, **kwargs):
    out = Path(argv[-1])
    out.mkdir(parents=True, exist_ok=True)
    (out / "A-after.bin").write_bytes(oracle.approved(11,22))
    (out / "B-after.bin").write_bytes(oracle.approved(33,44))
    (out / "MULTI-INSTANCE.tsv").write_text(
        "format\t125A-DUAL-INSTANCE-v1\n"
        "same_process_instances\t2\nprocess_callbacks\t4\n"
        "A_first_pcm\t0.25\nB_first_pcm\t0.125\n"
        "B_second_pcm\t0.125\nA_second_pcm\t0.25\n",
        encoding="utf-8")
    return subprocess.CompletedProcess(
        argv, 0, "[PASS] two real VST3 instances processed in same host process", "")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    manifest_file, manifest = fixture_files(root)
    out = root / "result"
    passing = dual.run(manifest_file, out, runner=simulate)
    assert passing["status"] == "TECHNICAL_PASS"
    assert passing["saved_state_isolation"] == "PASS"
    assert passing["reference_pcm_isolation"] == "PASS"
    assert passing["release_approved"] is False

    def broken_global(argv, **kwargs):
        result = simulate(argv, **kwargs)
        folder = Path(argv[-1])
        (folder / "A-after.bin").write_bytes(oracle.approved(33,44))
        (folder / "MULTI-INSTANCE.tsv").write_text(
            (folder / "MULTI-INSTANCE.tsv").read_text(encoding="utf-8")
            .replace("A_second_pcm\t0.25","A_second_pcm\t0.125"),
            encoding="utf-8")
        return result

    failed = dual.run(manifest_file, out, runner=broken_global)
    assert failed["status"] == "FAIL"
    assert failed["saved_state_isolation"] == "FAIL"
    assert failed["reference_pcm_isolation"] == "FAIL"

    def fake_success(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 0, "[PASS] two real VST3 instances processed in same host process", "")

    old = dual.run(manifest_file, out, runner=fake_success)
    assert old["status"] == "FAIL", "stale green native state reused"

    mismatch = json.loads(json.dumps(manifest))
    mismatch["reference"]["expected_pcm"]["B_second_pcm"] = 0.5
    manifest_file.write_text(json.dumps(mismatch), encoding="utf-8")
    wrong = dual.run(manifest_file, out, runner=simulate)
    assert wrong["status"] == "FAIL" and wrong["reference_pcm_isolation"] == "FAIL"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    tampered = json.loads(json.dumps(manifest))
    tampered["product"]["sha256"] = "f" * 64
    manifest_file.write_text(json.dumps(tampered), encoding="utf-8")
    assert dual.run(manifest_file, out, runner=simulate)["status"] == "FAIL"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    tampered = json.loads(json.dumps(manifest))
    tampered["initial_states"]["A"]["sha256"] = "f" * 64
    manifest_file.write_text(json.dumps(tampered), encoding="utf-8")
    assert dual.run(manifest_file, out, runner=simulate)["status"] == "FAIL"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    manifest["reference"]["expected_pcm"]["A_first_pcm"] = float("nan")
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    assert dual.run(manifest_file, out, runner=simulate)["status"] == "FAIL"

print("[PASS] external A/B state, PCM and real-plugin identity oracles reject corruption and stale evidence")
