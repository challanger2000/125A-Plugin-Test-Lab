#!/usr/bin/env python3
"""P72 integrated, zero-click VST3 onboarding: ABI + GUI + owner handoff.

A single command collects independent P68/P71 native evidence, checks
current product and host SHA-256 and generates an honest non-executable
review pack for the plugin-owning chat. No per-plugin Test Lab edits.
"""
import argparse
import json
from pathlib import Path

from run_vst3_auto_discovery import discover as abi_discover, verify_bundle, digest
from run_gui_unified_discovery import run as gui_discover
from run_plugin_quickcheck import run as technical_run

SCHEMA = "125a-plugin-onboarding-v1"


def combine(abi, gui, draft, module_sha, host_sha):
    if (not isinstance(abi, dict) or not isinstance(gui, dict)
            or not isinstance(draft, dict)
            or abi.get("schema") != "125a-vst3-discovery-v1"
            or abi.get("status") != "DISCOVERY_COMPLETE"
            or type(abi.get("reported_editor_available")) is not bool
            or abi.get("verified_module_sha256") != module_sha
            or abi.get("verified_gui_host_sha256") != host_sha
            or abi.get("release_approved") is not False
            or draft.get("schema") != "125a-vst3-test-plan-draft-v1"
            or draft.get("product", {}).get("sha256") != module_sha
            or draft.get("hosts", {}).get("gui", {}).get("sha256") != host_sha
            or draft.get("executable_p65_plan") is not False
            or draft.get("required_feature_inventory") != "NOT DECLARED"
            or draft.get("release_approved") is not False):
        raise ValueError("P72 current and consistent read-only native evidence required")
    exposed_editor = abi["reported_editor_available"]
    if exposed_editor:
        if (not isinstance(gui, dict)
                or gui.get("schema") != "125a-unified-gui-discovery-v1"
                or gui.get("status") != "CANDIDATES_COMPLETE"
                or gui.get("mode") != "READ_ONLY"
                or gui.get("click_observation") != "NOT RUN"
                or gui.get("verified_module_sha256") != module_sha
                or gui.get("verified_gui_host_sha256") != host_sha
                or gui.get("release_approved") is not False):
            raise ValueError("P73 editor advertised but GUI observation absent or forged")
        candidates = gui.get("proposed_candidates")
    else:
        if gui is not None:
            raise ValueError("P73 headless plugin cannot claim GUI control observations")
        candidates = []
    if not isinstance(candidates, list) or len(candidates) > 16:
        raise ValueError("P72 impossible or missing GUI candidate list")
    seen = set()
    for c in candidates:
        if (not isinstance(c, dict) or c.get("source") not in
                {"NATIVE_HWND","PAINTED_VISUAL_REGION"} or
                c.get("approved_to_click") is not False or
                c.get("semantics") != "UNKNOWN" or
                type(c.get("x")) is not int or type(c.get("y")) is not int
                or not 0 <= c["x"] < 4096 or not 0 <= c["y"] < 4096
                or (c["x"], c["y"]) in seen):
            raise ValueError("P72 untrusted GUI candidate in owner handoff")
        seen.add((c["x"],c["y"]))
    # This is an owner-facing task list, NOT a P65 runnable contract.
    tasks = [
        {"id": "review_feature_inventory",
         "status": "OWNER REVIEW REQUIRED",
         "note": "List all required functions not exposed by VST3 ABI; never infer completeness"},
        {"id": "confirm_expected_parameter_behavior",
         "status": "OWNER REVIEW REQUIRED",
         "note": "Provide independent expected values for actual controls"},
        {"id": "review_visual_gui_candidates",
         "status": "OWNER REVIEW REQUIRED" if exposed_editor else "NOT APPLICABLE",
         "note": ("Confirm that each proposed click is safe, correctly mapped and not destructive"
                  if exposed_editor else "VST3 declares no editor; no GUI controls were probed")},
        {"id": "provide_test_reference_assets",
         "status": "OWNER REVIEW REQUIRED",
         "note": "Provide independently verifiable musical/export/PCM results if applicable"},
        {"id": "prepare_p65_p66_test_plan_and_p67_matrix",
         "status": "OWNER REVIEW REQUIRED",
         "note": "Only approved complete cases may run; missing mandatory features remain NOT COVERED"}
    ]
    return {
        "schema": SCHEMA, "status": "REVIEW_PACK_COMPLETE",
        "product": draft["product"],
        "verified_module_sha256": module_sha,
        "verified_gui_host_sha256": host_sha,
        "discovered_parameter_count": abi.get("parameter_count"),
        "discovered_bus_count": abi.get("bus_count"),
        "gui_editor_status": ("EDITOR_OBSERVED" if exposed_editor
                              else "VST3_NO_EDITOR_EXPOSED"),
        "native_gui_candidates": gui.get("native_candidates") if exposed_editor else 0,
        "painted_gui_candidates": gui.get("painted_candidates") if exposed_editor else 0,
        "reviewable_gui_click_coordinates": candidates,
        "proposed_technical_cases": draft.get("proposed_cases", []),
        "owner_tasks": tasks,
        "clicks_performed": 0, "automatically_approved_expectations": 0,
        "executable_p65_plan": False, "required_feature_coverage": "NOT DECLARED",
        "full_product_functional_coverage": "NOT COVERED",
        "real_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False
    }


def run(bundle, gui_host, out, *, max_points=9, timeout=40,
        audio_host=None, stress_host=None, run_technical=False,
        inventory=abi_discover, gui=gui_discover, technical=technical_run):
    bundle, dll = verify_bundle(bundle)
    gui_host = Path(gui_host).resolve(strict=True)
    if not gui_host.is_file():
        raise ValueError("P72 native Windows GUI host missing")
    if type(timeout) is not int or not 5 <= timeout <= 90:
        raise ValueError("P72 invalid bounded timeout")
    if type(max_points) is not int or not 1 <= max_points <= 16:
        raise ValueError("P72 invalid candidate budget")
    if type(run_technical) is not bool:
        raise ValueError("P73 explicit technical opt-in must be boolean")
    if run_technical and (audio_host is None or stress_host is None):
        raise ValueError("P73 automatic technical VST3 test requires real audio and stress hosts")
    dll_sha, host_sha = digest(dll), digest(gui_host)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result_file = out / "PLUGIN-ONBOARDING-RESULT.json"
    result_file.unlink(missing_ok=True)
    result = {
        "schema": SCHEMA, "status": "FAIL",
        "verified_module_sha256": dll_sha,
        "verified_gui_host_sha256": host_sha,
        "clicks_performed": 0, "release_approved": False,
        "faults": []
    }
    try:
        abi = inventory(bundle, gui_host, out / "vst3-inventory",
                        audio_host=audio_host, stress_host=stress_host,
                        timeout=timeout)
        if abi.get("status") != "DISCOVERY_COMPLETE":
            raise ValueError("P72 native VST3 interface inventory incomplete")
        if type(abi.get("reported_editor_available")) is not bool:
            raise ValueError("P73 native VST3 does not provide reliable GUI availability")
        observed = None
        if abi["reported_editor_available"]:
            observed = gui(bundle, gui_host, out / "gui-inventory",
                           acknowledge=False, max_points=max_points, timeout=timeout)
            if observed.get("status") != "CANDIDATES_COMPLETE":
                raise ValueError("P72 combined GUI inspection incomplete")
        draft_path = out / "vst3-inventory" / "PROPOSED-TEST-PLAN.json"
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        result = combine(abi, observed, draft, dll_sha, host_sha)
        result["native_technical_status"] = "NOT RUN"
        result["native_technical_verified_coverage"] = []
        if run_technical:
            audio = Path(audio_host).resolve(strict=True)
            stress = Path(stress_host).resolve(strict=True)
            if not audio.is_file() or not stress.is_file():
                raise ValueError("P73 native technical host missing")
            audio_sha, stress_sha = digest(audio), digest(stress)
            observed_technical = technical(
                bundle, audio, stress, out / "technical-baseline",
                timeout=min(120, max(timeout, 35)))
            if (not isinstance(observed_technical, dict)
                    or observed_technical.get("schema") != "125a-quickcheck-result-v1"
                    or observed_technical.get("verified_module_sha256") != dll_sha
                    or observed_technical.get("release_approved") is not False
                    or not isinstance(observed_technical.get("coverage"), dict)
                    or observed_technical["coverage"].get("physical_asio_hardware") != "NOT RUN"
                    or observed_technical["coverage"].get("real_commercial_daw_session") != "NOT RUN"
                    or digest(audio) != audio_sha or digest(stress) != stress_sha):
                raise ValueError("P73 invalid independent native audio/save evidence")
            baseline = ("api_playback_save", "sample_rate_buffer_matrix",
                        "native_audio_state_capture")
            result["native_technical_verified_coverage"] = [
                name for name in baseline
                if observed_technical["coverage"].get(name) == "PASS"]
            result["native_technical_status"] = (
                "TECHNICAL_PASS" if observed_technical.get("status") == "TECHNICAL_PASS"
                and len(result["native_technical_verified_coverage"]) == len(baseline)
                else "FAIL")
            if result["native_technical_status"] != "TECHNICAL_PASS":
                raise ValueError("P73 existing native technical host found real plugin regression")
        if digest(dll) != dll_sha or digest(gui_host) != host_sha:
            raise ValueError("P72 module/host modified during read-only onboarding")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        result = {"schema": SCHEMA, "status": "FAIL",
                  "verified_module_sha256": dll_sha,
                  "verified_gui_host_sha256": host_sha,
                  "clicks_performed": 0, "release_approved": False,
                  "faults": [str(exc)]}
    result_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", required=True, type=Path)
    p.add_argument("--gui-host", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--audio-host", type=Path)
    p.add_argument("--stress-host", type=Path)
    p.add_argument("--run-technical-baseline", action="store_true",
                   help="Opt-in real VST3 native audio, save/recall and sample-rate tests")
    p.add_argument("--max-points", type=int, default=9)
    p.add_argument("--timeout", type=int, default=40)
    a = p.parse_args()
    try:
        result = run(a.plugin, a.gui_host, a.out, audio_host=a.audio_host,
                     stress_host=a.stress_host,
                     max_points=a.max_points, timeout=a.timeout,
                     run_technical=a.run_technical_baseline)
    except (OSError, ValueError, TypeError) as exc:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL",
                  "clicks_performed": 0, "release_approved": False,
                  "faults": [str(exc)]}
        (a.out / "PLUGIN-ONBOARDING-RESULT.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "REVIEW_PACK_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
