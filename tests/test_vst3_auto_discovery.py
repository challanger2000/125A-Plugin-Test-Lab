#!/usr/bin/env python3
"""P68 adversarial native read-only discovery and no-guessed-oracles tests."""
import json
import tempfile
from pathlib import Path
import unittest
from run_vst3_auto_discovery import (
    parse_capabilities, parse_parameters, build_draft, discover, digest)


def capability(param_count=2, buses=None, *, editor=1):
    if buses is None:
        buses = ["bus\t0\t1\t0\t2\t0\t0",
                 "bus\t1\t0\t0\t1\t0\t0"]
    return "\n".join([
        "format\t125A-VST3-CAPABILITIES-v1",
        "audio_classes\t1", f"parameter_count\t{param_count}",
        f"editable_parameters\t{param_count}",
        "readonly_parameters\t0", "bypass_parameters\t0",
        "program_parameters\t0", f"editor_available\t{editor}",
        f"editor_win32_hwnd\t{editor}", f"bus_count\t{len(buses)}",
        *buses, "end\tCOMPLETE", ""])


def parameters(param_count=2):
    rows = ["format\t125A-GUI-PARAMS-v1",
            f"param_count\t{param_count}"]
    for idx in range(param_count):
        rows.append(f"param\t{idx}\t{9001 + idx}\t0\t0.5\t0.5\t1")
    return "\n".join(rows) + "\n"


class ReadOnlyDiscoveryTests(unittest.TestCase):
    def test_genuine_metadata_and_parameter_roundtrip(self):
        caps = parse_capabilities(capability())
        self.assertEqual(caps["parameter_count"], 2)
        self.assertEqual(caps["buses"][0]["media"], "audio")
        self.assertEqual(caps["buses"][1]["media"], "event")
        rows = parse_parameters(parameters(), caps["parameter_count"])
        self.assertEqual([p["param_id"] for p in rows], [9001, 9002])
        self.assertEqual(rows[0]["semantic_meaning"], "NOT DISCOVERED")

    def test_fake_or_ambiguous_native_evidence_fails(self):
        bad = [
            capability().replace("audio_classes\t1", "audio_classes\t2"),
            capability().replace("parameter_count\t2", "parameter_count\t3"),
            capability().replace("bus_count\t2", "bus_count\t1"),
            capability().replace("end\tCOMPLETE", "end\tNOT_DONE"),
            capability().replace("editable_parameters\t2", "editable_parameters\t1"),
            capability().replace("editor_win32_hwnd\t1", "editor_win32_hwnd\t2"),
            capability().replace("bus\t1\t0\t0\t1\t0\t0",
                                 "bus\t0\t1\t0\t2\t0\t0"),
            capability().replace("parameter_count\t2", "parameter_count\t02"),
            capability() + "unexpected\n",
        ]
        for item in bad:
            with self.subTest(text=item[-100:]), self.assertRaises(ValueError):
                parse_capabilities(item)
        for item in [
            parameters().replace("9002", "9001"),
            parameters().replace("param\t1", "param\t0"),
            parameters().replace("0.5\t0.5", "nan\t0.5"),
            parameters().replace("param_count\t2", "param_count\t0"),
            parameters()[:-12],
        ]:
            with self.subTest(text=item[-80:]), self.assertRaises(ValueError):
                parse_parameters(item, 2)

    def test_unapproved_draft_never_invents_gui_or_audio_oracles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dll = root / "Synth.vst3" / "Contents" / "x86_64-win" / "Synth.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"module")
            host = root / "native.exe"
            host.write_bytes(b"host")
            draft = build_draft(dll.parents[2], dll, host,
                                parse_capabilities(capability()),
                                parse_parameters(parameters(), 2), {})
            self.assertFalse(draft["executable_p65_plan"])
            self.assertFalse(draft["release_approved"])
            self.assertEqual(draft["musical_oracles"], "NOT DISCOVERED")
            self.assertEqual(draft["inventory_summary"]["event_inputs"], 1)
            self.assertTrue(any(p["approval"].startswith("REQUIRES")
                                for p in draft["proposed_cases"]))
            self.assertFalse(any("expected_normalized" in json.dumps(p)
                                 for p in draft["proposed_cases"]))

    def test_native_wrapper_real_files_and_wrong_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dll = root / "Fixture.vst3" / "Contents" / "x86_64-win" / "Fixture.vst3"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"actual-module")
            host = root / "gui.exe"
            host.write_bytes(b"host")
            class Done:
                returncode = 0
                stdout = "native-verified"
                stderr = ""
            calls = []
            def runner(command, **kwargs):
                calls.append(command[1])
                Path(command[3]).write_text(
                    capability() if command[1] == "--inventory-capabilities"
                    else parameters(), encoding="utf-8")
                return Done()
            result = discover(dll.parents[2], host, root / "success", runner=runner)
            self.assertEqual(result["status"], "DISCOVERY_COMPLETE")
            self.assertEqual(calls, ["--inventory-capabilities", "--inventory-parameters"])
            self.assertEqual(result["verified_module_sha256"], digest(dll))
            draft = json.loads((root / "success" / "PROPOSED-TEST-PLAN.json").read_text())
            self.assertFalse(draft["executable_p65_plan"])
            def corrupt(command, **kwargs):
                response = runner(command, **kwargs)
                if command[1] == "--inventory-parameters":
                    dll.write_bytes(b"replaced-after-probe")
                return response
            bad = discover(dll.parents[2], host, root / "corrupt", runner=corrupt)
            self.assertEqual(bad["status"], "FAIL")
            self.assertFalse((root / "corrupt" / "PROPOSED-TEST-PLAN.json").exists())
            self.assertFalse(bad["release_approved"])


if __name__ == "__main__":
    unittest.main()
