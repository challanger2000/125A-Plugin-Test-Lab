# P99 — 125A Plugin Test Lab: adversarialer Auditbericht

**Datum:** 07.11.2026 · **Auditvertrag:** 125A-Engineering/QA/AUDIT-COMPLETENESS-CONTRACT.md  
**Endstatus: PARTIAL AUDIT · FEHLER NACHGEWIESEN · FULL AUDIT NICHT ERREICHT · QA NO-GO.**

## 1. Geltungsbereich und Herkunft

- Ziel: [125A-Plugin-Test-Lab](https://github.com/challanger2000/125A-Plugin-Test-Lab), Branch main, exakt **4267c86065bc8665b7af056f08af0a08760256d4** (P98).
- Adversarialer Nachweis auf **getrenntem Auditbranch**, [PR #124](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/124); produktiver Stand bleibt unverändert.
- [GitHub Actions P99 #42413119850](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42413119850), Job 128525301574: SUCCESS bedeutet **Reproduktion des Testfehlers**, NICHT Produkt-PASS. Artefakt: P99-AUDIT-KNOWN-ORACLE-GAP-NOT-RELEASE-APPROVAL mit zwei maschinenlesbaren JSON-Protokollen.
- Durchgearbeitet: 125A-Engineering/START-HERE.md und README, ENGINEERING-GUARDRAILS.md vollständig, QA/AUDIT-COMPLETENESS-CONTRACT.md, QA/RELEASE-QA.md, QA/REALTIME-QA.md, QA/AUDIO-FIXTURES.md, die einschlägigen Standards PROFESSIONAL-PLUGIN-BEHAVIOR, REPOSITORY-WORKFLOW und SOURCE-BASELINE-GATE. Im Zielrepository START-HERE.md, README und CMakeLists.txt vollständig abgerufen.
- Umgebung der **neu ausgeführten** Gegenproben: Linux/Ubuntu-GitHub-Runner mit realer Ausführung des unveränderten P95-Python-Orakels und gültigen synthetischen Float-PCM-Dateien. KEIN Windows-Audiotreiber, KEINE Hardware, KEINE DAW und KEIN Benutzerrechner benutzt.
- Externe Abhängigkeiten: Windows x64, VS 2022/C++23, VST3-SDK-Tag v3.8.1_build_84, externes ASIO-SDK Commit 496a0765b8bb9c26f764f22f9a9712a937177db2, optional REAPER und VB-CABLE/ASIO4ALL. Eine vollständige unabhängige Third-Party-Lizenz-/Security-/Hash-Abnahme liegt nicht vor.

## 2. Vollständiges Dateiverzeichnis – keine vollständige Quellcodeprüfung

Der GitHub-Git-Tree des fixierten Baselines enthält **301 Dateien mit 2.199.732 Bytes**:

| Kategorie | Dateien | Tatsächlich geprüfter Umfang |
| --- | ---: | --- |
| src (Windows-C++) | 11 | Alle Pfade und wesentlichen Funktionsgruppen inventarisiert; ASIO-Host detaillierter, GUI/Audio/State teilweise gelesen. **Nicht jede Zeile geprüft.** |
| tests (Python/PowerShell/CMD/C++/Lua) | 170 | Alle Pfade inventarisiert; Schwerpunkt P94–P97, P95-Python-Verifier und Fixtures, Quickcheck/Feature-Coverage; übrige Testkörper/Assertions unvollständig. |
| .github/workflows | 57 | P58 und P94–P99 sowie CI-Belege untersucht; übrige Workflows nicht alle vollständig gelesen. |
| docs | 55 | Projekthandbuch und einschlägige Standards/ASIO-Dokumentation; historische Dokumente nicht alle. |
| tools | 4 | Inventarisiert, nicht vollständig quellengeprüft. |
| Repositorywurzel | 4 | START-HERE, README, CMake gelesen; .gitignore nicht vollständig auditiert. |
| **Insgesamt** | **301** | **SOURCE REVIEW NOT COMPLETE.** |

**Vollständige Aufzählung der nativen Hostquellen:** src/main.cpp (Audio-/MIDI-/PCM24-Host); src/gui_host.cpp (Win32-Editor, Buttons, Dialoge, Screenshots, Parameter, Export); src/state_stress.cpp (Audiothread/Save-Konkurrenz); src/state_recovery.cpp; src/controller_recovery.cpp; src/gui_recovery.cpp; src/instance_isolation.cpp; src/rate_block.cpp; src/voice_stress.cpp; src/physical_asio.cpp (IASIO/2-in-2-out/PCM/Report); src/p15_dropfiles.h.

Die angeforderte *bidirektionale* Übersicht über **jedes** sichtbare GUI-Element, jeden VST3-Parameter, jede DSP-Route, jede Dokumentationszusage und jede passende unabhängige Testassertion konnte nicht vollständig belegt werden. Der Test-Lab-Kern kennt ohne zuvor genehmigte P65/P67-Verhaltensreferenzen nicht automatisch sämtliche Funktionen fremder Plugins. **Diese Lücken gelten ausdrücklich NICHT als PASS.**

## 3. Reproduzierte und quellenbestätigte Befunde

### F01 — HOCH: Falsches VST3-Quellsignal besteht die P95-Klangprüfung (REPRODUZIERT)

**Code:** [verify_virtual_asio_loopback.py](../tests/verify_virtual_asio_loopback.py), Funktion analyze; [QA-VST3-Generator](../tests/virtual_asio_signal_fixture.cpp); [unabhängige P99-Gegenprobe](../tests/audit_p99_oracle_counterproof.py).

Unabhängige Erwartung des Testinstruments: **317 Hz links, 557 Hz rechts** plus die deklarierten unterschiedlichen Gate-Muster. Kontrolltest mit richtigen Daten: **VIRTUAL_ASIO_PCM_LOOPBACK_PASS**.

Gezielte sichere Mutation: Ausgabe **911 Hz links und 1277 Hz rechts** bei unveränderten Gates, gültigem Datei-/Callback-/Nonce-Beleg; dazu passend zurückkehrendes PCM. Erwartung: fehlerhafter Prüfsignalgenerator muss **FAIL** ergeben. Tatsächlich: **VIRTUAL_ASIO_PCM_LOOPBACK_PASS**. Der Verifier vergleicht hauptsächlich Output- und Input-Hüllkurven miteinander, nicht den Output gegen eine unabhängige Sollfrequenz. **Falschpositiv der Testqualität bestätigt**; kein realer VST3 oder Treiber wurde dadurch als fehlerhaft bewiesen.

**Warum alte Tests es übersahen:** Die vorhandenen P95-Gegenproben prüfen Stille, Kanaltausch, kaputte Dateien, falsche Rate/Callbacks; sie verändern nicht das *Quellsignal selbst bei korrekt zurückkehrendem Audio*.

### F02 — HOCH: +12,041 dB unerlaubte Verstärkung wird als intakter Loopback akzeptiert (REPRODUZIERT)

**Code:** [verify_virtual_asio_loopback.py](../tests/verify_virtual_asio_loopback.py), analyze/normalized_correlation. Die Ausgangsdaten bleiben exakt korrekt; nur die zurückgelieferten beiden Kanäle werden **vierfach verstärkt**. Erwartet: für einen transparenten Rückweg deutlicher Level-Fehler, daher FAIL oder explizit NICHT GEPRÜFT. Tatsächlich **VIRTUAL_ASIO_PCM_LOOPBACK_PASS**. Pearson-Korrelation ist pegelinvariant, und der Prüfer hat nur untere RMS-Schwellen. Der akzeptierte Pegelfehler ist nicht durch eine unabhängige Gain-Toleranz autorisiert. **Ausgeführter echter Python-Verifier, kein ASIO-Treiberlauf.**

### F03 — MITTEL: Null-Latenz wird fälschlich als 256 Frames gemessen (REPRODUZIERT)

**Code:** derselbe P95-Verifier, Zeile 100: Die Lag-Suche startet mit **1** statt 0 bei 256-Frame-Analysefenstern. Testeingang hat gemessene Sollverzögerung **0 Samples**. Tatsächliches Ergebnis: **VIRTUAL_ASIO_PCM_LOOPBACK_PASS**, aber gemeldete **256 Frames** (etwa 5,80 ms bei 44,1 kHz). Messfehler im synthetischen Grenzfall bestätigt; keine Behauptung, dass echte Hardware 0 Frames erreichen muss.

### F04 — HOCH: ASIO-Prozesskontext setzt PPQ-Gültigkeitsflag nicht (QUELLCODE-BEFUND, Laufzeit NICHT GEPRÜFT)

**Code:** [physical_asio.cpp](../src/physical_asio.cpp) Zeile 173–175 setzt Playing/TempoValid/TimeSigValid, schreibt später jedoch projectTimeMusic **ohne kProjectTimeMusicValid**. Der gewöhnliche [main.cpp](../src/main.cpp) setzt dieses Flag; die echte QA-VST3-[signal_fixture.cpp](../tests/signal_fixture.cpp) Zeile 65 verlangt es. Die [zusätzliche P99-Quellcode-Gegenprobe](../tests/audit_p99_host_context_challenge.py) bestätigt den Widerspruch. Ein PPQ-abhängiges Plugin kann dadurch den Taktwert legitimerweise ignorieren oder process() zurückweisen.

**Grenze:** Keine tatsächliche ASIO-Callback-Ausführung mit einem auf das PPQ-Flag reagierenden VST3; konkrete Laufzeitfolge ist **Hypothese**, Flag-Vertragsverletzung ist quellenbestätigt. Nötig ist ein eventfreies, aber PPQ-validierendes reales Windows-VST3 mit Positiv-/Negativ-Hosttest.

### F05 — MITTEL: GUI-Zoom/Maximalgröße unter Windows nicht vollständig abgesichert (RISIKO, NICHT REPRODUZIERT)

**Code:** [gui_host.cpp](../src/gui_host.cpp) Zeile 73–75, 89–105 und 116–139. Das Fenster leitet alle Nachrichten an DefWindowProcW weiter; es fehlt eine explizite Behandlung von WM_GETMINMAXINFO und ein nachgewiesener Scroll-/Pan-/Rand-Interaktionstest für große oder auf 150 % skalierte Editoren. Die tatsächliche Erreichbarkeit von Buttons am rechten/unteren Rand unter kleinem Windows-Desktop ist **NICHT GEPRÜFT**. Keine unbelegte Behauptung, dass jeder Editor deshalb abgeschnitten wird.

### F06 — MITTEL: Herstelleridentität und Installationsstatus nicht zuverlässig geprüft (QUELLENFUND, AUSFÜHRUNG NICHT GEPRÜFT)

**Code:** [Prepare-VirtualASIO.ps1](../tests/Prepare-VirtualASIO.ps1) Zeile 105–113 und 150–158. Das Skript akzeptiert **jede gültige Authenticode-Signatur**, ohne zu beweisen, dass ihr Aussteller dem jeweils erwarteten ASIO4ALL/VB-CABLE-Anbieter entspricht. Zudem wird **INSTALLERS_LAUNCHED_REBOOT_REQUIRED vor beiden Start-Process-Aufrufen** gespeichert und kein Hersteller-Installer-Exitstatus geprüft. So kann ein Marker erscheinen, obwohl eine Installation noch nicht begonnen hat. **Kein Installer wurde mit Administratorrechten ausgeführt.**

### F07 — MITTEL: Versprochener lokaler Ein-Klick-Test setzt Python voraus (QUELLCODE-BEFUND)

**Code:** [Run-VST3-Test.cmd](../tests/Run-VST3-Test.cmd) Zeile 21–30 verweigert ohne py/python die Ausführung. Der weitere P97-Praxistest braucht zusätzlich Git/CMake/Visual Studio. Ein einziges CMD-Skript existiert, aber **ein sauberer Windows-Endanwender-Test ohne Entwicklungsinstallationen ist NICHT NACHGEWIESEN**. Das ist ein Nutzer-/Packaging-Vertrag, kein Beweis defekten Audio-DSP.

### F08 — NIEDRIG: Historische P56-Hinweise im Handbuch widersprechen P58ff

README und START-HERE enthalten historische Aussagen „ASIO Executor fehlt“, während die späteren P58–P98-Abschnitte und CMake einen nativen Executor aufführen. Historische Grenzen sollten eindeutig datiert sein; sonst droht falsche Aufgabenplanung. Kein Laufzeitfehlernachweis.

## 4. Anforderungs-/Abnahmematrix

| ID | Kritische Kette / Implementierung | Positiv, Negativ und unabhängiger Sollwert | Im Audit tatsächlich beobachtet | Gesamtstatus |
| --- | --- | --- | --- | --- |
| R01 | Windows-VST3-Fabrik/Host, Audio-/MIDI-Rendering, CMake, P02 | Vorherige Windows-CI mit NaN-Negativfixture; keine vollständig neue Quell-Buildmatrix | Alte CI-Nachweise, aktuelle Vollprüfung fehlt | **NOT VERIFIED** |
| R02 | MIDI-/Eventinput, Voice-Stress, Stop/Start, P29 | Vorhandene Gut/Defekt-Stimmenfixtures; keine produktspezifischen Soll-Noten geprüft | Keine neu ausgeführte Event/Instrument-Abnahme | **NOT RUN** |
| R03 | Save/Recall/Konkurrenz/Rollback/2 Instanzen, P25–P31 | Alte native Gut-/Defektfixtures; keine vollständige neue Race- und Produktzustandsmatrix | Historisches Teil-Evidenzmaterial | **NOT VERIFIED** |
| R04 | 44,1/48/96 kHz, Blockgrößen, Offline/RT, P27 | Historische Sample-/Block-Orakel | Kein kompletter neuer Vergleich aller Varianten | **NOT RUN** |
| R05 | GUI-Lifecycle, DPI, Buttons, Popup-Menüs, Pixel, P04/P42–P64 | Historische GUI-CI; neu F05 ohne realen Oversize-Test | Rand-/DPI- und Komplettbedienung ungesichert | **NOT VERIFIED** |
| R06 | Alle ABI-Parameter gegen reale GUI/DSP/Beschriftung, P35/P40/P67 | Vorhandene Controller-VST3-Gut/Defekt-Fixtures | Keine vollständige unabhängige Liste für alle Produkt-Controls | **NOT VERIFIED** |
| R07 | GUI-korrekter WAV-/MIDI-Export, P46/P76 | Historische richtige/falsche Datei-Orakel | Keine Abnahme jedes aktuellen Verkaufsplugins/ZIP | **NOT VERIFIED** |
| R08 | Batch/Timeout/Untrusted-Plugin-Isolation, P75/P89 | Historische einzelne Positiv/Negativ-Fälle | Nicht alle 170 Tests/57 Workflows vollständig geprüft | **NOT VERIFIED** |
| R09 | Echte REAPER-Datei/Save/Reopen/MIDI-Audio, P91/P92 | Alte **reale REAPER-Windows-CI**; nicht Produkt-Fender-Studio-Pro | Keine neue reale Produktsitzung | **NOT RUN** für Produktausgabe |
| R10 | P95 virtueller ASIO-Rückweg: Klang, Stereo, Pegel, Zeit | **P99 positiver Kontrollfall PASS, negative falsche Tonhöhe + 12 dB beide fälschlich PASS; 0→256 Frames** | Kontrollierter Oracle-Fehler **reproduziert** | **FAIL**; echter Treiber **NOT RUN** |
| R11 | ASIO-VST3-Prozesskontext und Takt/PPQ | Eigener Host vs. normaler Host und reales Test-VST3 | Fehlendes PPQ-Valid-Bit source-confirmed | **SOURCE FAIL**; Laufzeit **NOT RUN** |
| R12 | Physische/virtuelle Treiber-Callbacks, XRUN, deadlines, Heap, P58/P98 | Alte Windows-Compile/Negativtests | Keine echten Treiber-Callbacks oder ETW im Audit | **NOT RUN** |
| R13 | P96/P97 Treibereinrichtung, Reboot, BAT/Terminal | Windows-NOT_READY und Consent-Gates in bisheriger CI | Keine tatsächliche Installation und Neustartkontrolle | **NOT VERIFIED** |
| R14 | Lieferumfang/Abhängigkeiten/SHA/SDK/Lizenzen | Nur CMake, wesentliche Workflowinfos und Originaldokumente geprüft | Kein vollständiger Security-/Paketaudit | **NOT VERIFIED** |
| R15 | Test erkennt neue kritische Fehler | **P99: Positiv korrekt PASS; zwei valide Negativfälle falsch PASS** | Gegentest bestätigt Lücke | **FAIL** |

**N/A:** Eine FULL- oder Demo-Produktlizenzprüfung betrifft das zu testende kommerzielle VST3, nicht die Qualitätsprüfinfrastruktur als eigenständiges Release. Das Test Lab kann keinerlei fremde FULL-Version allein durch einen generischen TECHNICAL_PASS freigeben.

## 5. Qualitätssicherung des Audits

Die **neu ausgeführten** Gegenproben sind ausschließlich:
1. Richtiges Stereo-Referenzsignal → erwartetes Kontroll-PASS.
2. Gleiches Rückführungsprotokoll, aber 911/1277 Hz Quellsignal → **fehlerhaftes PASS**.
3. Richtiges Quellsignal, aber 4× verstärkter Eingang → **fehlerhaftes PASS**.
4. Zero-Lag-Test → gemeldete 256-Frame-Verzögerung.
5. Quellvergleich ProcessContext mit unabhängigen VST3-Fixtures → fehlendes Validitätsflag.

Die Original-Tests für Stille, Swap, Trunkierung, Rate, Nonce und GitHub Windows Builds wurden als vorhandene Gegenproben identifiziert, aber **nicht alle im aktuellen Audit neu ausgeführt**. Keine dieser Gegenproben darf ohne genaue SHA-/Host-Bindung als Vollabnahme übernommen werden.

**Zweiter unabhängiger Reviewer: NOT RUN.** P99 ist ein getrennter adversarialer Selbsttest mit eigener Testdatei, keine von einem unabhängigen Prüfer neu überprüfte Gesamtinventur.

## 6. Priorisierte Nacharbeiten

1. **P0:** P95-Ausgangssignal zusätzlich unabhängig gegen Soll-Frequenzen, Amplituden-/Gate-Muster, Kanalbezug und tolerierte PCM-Fehler prüfen. **Falscher 911/1277-Hz-VST3 muss FAIL ergeben.** Sollwerte nicht einfach aus der zu prüfenden Implementierung kopieren.
2. **P0:** Pegel-/Clipping-/Noise-/DC-Grenzen für tatsächlichen virtuellen Rückweg unabhängig festlegen. **4× Eingang muss FAIL ergeben**, sofern nicht ausdrücklich genehmigt.
3. **P0:** kProjectTimeMusicValid korrekt setzen und einen auf PPQ-Gültigkeit bestehenden realen source-built ASIO-VST3-Test mit mutiertem schlechten Hostkontext hinzufügen.
4. **P1:** Zero-Lag zulassen, Latenzauflösung und Unsicherheit korrekt berichten; 0 Samples darf nicht systematisch 256 Frames ergeben.
5. **P1:** GUI-Randbedienbarkeit unter 150%-DPI und kleiner Auflösung wirklich testen (inklusive WM_GETMINMAXINFO, Zoom, Scroll/Pan), nicht nur HWND-Existenz.
6. **P1:** Installer-Publisher und Hash gegen genehmigten Anbieter prüfen; Status erst nach tatsächlichem Aufruf setzen; ohne ausdrückliche Freigabe niemals Treiber installieren.
7. **P1:** Benutzerfähiges BAT/CMD-Paket ohne manuelles Kompilieren oder versteckte Python-Voraussetzung beweisen oder Voraussetzungen explizit als NOT RUN anzeigen.
8. **P1:** Ungeprüfte Quellfunktionen, 170 Testkörper und 57 Workflows vollständig nachverfolgen; alle kritischen GUI-/Audio-/Save-Ketten mit guten und gezielt fehlerhaften echten VST3s testen.
9. **P2:** Zweiter unabhängiger Auditdurchgang, Abhängigkeits-/Lizenzen-/Binary-SHA-Paketnachweis und Korrektur widersprüchlicher historischer Dokumentation.
10. **Abnahme:** Nach jeder Korrektur neue reale Windows-CI/CTest/Validator/125A-Tester-Belege auf exakt gepinntem Commit. Physische ASIO-Hardware, tatsächlicher VB-CABLE-Treiber und Produkt-DAW-Abnahme dürfen bei fehlendem Gerät **niemals PASS** erhalten.

## 7. Verbindliches Schlussurteil – getrennte Gates

| Tor | Ergebnis |
| --- | --- |
| Vollständigkeit Source-Review | **NOT VERIFIED** (301 Dateien inventorisiert, nicht alle komplett geprüft) |
| Automaten-/Funktionstests | **PARTIAL; P95 ORACLE FAIL** |
| C++-Quell-Vertragsprüfung | **PPQ FLAG FAIL**; nativer Laufzeitfehler nicht nachgewiesen |
| Windows-CI-Builds | Historische gezielte PASS vorhanden; vollständiger aktueller Gesamtaudit **NOT RUN** |
| VST3 Validator für alle aktuellen Zielprodukte | **NOT RUN** |
| 125A Plugin Tester / produktweite Auditmatrix | **NOT RUN** |
| Tatsächlicher REAPER-/kommerzieller DAW-Produktdurchlauf | **NOT RUN** |
| Tatsächlicher ASIO4ALL/VB-CABLE-Treiberloopback | **NOT RUN** |
| Physisches ASIO / analoge Hardware | **NOT RUN** |
| Zweitreview | **NOT RUN** |
| **FULL AUDIT / QA FREIGABE / RELEASE** | **NO-GO / NOT VERIFIED** |

**Ein grüner P99-Workflow bedeutet ausdrücklich, dass der vorhandene Test durch absichtlich falsche Daten überlistet werden konnte. Er ist niemals eine Freigabe.** Der produktive main-Code wurde durch diesen Audit nicht verändert.
