# P220 – Verbindliches 77-Preset-Klang-Gate des 125A-AWE-Synthesizers

## Stereo-Korrektur aus AWE-Issue #104 – 11.11.2026

**Vergleichsversion: `p220-stereo-v2`; Testversion: `p220-stereo-regression-v2`.**
Bestehender Branch `qa/p220-awe-sf2-77-sound-gate`; keine Änderungen an
Produkt-Engine, ASIO-Limits oder Freigabestatus. Die folgenden Nachweise
betreffen ausschließlich die Qualität des Vergleichswerkzeugs. Originale
Creative-/VST3-Aufnahmen und reale Klangtreue bleiben **NOT RUN / BLOCKED**.

**Reproduzierter Fehler:** Der alte Vergleicher summierte `(L+R)/2` vor
RMS-, Hüllkurven- und Spektralprüfung. Ein asymmetrisches Stereo-WAV mit
vollständig vertauschten Kanälen bestand deshalb. Ebenso konnten
einseitige Gain-, Polaritäts- und Zeitfehler verborgen bleiben; gültiges
gegenphasiges Stereo wurde dagegen fälschlich als stumm zurückgewiesen.
Die neuen Tests wurden zuerst gegen die unveränderte alte Implementierung
ausgeführt: 7/13 Erwartungen erfüllt, fünf Stereo-Mutanten falsch grün
und die passende Antiphasen-Kontrolle falsch rot.

**Korrektur im vorhandenen P220/P89-Pfad:**

- Unveränderte PCM16-WAVs und SHA-Receipts bleiben Eingang. Stereoenergie
  bestimmt Signalpräsenz und groben Onset; L/R werden getrennt erhalten.
- Jeder aktive Kanal muss RMS, Peak, 10-ms-Log-Hüllkurve und die acht
  bisherigen Goertzel-Spektralbänder bestehen. Ein guter linker Kanal
  kann keine fehlerhafte rechte Spur mehr verdecken.
- Die bereits vorhandene **P90**-Funktion `_compare` schätzt nach dem
  groben Onset **einen gemeinsamen** feinen Zeitversatz. Alle aktiven
  Kanäle müssen an genau diesem Versatz positive PCM-Korrelation und
  kleinen Residualfehler zeigen. Kein separater Kanalversatz und keine
  Polaritätskorrektur werden zur Reparatur eines schlechten Captures benutzt.
- L/R-Korrelation sowie Mid-/Side-RMS und Side-Energieanteil werden
  zusätzlich ausgewiesen. Passende Referenz-/Capture-Ruhe in einem Kanal
  ist zulässig; ein Referenzkanal mit Signal und ein stummer Capturekanal
  schlagen fehl. Dual-Mono hat keine unterscheidbare Kanalreihenfolge.
- P89 verlangt `audio_comparison_version=p220-stereo-v2`, Stereo- und
  PCM-PASS sowie beide Kanalresultate in jedem Szenario. Alte rein
  monofone grüne Reports bleiben BLOCKED und dürfen nicht wiederverwendet
  werden. Fehlende fallweise Stereonachweise ergeben FAIL.

**Vor Auswertung festgelegte Screening-Grenzen:**

| Größe | Grenze |
|---|---|
| Absolutes RMS- und Peakdelta je aktivem Kanal | jeweils ≤ 1,0 dB |
| Log-Hüllkurvenkorrelation je Kanal | ≥ 0,90 |
| Spektraldelta in bedeutenden Bändern je Kanal | ≤ 4 dB; bisherige −42-dB-Bandmaske |
| Differenz L/R-Korrelation | ≤ 0,10, wenn beide Kanäle aktiv sind |
| Differenz Side-Energieanteil `S²/(M²+S²)` | ≤ 0,05 |
| Gemeinsam erlaubter grober Aufnahme-Onset | bisherige ≤ 250 ms |
| Gemeinsamer feiner P90-Versatz nach 10-ms-Onset-Raster | ±441 Frames |
| P90 signed PCM | Korrelation ≥ 0,90, positiver Gain 0,2..5, gainbereinigter relativer Residualfehler ≤ 0,18 |
| Ruhegrenze je Kanal | bisherige RMS-Grenze 0,00015 |

Die P90-Gain-Schätzung dient nur der Residualmetrik: der unabhängige
absolute 1-dB-Pegeltest bleibt verpflichtend. Die Original-WAVs werden
weder normalisiert noch verändert. Diese technischen Screening-Grenzen
sind **keine gemessenen universellen Hardware-/Wahrnehmungstoleranzen**.
Kein Nachweis für Sampleidentität, beliebig kleine Kanalversätze,
Recorder-Clock-Drift, sämtliche musikalischen Effekte oder echte
Equal-State-/Originaltreiber-Provenienz wird daraus abgeleitet.

**Gezielte echte WAV-Gegenproben (synthetisch erzeugtes PCM):**

- PASS-Kontrollen: asymmetrisches Stereo mit unabhängigem 1-LSB-Unterschied,
  unverändertes Dual-Mono nach Kanaltausch, passende Antiphase, passendes
  Hard-Left mit stiller rechter Referenz, gemeinsamer +0,5-dB-Gain und
  gemeinsamer Aufnahmeversatz von 211 Frames.
- Erwartetes FAIL: asymmetrischer L/R-Tausch; nur L bzw. R stumm;
  R −3 dB; R polaritätsinvertiert; beide Polaritäten invertiert;
  ausschließlich R um 128 Frames verzögert. Alle Mutanten haben korrekt
  formatierte Dateien und frisch passende SHA-Receipts: ein kaputter
  Hash oder Parserfehler ist nicht ihr Ablehnungsgrund.
- Die zehn vorhandenen 77-Preset-/154-Szenarien-Mutationen, P89-Sperrlogik
  und die unveränderten P90-Capture-Regressionen bleiben Bestandteil
  desselben bestehenden Workflows. Er läuft gezielt auf Ubuntu und
  Windows; dies ist kein nativer Plugin-Neubuild und kein Originalklangtest.

Aufruf: `python tests/test_p220_awe_sf2_sound_gate.py --stereo-evidence <JSON>`.
`--stereo-only` führt nur die 13 gezielten Stereoerwartungen aus. Das
JSON enthält beide WAV-Hashes, Werkzeug-/Testquellhash, Version,
Einzelmessungen, Soll-/Ist-Ergebnisse und `release_approved=false`.
Die tatsächlichen CI-Run-/Commit-Nachweise werden nach Abschluss hier
nachgetragen; bis dahin Windows **NOT RUN**.

---

**Status am 10.11.2026:** Test-/Release-Sperrlogik und Negativmutationen technisch geprüft, **echte Originaltreiber- und Windows-VST3-Klangabnahme der privaten 77-Preset-Bank NICHT RUN / BLOCKED**. Das ist KEIN Klang-PASS und keine Verkaufsfreigabe.

## Referenzen und Zuständigkeiten

- Private Anwenderbank `Synth 512 Bank.sf2`, exakt **555.754 Bytes**, SHA-256 `d5b99ec38fddf59f53f66b90921e170d207bf3bbd73960f6e4175c39ef68349b`. Die originale Datei verbleibt privat und wurde **nicht** an GitHub Actions übergeben.
- `tools/p80_full_sf2_inventory.py` im [AWE-Quellprojekt](https://github.com/challanger2000/125A-AWE-Synthesizer/tree/qa/p220-77-preset-original-sound-acceptance): 77 wirkliche MIDI-Programme **0–62, 64–77**; 63 fehlt, phdr-Diskreihenfolge ist umgekehrt. Dateiinventar und MIDI-Programm sind nicht gleichwertig zu Klang.
- Original-Creative-Quelle: **originales Windows 95/Creative WinMM/SBAWE.VXD**, SHA-256 `d343f2428ab3e593c9e42a668cf521b7801e1239792eaf7f2b11b5f179bc7c9a`, über die bereits bewährte **86Box-AWE64-Gold/EMU8000-Emulation** (kein neuer Emulator). Die originale Creative-Treiberlogik wird ausdrücklich vom emulierten EMU8000-Signal und von einer **nicht getesteten physischen AWE64** getrennt.
- Gegenprobe: tatsächlich gebaute **Windows-x64-VST3**, exakter Modul-SHA-256 im Testbeleg; eine reine native 86Box-Engine zählt **nicht** als echte VST3-Aufnahme.
- Bestehende Vorarbeit: P63 COM1/WinMM, P75 FAT-Staging/EMU8000-Sample-Upload, P80 komplette Programmauflistung, P87 sechs echte WAV-Paare, P89 I/O-Register, P97 öffentliche *andere* SoundFont gegen CT4390, P210–P218 driver/EG1/Filter; **keines dieser Einzel-PASS ersetzt die 77 Preset-Audioabnahme**.
- **Independenter Test Lab code:** `tests/p220_awe_sf2_sound_gate.py`; 154 Original- und 154 VST3-Captures nach MIDI-Plan; technische Vorprüfung des originalen Creative-Treibers und seines AWE-Uploads sowie tatsächlicher Sample-Startregister und Windows VST3 process() wird verlangt. Der Eingang ist eine auditable JSON-Quelle samt **zweier voneinander unabhängiger PCM-Dateisätze**. Konkrete Sampledaten dürfen nicht in öffentliche Actions-Artefakte.
- **Verbindlicher Release-Gate im bestehenden P89-Gap-Reporter:** `tests/run_unified_qa_gaps.py --require-awe77-for awe --awe77-evidence awe=P220-RESULT.json`. Fehlt Original-Audio oder stimmen Modul-SHA/77-Cases nicht, bleibt `required_awe_77_sonic_gate=BLOCKED/FAIL`, die Release-CLI liefert Exitcode ≠0, technische VST3-PASS bleibt separat als solches sichtbar. Andere Plugins bleiben unverändert.

## Frozen 77×2 MIDI-Plan (ein erster Mindesttest, keine Vollständigkeitsbehauptung)

Jeder der 77 echten `phdr.wPreset`-Werte erhält 2 voneinander getrennte Versuche, im Creative-MIDI-**User-Bank-1**, für den VST3-Pfad mit der dort tatsächlich passenden Original-SF2-Bank 0:

| Versuch | Note | Velocity | Vorgeschriebene Controller | NoteOff | Capture |
| --- | ---: | ---: | --- | ---: | ---: |
| `DRY` | 48 | 64 | CC1=0; CC7=100; CC11=127; CC91=0; CC93=0 | 1000ms | 3000ms |
| `MODFX` | 72 | 120 | CC1=96; CC7=100; CC11=127; CC91=48; CC93=32 | 1000ms | 3000ms |

Alle 154 eindeutigen `P000-DRY` … `P077-MODFX` mit bewusst fehlendem P063 bilden ein fixiertes numerisches MIDI-Protokoll. Jeder Durchgang beginnt mit explicit user-bank/controller/program reset, gefolgt von Note-On, Note-Off und separatem Original-Wavetable-Audio (11-Protokollwerte in den einzelnen Scripts). Der Plan wird aus der tatsächlich privaten Benutzerbank mithilfe des P80-Inspectors und **exaktem SF2-SHA** erzeugt. **Wichtig:** Zwei Noten/Velocities können Sample-Keyzonen und musikalisch ungleiche Presets nur begrenzt abdecken; individuelle registrierte Keyrange/Velocity- und Loop-Gates sind für einen echten FINAL-PASS zusätzlich Pflicht.

## Auswertung und Grenzen des Orakels

- Tatsächliche stereo PCM16 WAV 44.1 kHz, passender Szenariendauer, Echtheits- und SHA-Receipts, 77 korrekte Programme (kein GM- oder Program-63-Ersatz), echte Quell-Sample-Upload-Prüfung, tatsächliche I/O-Register und MIDI-Ereignisse.
- **Nicht normalisierte Lautstärke:** RMS-dB-Differenz (vor jeglichem Level-Match), kein Clipping, keine Stille. Grobe Signal-Startverschiebung dokumentiert; der Onset-Vergleich lässt nur deklarierte Zeitdifferenzen zu.
- **Log-Hüllkurvenkorrelation:** grobe 10ms-RMS-Frames; FFT-nahe diagnostische 8-Frequenz-Bandwerte über Goertzel. Ein einzelner blinder RMS-Wert ist kein Gesamt-Klangnachweis.
- Die konservativen maximal erlaubten Screening-Deltas 1,0dB Pegel, envelope corr ≥0,90, aktive Frequenzbänder ≤4dB und ≤250ms Startabstand sind **explizite Anfangs-Toleranzen** für die 86Box-A/B-Referenz, keine zugesicherte Original-Creative-Hardware-Klangidentität; sie bedürfen musikalischer/hardwareorientierter Eigentümerabnahme.
- Zusätzliche **verbindliche 77 Einzel-Gates**, für die echte unabhängige Belege vorhanden sein müssen: vollständige Amp-ADSR, dynamische Filter-Sweeps, tatsächliche Sample-Loops, trockene und nasse Reverb/Chorus-Wege und Preset-/State-Recall. Sie sind **aktuell für alle 77 `NOT TESTED`**; der erste Audio-Screen kann diese nicht pauschal ersetzen.
- Auch bei einer hypothetischen 77/77 A/B-Übereinstimmung gelten originale physische AWE64/Silicon-/Analog-/S/PDIF-Übertragung und Studio One/ASIO als separate **NOT TESTED** Gates. `release_approved=false` bleibt im Resultat.

## Reproduzierbarkeit / Bedienung

Der private Original-SF2-MIDI-Plan wird im **AWE**-Repo erstellt:

```powershell
python tools/p220_77_preset_capture_plan.py --sf2 "C:\Private\Synth 512 Bank.sf2" --out "C:\Private\P220\contract.json"
```

Die Original-Creative-Aufnahme erweitert **denselben bereits verwendeten P48/86Box/Win95/Creative AWECP32 MIDI-Pfad**, ohne eine neue Testumgebung:

```text
tools/p48_86box_boot_win95.py <existing P48 --binary/--roms/--disk/--out> \
  --p64-bridge --sound-card sbawe64_gold --private-sf2 <exact-private-SF2> \
  --require-full-bank --p220-plan <contract.json> \
  --p220-private-audio-dir <private-not-public-result-dir>
```

Hinweis: Das startet eine **lange neue Aufnahme innerhalb der vorhandenen Win95-86Box-Umgebung**; ein normales öffentliches GitHub-Job-Setup verfügt weder über die private Benutzer-SoundFont noch über das eigentliche installierte Win95-Laufwerk samt Benutzerdateien. Eine erfolgreiche **statische** Prüfung dieses Codes ist kein tatsächlicher Guest-Boot.

Der eigenständige Release-Soundtest erwartet genuine, getrennt erworbene Belege:

```powershell
python tests/p220_awe_sf2_sound_gate.py --contract "C:\Private\P220\contract.json" --creative-receipts "C:\Private\P220\creative-verified.json" --vst3-receipts "C:\Private\P220\vst3-verified.json" --creative-audio-dir "C:\Private\P220\creative" --vst3-audio-dir "C:\Private\P220\vst3" --out "C:\Private\P220\P220-RESULT.json"
python tests/run_unified_qa_gaps.py --batch "C:\QA\batch" --out "C:\QA\results" --require-awe77-for awe --awe77-evidence awe="C:\Private\P220\P220-RESULT.json"
```

**Wichtig:** Die 77-Originalaufnahmen und die tatsächlichen VST3-Receipts sind aktuell **nicht** vorhanden; insbesondere ein vorläufiger P48-Aufnahmelauf darf nicht mit der unabhängig geprüften P67-Gast- und VST3-Identität verwechselt werden. Der angehängte Originalbank-Plan ist vorhanden, aber die echte Klangerfassung ist **BLOCKED**, nicht vom User manuell bestätigt oder CI-fiktiv ausgeführt.

## Ausgeführte adversariale Kontrollen

[**P220 Test Lab #42757151400 SUCCESS**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42757151400), echte Testskript-Ausgabe:

- 77/77 und 154/154 in **SYNTHETISCHER** guter Test-Oracle-Fixture, keine Original-Creative-Aufnahme (reine Prüfqualität, nicht Klangtreue).
- **10/10 bewusst kaputte Fälle erkannt**: ohne Creative/WAV, falscher VxD-SHA, kein SF2-Upload, falsches Creative-MIDI-Programm, falsches VST3-Programm, fehlender FX-Nachweis, tatsächlich falsches aber valides PCM, komplett stumme aber valide WAV, exakt duplizierte Audio-Bytes und eingefügtes nicht existentes Programm63.
- **P89 konsolidierter Release-Modus separat getestet**: ein tatsächlich technisch bestandener AWE-VST3-Batch mit fehlendem originalen SF2-Klang liefert **nonzero exit, BLOCKED**. Falsche Status-Summen/Modul-SHA werden zurückgewiesen. Standard-Batch-Nicht-AWE unverändert.
- Öffentliche CI mit absichtlich fehlender Benutzerbank und Original-WAV: **77/77 `BLOCKED`, 0/77 `PASS`**, No-GO. Ein erfolgreiches Actions-Symbol ist hier nur die Bestätigung dieser Ablehnungslogik.

## Kritische noch offene reale Abhängigkeiten

| Gate | Realtest-Evidenz | Status |
| --- | --- | --- |
| Private SF2 SHA, exakte 77-Programmbindung | Lokale Datei + P80 + exportierter numerischer Plan | **PASS – Inventar/Identität allein** |
| P48 Originaltreiber, 77 Original-Programme vollständig geladen und MIDI gespielt | Bisher nur andere Original-SF2-Teiltests; keine 154 echten Benutzerbank-WAV | **BLOCKED / NOT RUN** |
| 154 echte Creative/86Box-WAV & tatsächlich unabhängige P67-Receipts | Kein physischer/Cloud-Gast mit privater Benutzerdatei in aktueller Ausführungsumgebung | **BLOCKED / NOT RUN** |
| 154 echte *Windows VST3* WAV der exakten Nutzerbank | Kein vollständiger 154-Aufnahmen-Hostnachweis | **NOT RUN** |
| ADSR, Filter, Loops, trocken/nass FX, Preset-Recall, 77 Einzelberichte | Keine echte Doppelaufnahmereihe und Detailbelege | **NOT RUN** |
| Synthetische 77×2 Testlogik und 10 Negativmutationen | CI #42757151400 | **PASS NUR TEST-OF-TEST** |
| P89 vorhandenes Test Lab funktional an AWE-Soundgate angeschlossen | CI #42757151400 | **PASS NUR RELEASE-SPERRLOGIK** |
| Physische AWE64 Gold Klangtreue / Studio One ASIO | Keine neue Hardware-/DAW-Prüfung | **NOT RUN** |

**GESAMT: P220-KLANGABNAHME NICHT BESTANDEN, da 77 echte Original-Creative-VST3 Audiopaare fehlen. RELEASE NO-GO.** Keine produktive DSP-Änderung, keine private Bank oder Originaltreiber in öffentlichem Repository und kein Merge.
