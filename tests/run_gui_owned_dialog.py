#!/usr/bin/env python3
"""P60 independently verify real owned Win32 dialog activation and cleanup."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

SCHEMA = "125a-owned-dialog-result-v1"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_native(raw, *, expect_button=False, expect_menu=False,
                    expect_popup=False):
    lines = raw.splitlines()
    if len(lines) < 4 or lines[0] != "format\t125A-OWNED-DIALOG-v1" or lines[-1] != "end\tCOMPLETE":
        raise ValueError("P60 owned-dialog native observation missing or truncated")
    if lines[1] != "baseline\t0" or not lines[2].startswith("after\t"):
        raise ValueError("P60 native dialog baseline or count invalid")
    count = lines[2][6:]
    if not count.isascii() or not count.isdecimal() or str(int(count)) != count:
        raise ValueError("P60 dialog count malformed")
    number = int(count)
    if sum(bool(v) for v in (expect_button, expect_menu, expect_popup)) > 1:
        raise ValueError("P63 requires one independent native UI oracle")
    expected_lines = number + 4 + (1 if expect_button or expect_menu or expect_popup else 0)
    if not 0 <= number <= 15 or len(lines) != expected_lines:
        raise ValueError("P60/P61 missing, duplicated or excessive native dialog records")
    if expect_button and lines[-2] != "button\t43061\tButton\tactioned\tdialog_closed":
        raise ValueError("P61 dialog button not independently observed and dismissed")
    if expect_menu and lines[-2] != "menu\t43062\tApply Preset\tenabled\tcommand_dispatched\tdialog_closed":
        raise ValueError("P62 native HMENU item or command result missing or forged")
    if expect_popup and lines[-2] != (
        "popup\t43064\tActions/Apply Preset\tmouse_input\t"
        "trackpopup_selected\tcommand_handled\tdialog_closed"
    ):
        raise ValueError("P63 real mouse-driven OS popup selection not independently reported")
    dialog_records = lines[3:3 + number]
    for i, line in enumerate(dialog_records):
        if line != f"dialog\t{i}\t#32770\tvisible\towned":
            raise ValueError("P60 dialog class, native ownership or order invalid")
    return number


def run(plugin, host, out, *, x=160, y=90, acknowledge=False,
        timeout=35, runner=subprocess.run, button=False, menu=False,
        popup=False):
    if acknowledge is not True:
        raise ValueError("P60/P61 requires opt-in to real plugin UI click")
    if type(menu) is not bool or type(popup) is not bool or (
            sum(bool(v) for v in (button, menu, popup)) > 1):
        raise ValueError("P63 invalid simultaneous native menu modes")
    if type(button) is not bool:
        raise ValueError("P61 native dialog button mode invalid")
    if type(x) is not int or type(y) is not int or not 0 <= x <= 8191 or not 0 <= y <= 8191:
        raise ValueError("P60 invalid approved GUI click coordinate")
    if type(timeout) is not int or not 5 <= timeout <= 120:
        raise ValueError("P60 invalid bounded native process timeout")
    plugin, host, out = Path(plugin).resolve(strict=True), Path(host).resolve(strict=True), Path(out)
    binary = [v for v in plugin.rglob("*.vst3") if v.is_file()]
    if plugin.suffix.lower() != ".vst3" or len(binary) != 1 or not host.is_file():
        raise ValueError("P60 needs one actual native VST3 DLL and GUI host")
    module_sha, host_sha = digest(binary[0]), digest(host)
    out.mkdir(parents=True, exist_ok=True)
    native = out / "native-owned-dialog.tsv"
    native.unlink(missing_ok=True)
    report_path = out / "OWNED-DIALOG-RESULT.json"
    report_path.unlink(missing_ok=True)
    report = {
        "schema": SCHEMA, "status": "FAIL", "faults": [],
        "verified_module_sha256": module_sha, "verified_host_sha256": host_sha,
        "baseline_owned_dialogs": 0, "observed_owned_dialogs": 0,
        "popup_cleanup": "NOT VERIFIED",
        "native_dialog_button": "NOT TESTED",
        "native_win32_menu": "NOT TESTED",
        "physical_menu_selection": "NOT COVERED",
        "actual_win32_popup_tracking": "NOT TESTED",
        "custom_painted_popups": "NOT COVERED",
        "blocking_modal_file_dialogs": "NOT COVERED",
        "complete_gui_controls": "NOT COVERED",
        "commercial_daw_sessions": "NOT COVERED", "release_approved": False
    }
    try:
        p = runner([str(host), "--select-owned-popup-mouse" if popup
                    else "--audit-owned-dialog-menu" if menu
                    else "--exercise-owned-dialog-button" if button
                    else "--observe-owned-dialog", str(plugin),
                    str(x), str(y), str(native)], capture_output=True,
                   text=True, errors="replace", check=False, timeout=timeout)
        (out / "native.log").write_text(
            (p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8")
        if p.returncode != 0 or not native.is_file():
            raise ValueError("P60 real native editor click or dialog cleanup failed")
        if module_sha != digest(binary[0]) or host_sha != digest(host):
            raise ValueError("P60 native VST3 module or GUI host modified during run")
        count = validate_native(native.read_text(encoding="utf-8"),
                                expect_button=button, expect_menu=menu,
                                expect_popup=popup)
        report["observed_owned_dialogs"] = count
        report["popup_cleanup"] = "NATIVE_HOST_VERIFIED"
        if button:
            report["native_dialog_button"] = "ACTUATED_AND_CLOSED"
        if menu:
            report["native_win32_menu"] = "ITEM_VERIFIED_AND_COMMAND_DISPATCHED"
        if popup:
            report["actual_win32_popup_tracking"] = "MOUSE_SELECTED_OS_MENU"
            report["physical_menu_selection"] = "MOUSE_SELECTED_OS_MENU"
        if count != 1:
            raise ValueError("P60 approved UI click did not open exactly one native owned dialog")
        report["status"] = "CONTRACT_PASS"
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as exc:
        report["faults"].append(str(exc))
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True, type=Path)
    parser.add_argument("--gui-host", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--x", type=int, default=160)
    parser.add_argument("--y", type=int, default=90)
    parser.add_argument("--acknowledge-ui-clicks", action="store_true")
    parser.add_argument("--exercise-dialog-button", action="store_true")
    parser.add_argument("--audit-native-menu", action="store_true")
    parser.add_argument("--select-popup-mouse", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.plugin, args.gui_host, args.out, x=args.x, y=args.y,
                     acknowledge=args.acknowledge_ui_clicks,
                     button=args.exercise_dialog_button,
                     menu=args.audit_native_menu,
                     popup=args.select_popup_mouse)
    except (OSError, ValueError, TypeError) as exc:
        args.out.mkdir(parents=True, exist_ok=True)
        result = {"schema": SCHEMA, "status": "FAIL",
                  "faults": [str(exc)], "release_approved": False}
        (args.out / "OWNED-DIALOG-RESULT.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "CONTRACT_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
