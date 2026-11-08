# 125A Plugin Test Lab – adversariale Gesamtabnahme, Teilbericht P113 (08.11.2026)

## Gesamturteil

**NEIN: Ein unabhängiger FULL AUDIT ist noch nicht vollständig nachgewiesen.** Die vorhandene Prüfung ist eine adversariale **Eigen-Gegenprüfung** mit echtem, neuem Red/Green-Fehlernachweis. Ein *unabhängiger* zweiter Auditor ist nicht durch bloßes Umbenennen eines Chats, Branches oder CI-Runs ersetzt.

**Funktionaler Scope P106–P112 Windows Testfixtures: PASS.** Im neu geprüften Bereich P91 wurde ein zusätzlicher **konkreter falscher DAW-PASS (P113)** reproduziert und der Displaynamen-Abgleich korrigiert. Die P113-Unitregression unter Windows hat die Korrektur bestanden; echte REAPER-Läufe sind separat vom Unit-Test auszuwerten. Das exakte Laufzeit-DLL-Lademodul bleibt **NOT VERIFIED**.

### Verbindliche Provenienz

- Repository: `challanger2000/125A-Plugin-Test-Lab`.
- Zur Bestandsaufnahme gepinnter Source HEAD: `10fe2e59088efd15fe3287729f227637b4ddbdcc` (`feature/p106-universal-windows-installer`, Draft-PR #132).
- Auditbranch: `audit/2026-11-08-full-test-lab-review`, eigener Draft-PR #137. P113-Bugfix + Negativkontrolle: `bae86ee0fc3ead4a1d4d2a13285b06b101a9da92`.
- `main` zum Prüftermin: `bc839e345bfc5657f9196f7db8d6945584e1bec7`; nur die P106-basierte Auditlinie enthält P106–P112.
- Vollständiger Git-Baum wurde über GitHub REST `git/trees/<SHA>?recursive=1` ohne `truncated` inventarisiert: **326 Tree-Einträge, davon 319 Dateien, 2.300.795 Byte**. Darunter 60 Workflows, 58 `docs/`-Dateien, 11 `src/`-Dateien, 182 `tests/`-Dateien, vier `tools/`-Dateien sowie Projekt-/Engineering-Dateien.
- Verbindliche Vorgaben: `125A-Engineering/START-HERE.md`, `ENGINEERING-GUARDRAILS.md`, `QA/AUDIT-COMPLETENESS-CONTRACT.md`, `QA/RELEASE-QA.md`, `STANDARDS/SOURCE-BASELINE-GATE.md`.

## Vollständigkeits- und Quellcodeinventar (ehrlich)

| Subsystem / Hauptpfade | Quelltext-/Testinspektion | Ausgeführte Evidenz | Auditorisches Urteil |
| --- | --- | --- | --- |
| P106–P112 `Invoke-UniversalInstaller.ps1`, `Invoke-InstalledVst3QA.ps1`, Manifestgenerator/-prüfer, Win32-NTFS-Helper, EXE-/MSI-Fixtures, Windows-Workflow | PR-Änderungen und Assertions aus vorherigen Abnahmeschritten geprüft | [P112 Windows #42498187685](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42498187685) SUCCESS; 11 EXE-/4 MSI-Fälle, installierte VST3/P74, P107–P112 Negatives | **PASS für harmloses Fixture**; Hersteller-UAC/Reboot/Child-Prozesse NOT RUN |
| P68/P72/P74 `run_vst3_auto_discovery.py`, `run_plugin_onboarding.py`, `run_universal_qa.py` | zentrale Pfade, Funktionen, Freigabe-/Hash-Semantik und Statusverträge geprüft; nicht sämtliche transitiven GUI- und Native-Fixtures | bestehende P74-Integration aus P106 erfolgreich, ohne freigegebenen Produktplan | **PARTIAL**, vollständiges Per-Control-/Produktinventar NOT VERIFIED |
| P91 `run_reaper_daw_qa.py`, `reaper_qa_driver.lua`, `test_p91_reaper_daw_qa.py` und REAPER-Workflow | Eingabe-/Kernprozess-/Output-/Testorakel-Pfade einschließlich Negativkontrolle gelesen | [P113 RED #42516565467](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516565467) und [P113 Windows Unit GREEN #42516681961](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516681961); genuine [REAPER #42393638707](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42393638707) vom 07.11. | **PASS** für Namen-Korrektur-Unit-Test; tatsächliche geladene DLL-Herkunft **NOT VERIFIED** |
| P92 `tests/test_p92_reaper_midi_audio.py`, `.github/workflows/p92-reaper-real-midi-audio.yml` | Workflow und Unit-Testinventar geprüft, Quellcode des hörbaren VST3-Fixtures nicht vollständig | P92 Windows-Unit-Regressionen; genuine DAW-Ergebnisse separat auswerten | **PARTIAL** |
| P56/P58 `src/physical_asio.cpp`, `tests/run_physical_asio.py`, `tests/test_physical_asio.py` | native Callback-Engine teilweise geprüft, Python-Vertrags-/Fehlerpfade und Unit-Testinventar geprüft | native Windows-Compile-/Negativtests existieren | **PARTIAL**; echte Hardware-/Driver-Callbacks **NOT VERIFIED** |
| P90 `tests/run_external_daw_capture_check.py` | Quellenvertrags-, Audiovergleichs- und Herkunftsstatus geprüft | Keine reale Nutzeraufnahme in diesem Audit | **NOT VERIFIED** |
| GUI/State/DSP: `src/gui_host.cpp` (164.473 Byte), `src/main.cpp`, `src/state_stress.cpp`, weitere `src/`-Dateien sowie ca. 150 weitere Python-Testdateien | **Nicht vollständig Zeile für Zeile geprüft**; Git-Baum und zentrale entrypoints inventarisiert | Breite CI-Historie ersetzt hier nicht komplette Source-/Testorakelinspektion | **NOT VERIFIED** |
| Vollständiger VST3-Validator, universelles 125A-Testlabor, echte DAW-/ASIO-Gesamtabnahme und User-spezifische Produkte | Kein vollständiges unabhängiges Tracing jeder Anforderung zu Code, UI, Audio, State und Tests | Teilnachweise vorhanden, nicht als einheitlich vollständiger Produktvertrag | **NOT VERIFIED** |

**Wichtig:** `319 Dateien inventarisiert` bedeutet **nicht** `319 Dateien vollständig gelesen`. Alle nicht vollständig geprüften Quellbereiche und Testassertions bleiben offen. Deshalb darf laut Audit-Completeness-Contract kein SOURCE REVIEW COMPLETE oder FULL AUDIT behauptet werden.

## P113 – Reproduzierter neuer False-PASS in der DAW-Testqualität

**Vertrag:** Ein P91-Testplan benennt einen bestimmten VST3-Effekt. Ein anderer tatsächlich beobachteter Effekt darf auch dann keinen DAW-PASS erzeugen, wenn Save/Reload, MIDI-Noten und PCM-Rendertest übereinstimmen.

**Vorheriger Produktionspfad:** `tests/run_reaper_daw_qa.py` prüfte nach REAPER-Setup nur, dass der zurückgemeldete `fx_name` nicht leer ist; im Reload erforderte er ausschließlich Übereinstimmung mit der Setup-Phase. Eine Übereinstimmung mit `plan["plugin"]["reaper_fx_name"]` wurde **nie geprüft**. Auch der alte „positive“ Mocktest nutzte einen nicht übereinstimmenden FX-Namen, ohne dass der Test rot wurde. Testmangel und Produktionsursache begünstigten einander.

**Negativkontrolle:** `test_foreign_plugin_fx_identity_must_not_pass` simuliert denselben guten MIDI/PCM-Renderprozess, meldet aber in **beiden** Phasen `VST3i: Totally Different Synth (OtherVendor)`, obwohl der genehmigte Plan `125A QA Synth` verlangt. Der Test fordert FAIL.

- [**P113 RED** Windows #42516565467](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516565467): Der zusätzliche Unit-Test scheiterte exakt mit `AssertionError: 'REAL_REAPER_DAW_PIPELINE_PASS' != 'FAIL'`. **Echter nachgewiesener Testorakel-/Quellfehler**, keine ungültige Fixture.
- Fix: neuer `observed_fx_matches_request(requested, actual)`-Gate in `tests/run_reaper_daw_qa.py`; prüft den genehmigten Effektnamen sowohl bei Setup als auch Reload, berücksichtigt legitimes REAPER-`VST3i:`-Präfix und angehängtes Anbieter-Suffix. Die alten Positiv-/Negativfixtures wurden auf den tatsächlich **genehmigten** FX-Namen korrigiert.
- [**P113 Unit GREEN** Windows #42516681961](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516681961): **PASS**. Testfall reagiert auf fremden FX mit FAIL und der gültige Adapterpfad bleibt grün.
- **Restrisiko:** Der Displayname ist **kein** kryptografischer oder OS-Loader-Beleg für den geladenen Dateipfad. REAPER kann legitimerweise `VST3i: ... (Vendor)` als Name anzeigen. Eine andere DLL mit derselben VST3-Darstellungsbezeichnung wäre mit diesem Gate noch nicht ausgeschlossen.

### P91 genuine DAW – präziser als bisherige Statusangaben

[REAPER Windows #42393638707](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42393638707) hat tatsächlich REAPER **7.83/x64** installiert, ein source-built 125A-VST3 geladen, das Projekt gespeichert, wieder geöffnet und mit REAPER CLI **88.200 Frames / 44,1 kHz / 24 Bit Stereo** gerendert. `REAL_REAPER_DAW_PIPELINE_PASS` wurde dokumentiert; `rms=0` war für das spezielle stille GUI-Click-Fixture erwartet. Der Report markierte ausdrücklich `loaded_module_file_provenance=NOT INDEPENDENTLY VERIFIED` und `physical_asio_hardware=NOT RUN`. Frühere pauschale Aussagen „keine echte DAW getestet“ sind dadurch **korrigiert**: echte REAPER-Integration **JA**, vollständige Produkt-/DLL-/Hardwareidentität **NEIN**.

[P113 Provenienzblocker #136](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/136) dokumentiert die verbleibende Zuordnung von angefordertem VST3 zu tatsächlich geladenen Bytes.

## Kritische ungetestete Hypothesen und Qualitätsrisiken

- Unterschiedlicher VST3-Binärcode unter demselben DAW-Anzeigenamen; im P91-Report weiterhin `loaded_module_file_provenance=NOT INDEPENDENTLY VERIFIED`.
- Physische ASIO-Treiber und reale Audiointerfaces auf einem eigenen Windows-Rechner; erfolgreiche Treiber-Compiletests, virtuelle Schleifen oder REAPER ohne physisches ASIO gelten hier nicht als PASS.
- Event-/GUI-/Controller-Mapping, dynamische Editor-Controls und per-Parameter-Default/Automation/Recall über **alle** aktuellen und zukünftigen Produkte; kein vollständiger bidirektionaler Inventarvertrag/Owner-Acceptance im vorliegenden Audit.
- Installer-Artefakte mit UAC/GUI, Reboot, Kindprozessen, privilegierter Registry-/Treiberinstallation, NTFS-Races und beabsichtigten Dateiänderungen **außerhalb** des VST3-Bundles.
- Unabhängiger Zweitreview aller 319 Dateien inklusive kompletter Testassertions und Native-Hosting-ABI; **nicht ausgeführt**.
- RELEASE-BASELINE-GATE ist projektspezifisch erst bei unabhängig freigegebenem Originalstand zu bescheinigen; eine beliebige neue Draft-PR ist keine gebilligte Release-Baseline.

## getrennte Freigabe-Gates

| Gate | Status |
| --- | --- |
| P106–P112 Windows-Installer-Testfixtures | **PASS**, aber nur Fixturescope |
| P113 neue negative Fremd-FX-Identitätskontrolle | **PASS als Windows Unit** |
| Echte REAPER-Save/Reload/Render-Integration für source-built Fixture | **PASS am 07.11.2026**; konkrete Nachweise oben |
| Unabhängige tatsächlich geladene VST3-DLL-Identität | **NOT VERIFIED** |
| Product/Control/GUI-/DSP-/State-Komplettinventar inklusive vollständigem Code-Audit | **NOT VERIFIED** |
| Native physische ASIO-Hardware | **NOT RUN** |
| Hersteller-EXE/MSI mit Installer-UI, Reboot, UAC | **NOT RUN** |
| Unabhängiger zweiter Reviewer / unabhängiger FULL AUDIT | **NOT RUN** |
| Full release / Merge aller offenen Änderungen | **NO-GO** |

**Daher:** Dieser dokumentierte Pass ist ein wichtiger *Teil* des adversarialen Gesamtaudits, aber weder ein abgeschlossener unabhängiger FULL AUDIT noch eine Berechtigung, blind in `main` zu mergen.

## P113 echte DAW-Abnahme NACH Fix (zusätzliche Windows-Belege)

Der vorstehende RED/Unit-GREEN-Nachweis wurde unabhängig von Unit-Mocks auch durch beide **echten** REAPER-Workflows ergänzt (jeder startete eine tatsächlich installierte REAPER-7.83-Windows-Instanz):

- [**P91 REAPER genuine Windows #42516682023**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516682023): **SUCCESS**. `REAL_REAPER_DAW_PIPELINE_PASS`, beobachteter Name `VST3i: 125A GUI Click Fixture (125A Internal Test Infrastructure)` entspricht dem genehmigten Suchnamen `VST3: 125A GUI Click Fixture`; erwartungsgemäß Stille `rms=0.0`. Setup, Save, Reload und REAPER-Render wurden erneut geprüft.
- [**P92 REAPER genuine Windows #42516681858**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516681858): **SUCCESS**. Echtes source-built MIDI-VST3 bei vorhandener Note: `rms=0.0806226`, `peak=0.1999999`, `audible_in_render=true`. Derselbe Prozess und dieselbe VST3 bei **fehlender Note**: `rms=0.0`, `peak=0`, `audible_in_render=false`; der Workflow verglich beide kausal und meldete `P92 genuine REAPER audio causality PASS; audible MIDI vs silent no-note`. Beide API/CLI- und Unit-Testjobs erfolgreich.
- [**P91 Windows unit #42516681961**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516681961): **SUCCESS**, inklusive P113-Fremd-Effekt-Negativkontrolle.

**Erweitertes Gate-Urteil:** P91/P92 echte REAPER-Lade-/Save-/Reload- und MIDI-Audio-Kausalitätsprüfung mit nach dem P113-Fix beobachtetem, genehmigten **Anzeigenamen: PASS für die beiden Testfixtures**. Trotzdem bleibt `loaded_module_file_provenance=NOT INDEPENDENTLY VERIFIED` ausdrücklich im REAPER-Report, und echte physische ASIO-Hardware `NOT RUN`. Echte Tests sind kein vollständiger unabhängiger Quell-Audit der 319 Repository-Dateien.

## P114 – native Subprozess-Timeout verliert verpflichtenden QA-Fehlerbericht

**Auditbefund:** `tests/run_universal_qa.py` behandelte `OSError/ValueError/KeyError/TypeError` im eigentlichen P74-Pipeline-Runner, nicht aber `subprocess.TimeoutExpired` und `subprocess.CalledProcessError`. Bei einer Fristüberschreitung des tatsächlichen GUI-/VST3-Hosts propagiert die Exception nach außen. Der zuvor bereits initialisierte `UNIVERSAL-QA-RESULT.json`-Zielpfad wird nicht mehr geschrieben. Das gilt dem strengen `FAIL with durable evidence`-Vertrag als No-Go, auch wenn ein nichtnull Prozessstatus den Workflow insgesamt blockiert.

**Gezielte Gegenprobe:** `test_child_timeout_emits_explicit_fail_report` in `tests/test_universal_qa.py` ersetzt nur die native `onboarding`-Ausführung durch eine kontrollierte `subprocess.TimeoutExpired`. Sie verlangt vom echten `execute()`-Pfad `status=FAIL`, `release_approved=false`, ein nichtleeres `faults`-Array und eine tatsächlich neu geschriebene JSON-Datei.

- [**RED P114 Windows #42517771058**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42517771058): die Gegenprobe meldete `ERROR` mit unaufgefangener `subprocess.TimeoutExpired`, kein geordneter QA-FAIL-Report. Das ist ein **echter Fehler der Fehlerberichterstattung**, kein falsch positiver PASS des ausführenden GitHub-Workflows.
- **Fix:** `subprocess`-Exceptionklassen `TimeoutExpired` und `CalledProcessError` werden im P74-Runner und in der oberen CLI-Exceptionbehandlung aufgenommen. Die Pipeline schreibt bei diesem Ereignis wie bei anderen kontrolliert fehlgeschlagenen Schritten einen expliziten `FAIL`-Bericht, ohne Releases zu genehmigen.
- [**P114 GREEN Windows P74 #42517821020**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42517821020): Unit-Regressionsjob `fail-closed-contract` **SUCCESS** am Fixcommit `696894dcdc1ee5071acc1a2e5c2b4a2afee700e3`. Die echte native VST3-E2E-Jobauswertung separat erforderlich.

**Scope:** Ein einzelner kontrollierter Timeoutfall beweist nicht vollständige Systemrobustheit bei `KeyboardInterrupt`, Prozess-Crash ohne Python-Catch, Betriebssystem-Ende, out-of-disk, Teilbaum-Kill oder jeglicher nicht erfasster Python-Exception. Solche Ereignisse bleiben `NOT VERIFIED`, nicht `PASS`.
