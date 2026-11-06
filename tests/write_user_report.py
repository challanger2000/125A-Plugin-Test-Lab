#!/usr/bin/env python3
"""Human-readable native VST3 test verdict, without fake product certification.

Renders only findings present in the current JSON output. Always spells out
which user workflows are NOT COVERED and that product release is not approved.
"""
import argparse
import html
import json
from pathlib import Path
import sys


LABELS = {
    "api_playback_save": "Audioverarbeitung und Speichern waehrend der Wiedergabe",
    "realtime_deadline_observation": "Gemessene Audio-Callback-Deadlines",
    "sample_rate_buffer_matrix": "44,1 / 48 / 96 kHz mit 64 / 512 Samples",
    "native_audio_state_capture": "Native Audio- und Projektzustandsaufzeichnung",
    "fresh_process_project_recall": "Projektzustand in zwei neuen Hostprozessen laden",
    "same_process_dual_instance_lifecycle": "Zwei gleichzeitige Plugininstanzen in einem Host",
    "distinct_instance_state_isolation": "Unabhaengige Bank-/Projektzustaende beider Instanzen",
    "reference_pcm_isolation": "Unabhaengige A/B-Referenzpruefung von vier PCM-Beobachtungen",
    "active_playback_state_replay": "500 echte Zustand-Reloads parallel zur Wiedergabe je Konfiguration",
    "recall_audio_determinism": "Samplegenauer Vergleich nach Neuladen",
    "native_gui_lifecycle": "Pluginfenster oeffnen und erneut oeffnen",
    "native_parameter_inventory": "Alle vom VST3-Controller gemeldeten Parameter aufgueltigkeit pruefen",
    "native_parameter_sweep": "Alle automationsfaehigen VST3-Parameter an Grenzwerten durchtesten",
    "native_gui_workflow": "Mehrstufige echte Mausbedienung im selben Pluginfenster",
    "declared_gui_controls": "Explizit definierte Bedienelemente",
    "product_gui_controls": "Alle Bedienelemente des Produktes",
    "independent_musical_audio": "Musikalisch korrekter Klang",
    "externally_referenced_audio": "Vergleich mit freigegebener WAV-Referenz",
    "midi_wav_export": "MIDI- und WAV-Export / Drag-and-drop",
    "preset_semantics": "Preset-Auswahl und klangrichtiger Recall",
    "commercial_daw_integration": "Echte DAW-Sitzung, Routing und Drag-and-drop",
}
ALLOWED = {"PASS", "FAIL", "NOT COVERED", "NOT EXECUTED", "TECHNICAL_PASS", "REFERENCE_MATCH"}


def report_html(data):
    if not isinstance(data, dict):
        raise ValueError("quickcheck report must be a JSON object")
    status = data.get("status")
    if status not in ("TECHNICAL_PASS", "FAIL"):
        status = "FAIL"
    coverage = data.get("coverage", {})
    if not isinstance(coverage, dict):
        coverage = {}
    product = html.escape(str(data.get("product", "Unbekannt")))
    module = str(data.get("verified_module_sha256", "nicht verifiziert"))
    sha = html.escape(module) if len(module) == 64 else "nicht verifiziert"
    # The technical host can finish successfully while its independent
    # real-time timing oracle (or another checked domain) reports FAIL.
    # Do not display a green overall headline above a red failure row.
    failed_checks = [key for key in LABELS if coverage.get(key) == "FAIL"]
    if status == "TECHNICAL_PASS" and not failed_checks:
        headline = "Technische Pruefungen bestanden"
        summary = ("Die ausgefuehrten technischen Tests waren erfolgreich. "
                   "Das ist keine Freigabe des Plugins.")
    elif status == "TECHNICAL_PASS":
        headline = "Technische Pruefung mit Fehlern"
        summary = ("Die technischen Basispruefungen wurden abgeschlossen, "
                   "aber mindestens ein gepruefter Bereich meldet FEHLER. "
                   "Das ist kein vollstaendig bestandener Test.")
    else:
        headline = "Technische Pruefung fehlgeschlagen"
        summary = ("Mindestens ein Test ist fehlgeschlagen oder konnte nicht "
                   "ordnungsgemaess ausgefuehrt werden.")
    rows = []
    missing = 0
    passed = 0
    for key, label in LABELS.items():
        verdict = coverage.get(key, "NOT COVERED")
        if verdict not in ALLOWED:
            verdict = "NOT COVERED"
        if verdict in ("PASS", "REFERENCE_MATCH"):
            passed += 1
        else:
            missing += 1
        display = ("BESTANDEN" if verdict in ("PASS", "REFERENCE_MATCH") else
                   "FEHLER" if verdict == "FAIL" else "NICHT GEPRUEFT")
        cls = "pass" if verdict in ("PASS", "REFERENCE_MATCH") else "fail" if verdict == "FAIL" else "unknown"
        rows.append("<tr><td>" + html.escape(label) + "</td><td class='" +
                    cls + "'>" + display + "</td></tr>")
    if coverage.get("realtime_deadline_observation") == "FAIL":
        missed = data.get("measured_callback_overruns", "unbekannt")
        rows.append("<tr><td>Gemessene Audio-Deadline-Ueberschreitungen</td>"
                    "<td class='fail'>" + html.escape(str(missed)) + "</td></tr>")
    if status == "FAIL" and data.get("error") is not None:
        reason = str(data.get("error"))
    elif status == "FAIL":
        reason = str(data.get("reason", "Der technische Test ist fehlgeschlagen."))
    else:
        reason = ""
    detail = ("<p class='reason'>" + html.escape(reason) + "</p>") if reason else ""
    return """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>125A Plugin Test Lab - Testergebnis</title>
<style>
body{background:#15191f;color:#e6ebf0;font:16px/1.55 Segoe UI,Arial,sans-serif;
max-width:920px;margin:35px auto;padding:0 20px}
h1{font-size:28px}h2{font-size:20px;margin-top:35px}
small{color:#aab5c0;overflow-wrap:anywhere}p{max-width:800px}
table{width:100%;border-collapse:collapse}
td{padding:11px 14px;border-bottom:1px solid #343b45}
td:last-child{white-space:nowrap;text-align:right;font-weight:600}
.pass{color:#8ee3ab}.fail{color:#ff9696}.unknown{color:#c1c8ce}
.warning{border-left:4px solid #ffbe6b;padding:12px 16px;background:#26221d}
.reason{color:#ffb5b5;white-space:pre-wrap}
</style></head><body>
<h1>""" + html.escape(headline) + """</h1><p>""" + html.escape(summary) + """</p>
<p><b>Plugin:</b> """ + product + """</p>
<small><b>SHA-256 des getesteten VST3-Moduls:</b> """ + sha + """</small>
<h2>Einzelpruefungen</h2><table><tbody>""" + "".join(rows) + """</tbody></table>
<p>""" + str(passed) + """ Bereiche mit technischem PASS; """ + str(missing) + """ weitere
Bereiche nicht bestanden oder nicht vollstaendig geprueft.</p>
""" + detail + """
<h2>Freigabe</h2>
<p class="warning"><b>KEINE PRODUKTFREIGABE.</b> Selbst wenn alle obigen
technischen Tests bestanden sind, bleiben produktspezifische Klang-,
Preset-, Bedienungs- und DAW-Ablaufpruefungen ohne unabhaengige
Sollwerte unbewiesen. Eine professionelle Freigabe darf nicht aus diesem
Kurztest abgeleitet werden.</p>
<p><small>Maschinenlesbare Originaldaten: QUICKCHECK-RESULT.json.
Die HTML-Datei ist nur eine Darstellung dieser Daten, kein eigener
Test oder zusaetzlicher Nachweis.</small></p>
</body></html>"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--result", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    try:
        data = json.loads(args.result.read_text(encoding="utf-8"))
        body = report_html(data)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        body = report_html({"status": "FAIL", "error": "Ergebnisdatei ungueltig: " + str(exc)})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(body, encoding="utf-8")
    print("[PASS] Klartext-Testbericht erzeugt; keine Produktfreigabe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
