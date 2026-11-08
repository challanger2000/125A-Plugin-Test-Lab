# P106–P111 – Abschließende, adversariale Installer-Abnahme (08.11.2026)

## Urteil / Scope

**SCOPED TECHNICAL ACCEPTANCE: PASS** für die im PR neu hinzugefügte, quellcodebasierte Windows-EXE/MSI-Installerstrecke mit den tatsächlich ausgeführten, harmlosen Testpaketen.

**FULL AUDIT: NOT VERIFIED / QA RELEASE: NO-GO / MERGE: HOLD.** Diese Beurteilung ist eine **adversariale Eigen-Gegenprüfung** der Entwicklung und kein unabhängiges Gutachten einer zweiten Person oder eines zweiten Auditors. Sie ersetzt keinen vollständigen Audit aller älteren Plugin-Test-Lab-Subsysteme, keine reale Herstellerpaketabnahme und keine DAW-/ASIO-Abnahme.

- Repository: `challanger2000/125A-Plugin-Test-Lab`
- PR: [#132](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/132); Entwicklungsbranch `feature/p106-universal-windows-installer`; Basis `main` bei `bc839e345bfc5657f9196f7db8d6945584e1bec7`.
- **Exakt geprüfter P111-Codecommit:** `7f1a06a2886f998d1f5d14f5506b46a6e9d8309b`.
- Ausführungsumgebung: GitHub-hosted `windows-2022`, Windows PowerShell 5.1, Visual Studio 2022, source-built VST3/Hosts, pinned WiX 6.0.2; Python nur auf dem Windows-CI-Runner für den bereits vorhandenen P74-Host.
- Vorgaben: `125A-Engineering/START-HERE.md`, `QA/AUDIT-COMPLETENESS-CONTRACT.md`, `QA/RELEASE-QA.md`, `STANDARDS/SOURCE-BASELINE-GATE.md` und projektspezifische P106-Beschreibung. Keine Änderung eines bestehenden Kundenplugins.

## Inventar der geänderten PR-Oberflächen

**13 geänderte Dateien**, davon **8 PowerShell-Skripte**, **1 C#-Fixture**, **1 WiX-MSI-Fixture**, **1 Marker-Testdatei**, **1 GitHub-Actions-Workflow** und **1 Produktdokumentation**.

| Surface | Produktionspfad / Vertrag | Auditstatus |
| --- | --- | --- |
| `tests/Invoke-UniversalInstaller.ps1` | SHA-/Signatur-/Zustimmungsprüfung, EXE/msiexec, Timeout, tatsächlicher Dateinachweis, JSON | Code geprüft; Windows-fixture PASS |
| `tests/Invoke-InstalledVst3QA.ps1` | Unveränderter Installer-/Modulnachweis, P74-Handoff, strikte P74-Statusprüfung, ganze Bundle-Manifestprüfung vor/nach P74 | Code geprüft; Windows-fixture PASS |
| `tests/Get-Vst3BundleManifest.ps1` | Manifest v2 für Dateien UND Verzeichnisse | Code geprüft; Windows-fixture PASS |
| `tests/Test-Vst3BundleManifest.ps1` | Vollständigkeit, Pfade, Hashes, Reparse/Hardlinks, Leerordner | Code geprüft; Windows-fixture PASS |
| `tests/P109-LinkCount.ps1` | Win32-Handle-Linkzählung für NTFS-Hardlinks | Code geprüft; Windows-fixture PASS |
| `tests/Test-UniversalInstaller.ps1` | 11 tatsächliche EXE-Fallprüfungen | Assertions geprüft; Windows PASS |
| `tests/Test-UniversalMSI.ps1` | 4 echte MSI-/msiexec-Fallprüfungen | Assertions geprüft; Windows PASS |
| `tests/Test-InstalledVst3Handoff.ps1` | Komplette Kopie, P74-Positivtest und fehlerhafte Berichte/Dateibäume | Assertions geprüft; Windows PASS |
| `tests/p106_installer_fixture.cs` | Harmloser EXE-Prozess mit Dateibaum-Kopie inkl. Leerordner | Code geprüft; tatsächlicher Windows-Prozess PASS |
| `tests/p106_msi_fixture.wxs` | Harmloses per-user-MSI; kein fremdes Herstellerpaket | Code geprüft; msiexec PASS |
| `tests/p106-msi-marker.txt` | Unabhängig erwartete MSI-Markerbytes | Geprüfter Fixturescope |
| `.github/workflows/p106-universal-installer.yml` | Windows-CI mit Fail-fast-Parser, realer EXE/MSI und installiertem VST3 | Workflow/Logs geprüft |
| `docs/P106-UNIVERSAL-WINDOWS-INSTALLER.md` | Nutzervertrag, CLI und Grenzen der Evidenz | Geprüft |

**Nicht als vollständig unabhängig quellengeprüft:** die bereits vor P106 vorhandenen umfangreichen P74-Python-/C++-Implementierungen, alle sonstigen Test-Lab-Funktionen und ihre Tests. Ihre erfolgreiche **Ausführung** ist nicht gleichbedeutend mit umfassendem Source-Audit. Kunden-/Vollprodukt-GUI- und Kontrollinventar, ASIO und DAW sind außerhalb des ausgeführten Fixturescopes.

## Nachweismatrix (Status getrennt)

| Pflichtvertrag / beobachtbarer Sollwert | Positiv & adversarialer Gegenbeweis | Ausgeführte Evidenz | Ergebnis / Restrisiko |
| --- | --- | --- | --- |
| EXE nicht ungefragt ausführen; SHA/Signatur prüfen | Read-only, Hash falsch, unsigned ohne Opt-in, Zustimmung fehlt; harmloser Installer erzeugt exakt bekannte Datei | [P111 Green CI #42494085355](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42494085355), 11/11 EXE | **PASS** für Fixture; echter Anbieter NOT RUN |
| MSI wirklich durch Windows Installer ausführen | per-user-MSI erzeugt gehashte Datei; Inspect, Consent und Stale-Negative | selbe CI, 4/4 MSI | **PASS** für Fixture; Admin/UAC/Reboot NOT RUN |
| Timeout/Abbruch und falschen Zero-Exit erkennen | absichtlich 8 Sekunden verzögerter EXE bei 5s Deadline, unvollständige und falsche Dateien | selbe CI, gezielte Negativfälle | **PASS** für Hauptprozess; Child-Prozesse/strikter Rollback NOT RUN |
| Nachweis darf vor P74 nicht gefälscht sein | sechs gezielt veränderte JSON-Berichte (Exit, DAW, VST3-QA, Fehler, Installer-SHA, Modul-SHA) | selbe CI, 6/6 korrekt vor P74 abgewiesen | **PASS** für kontrollierte Inkonstanzen; lokales JSON ist keine kryptografische Fernattestierung |
| Tatsächlich installiertes VST3 statt Buildkopie prüfen | EXE kopiert VST3 in neuen Pfad, unabhängiger SHA, P74 prüft diese Kopie | selbe CI: native P74 GUI/ABI + Audio/State PASS | **PASS** für quellcodebasiertes Fixture; realer Hersteller-VST3 NOT RUN |
| Ressourcen des gesamten VST3-Bundles | positive Dateiliste und nachgelagerte Hashes; veränderte, fehlende, zusätzliche Datei, falscher Manifest-SHA | selbe CI, P109 vier Negativkontrollen | **PASS**, wenn Manifest explizit unabhängig gepinnt; ohne Manifest `NOT VERIFIED` |
| NTFS-Hardlink/Manifest-Traversal | echter Hardlink auf externe Datei und neu gehashtes `../`-Manifest werden zurückgewiesen | selbe CI, P110 | **PASS** für Fixture; alternative Dateiströme/TOCTOU NOT RUN |
| **P111 leere, aber erforderliche Verzeichnisse** | source-built EXE verliert vor der Reparatur einen Leerordner; Soll ist vollständiger Tree; nach Fix fehlenden und zusätzlichen Leerordner zurückweisen | **RED** [#42493968858](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42493968858) mit `P111 discovered installer false PASS: required empty VST3 directory absent`; **GREEN** [#42494085355](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42494085355) mit beiden falsifizierenden Negativfällen | **PASS NACH REPARATUR**; v1-Dateimanifeste nicht fälschlich als vollständiges v2-Manifest anerkennen |
| Tatsächlicher Herstellerinstaller inklusive grafischer Interaktion, UAC, Reboot, Treiber und Deinstallation/Rollback | Kein freigegebenes echtes Herstellerpaket in CI | Keine entsprechende CI-/Windows- oder Kundenaufnahme | **NOT RUN – BLOCKER für universelle Produktabnahme** |
| Reale DAW/ASIO und separater unabhängiger Gesamtaudit | Kein vollständiger, unabhängig überprüfter Kontroll-, Driver-, Host- oder Reviewer-Nachweis | Kein gültiger Gesamtnachweis | **NOT VERIFIED – BLOCKER** |

## Neuer Root-Cause-Befund: P111 (HIGH im Installer-Vollständigkeitsvertrag)

**Erwartung:** Ein VST3-Installationsvorgang muss alle freigegebenen und für die Funktion erforderlichen Dateien **und Verzeichnisse** vollständig übertragen oder nach der Installation explizit als nicht vollständig verifiziert markiert werden.

**Tatsächliche Ausgangslage:** Das source-built EXE-Fixture kopierte nur gefundene Dateien und legte nur deren übergeordnete Verzeichnisse an. Das P109-Manifest v1 enthielt selbst nur Dateipfade. Ein erforderlicher Leerordner verschwand, ohne dass die vorherigen Hash-/Manifest- und P74-Tests dies entdecken konnten.

**Adversarialer Nachweis:** Bei unveränderter Copy-Implementierung erzeugte die neue Quelle einen leeren `Contents/Resources/P111-required-empty-directory`; [RED #42493968858](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42493968858) scheiterte genau an der fehlenden Verzeichnisübertragung, nicht an einem ungültigen Testfixture.

**Reparatur:** Installer-Fixture kopiert die gesamte Ordnerstruktur; das Manifest wurde auf `125a-vst3-whole-bundle-sha256-v2` mit Verzeichnisliste erweitert; der Verifier vergleicht den gesamten tatsächlichen Dateibaum vor P74. Fehlen eines freigegebenen Leerordners und Hinzufügen eines fremden Leerordners müssen **vor P74** fehlschlagen. [GREEN #42494085355](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42494085355) bestätigt Positivpfad und beide Negativfälle. [Befund #133](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/133).

**Warum frühere Prüfungen dies übersahen:** Alle vorherigen positiven Bundles und Negativtests waren **dateiorientiert**. Sie veränderten oder verglichen vorhandene Dateien, aber nie einen legitimen, leeren Quellordner. Die Tests wurden dadurch auch mit einer unvollständigen Installation grün.

## Echte noch offene Voraussetzungen für die vollständige Abschlussfreigabe

1. **Herstellerpaket**: separat autorisiertes, exakt SHA-256-gepinntes echtes Windows-EXE/MSI in isolierter, wiederverwendbarer Test-VM; Herstelleroptionen, Silent-/interaktiver UI-Pfad, Zielpfade, UAC und Deinstallations-/Neustart-Szenario prüfen. Ohne solches Paket ist der Anspruch **universell für Hersteller-Installer** nicht abgenommen.
2. **Vollständiger unabhängiger Code-Audit** des Test Labs nach dem verbindlichen QA-Contract – über PR #132 hinaus, einschließlich Produktionspfade, Regressionen, Testorakel, GUI, Audiopipelines und ungetesteten Integrations-/Lebenszykluspfaden. Eine Eigen-Gegenprüfung durch den Implementierer erfüllt nicht die unabhängige zweite Prüfung.
3. **Anwendungs-/Hardwarebelege**, soweit zum beworbenen Umfang gehörig: tatsächliches Windows-VST3 in einer realen DAW, dynamische GUI-/Controller-Aktionen, state recall, reale ASIO/Driver-Callbacks; GitHub-Workflow mit simulierten/virtuellen Audioquellen reicht nicht.
4. **Installer-Ausführung bleibt nicht sandboxed.** Externe Child-Prozesse, privilegierte Systemeingriffe, Dateirennen, Symlink-Ahnen/ADS und Auswirkungen außerhalb des VST3-Bundles sind nicht umfassend abgesichert.

## Gate-Entscheidung

- **P106–P111 scoped Windows-Regression nach P111: PASS** auf exakt dokumentiertem Commit.
- **PR-Source- und Tester-Review: adversariale Eigenprüfung durchgeführt; zweiter unabhängiger Reviewer NOT RUN.**
- **Gesamtes 125A Plugin Test Lab FULL AUDIT: NOT VERIFIED.**
- **Freigabe für universelle Herstellerinstaller: NO-GO.**
- **Merge/FINAL/Gumroad/Produktfreigabe: NICHT erteilt.** PR #132 bleibt Draft; keine Änderung an `main`.

Diese Abnahme dokumentiert ein nachweislich bestandenes Teilziel **und** einen aus den zuvor grünen Tests aufgedeckten Fehler. Sie bescheinigt weder Fehlerfreiheit noch ungetestete Hersteller-, DAW- oder Hardwarefunktionen.
