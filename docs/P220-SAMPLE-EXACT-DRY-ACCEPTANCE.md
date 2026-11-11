# P220: samplegenaue Dry-Prüfung — Werkzeugprüfung und Klangabnahme getrennt

Repository: `challanger2000/125A-Plugin-Test-Lab`.
Bestehender Branch: `qa/p220-awe-sf2-77-sound-gate`.
Ausgangspunkt: `f96213b20f234eef2c6fadf8d0706818cc5681dd`.
Die abgenommene Integrationsvorprüfung **#42946883199 wurde nicht wiederholt**.
Dieser Auftrag prüft die neue Dry-Erweiterung am aktuellen QA-Quellstand.
Produkt-Engine, Chorus/Reverb-DSP und ASIO-Grenzwerte bleiben unverändert.

## Versionen und Abnahmeumfang

| Rolle | Exakter Stand |
|---|---|
| Erste Dry-Implementierung, durch Nachkorrektur überholt | `aa846205104f4875d7f40b853bdff64c179df0cf` |
| **Auf beiden OS geprüfter Quellcommit** | **`2e541bb553a584a452a4f1127c007e88813a2404`** |
| **Quellbaum dieses Commits** | **`5090bc5ee9e30b14430c4670ccf1c5493ff5b6e2`** |
| Historische Gegenkontrolle, nur ausgewählte PCM-Fälle | `f96213b20f234eef2c6fadf8d0706818cc5681dd` |
| Bestehender Stereo-Vergleicher | `p220-stereo-v2` |
| Neue Dry-Vertragsprüfung | `p220-sample-exact-dry-v1` |
| Synthetische Dry-Regression | `p220-dry-regression-v1` |

**Prüfwerkzeug auf Windows-2022 und Ubuntu-24.04 bestanden. Echte
Dry-Klangabnahme: BLOCKED.** Tatsächlicher neuer Lauf
[#42989599864, SUCCESS, 6m 40s](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42989599864),
exakt auf Quellcommit und Baum oben. Die abschließenden öffentlichen
Job-Annotationen bestätigen beide Identitäten und alle Testzähler.

| Tatsächlich ausgeführt | Ubuntu-24.04 | Windows-2022 | Cloud-Linux lokal |
|---|---|---|---|
| Dry-Erwartungen | 42/42 | 42/42 | 42/42 |
| Davon gültige synthetische PCM-Kontrollen / erwartete Fehler / erwartete Herkunftssperren | 7 / 33 / 2 | 7 / 33 / 2 | 7 / 33 / 2 |
| Bestehende Stereo-Erwartungen | 13/13 | 13/13 | 13/13 |
| Bestehende synthetische Audio-Screeningfälle | 154/154 | 154/154 | 154/154 |
| Bestehende Fehlermutanten erkannt | 10/10 | 10/10 | 10/10 |
| P220-/P89-/P90-Unit-Tests, einschließlich sechs neuer | 7 + 4 + 14 | 7 + 4 + 14 | 7 + 4 + 14 |
| Tatsächliche historische Quellcodekontrollen | 7/7 | 7/7 | 7/7 |
| Fehlende echte Original-/VST3-Dry-Aufnahmen | 77 BLOCKED / 0 PASS | 77 BLOCKED / 0 PASS | 77 BLOCKED / 0 PASS |

Direkte geprüfte Jobs:
[Ubuntu #130418934383, 4m 51s](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42989599864/job/130418934383),
[Windows #130418934661, 6m 36s](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42989599864/job/130418934661).
Der lokale vollständige P220-Lauf dauerte 455,66 Sekunden; alle regulären
Befehle endeten mit Exitcode 0. Die beiden fehlende-Aufnahmen-Gegenproben
endeten wie verlangt mit Nichtnull-Exit und BLOCKED. Derselbe abschließende
CI-Ergebnisverifier wurde zusätzlich auf den lokalen Rohprotokollen ausgeführt.

[Maschinenlesbare Nachweise](evidence/P220-SAMPLE-EXACT-DRY-20261111/evidence.json),
[alle 42 Dry-Erwartungen und Rohmesswerte](evidence/P220-SAMPLE-EXACT-DRY-20261111/p220-dry-v1.json),
[lokale Testprotokolle](evidence/P220-SAMPLE-EXACT-DRY-20261111/local-test-logs.txt) und
[77 tatsächlich blockierte Dry-Fälle](evidence/P220-SAMPLE-EXACT-DRY-20261111/required-real-dry-evidence.json)
sind dauerhaft im Repository veröffentlicht. Die archivierten synthetischen
Eventdateien stehen daneben unter `synthetic-inputs/`; die zugehörigen WAVs
liegen in den CI-Artefakten, nicht als neue Audio-Binärdateien in Git.

| Download mit synthetischen WAVs, Rohtraces, JSONs, Logs und QA-Quellarchiv | Von Actions veröffentlichter SHA-256 |
|---|---|
| [Ubuntu-Artefakt #13841492477](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42989599864/artifacts/13841492477) | `0c4b567d39b8d5c9285bf58be839df43aedcb2bb1d49abb1c73d685e43f8f2f6` |
| [Windows-Artefakt #13840783363](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42989599864/artifacts/13840783363) | `e93e0db02f669cd9fc5b10047c8f17136f4fdac42b0ee33d0fd3c766641a19e3` |

Artifact-Retention: 14 Tage; GitHub kann für den Download eine Anmeldung
verlangen. Die Ergebnisprüfung stützt sich auf die spezifischen
Quellstands-/Testzähler-Annotationen **nach** der JSON-/Log-Verifikation,
nicht allein auf einen grünen Run. Die Artefaktinhalte wurden in dieser
Cloud nicht zusätzlich heruntergeladen; ihre von Actions veröffentlichten
Digests sind unverändert dokumentiert. Beide Jobs melden lediglich die
bekannte Node-20-Abkündigung der vorhandenen Checkout-/Upload-v4-Actions;
GitHub führte sie erfolgreich unter Node 24 aus.

Die sieben geänderten Implementierungs-/Test-/Workflowdateien sind vollständig
im deklarierten QA-Umfang geprüft: `tests/p220_awe_sf2_sound_gate.py`,
`tests/run_external_daw_capture_check.py`, `tests/run_unified_qa_gaps.py`,
`tests/test_p220_awe_sf2_sound_gate.py`, `tests/test_p220_awe_unified_release.py`,
`tests/test_p90_external_capture_check.py` sowie der vorhandene P220-Workflow.
Die bestehende P89-Testsuite bleibt zusätzlich Teil der Regression.
Es gibt keinen neuen Audiotester, Workflow, Branch oder Pull Request.

Pfadzuordnung: D1–D4 und D7 werden in `dry_trace`, der Vergleich in
`dry_compare`/`compare` und P90 `_compare` erzwungen. `evaluate_dry` bindet
alle 77 Paare; `evaluate` und P89 `awe77_sound_report` verhindern den alten
Stereo-only-Freigabeweg. D6 wird in `dry_regressions` und den vorhandenen
P220-/P90-Unit-Suiten ausgeführt.

## Die verbindlichen Anforderungen und ihre Gegenproben

| ID | Implementierter Vertrag und unabhängige Erwartung | Positive und gezielte negative Kontrolle | Reale Produktkette |
|---|---|---|---|
| D1 Identität | Beide Trace-Dateien müssen mit dem unabhängig freigegebenen ROM-/Bank-Pin, Programm, Bank, MIDI-Kanal, Note, Velocity und 44.100 Hz übereinstimmen. Originaltreiber-/VST3-Modulhash und WAV-/Trace-Hashes werden getrennt gebunden. | Unabhängig gerundetes Stereo-PCM; falscher ROM-/Bank-/Modulhash, Programm, Note, Velocity sowie abweichende WAV-/Trace-Samplerate. | NOT RUN |
| D2 Dry-Sends | GUI-Anzeige, Controller und Processor müssen 0 melden; initiale und finale Sends **aller 32 Stimmen**, vollständige Send-Schreibhistorie und gemutete FX-Returns müssen Dry belegen. | GUI 0/Processor ungleich 0, GUI 0/Controller ungleich 0, nichtnuller Send auf Stimme 31, kurzzeitiger Send, offener Return; zusätzlich hörbarer Wet-Tail trotz behaupteter Nullwerte. | NOT RUN |
| D3 Ereignisse | MIDI-Offsets müssen in real protokollierte zusammenhängende Prozessblöcke fallen. MIDI-Sequenz, Voice-Registerereignis und Samplecounter müssen über vorab gepinnte Clock-/Latenzabbildungen dasselbe On-/Off-Ereignis bezeichnen. | Unterschiedliche Transportversätze und 17-/128-/512er Partitionen; um ein Sample verschobenes MIDI-Note-off, Register-Release, falsche Clock-Kalibrierung, Blocklücke oder ungültiger MIDI-Sampleoffset. | NOT RUN |
| D4 Fenster | Fensterbeginn = tatsächliches Sample-Start-Ereignis minus freigegebener Vorlauf; Fensterlänge exakt gleich. Abgeschnittene Prefix-/Suffix-Samples werden ausdrücklich gezählt. Kein automatisches Onset- oder Korrelations-Reparieren. | Explizit verworfene ganze Blockreste; zusätzliche 512 Samples im Messfenster, falscher Beginn, um ein Sample zu kurze WAV, verschobenes PCM und Audio im Vorlauf beider Quellen. | NOT RUN |
| D5 Klang/Release | Bestehende kanalweise RMS-/Peak-/Envelope-/Spektrum-/Stereo-Prüfung plus vollständiger P90-Vergleich bei Unit-Gain, ohne Lag-Suche oder Sampleauslassung. Release wird nach dem protokollierten Note-off separat verglichen. | Stereo, Hard-Pan, Gegenphase, stummer Release, 1-/2-LSB-Kontrollen; +0,5 dB, geänderter Release, Kanaltausch, ein einzelnes spätes fehlerhaftes Sample und versteckte Wet-Samples. | NOT RUN |
| D6 Testadäquanz | Frische passende WAV-, Trace- und freigegebene synthetische Manifest-Hashes dürfen semantische Fehler nicht verstecken. Historische Implementierung muss den positiven Kontrollfall bestehen. | 42 feste Dry-Erwartungen; darunter sieben tatsächliche historische Quellcodevergleiche: ein gültiger Kontrollfall und sechs frühere False-PASS-Fälle. | Keine unabhängige Hardwareprüfung |
| D7 Herkunft | `ORIGINAL_CREATIVE_86BOX`, `WINDOWS_VST3`, `WINDOWS_DAW_VST3`, `NATIVE_ENGINE_DIAGNOSTIC` und `SYNTHETIC_FIXTURE` dürfen nicht austauschbar sein. DAW-Signalweg muss zusätzlich neutral sein. | Native Diagnose bleibt BLOCKED; synthetische Fixtures bleiben auch bei gutem PCM BLOCKED; falscher Audio-Tap, falsche Kanalmetadaten und DAW-Pegeländerung werden zurückgewiesen. | NOT RUN |

Dies sind ausführbare **Prüfverträge für gelieferte Beobachtungen**, keine
Behauptung, die echte GUI-, Creative-, Windows-VST3- oder DAW-Kette sei durch
synthetische Daten nachgewiesen. Die genaue automatisierte Ergebnismatrix
steht im abschließenden Abschnitt dieses Berichts.

## Aufnahmevertrag im bestehenden P220-Pfad

Der vorhandene 77-Programm-/154-Szenario-Vertrag bleibt der gemeinsame
Einstieg. Zusätzlich enthält er `sample_exact_dry` mit Schema
`125a-p220-sample-exact-dry-contract-v1`:

```json
{
  "schema": "125a-p220-sample-exact-dry-contract-v1",
  "rom_sha256": "<freigegebener Original-ROM-SHA256>",
  "bank_sha256": "d5b99ec38fddf59f53f66b90921e170d207bf3bbd73960f6e4175c39ef68349b",
  "vst3_module_sha256": "<Hash der tatsächlich aufzunehmenden Windows-VST3>",
  "vst3_capture_kind": "WINDOWS_VST3",
  "sample_rate": 44100,
  "channels": ["L", "R"],
  "pre_note_frames": 4410,
  "note_length_frames": 44100,
  "window_frames": 132300,
  "captures": {
    "P000-DRY": {
      "creative": {
        "wav_sha256": "<unabhängig freigegebener WAV-Hash>",
        "trace_sha256": "<unabhängig freigegebener Eventdatei-Hash>",
        "sample_to_audio_offset_frames": 0,
        "midi_to_sample_on_frames": 0,
        "midi_to_sample_off_frames": 0
      },
      "vst3": "<gleiches Pin-Objekt mit tatsächlich ermittelten Werten>"
    }
  }
}
```

Das Beispiel ist **keine freigegebene Aufnahmeplanung**. Alle 77 DRY-IDs,
wirkliche Hashes und tatsächlich beobachtete Clock-Abbildungen sind
erforderlich; keine fehlenden Werte mit Null auffüllen. Null-Latenzen oben
sind ausschließlich Schemaillustration. Das Tool akzeptiert keine
automatisch aus der PCM-Korrelation nachträglich gewählte Kalibrierung.

Je Aufnahme liegt neben `Pxxx-DRY.wav` eine SHA-gepinnte
`Pxxx-DRY.events.json` mit Schema
`125a-p220-midi-register-sample-trace-v1`. Der bestehende Trial-Receipt
enthält `event_trace` und `event_trace_sha256`. Die Rohdatei enthält:

- Backend-/Herkunftsklasse, Audio-Tap, L/R-Zuordnung und dieselben Identitäten
  wie der freigegebene Vertrag, einschließlich des WAV-Hashes.
- Tatsächliche rohe Framezahl und lückenlose Prozessblöcke; MIDI-Bank/Programm,
  Note-on/-off mit Sequenz, Blockbeginn und Sampleoffset.
- Tatsächliche Voice-Start-/Release-Registerereignisse für alle beteiligten
  Stimmen und ihre zugeordneten Samplecounter-/Audioframe-Ereignisse.
- Exakten Fensterbeginn, exakt 132.300 Messframes im Beispiel und ausdrücklich
  verworfene Vor-/Nachlauf-Samples. Der Vorlauf muss digital ruhig sein.
- GUI-/Controller-/Processor-Beobachtungen, alle 32 initialen/finalen Send-
  Readbacks, vollständige Send-Schreibbeobachtung und FX-Return-Mutezustand.

Für `WINDOWS_DAW_VST3` sind zusätzlich DAW-Name/-Version, null Insert-Effekte
im Aufnahmeweg, Track-/Mastergain 0 dB und deaktivierte Normalisierung
erforderlich. Die zugelassenen Abgriffe sind exakt
`86box_emu8000_stereo_output`, `windows_vst3_process_output` bzw.
`windows_daw_post_plugin_output`. Ein nativer Offline-Engine-Abgriff ist
keine tatsächliche Windows-VST3-Aufnahme.

Die vier archivierten synthetischen Positiv-/Negativdatensätze enthalten
vollständige WAVs, Eventdateien und `SYNTHETIC-INPUTS.json` als ausführbares
Formatbeispiel. Sie sind **keine Original-Creative- oder Produktaufnahmen**.
Echte ROMs, SF2s, Creative-Treiber und private Aufnahmen werden nicht gebündelt.

## PCM- und Release-Vergleich ohne Pegelnormalisierung

Der bestehende P90-Oracle erhält nur einen opt-in `sample_exact=True`-Modus.
Alle bisherigen P90-Aufrufe behalten ihre bisherigen Lag-/Gain-/Screening-
Semantiken. Dry erzwingt gleich lange L/R-Arrays, Lag-Budget 0, Stride 1 und
Unit-Gain-Fehlerberechnung. Der geschätzte Gain bleibt Diagnosewert und
skaliert keine Aufnahme. Jedes Sample beider Kanäle wird geprüft.

Zusätzlicher vorab festgelegter digitaler Quantisierungsvertrag: maximal
**2/32768** absoluter Samplefehler bei den vorgeschriebenen 16-Bit-WAVs.
Das ist eine explizite Zwei-LSB-Vergleichsgrenze für unabhängig quantisierte
digitale Aufnahmen, **keine gemessene analoge Hardwaretoleranz und keine
ASIO-Grenzwertänderung**. Die 1-/2-/3-LSB-Unit-Gegenprobe sichert die Grenze.
Ob reale Original-Creative-/VST3-Aufnahmen sie erfüllen, bleibt NOT RUN.

RMS und Peak bleiben absolut. Hüllkurven werden über das ganze Messfenster
verglichen. Die acht bestehenden Spektralzentren bleiben erhalten; Dry
berichtet absolute, mit dem festen Hann-Fensterfaktor kalibrierte dBFS-
Bandpegel. Diese analytische Fensterkorrektur verändert keinen PCM-Pegel.
Die Messung beginnt 1000 Samples **nach** dem tatsächlichen Note-on, die
separate Release-Messung nach Note-off. Ein stilles Vorlauf-Spektrum ist kein
gültiger positiver Test. Ein bereits stummer Release darf dagegen bei
übereinstimmend ruhigem PCM bestehen; eine stille rechte Seite bei Hard-Pan
wird weiterhin korrekt behandelt.

Konkrete synthetische Positivkontrolle: 132.300 Fensterframes und 83.790
Releaseframes; gemeinsamer Lag 0, keine Gain-Normalisierung, maximaler
Samplefehler je Kanal **1/32768**. Der Spektralstart liegt bei Frame 5410
nach Note-on bei Frame 4410. Die stärksten Referenzbänder betragen links
-14,6187 und rechts -21,6687 dBFS; es wird somit tatsächlich aktives
asymmetrisches Stereo gemessen. Trotz positivem PCM lautet die
Herkunfts-/Klangentscheidung dieser Fixture **BLOCKED**.

Der vollständige 154er-Report verwendet bei vorhandenem Dry-Vertrag dieselben
validierten Eventfenster. Er darf deren rohe Blockreste nicht noch einmal
mit dem alten Whole-WAV-Pfad übernehmen. Eine eigene Routing-Gegenprobe
sichert genau diese Integration. Ohne Dry-Evidenz bleibt der bisherige
Stereo-Screen als `screen_status` sichtbar, aber die gesamte Klangabnahme
und der P89-Releasepfad bleiben BLOCKED.

## Reproduzierbare Ausführung

Bestehende synthetische P220-/P90-Prüfung, keine Original-Assets nötig:

```text
python tests/test_p220_awe_sf2_sound_gate.py --dry-only --compare-baseline --dry-evidence dry.json --dry-fixtures-out synthetic-inputs
```

Ohne `--dry-only` und mit `--dry-evidence` laufen zusätzlich die 13 bestehenden
Stereoerwartungen, 154 Audio-Screeningfälle und zehn bisherigen Mutanten.
`--compare-baseline` lädt ausschließlich die zwei fest gepinnten historischen
Python-Quelldateien aus Git; dafür muss Commit `f96213b...` lokal vorhanden sein.
Es baut keinen Integrationsbaum und wiederholt keine Integrationsvorprüfung.

Echte gelieferte Aufnahmen durch denselben vorhandenen CLI-Pfad prüfen:

```text
python tests/p220_awe_sf2_sound_gate.py --dry-only --contract approved-77-contract.json --creative-receipts creative-receipts.json --vst3-receipts vst3-receipts.json --creative-audio-dir private-creative --vst3-audio-dir private-vst3 --out dry-result.json
```

Fehlende Originalaufnahmen oder ein fehlender Dry-Vertrag ergeben BLOCKED
und einen Nichtnull-Exitcode. Eine positive synthetische PCM-Kontrolle hat
`comparison_status=PASS`, aber **`status=BLOCKED`, `release_approved=false`**.
Das Testflag zum Zulassen synthetischer Fixtures ist nur ein interner
Python-Testaufruf; die produktive CLI bietet keinen entsprechenden Schalter.

## Nachkorrektur und Grenzen

Bei der eigenen Rohdatenkontrolle von `aa84620` wurde ein Fehler der neuen
Erweiterung reproduziert: Der bisher feste Spektralstart bei Frame 1000 lag
im 4410-Frame-Vorlauf. 1024 Nullsamples ergaben acht gleiche relative
Bandwerte von -9,03089987 dB statt eines musikalisch aussagekräftigen
Spektrums. `2e541bb` korrigiert das ereignisbezogen und ergänzt eine
Positivkontrolle auf tatsächliche spektrale Energie. **Der Erststand ist
überholt und wird unabhängig von seinem CI-Status nicht als Abnahme gezählt.**
Der [Erstlauf #42989046260](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42989046260)
war tatsächlich SUCCESS; sein damaliger Spektraltest war dennoch unzureichend.
Der neue Energieschutz ist Teil des abschließend geprüften Quellstands.
Dies ist ein dokumentierter adversarialer Eigen-Gegencheck; keine getrennte
unabhängige Reviewer- oder Hardwareabnahme wird behauptet.

Die Prüfung liest SHA-gepinnte **gelieferte** Beobachtungen. Sie ist kein
Capture-Producer und attestiert nicht kryptografisch, welcher Prozess oder
welche Hardware die Dateien erzeugt hat. Eine vertrauenswürdige unabhängige
Aufnahme und Freigabe der Pins bleibt Voraussetzung. Die tatsächlichen
Creative-/VST3-/GUI-/Register-Exporter müssen das Format mit echten
Beobachtungen liefern; ihre Live-Ausführung ist hier **NOT RUN**. Fehlende
Beobachtungen dürfen weder geraten noch aus derselben zu prüfenden PCM-WAV
als angeblich unabhängige Register-/MIDI-Ereignisse abgeleitet werden.

Reale Original-Creative-/86Box-Aufnahmen, die tatsächliche AWE-Windows-VST3,
eine reale DAW, physisches ASIO, native Produkt-CTests, Validator und GUI-
Smokes wurden in diesem Python-QA-Auftrag nicht ausgeführt: **NOT RUN**.
Die Klangfreigabe bleibt ohne diese echten Capturepaare **BLOCKED**.
Keine FULL-AUDIT-, Produkt- oder Releasefreigabe. Kein Merge nach main,
kein neuer Branch/PR und keine Änderung an P232 bzw. der AWE-Produkt-Engine.
