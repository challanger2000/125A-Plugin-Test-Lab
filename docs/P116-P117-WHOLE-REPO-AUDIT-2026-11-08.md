# 125A Plugin Test Lab – repositoryweiter adversarialer Auditabschluss (08.11.2026)

## Prüfurteil und Evidenz

**Audit-Entscheidung: FULL AUDIT = NO-GO / NOT VERIFIED.** Das ist das **abschließende Prüfurteil dieses Auditdurchlaufs**, nicht die Ankündigung eines künftigen Berichts. Ungetestete Bereiche dürfen gemäß `125A-Engineering/QA/AUDIT-COMPLETENESS-CONTRACT.md` niemals durch die bestandenen Teilprüfungen als PASS gelten. Keine Releasefreigabe und kein Merge.

**Verifizierte Teilergebnisse:** Windows-Quell-/Build-/Unit-Sweep **SUCCESS**; echte REAPER-7.83-Integration P91/P92 **SUCCESS**; P106–P112 Installer-Fixtures **SUCCESS**; neu entdeckte kritische/hohe Testorakel- und Fehlerbericht-Mängel P113–P115/P117 nach echten RED/GREEN-Prüfungen behoben. Das beseitigt nicht die ausdrücklich offenen Hardware-, Hersteller-, Produkt- und vollständigen Source-Review-Gates.

**Unabhängigkeit:** Der gesamte Entwicklungs-/Auditdurchlauf wurde durch **denselben Assistenten** ausgeführt. Gezielte Negativfixtures und selbständig gemessene Windows-Läufe sind reproduzierbare *Gegenproben*, jedoch keine organisatorisch unabhängige zweite Source-Prüfung. `INDEPENDENT SECOND REVIEW = NOT RUN`. Die Bezeichnung dieses Branches als `audit/` ändert diese Tatsache nicht.

### Geprüfter Source-Zustand und weitere Abstammung

- Basis-Repository `challanger2000/125A-Plugin-Test-Lab`, `main` bei `bc839e345bfc5657f9196f7db8d6945584e1bec7`; P106–P112 zunächst auf Draft-PR [#132](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/132) SHA `10fe2e59088efd15fe3287729f227637b4ddbdcc`.
- Separater Code-/Auditbranch `audit/2026-11-08-full-test-lab-review`, Draft-PR [#137](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/137).
- Auf dem **P116-CI-SHA `77985a541c117f21eef7ec53b01eb1cdbe23e9e5`** sind laut echter Git-Arbeitsbaum-Inventur **321 getrackte Dateien** inventarisiert, namentlich und mit **SHA256 pro Datei**. **203 aus Python-AST erkannte Testfunktionen** und **0 Python-Syntaxfehler**. 60+ GitHub Workflows im Projekt, darunter hardware- und VM-spezifische gated Workflows.
- Die durchgeführten Repo-/Dokument-Sichten umfassten `125A-Engineering/START-HERE.md`, `QA/AUDIT-COMPLETENESS-CONTRACT.md`, `QA/RELEASE-QA.md`, `STANDARDS/SOURCE-BASELINE-GATE.md`, die ca. 316-KB `ENGINEERING-GUARDRAILS.md`, die komplette Test-Lab-`START-HERE.md` sowie die README und relevanten P91–P116-Workflows. Der komplette native `src/`-Dateisatz (11 Dateien) wurde auf offensichtliche unsichere Aufrufe und Release-kompilierte `assert()`-Verwendung geprüft. Diese maschinelle Bestandsaufnahme ist ausdrücklich **kein vollständiges semantisches Lesen jeder Zeile und jedes Aufrufs**.

## P116 – alle bekannten generischen Python-Unittests und First-Party-C++-Hosts unter Windows

**Primärnachweis:** [P116 Windows-2022 Actions #42520168710](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42520168710), Job `whole-repo-automated-sweep` = **SUCCESS** am exakten `77985a541...`-Commit. Artifact `P116-whole-repo-native-and-python-source-test-evidence-NOT-full-audit` (GitHub Actions Artifact ID `13633247097`).

| Gate | Tatsächliche Probe | Ergebnis |
| --- | --- | --- |
| Quell- und Testinventur | Git `ls-files` mit pro-Datei SHA/Größe, Python-AST-Parsing, erkannte Tests | **321 Dateien erfasst, 203 AST-Testfunktionen, 0 Python-Parsefehler** |
| Native Windows-Lab-Binaries | VS2022 x64 Release: `TestLabHost`, `TestLabGUI`, `TestLabStateStress`, `TestLabRecovery`, `TestLabInstanceIsolation`, `TestLabRateBlock`, `TestLabVoiceStress`, `TestLabControllerRecovery`, `TestLabGuiRecovery` | **Alle gelisteten First-Party-Ziele gebaut** |
| Registrierte native CTests | `ctest --test-dir build -C Release --output-on-failure` | **2/2 PASS**: `transport_selftest`, `invalid_plugin_rejected` |
| Alle importierbaren Python-Unittest-Module | 42 mit AST als echte Testklassen ausgewiesene `tests/test_*.py`-Module; `unittest.TextTestRunner` | **216 Tests, 0 FAIL, 0 ERROR, 0 SKIP** |
| Python-Testskripte mit eigener CLI | 26 Dateien namens `test_*.py` sind **keine importierbaren Unittest-Module**, sondern eigenständige CLIs mit verpflichtenden Argumenten | **NICHT im P116-Unittest-Sweep ausgeführt**, andere produktspezifische Workflows teilweise vorhanden; separate Evidenz erforderlich |
| Reale ASIO-Hardware + beliebiger Vendor-Installer + Kundenprodukt | Kein solcher Job im P116-Sweep | **NOT RUN** |

**Auditfehler im ersten Sweep:** [P116 RED #42519883971](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42519883971) versuchte alle `test_*.py` als `unittest` zu importieren. Genau `test_audio_reference.py` und `test_native_gui_snapshot.py` parsten bereits beim Import CLI-Argumente und führten zu `SystemExit(2)`. Dieses **Test-Harness-/Discovery-Problem**, nicht ein bewiesener Pluginfehler, wurde behoben: P116 inventarisiert die Standalone-CLIs explizit als separate, nicht aus dem Unittest-Resultat abgedeckte Gruppe. Danach 216/216 grün. Die 26 CLIs wurden **nicht stillschweigend als bestanden markiert**.

**Wichtiger Umfangsvorbehalt:** In `CMakeLists.txt` sind nur **zwei** Tests bei CTest registriert. Viele native Fixture-/Host-Torture-Prüfungen werden von individuellen GitHub-Workflows statt CTest aufgerufen. Der universelle P116-CMake-Lauf belegt Bau-/Verknüpfbarkeit von neun Host-Targets plus die beiden registrierten CTests; er belegt **nicht** sämtliche nicht registrierten native Codepfade als ausgeführt.

## Adversariale Fehlerbefunde: wiederholtes RED → ursächliche Korrektur → GREEN

| Fall | Tatsächlicher Fehler im zuvor grünen Umfang | RED Windows | GREEN Windows | Bewertung |
| --- | --- | --- | --- | --- |
| **P111** | EXE-Fixture verlor benötigte leere VST3-Ordner; Manifest erfasste nur Dateien | [#42493968858](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42493968858) | [#42494085355](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42494085355) | Vollständige Verzeichnisliste, Quell-/Installationsvergleich, Fehl-/Extraordner-Gegenproben; PASS |
| **P112** | NTFS ADS `P112Hidden` änderte Bundle-Zustand, ohne Hauptdatei-SHA zu ändern | [#42497526541](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42497526541) | [#42497870451](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42497870451) | Ausschließlicher namenloser `:$DATA`-Stream beim Quell-/Installmanifest; PASS |
| **P113** | REAPER-Adapter meldete PASS für **vollständig anderen FX**, solange Setup/Reload denselben falschen Namen lieferten | [#42516565467](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516565467) | [P91 Unit #42516681961](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516681961), [genuine P91 #42516682023](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516682023), [P92 #42516681858](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42516681858) | Angeforderten/geladen angezeigten Namen in beiden Phasen abgleichen; **bloßer Anzeigename ist keine OS-DLL-Attestierung** |
| **P114** | P74 verlor `UNIVERSAL-QA-RESULT.json` bei `subprocess.TimeoutExpired` | [#42517771058](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42517771058) | [#42517821020](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42517821020) | Timeout/CalledProcessError abgefangen, tatsächlicher FAIL-Bericht geschrieben; Native E2E PASS |
| **P115** | P72 verlor `PLUGIN-ONBOARDING-RESULT.json` bei nativem Timeout | [#42517976378](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42517976378) | [P72 #42518105900](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42518105900), [P73 #42518105856](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42518105856) | P72-/P73-Unit- und reale Windows-VST3-Gates PASS |
| **P117** | P91 ignorierte **Exit 42 vom Render-Subprozess**, wenn trotzdem eine gültige WAV-Datei vorhanden war; falsch `REAL_REAPER_DAW_PIPELINE_PASS` | [#42519950331](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42519950331) | [P91 Unit #42520084941](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42520084941), [P91 genuine #42520084940](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42520084940), [P92 genuine #42520084936](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42520084936) | Render-Rückgabecode `int(0)` jetzt explizit verlangt, statt WAV-Existenz als Erfolg; PASS |

Die Änderung an P117 ist in [Issue #140](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/140) dokumentiert. P113, P114, P115 in Issues [#136](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/136), [#138](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/138), [#139](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/139). Die zusätzlichen Quellreparaturen sind im separaten Auditbranch, **nicht in `main`**.

## Quell-/Schnittstellen-Tracing und negative Nachweise

| Funktionskette | Quell-/Tool-Auditstatus | Negativ-/Positivnachweise | Rest |
| --- | --- | --- | --- |
| Windows EXE/MSI-Installer → Dateibeweis → installierter VST3-Host | Direktquellen, SHA-Pinning, echten `msiexec`-Pfad, EXE-Timeout, Snapshot-/Reparse-/Hardlink-/ADS-/Datei-/Ordner-Kontrakte und JSON-Übergabe betrachtet | P106–P112 grün, jeweils echte Windows-Fixtures | Kein beliebiger Vendor-/UAC-/Reboot-/Treiberinstallertest, Kindprozess-/Dateirennen nicht bewiesen |
| Universal P68 ABI → P72 Read-only GUI → P74 echte Audio-/State-Host-Prüfung | Entscheidende Eintritts-, Fehler- und PASS-Bedingungen gelesen; P114/115-Timeoutlücken und neue Negativtests | P74, P72, P73 Native Windows RED/GREEN; P116 Unit-Sweep | Andere seltene Python Exceptions, Kernel-/Prozessabbruch und alle dynamischen Editor-/Musikvertragskanten nicht erschöpfend validiert |
| REAPER-CLI → ReaScript Setup → FX → Projekt sichern/neuladen → Render → PCM | Ganze P91-Produktionsdatei, ReaScript-/P92-Workflow-/Unit-Überprüfungen und falschen FX sowie falschen Exit als Gegenproben | P113/P117 + echte P91/P92 Windows-Sessions; P92 Noten-RMS ~0,0806226 vs ohne Note 0 | `loaded_module_file_provenance=NOT INDEPENDENTLY VERIFIED`; fremde DLL mit gleichem Namen noch denkbar |
| GUI/Controller/Parameter → Plugin DSP/State → Ausgabe | Read-only Inventur und einige GUI-Codepfade, 216 Python-Unittests, gebaute neun native Hosts | Mehrere echte Source-Fixture-Workflows, u.a. GUI-/Editor-Aktionen | **Keine vollständige Zuordnung jedes angezeigten Controls aller Plugins zu ParamID/Host/PCM/Recall**; generischer Tester kann diese nicht ohne Owner-Orakel erfinden |
| Native ASIO-Driver-Callback → VST3 `process()` → PCM/Deadlines | `src/physical_asio.cpp` (ASIO Driver COM, Callback, PCM-/Deadline-Checks) sowie P56/P58/P94/P95/P97 Workflows/Verträge quellengeprüft | Native Compile-/Negativtests existieren | Physischer Treiber/Hardware und echter Input/Output auf Benutzerrechner **NOT RUN**; virtuelle Workflows sind kein Hardware-PASS |
| CI-/Release-Gate/Quellherkunft | Alle Workflowpfade inventarisiert, Trigger- und Testscripte der 60+ YAMLs in der aktuellen Auditlinie betrachtet; P116 weist eine separat ungelaufene CLI-Gruppe aus | P116 Source-Manifest und Py AST; Build+2 CTests+216 Unittests | Keine umfassend unabhängige Prüfung jeder YAML-Shell-Zeile und jedes Kommando-Rückgabewertes, alle 60+ Workflows nicht als ein einziger vollständiger Batch ausgeführt |

### Explizite Fehler- und Testorakel-Disziplin

- **Testdetektion ≠ Testsemantik:** Importierbare Unittests sind von ausführbaren CLI-Prüfscripts zu unterscheiden; `test_*.py` ist kein hinreichendes Argument, um alle Dateien mit `unittest discover` aufzurufen.
- **Echte Integration ≠ bloßer Prozessname:** Für P91 wurde ein tatsächlich gestartetes REAPER 7.83 und echte MIDI-abhängige Audioausgabe nachgewiesen. Die exakte geladene Binärdatei wird trotzdem nicht vom OS/DAW unabhängig identifiziert.
- **Vorhandener WAV ≠ erfolgreicher Renderprozess:** P117 wurde durch absichtlich nichtnull Rückgabe, aber gültiges WAV enttarnt.
- **Prozessfehler ≠ auditable FAIL JSON:** P114/P115 lehrten, dass auch Timeout/CalledProcessError in den ausführenden Python-Grenzen aufgefangen werden müssen.
- **Datei-Hash ≠ kompletter Windows-Dateibaum:** P111, P112 belegten Verzeichnisse/ADS als fehlende Domänen.
- **Genuine negative statt Fake PASS:** Jeder RED-Lauf enthielt einen expliziten Soll-FAIL gegen das **unveränderte** schlechte Verhalten und wurde nach Korrektur positiv plus negativ erneut ausgeführt. Die roten Workflow-Conclusions werden nicht als grüne Plugin-Durchläufe umetikettiert.

## Für den FULL AUDIT und die finale Freigabe verbleibende Blocker

1. **Unabhängiger Zweitprüfer**: Kein von der Implementierung unabhängiger Reviewer hat alle technischen Pfade und Testassertions unabhängig validiert. `NOT RUN`. Ein zweites eigenes Audit-Dokument von demselben Assistenten ist kein unabhängiger Zweitprüfer.
2. **Vollständige source-level und dynamische Semantik**: Die 321 Dateien wurden inventarisiert/gehasht, 11 native Hostquellen grob auf Gefahrenmuster geprüft und zentrale Orchestratoren im Detail auditiert. Es fehlt der komplette durchgängige Beleg über **jede** Source-/Callback-/GUI-/Rendererfunktion, die vielen zusätzlichen `test_*.py`-CLI-Verträge und sämtliche YAML-Hooks. `NOT VERIFIED`.
3. **Echte physische ASIO-Hardware**: Kein mit Audient-/sonstigem physischem ASIO-Treiber verbundenes Windows-Gerät wurde im aktuellen Lauf benutzt. `NOT RUN`. Keine Phantom-Freigabe durch virtuelle/SDK-basierte Tests.
4. **Echte Hersteller-/Vendor-Installer**: P106–P112 nutzt source-built harmlosen EXE-/MSI-Testcode; beliebige Hersteller-EXE-/MSI samt UAC/Reset/Driver/Interaktionspfad `NOT RUN`.
5. **Exakte Modul- und Kundenprodukt-Provenienz**: REAPER bestätigt den FX-Anzeigenamen und audibles MIDI, nicht den tatsächlichen geladenen DLL-Pfad; das vollständige Besitzer-/Produkt-Control-/Audio-/WAV-/MIDI-Inventar benötigt externe Freigaben und realen DAW-Workflow. `NOT VERIFIED`.
6. **Reproduzierbare Snapshot-/Offline-/Multithreading-/Audio-/Host-Semantik aller Produkte** kann vom universellen Test Lab nicht ohne separate Produktverträge und unabhängige Golden-Samples automatisch abgeleitet werden. Spezifische echte P53-AWE/P47-Drumator Gates sind nicht durch P116 generisch bestanden.

### Finaler Sign-off

| Bereich | Urteil |
| --- | --- |
| P116 breit angelegter Windows x64 Native + Python Testlauf | **PASS, strikt eingeschränkter automatisch ausführbarer Scope** |
| P111–P115/P117 behobene Fehler, gezielte adversariale Windows RED/GREEN | **PASS, jeweilige gelistete Szenarien** |
| Echtes REAPER P91/P92 Speichern/Reload/Render, MIDI-Positiv/Silence-Negativ | **PASS für freigegebene Source-Fixtures** |
| Herstellerinstaller, physische ASIO-Hardware, persönliches DAW-Setup | **NOT RUN** |
| Vollständiger unabhängiger Source-/Testorakel-/Kontrollpfad-Audit | **NOT VERIFIED** |
| Gesamtrelease/FULL AUDIT/Automatische Merge-Freigabe | **NO-GO** |

**Diese Audit-Runde ist mit einem nachvollziehbaren, negativen Gesamturteil abgeschlossen.** Sie hat zusätzlich zur umfangreichen grünen technischen Regression echte früher unentdeckte Testlücken beseitigt und dokumentiert die verbleibenden ungeprüften Bereiche. Es wird **nicht** behauptet, dass ein fehlender unabhängiger zweiter Reviewer oder fehlende physische Hardware durch mehr eigene Unit-Tests ersetzt werden könnte. PR #132 und #137 bleiben **Draft und ungemergt**.

---

## P118/P119 Nachaudit: weiterer vollständiger Windows-Sweep und zwei neu nachgewiesene P75-Fehler

Der repositoryweite Audit wurde auf dem getrennten Branch `audit/2026-11-08-full-test-lab-review` fortgesetzt. Die abschließende geprüfte **Code-SHA** für diesen Nachtrag ist `a38b9e374b954321f5abdf175c16c3cabd5f202b`. Dies überschreibt **nicht** die früheren genauen SHA-Zuordnungen im Hauptbericht.

### P118: P75-Prozessfehler unterbrechen die gesamte Pluginliste

**Verletzter Vertrag:** Bei einer mehrteiligen P75-Abnahme darf ein fehlerhafter nativer Child-Prozess die folgenden Plugin-Prüfungen nicht ausfallen lassen; seine Fehlermeldung muss im strukturierten Batchbericht landen. Die bisherige Ausnahmebehandlung in `tests/run_vst3_batch_qa.py` behandelte einen `subprocess.TimeoutExpired`, aber nicht `subprocess.CalledProcessError`. Ein fehlgeschlagener Child-Prozess mit geworfener Exception brach deshalb den gesamten Batch ab.

- [**RED P75 #42521491226**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42521491226): `test_child_raised_calledprocesserror_is_isolated_and_reported` meldete die unaufgefangene `CalledProcessError(23)` als **ERROR**.
- Fix: Child- und CLI-Grenzen behandeln `CalledProcessError` kontrolliert als FAIL, die nächste unabhängig ausgewählte VST3 wird weiter geprüft. Unvollständige `runner`-Prozessresultate werden explizit abgewiesen, anstatt mit `AttributeError` aus dem Berichtspfad zu fallen.
- [**GREEN P75 #42521746503**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42521746503): `adversarial=SUCCESS`, `real-multiple-vst3=SUCCESS`. [Issue #141](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/141).

### P119: Wiederholter Batch akzeptiert alten Kindbericht fälschlich als frisch

**Nachgewiesener False-PASS:** `run_vst3_batch_qa.run()` entfernte zwar die vorherige Gesamtdatei `BATCH-QA-REPORT.json`, aber nicht `UNIVERSAL-QA-RESULT.json` in den Unterverzeichnissen. Beim erneuten Aufruf mit identischem Output-Ordner konnten korrekt passende Ergebnisse des *vorherigen* Durchlaufs von einem Child, das nur noch Exit 0 meldete, als neue Testbelege akzeptiert werden.

- Die adversariale Gegenprobe führte zunächst einen echten P75-Runner-Pfad mit zwei separat geprüften Schema-/Hash-/Host-konformen Child-Belegen aus. Beim zweiten Aufruf auf denselben `--out`-Ordner lieferte der Child-Adapter 0 **ohne ein neues JSON zu schreiben**.
- [**RED P75 #42522220724**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42522220724): bisherige Implementierung antwortete fälschlich `BATCH_TECHNICAL_PASS` statt `FAIL`.
- Fix: Vor jedem Child-Start wird das vorherige `UNIVERSAL-QA-RESULT.json` dieses Plugins entfernt. Nur ein frisch produzierter und gesondert geprüfter Resultatpfad kann PASS liefern; die vorhandenen Host-/Modul-SHA, Schema-, Coverage- und Rückgabecodeprüfungen bleiben erhalten.
- [**GREEN P75 #42522353810**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42522353810): `adversarial=SUCCESS`, `real-multiple-vst3=SUCCESS`. [Issue #142](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/142).

### P116: Ausführbare Einzelprüfer zusätzlich zu den Unittests

Der erste generische P116-Lauf hatte alle `test_*.py`-Skripte inventorisiert, aber nur die unittest-kompatiblen ausgeführt. Dies wurde durch eine zweite, echte **Windows-Subprozess-Teststrecke** behoben:

- Der aktuelle Source-Inventurlauf zählt **322 getrackte Dateien**, **205 AST-Testfunktionen**, **0 Python-Syntaxfehler**. Für jede getrackte Datei liegt ein eigener SHA-256-Eintrag im herunterladbaren CI-Artefakt.
- **Neun** zentrale Windows-x64-C++-Hostziele wurden mit Visual Studio 2022 im Release-Modus gebaut.
- **2/2 registrierte CTests PASS**.
- **218/218 Python-`unittest`-Fälle PASS**, 0 Fehler/Skips.
- **25/25 eigenständige, ohne Produkt-/Bildargumente lauffähige Python-Prüfskripte** wurden **in getrennten Windows-Prozessen** mit überprüftem tatsächlichen Returncode und begrenztem Timeout ausgeführt: **alle PASS**. `PYTHONOPTIMIZE=0` wird erzwungen, damit in solchen älteren CLI-Skripten enthaltene `assert`-Orakel nicht abgeschaltet werden.
- **Ein** separat geführter CLI-Prüfer `tests/test_native_gui_snapshot.py` benötigt als Pflicht-Eingabe eine echte Win32-HWND-BMP-Aufnahme und ist **nicht** Teil der generischen 25-Skript-Strecke. Native GUI-BMP-Funktionalität ist über P04-Workflows separat belegt, aber der komplette eigenständige Skriptaufruf wird in diesem Nachlauf korrekt als **NOT RUN** geführt.

[**P116 Windows #42522353765**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42522353765) **SUCCESS** auf `a38b9e374b954321f5abdf175c16c3cabd5f202b`; Job-/Schrittmeldungen und alle 25 einzelnen PASS-Ausgaben wurden geprüft. Der zugehörige ursprüngliche fehlerhafte neue CLI-Testlauf [#42521746591](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42521746591) war aufgrund eines JSON-Reporter-Escaping-Fehlers rot; die Quelle wurde korrigiert und mit gültiger JSON-Datei grün neu ausgeführt. Dadurch wird kein zuvor nicht ausgeführter Test fälschlich zur PASS-Zahl addiert.

### Erneutes Urteil / endgültige Gate-Grenze

**P118 + P119: REPRODUZIERT RED / GEZIELT BEHOBEN / WINDOWS GREEN.**  
**P116 Auto-Test-Vollinventur: PASS nur für tatsächlich aufgezählte 218 Unittests, 25 CLI-Skripte, 2 CTests und die neun Builds.**

Diese sehr breite automatisierte Testabnahme ist **keine vollständige unabhängige semantische Prüfung aller 322 Quelldateien**. Ein separater unabhängiger Source-Reviewer, eine echte physische ASIO-Konfiguration, ein beliebiger Herstellerinstaller, exakte REAPER-Laufzeit-DLL-Provenienz und vollständige, vom jeweiligen Pluginbesitzer freigegebene Produkt-Control-/DSP-Orakel sind weiterhin **NOT RUN / NOT VERIFIED**.

**FULL AUDIT bleibt NO-GO. PR #132 und #137 bleiben Draft/unmerged.** Weitere reine eigene, generische Unit-Tests können diese realen und unabhängigen Anforderungen nicht im Alleingang ersetzen.

---

## P120/P121 – alle 26 eigenständigen Testskripte jetzt durch reale Windows-Prüfungen abgedeckt

**Neue echte Windows-Evidenz:** Der bisher separat als `NOT RUN` geführte `tests/test_native_gui_snapshot.py` wurde in `.github/workflows/p116-full-repo-test-sweep.yml` nun ausdrücklich gegen einen **vom kompilierten Windows-GUI-Host** aufgenommenen, echten Win32-HWND-Editor-BMP ausgeführt. Dazu wurden im selben CI-Lauf `TestLabGUI` und `QAGuiClick` gebaut; der tatsächliche Host `125A_Test_Lab_GUI.exe --snapshot-editor` nahm `native-hwnd-fixture.bmp` auf. Der externe Python-Oracle prüft BMP-Header, 320×180-Bildgröße, RGB-Pixel an Position 10/10, die Ablehnung einer falschen Referenzfarbe und eine gezielte Mutation echter BMP-Bytes.

- [**P120 Windows #42523490356**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42523490356): **SUCCESS** mit tatsächlichem `P120 real HWND BMP snapshot and final standalone test script PASS`. Damit sind **25/25** unmittelbar ausführbare CLI-Skripte plus **1/1** vom nativen VST3-HWND-Capture abhängiger CLI-Prüfer unter Windows nachweislich ausgeführt. Das ist die zuvor fehlende **26.** Einzeltestskript-Abnahme; sie prüft explizit die source-built GUI-Fixture, keine beliebigen Hersteller-GUIs.
- [**P121 Windows #42523585407**](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42523585407): **SUCCESS**. Zusätzliche adversariale Negativprobe in `tests/test_plugin_quickcheck.py` simuliert einen nativen GUI-Parameter-Sweep mit tatsächlich **gültiger TSV-Evidenz**, aber **Exitcode 23**. Die bereits vorhandene Produktionsprüfung `run_plugin_quickcheck.py` verlangte bereits `sweep_proc.returncode == 0` UND `checked["status"] == "PASS"` – die Gegenprobe konnte daher **keinen Fehler nachweisen**, sondern bestätigte das bestehende korrekte Fail-closed-Verhalten. **Kein P121-Fehler, keine Scheinreparatur.**
- Der P121-HEAD-Workflow bestand den vollständigen Windows-Sweep mit nativen Builds, registrierten CTests, **219/219** Python-`unittest`-Fällen, **25/25** standalone CLIs und dem realen letzten BMP-Test. Die vorherige P120-HEAD-Version bestand 218/218 Unittests und den gleichen tatsächlichen BMP-Test. Genaue Testzahlen sind immer auf den jeweils getesteten SHA bezogen.

**Neuer vollständiger Skriptstatus:** Die ursprüngliche Lücke `26 eigenständige test_*.py, davon 25 ausgeführt und 1 unerprobt` wurde auf **26/26 unter Windows ausgeführt** geschlossen. Das ist kein allgemeiner Anspruch auf Vollständigkeit über jeden verschachtelten Produkt-/Host-/ASIO-Callback. Deren externe Abnahmen bleiben den oben dokumentierten NO-GO-Gates unterworfen. Die Prüfung aller individuellen Produktkontroll-Semantiken und ein unabhängig unterzeichneter FULL AUDIT bleiben **NOT VERIFIED**.
