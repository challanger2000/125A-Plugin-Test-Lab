#!/usr/bin/env python3
"""No misleading green UI or unsafe HTML content in human QA summary."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("report", Path(__file__).with_name("write_user_report.py"))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

passed = {
    "status": "TECHNICAL_PASS",
    "product": "<script>alert(1)</script>",
    "verified_module_sha256": "a" * 64,
    "coverage": {
        "api_playback_save": "PASS",
        "sample_rate_buffer_matrix": "PASS",
        "fresh_process_project_recall": "PASS",
        "native_gui_lifecycle": "PASS",
        "product_gui_controls": "NOT COVERED",
        "commercial_daw_integration": "NOT COVERED",
    }
}
page = report.report_html(passed)
assert "Technische Pruefungen bestanden" in page
assert "KEINE PRODUKTFREIGABE" in page
assert "NICHT GEPRUEFT" in page
assert "<script>alert(1)</script>" not in page
assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
assert "Freigabe des Plugins" in page
assert page.count("BESTANDEN") == 4
enriched = dict(passed)
enriched["coverage"] = dict(passed["coverage"])
enriched["coverage"]["same_process_dual_instance_lifecycle"] = "PASS"
enriched["coverage"]["distinct_instance_state_isolation"] = "NOT COVERED"
enriched["coverage"]["externally_referenced_audio"] = "REFERENCE_MATCH"
page = report.report_html(enriched)
assert "Zwei gleichzeitige Plugininstanzen in einem Host" in page
assert "Unabhaengige Bank-/Projektzustaende beider Instanzen" in page
assert "Vergleich mit freigegebener WAV-Referenz" in page
assert page.count("BESTANDEN") == 6, "independent reference falsely displayed untested"
assert "KEINE PRODUKTFREIGABE" in page

deep = dict(enriched)
deep["coverage"] = dict(enriched["coverage"])
deep["coverage"]["distinct_instance_state_isolation"] = "PASS"
deep["coverage"]["reference_pcm_isolation"] = "PASS"
deep["coverage"]["active_playback_state_replay"] = "PASS"
page = report.report_html(deep)
assert "Unabhaengige A/B-Referenzpruefung" in page
assert "500 echte Zustand-Reloads" in page
assert page.count("BESTANDEN") == 9
assert "KEINE PRODUKTFREIGABE" in page

critical = dict(passed)
critical["coverage"] = dict(passed["coverage"])
critical["coverage"]["realtime_deadline_observation"] = "FAIL"
critical["measured_callback_overruns"] = 3
page = report.report_html(critical)
assert "Gemessene Audio-Deadline-Ueberschreitungen" in page
assert "Gemessene Audio-Callback-Deadlines" in page
assert "FEHLER" in page
assert "Technische Pruefung mit Fehlern" in page
assert "Technische Pruefungen bestanden" not in page
assert "kein vollstaendig bestandener Test" in page
assert "KEINE PRODUKTFREIGABE" in page


# A fabricated top-level TECHNICAL_PASS cannot conceal another domain FAIL.
contradictory = dict(passed)
contradictory["coverage"] = dict(passed["coverage"])
contradictory["coverage"]["native_audio_state_capture"] = "FAIL"
page = report.report_html(contradictory)
assert "Technische Pruefung mit Fehlern" in page
assert "Technische Pruefungen bestanden" not in page
assert "FEHLER" in page

bad = {
    "status": "FAIL",
    "product": "Instrument",
    "reason": "<broken> corrupted saves",
    "coverage": {"api_playback_save": "FAIL",
                 "native_audio_state_capture": "PASS"}
}
page = report.report_html(bad)
assert "Technische Pruefung fehlgeschlagen" in page
assert "&lt;broken&gt;" in page
assert "<broken>" not in page
assert "KEINE PRODUKTFREIGABE" in page
assert "FEHLER" in page

invalid = report.report_html({"status": "TECHNICAL_PASS", "coverage": {
    "product_gui_controls": "unknown value", "commercial_daw_integration": "PASS"}})
assert "KEINE PRODUKTFREIGABE" in invalid
assert "NICHT GEPRUEFT" in invalid

assert "KEINE PRODUKTFREIGABE" in report.report_html(
    {"status": "FAIL", "error": "file missing"})
print("[PASS] plain-language result distinguishes technical PASS, failure, missing coverage and release NO-GO")
