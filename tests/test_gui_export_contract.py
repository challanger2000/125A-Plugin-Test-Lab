#!/usr/bin/env python3
"""P46: adversarial contract proof independent from VST3 GUI screenshots."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location(
    "export_contract", Path(__file__).with_name("run_gui_export_contract.py"))
x = importlib.util.module_from_spec(spec)
spec.loader.exec_module(x)

GOLDEN_HASH = "3c548b8ac23f3be44063b4afce2609137a6e274e409af17f2397f0c95172741b"
SAMPLES = (0, 1000, -1000, 32767, -32768, 4321, -4321, 0,
           256, -256, 8192, -8192, 123, -123, 1, -1)


def independent_wav():
    samples = struct.pack("<16h", *SAMPLES)
    assert len(samples) == 32
    return (
        b"RIFF" + struct.pack("<I", 68) + b"WAVE" +
        b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 44100, 88200, 2, 16) +
        b"data" + struct.pack("<I", 32) + samples)


assert hashlib.sha256(independent_wav()).hexdigest() == GOLDEN_HASH
# Independently hand-declared musical MIDI notes: 60 at t=0 on, t=96 off.
MIDI = (
    b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) +
    b"MTrk" + struct.pack(">I", 12) +
    b"\x00\x90\x3c\x64\x60\x80\x3c\x00\x00\xff\x2f\x00")
assert x.midi_evidence(MIDI) == {
    "format": 0, "tracks": 1, "ticks_per_quarter": 96, "note_on_count": 1}
for corrupt in (
        MIDI[:-1], MIDI[:-4], MIDI + b"\x00",
        MIDI.replace(b"MTrk", b"BAD!"), MIDI.replace(b"\x90", b"\xF1")):
    try:
        x.midi_evidence(corrupt)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed MIDI SMF escaped independent validator")


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    binary = root / "Good.vst3" / "Contents" / "x86_64-win" / "Good.vst3"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"source-built VST3 plugin content")
    gui_host = root / "GUI.exe"
    gui_host.write_bytes(b"native Windows VST3 GUI test host identity")
    workflow = {
        "schema": "125a-gui-workflow-v1",
        "product": {
            "binary": str(binary), "sha256": x.digest(binary)},
        "gui_host": str(gui_host),
        "initial": [{"param_id": 9001, "normalized": 0.0}],
        "steps": [{
            "id": "export_wav",
            "action": "click", "x": 160, "y": 90,
            "param_id": 9001, "before_normalized": 0.0,
            "expected_normalized": 1.0,
        }]
    }
    contract = {
        "schema": x.SCHEMA,
        "workflow": workflow,
        "expected_exports": [{
            "filename": "gui-export.wav", "type": "wav",
            "sha256": GOLDEN_HASH, "channels": 1,
            "sample_rate": 44100, "sample_width_bits": 16,
            "frames": 16,
        }]
    }
    x.validate(contract)
    failures = []
    def invalid(mutator):
        clone = json.loads(json.dumps(contract))
        mutator(clone)
        try:
            x.validate(clone)
        except (ValueError, KeyError, TypeError):
            return
        raise AssertionError("invalid GUI export oracle was accepted")
    invalid(lambda q: q["expected_exports"][0].update({"sha256": "f" * 63}))
    invalid(lambda q: q["expected_exports"][0].update({"filename": "../stolen.wav"}))
    invalid(lambda q: q["expected_exports"][0].update({"filename": "x/y.wav"}))
    invalid(lambda q: q["expected_exports"][0].update({"frames": -1}))
    invalid(lambda q: q["expected_exports"][0].update({"channels": "1"}))
    invalid(lambda q: q["expected_exports"][0].update({"sample_rate": 0}))
    invalid(lambda q: q["expected_exports"][0].update({"type": "unsupported"}))
    invalid(lambda q: q["expected_exports"].append(q["expected_exports"][0]))
    invalid(lambda q: q["workflow"]["product"].update({"sha256": "0" * 64}))

    mode = {"case": "good"}
    def fake_native(cmd, **kwargs):
        assert cmd[1] == "--gui-workflow", cmd
        exported = Path(kwargs["env"]["QA_TEST_LAB_EXPORT_ROOT"])
        assert exported.is_dir() and not list(exported.iterdir())
        target = exported / "gui-export.wav"
        case = mode["case"]
        if case != "missing":
            data = bytearray(independent_wav())
            if case == "wrong_pcm":
                data[51] ^= 1
            if case == "truncated_wav":
                data = data[:-8]
            target.write_bytes(data)
        if case == "extra":
            (exported / "unexpected.mid").write_bytes(MIDI)
        native = Path(cmd[4])
        native.write_text(
            "format\t125A-GUI-WORKFLOW-RESULT-v1\n"
            "step_count\t1\n"
            "step\t0\t9001\t0\t1\tPASS\n"
            "end\tPASS\n", encoding="utf-8")
        if case == "false_gui":
            native.write_text(native.read_text(encoding="utf-8").replace(
                "\t0\t1\tPASS", "\t0\t0\tPASS"), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "[PASS] real native action", "")

    out = root / "results"
    for case in ("good", "wrong_pcm", "truncated_wav", "missing",
                 "extra", "false_gui"):
        mode["case"] = case
        result = x.run(contract, out, runner=fake_native)
        expected = "CONTRACT_PASS" if case == "good" else "FAIL"
        assert result["status"] == expected, (case, result)
        assert result["release_approved"] is False, case
        assert result["unmapped_gui_controls"] == "NOT COVERED", case
        if case == "good":
            assert result["verified_export_count"] == 1, result
            assert result["approved_independent_file_oracles"] == "PASS"
            assert result["verified_exports"]["gui-export.wav"]["sha256"] == GOLDEN_HASH
        else:
            assert result["approved_independent_file_oracles"] == "FAIL", result

    # A valid real file is still insufficient with a forged independent oracle.
    broken_reference = json.loads(json.dumps(contract))
    broken_reference["expected_exports"][0]["sha256"] = "a" * 64
    mode["case"] = "good"
    assert x.run(broken_reference, out, runner=fake_native)["status"] == "FAIL"

    # A MIDI file must satisfy its own independent SMF oracle, not WAV rules.
    midi_dir = root / "midi"
    midi_dir.mkdir()
    (midi_dir / "groove.mid").write_bytes(MIDI)
    midi_item = {
        "filename": "groove.mid", "type": "midi",
        "sha256": hashlib.sha256(MIDI).hexdigest(),
        "format": 0, "tracks": 1, "ticks_per_quarter": 96,
        "note_on_count": 1}
    midi_contract = dict(contract, expected_exports=[midi_item])
    x.validate(midi_contract)
    assert x.audit_outputs(midi_dir, [midi_item])["groove.mid"][
        "metadata"]["note_on_count"] == 1
    midi_item_bad = dict(midi_item, note_on_count=2)
    try:
        x.audit_outputs(midi_dir, [midi_item_bad])
    except ValueError:
        pass
    else:
        raise AssertionError("MIDI golden note count mismatch passed")

print("[PASS] P46 real GUI-to-WAV/MIDI semantic contracts reject wrong PCM, missing/extra exports and false GUI PASS")
