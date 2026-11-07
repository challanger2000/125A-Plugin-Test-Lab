#!/usr/bin/env python3
"""P74 universal end-to-end VST3 QA: discover -> optional technical -> approved plan.

Default is read-only. Product test execution is opt-in and requires an
independently reviewed P67 feature matrix, exact binary/host identity and
native source-built evidence. Never claims unsupplied musical oracles,
hardware ASIO, commercial DAW verification or release readiness.
"""
import argparse
import json
from pathlib import Path

from run_vst3_auto_discovery import verify_bundle, digest
from run_plugin_onboarding import run as onboarding_run
from run_gui_exploration import run as exploration_run, parse_points
from run_product_test_plan import execute as contract_execute, validate as validate_contract
from product_feature_coverage import validate_matrix

SCHEMA = "125a-universal-vst3-qa-pipeline-v1"


def preflight(plan, matrix, module, gui, audio=None, stress=None):
    if (plan is None) != (matrix is None):
        raise ValueError("P74 approved product plan and feature matrix must be supplied together")
    if plan is None:
        return None
    actual, hosts, cases = validate_contract(plan)
    if (actual != Path(module).resolve(strict=True) or
            hosts["gui"] != Path(gui).resolve()):
        raise ValueError("P74 approved test plan references a different plugin or GUI host")
    for key, wanted in (("audio", audio), ("stress", stress)):
        if key in hosts and (wanted is None or hosts[key] != wanted):
            raise ValueError("P74 product contract uses unapproved audio/stress test host")
    if plan["product"]["sha256"] != digest(module):
        raise ValueError("P74 product bytes have changed")
    validate_matrix(matrix, plan)
    return cases


def execute(plugin, gui_host, out, *, audio_host=None, stress_host=None,
            run_technical=False, plan=None, matrix=None, timeout=90,
            onboarding=onboarding_run, product_runner=contract_execute,
            explore_unknown_gui=False, exploration_points=None, exploration_max_points=4,
            explorer=exploration_run):
    bundle, dll = verify_bundle(plugin)
    gui = Path(gui_host).resolve(strict=True)
    if not gui.is_file():
        raise ValueError("P74 actual native GUI test host required")
    if type(timeout) is not int or not 5 <= timeout <= 120:
        raise ValueError("P74 timeout must be 5..120 seconds")
    if type(explore_unknown_gui) is not bool:
        raise ValueError("P82 unknown GUI probing opt-in must be explicit boolean")
    if type(exploration_max_points) is not int or not 1 <= exploration_max_points <= 16:
        raise ValueError("P82 bounded GUI probe count must be 1..16")
    if exploration_points is not None and (
            not explore_unknown_gui or type(exploration_points) is not str):
        raise ValueError("P82 explicit coordinates require opt-in")
    if type(run_technical) is not bool:
        raise ValueError("P74 explicit technical-test option must be a boolean")
    if (audio_host is None) != (stress_host is None):
        raise ValueError("P74 both real audio and state-stress hosts required together")
    audio = Path(audio_host).resolve(strict=True) if audio_host else None
    stress = Path(stress_host).resolve(strict=True) if stress_host else None
    if audio is not None and (not audio.is_file() or not stress.is_file()):
        raise ValueError("P74 native audio/state-stress test hosts absent")
    if run_technical and audio is None:
        raise ValueError("P74 native technical tests require both native hosts")
    hashes = {dll: digest(dll), gui: digest(gui)}
    if audio is not None:
        hashes[audio] = digest(audio)
        hashes[stress] = digest(stress)
    # Fail the entire plan before any optional real GUI clicks or DSP rendering.
    preflight(plan, matrix, dll, gui, audio, stress)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "UNIVERSAL-QA-RESULT.json"
    target.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA,
        "status": "FAIL",
        "verified_module_sha256": hashes[dll],
        "verified_gui_host_sha256": hashes[gui],
        "discovery": "NOT RUN",
        "native_technical": "NOT RUN",
        "approved_product_cases": "NOT DECLARED",
        "required_feature_coverage": "NOT DECLARED",
        "required_feature_gaps": [],
        "gui_clicks_automatically_authorized": 0,
        "unknown_gui_exploration": "NOT RUN",
        "exploratory_clicks_performed": 0,
        "exploratory_candidates_observed": 0,
        "unknown_gui_semantics": "NOT ESTABLISHED",
        "all_product_features_automatically_discovered": False,
        "real_asio_hardware": "NOT RUN",
        "commercial_daw_session": "NOT RUN",
        "release_approved": False,
        "faults": []
    }
    try:
        onboarding_result = onboarding(
            bundle, gui, out / "discovery",
            audio_host=audio, stress_host=stress,
            run_technical=run_technical,
            timeout=timeout)
        if (not isinstance(onboarding_result, dict)
                or onboarding_result.get("schema") != "125a-plugin-onboarding-v1"
                or onboarding_result.get("status") != "REVIEW_PACK_COMPLETE"
                or onboarding_result.get("verified_module_sha256") != hashes[dll]
                or onboarding_result.get("verified_gui_host_sha256") != hashes[gui]
                or onboarding_result.get("release_approved") is not False
                or onboarding_result.get("clicks_performed") != 0
                or onboarding_result.get("executable_p65_plan") is not False
                or onboarding_result.get("required_feature_coverage") != "NOT DECLARED"):
            raise ValueError("P74 source VST3/GUI automatic discovery incomplete or misattributed")
        report["discovery"] = "PASS"
        if explore_unknown_gui:
            if onboarding_result.get("gui_editor_status") == "VST3_NO_EDITOR_EXPOSED":
                report["unknown_gui_exploration"] = "NOT APPLICABLE - NO EDITOR"
            elif onboarding_result.get("gui_editor_status") == "EDITOR_OBSERVED":
                # Prefer discovered native/painted candidate centers; grid is a
                # documented fallback. A candidate is NOT authorized as a
                # product-function test; this is explicitly opted-in probing.
                coordinates = exploration_points
                if coordinates is None:
                    raw = onboarding_result.get("reviewable_gui_click_coordinates")
                    if not isinstance(raw, list) or len(raw) > 16:
                        raise ValueError("P82 untrusted read-only candidate coordinate inventory")
                    candidate_points = []
                    for item in raw[:exploration_max_points]:
                        if (not isinstance(item, dict) or
                                item.get("approved_to_click") is not False or
                                type(item.get("x")) is not int or
                                type(item.get("y")) is not int or
                                not 0 <= item["x"] <= 4095 or
                                not 0 <= item["y"] <= 4095):
                            raise ValueError("P82 malformed unapproved GUI candidate")
                        point = "%d,%d" % (item["x"], item["y"])
                        if point not in candidate_points:
                            candidate_points.append(point)
                    if candidate_points:
                        coordinates = ";".join(candidate_points)
                observed = explorer(
                    bundle, gui, out / "unknown-gui-probes",
                    acknowledge=True,
                    points=coordinates,
                    max_points=exploration_max_points,
                    timeout=min(timeout, 35))
                expected_count = (len(coordinates.split(";")) if coordinates is not None
                                  else exploration_max_points)
                if (not isinstance(observed, dict)
                        or observed.get("schema") != "125a-gui-exploration-result-v1"
                        or observed.get("status") != "OBSERVATIONS_COMPLETE"
                        or observed.get("verified_module_sha256") != hashes[dll]
                        or observed.get("verified_gui_host_sha256") != hashes[gui]
                        or observed.get("requested_points") != expected_count
                        or observed.get("completed_points") != expected_count
                        or observed.get("sham_verified_points") != expected_count
                        or observed.get("sham_control") != "COMPLETE"
                        or observed.get("gui_control_discovery") != "OBSERVATIONS_ONLY"
                        or observed.get("product_gui_controls") != "NOT COVERED"
                        or observed.get("release_approved") is not False
                        or not isinstance(observed.get("candidates"), list)
                        or len(observed["candidates"]) > expected_count):
                    raise ValueError("P82 unknown VST3 GUI probe lacks complete sham-controlled evidence")
                report["unknown_gui_exploration"] = "OBSERVATIONS_COMPLETE"
                report["exploratory_clicks_performed"] = expected_count
                report["exploratory_candidates_observed"] = len(observed["candidates"])
                report["unknown_gui_semantics"] = "UNAPPROVED OBSERVATIONS ONLY"
            else:
                raise ValueError("P82 GUI editor availability not reliably established")
        if run_technical:
            if (onboarding_result.get("native_technical_status") != "TECHNICAL_PASS"
                    or set(onboarding_result.get("native_technical_verified_coverage", []))
                    != {"api_playback_save", "sample_rate_buffer_matrix",
                        "native_audio_state_capture"}):
                raise ValueError("P74 native audio/state technical baseline incomplete")
            report["native_technical"] = "PASS"
        if any(digest(path) != hashed for path, hashed in hashes.items()):
            raise ValueError("P74 verified binaries modified during discovery")
        if plan is not None:
            # The product case runner executes only independently approved
            # fixture coordinates and expected values, with P67 gate on.
            verified = product_runner(
                plan, out / "approved-cases",
                coverage_matrix=matrix, timeout=timeout)
            if (not isinstance(verified, dict)
                    or verified.get("schema") != "125a-product-test-plan-result-v1"
                    or verified.get("verified_module_sha256") != hashes[dll]
                    or verified.get("release_approved") is not False):
                raise ValueError("P74 foreign or counterfeit approved test-plan report")
            report["approved_product_cases"] = verified.get("status", "FAIL")
            report["required_feature_coverage"] = verified.get(
                "required_feature_coverage", "INVALID OR NOT DECLARED")
            report["required_feature_gaps"] = verified.get(
                "required_feature_gaps", [])
            if (verified.get("status") != "CONTRACT_PASS" or
                    verified.get("required_feature_coverage") !=
                    "REQUIRED_COVERAGE_COMPLETE" or
                    type(verified.get("declared_cases")) is not int or
                    verified.get("declared_cases") < 1 or
                    verified.get("passed_cases") != verified["declared_cases"] or
                    verified.get("failed_cases") != 0 or
                    verified.get("not_run_cases") != 0):
                raise ValueError("P74 approved native product cases or P67 features incomplete")
        if any(digest(path) != hashed for path, hashed in hashes.items()):
            raise ValueError("P74 executable/module bytes changed during test pipeline")
        report["status"] = (
            "DECLARED_COVERAGE_PASS" if plan is not None
            else "TECHNICAL_BASELINE_PASS" if run_technical
            else "INVENTORY_COMPLETE"
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["faults"].append(str(error))
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--gui-host", type=Path, required=True)
    p.add_argument("--audio-host", type=Path)
    p.add_argument("--stress-host", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--run-technical-baseline", action="store_true")
    p.add_argument("--explore-unknown-gui", action="store_true",
                   help="Explicitly opt in to risky, bounded exploratory clicks on unknown controls")
    p.add_argument("--exploration-points", type=str,
                   help="Optional semicolon-separated approved test-environment probe coordinates")
    p.add_argument("--exploration-max-points", type=int, default=4)
    p.add_argument("--approved-plan", type=Path)
    p.add_argument("--feature-matrix", type=Path)
    p.add_argument("--timeout", type=int, default=90)
    a = p.parse_args()
    try:
        plan = (json.loads(a.approved_plan.read_text(encoding="utf-8"))
                if a.approved_plan is not None else None)
        matrix = (json.loads(a.feature_matrix.read_text(encoding="utf-8"))
                  if a.feature_matrix is not None else None)
        result = execute(
            a.plugin, a.gui_host, a.out, audio_host=a.audio_host,
            stress_host=a.stress_host,
            run_technical=a.run_technical_baseline,
            plan=plan, matrix=matrix, timeout=a.timeout,
            explore_unknown_gui=a.explore_unknown_gui,
            exploration_points=a.exploration_points,
            exploration_max_points=a.exploration_max_points)
    except (OSError, ValueError, TypeError, KeyError,
            json.JSONDecodeError) as error:
        a.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL",
                  "faults": [str(error)],
                  "release_approved": False,
                  "real_asio_hardware": "NOT RUN",
                  "commercial_daw_session": "NOT RUN"}
        (a.out / "UNIVERSAL-QA-RESULT.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in (
        "INVENTORY_COMPLETE", "TECHNICAL_BASELINE_PASS",
        "DECLARED_COVERAGE_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
