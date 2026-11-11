# P220 Stereo-v2 + Test Lab main: tatsächlicher Integrations-Preflight

Auftrag: [AWE #104, Projektleitungsanweisung vom 11.11.2026](https://github.com/challanger2000/125A-AWE-Synthesizer/issues/104#issuecomment-6785041464).
Dieser Bericht betrifft ausschließlich die QA-Integration im **125A Plugin Test Lab**.
Die Produkt-Engine, PCM-Berechnung und ASIO-Grenzwerte werden nicht verändert.

## Unverwechselbare Quellstände

| Rolle | Exakter Git-Identifier |
|---|---|
| Geprüftes main-Eingangssnapshot | `7213fe1f81f4036f74431cb5b2d7dbd09b73ee5c` |
| Geprüftes korrigiertes QA-Eingangssnapshot | `6cc9579714c56ee14afa8d5b1612aeeec2f4fac1` |
| Gemeinsame Basis | `2c467e03d0a90b8c8d103be443bfe37d449bbc7c` |
| **Tatsächlich kombinierter Baum** | **`1d9b5c21866f383a108768e66529bcbd97f0a3b5`** |
| **Temporärer Test-Commit dieses Baums** | **`efc78988fb0e359c1205e8d809d856902cd1ac79`** |
| CI-Instrumentierung, erster Start | `036d753c6fa66c439c2ef1bd713dee763fc5142c` |
| CI-Trigger nach Workflow-Korrektur | `7e127add47073e1559ef55eae253590f9173d347` |

Der Test-Commit ist ein **lokal/auf jedem Runner erzeugtes, nicht als Branch
veröffentlichtes** Objekt mit den zwei unveränderten Eingangssnapshots als
Parents. Kein Repository-Branch wurde gemergt oder rebased. Der bestehende
QA-Branch erhält ausschließlich CI-Instrumentierung und Dokumentation in
gewöhnlichen Folgecommits; `main` wird nicht verändert. Die im Auftrag
genannten 15 QA-only / 9 main-only Commits beziehen sich auf die beiden
Eingangssnapshots, nicht auf später hinzugefügte Instrumentierungscommits.

**CI-Trigger-SHA und tatsächlicher Test-SHA sind verschiedene Größen.**
Das bestehende Stereo-JSON-Feld `github_source_sha` bezeichnet weiterhin
`GITHUB_SHA`, also den Workflow-Trigger. Die zusätzlichen Felder
`ci_trigger_sha`, `test_sha` und `combined_tree` in `integration-verified.json`
stellen die eindeutige Zuordnung zum tatsächlich ausgeführten Quellbaum her.

## Tatsächliche Zusammenführung und Konfliktverantwortung

In einem neuen **detached** Worktree des QA-Eingangs wurde ein echter
`git merge --no-commit --no-ff` des main-Eingangs ausgeführt. Das ist kein
`git apply --check`. Es entstand genau **ein Konflikt: `START-HERE.md`**.

Verantwortung für die Auflösung: Codex, Integrations-/QA-Auftrag #104.
Erhalten wurden der vollständige QA-P220-/Stereo-v2-Vorspann und der
vollständige main-P99-Vorspann, gefolgt vom **bytegleichen** gemeinsamen
P98-und-älter-Abschnitt. Kein alter Abnahmestatus wurde umgedeutet.
Ergebnisblob: `1babe74a33783bbddc62b817a3daf1959e824aaa`.

Die übrigen **12 main-only Dateien** bleiben blobgleich zu main; die übrigen
**6 QA-only Dateien** bleiben blobgleich zum QA-Eingang. Für jeden der
**316 getrackten Pfade** wird die korrekte Elternversion bzw. ausdrücklich
aufgelöste START-Version geprüft. Vor und nach den Tests werden zusätzlich
die tatsächlichen Dateibytes, Indexbaum, HEAD-Baum und unveränderte
`refs/heads`-/`refs/remotes`-Referenzen kontrolliert. Ein absichtlich
verändertes Testskript muss die Quellstandsprüfung scheitern lassen; erst
nach bytegenauer Wiederherstellung dürfen die regulären Tests laufen.

**44 native/P90-/DAW-/ASIO-Pfade** sind in main, QA-Eingang und kombiniertem
Baum identisch, darunter sämtliche `src/`-Dateien und
`tests/run_external_daw_capture_check.py`. Die kanalweise P220-Prüfung
verwendet weiterhin den unveränderten P90-PCM-Vergleicher.
Maschinenlesbare Blobnachweise werden neben diesem Bericht veröffentlicht.

## Die neun main-only Commits

Jeder Commit wurde einschließlich kumulativer Quellen-, Test- und
Workflowänderungen geprüft. Sie betreffen P99 sowie seine P74/P75-Anbindung;
keiner verändert den nativen Host, die DAW-/P90-/ASIO-Ausführung oder DSP.

| Commit | Erhaltene Änderung |
|---|---|
| `8619a8337367bc3d0fcb6691cd8a999da3d88a78` | Explizite optionale REA/Ghidra-Beobachtung in P74/P75, fail-closed |
| `7b041e2f01a0d1caea78782bfaf0719954bf5647` | Windows-Pfadidentität und positiver Batch-Auswahltest |
| `30be60423d5ff442c2b3fd71fdfcab43dfb32b28` | Kanonische Evidence und realer Windows-Provider-Workflow |
| `c551f3ae06c03f80e6d7e96a597edc66f2d9434b` | Begrenzte, bereinigte Provider-Fehlerdiagnose |
| `0cae5c5a7adb06e3e734a136db490cc2781817f7` | Fehlende kanonische Evidence-Felder klassifizieren |
| `7913fc80bf939d859bf9344991246371bfc4e4e0` | Nicht sensible Provider-Identität bei Ablehnung |
| `d71829b76e183c8d836331644ba3d40db6d0a87a` | Zusammengesetzte REA- und verschachtelte Ghidra-Providerbindung |
| `176d4fa94e45b0d604b0429f845157bfd271c737` | Präzise historische Windows-Nachweise und Grenzen |
| `7213fe1f81f4036f74431cb5b2d7dbd09b73ee5c` | Bestehender main-Merge von P99 / PR #149 |

Die `.github/workflows/p74-universal-qa.yml`,
`.github/workflows/p99-real-rea-ghidra-windows.yml`, README,
P74/P75/P99-Dokumente sowie REA-/Universal-/Batch-Runner und ihre drei
Testsuiten bleiben unverändert aus main erhalten. P99 bleibt ausdrücklich
eine **optionale binäre Beobachtung**, kein Klang-, DAW- oder Release-PASS.

## Prüfmethodik im vorhandenen Workflow

Der bestehende [P220-Workflow](../.github/workflows/p220-awe-sf2-77-gate.yml)
erhält die kleine [temporäre Quellbaum-Instrumentierung](../tests/prepare_p220_main_integration.py).
Es gibt keinen neuen Branch, keinen neuen Workflow und keinen zweiten
Audiovergleicher. Beide Runner bauen aus denselben gepinnten Git-Objekten
denselben temporären Test-Commit. Git-Checkout und Merge erzwingen LF;
auch unter Windows werden die tatsächlichen Dateibytes gegen die Git-Blobs
geprüft. **Alle fachlichen Tests laufen mit dem kombinierten Worktree als
Arbeitsverzeichnis**, nicht mit dem Instrumentierungs-Checkout.

Der bestehende Vergleich bleibt `p220-stereo-v2`; die gezielten
Stereo-Regressionen bleiben `p220-stereo-regression-v2`.
Die sechs erwarteten PASS-Fälle und sieben erwarteten FAIL-Fälle werden
einschließlich Kanaltausch, einseitiger Stille, Pegelabweichung,
Polaritätsinvertierung und einseitiger Verzögerung ausgeführt. Die
berechtigten Gegenkontrollen enthalten Dual-Mono-Tausch, übereinstimmendes
Gegenphasensignal, Hard-Pan, zulässige gemeinsame Pegelabweichung und
gemeinsame Latenz. Anschließend laufen die vollständigen 154 synthetischen
Audiofälle und die zehn bisherigen Mutanten, die 19 bestehenden P220-/P89-/P90-
Kompatibilitätstests und zusätzlich 15 vorhandene P99-/P74-/P75-Vertragstests.
Diese 15 Tests verwenden kontrollierte Provider-/Runner-Fixtures;
sie behaupten keine neue reale Ghidra- oder Plugin-Ausführung.

Jeder reguläre Test muss Exitcode 0 liefern; Shell-Pipelines verwenden
`set -euo pipefail`. Der Originalaudio-Negativlauf muss dagegen einen
Nichtnull-Exit und **77 BLOCKED / 0 PASS / release_approved=false** liefern.
Der abschließende Verifier prüft zusätzlich Stereo-JSON samt Quellenhashes,
vollständige Testzähler und Unit-Test-Endstatus ohne ausgelassene Tests.

## Tatsächliche Ergebnisse

**Integrations-Preflight: PASS auf Windows-2022 und Ubuntu-24.04.**
Neuer tatsächlicher Lauf [#42946883199, SUCCESS, 8m 0s](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42946883199)
auf CI-Trigger `7e127add47073e1559ef55eae253590f9173d347`.
Beide Jobs bestätigen per abschließender öffentlicher Annotation den
**Test-Commit `efc78988fb0e359c1205e8d809d856902cd1ac79`** und
**Baum `1d9b5c21866f383a108768e66529bcbd97f0a3b5`**.

| Tatsächlich ausgeführte Prüfung | Ubuntu-24.04 | Windows-2022 | Lokales Cloud-Linux |
|---|---|---|---|
| Stereo-v2-Erwartungen: 6 zulässige Kontrollen, 7 Fehlermutanten | 13/13 | 13/13 | 13/13 |
| Vollständige synthetische Programmszenarien | 154/154 | 154/154 | 154/154 |
| Bisherige Fehlermutanten erkannt | 10/10 | 10/10 | 10/10 |
| P220-Release / P89 / P90 Unit-Tests | 5 + 4 + 10 | 5 + 4 + 10 | 5 + 4 + 10 |
| main: REA / Universal-P74 / Batch-P75 Unit-Tests | 2 + 7 + 6 | 2 + 7 + 6 | 2 + 7 + 6 |
| Manipulierte Quelldatei zurückgewiesen, Original wieder geprüft | PASS | PASS | PASS |
| Echter Originalklang ohne private Aufnahmen gesperrt | 77 BLOCKED / 0 PASS | 77 BLOCKED / 0 PASS | 77 BLOCKED / 0 PASS |

Direkte Jobnachweise:
[Ubuntu-24.04 #130281708519, 5m 57s](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42946883199/job/130281708519),
[Windows-2022 #130281708509, 7m 56s](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42946883199/job/130281708509).
Der lokale vollständige P220-Lauf benötigte 456,53 Sekunden; alle sieben
regulären Testbefehle endeten mit Exitcode 0, der fehlende-Originalaudio-
Negativlauf mit dem erwarteten Exitcode 1.

[Permanente maschinenlesbare Nachweise](evidence/P220-MAIN-INTEGRATION-20261111/evidence.json)
enthalten Parent-Blob-Prüfungen, geschützte Pfade, Lauf-/Job-/Artefakt-IDs,
Quellenhashes und Grenzen. Daneben liegen die
[lokalen Stereo-Rohmesswerte](evidence/P220-MAIN-INTEGRATION-20261111/local-stereo.json),
[lokalen Testlogs](evidence/P220-MAIN-INTEGRATION-20261111/local-test-logs.txt),
[Exitcodes und Laufzeiten](evidence/P220-MAIN-INTEGRATION-20261111/local-suite-results.json)
sowie der [öffentliche CI-Ergebnistext](evidence/P220-MAIN-INTEGRATION-20261111/ci-public-summary.txt).
Die kompletten Windows-/Ubuntu-JSONs und Testlogs sind in den beiden
CI-Artefakten enthalten; der Artifact-Download kann eine GitHub-Anmeldung
erfordern. Die Auswertung stützt sich auf den konkreten geprüften Quellbaum
und die Ergebnis-Verifikation beider Jobs, nicht auf den grünen Run allein.

| CI-Artefakt | SHA-256 des von Actions veröffentlichten Artefakts |
|---|---|
| [Ubuntu #13823258035](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42946883199/artifacts/13823258035) | `44e8b781adf7f733be43190f02a703875c6e8ae3493bd1a22aebe7562c46ccec` |
| [Windows #13824065302](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42946883199/artifacts/13824065302) | `11b1d476dfea042a8293efd38e33ec24beedf51f13e6c7f75e3cdff53740a643` |

Beide Jobs enthalten den bestehenden Node-20-Abkündigungshinweis für
`actions/checkout@v4` und `actions/upload-artifact@v4`; GitHub führte die
Actions unter Node 24 erfolgreich aus. Das ist eine zukünftige CI-
Wartungsaufgabe, keine ausgelassene oder fehlgeschlagene Fachprüfung.

Der erste Start [#42946673492](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42946673492)
scheiterte bereits bei der Workflowvalidierung: `runner.temp` war im
Job-`env`-Kontext unzulässig. **Keine OS-Tests ausgeführt.** Korrektur
`7e127add47073e1559ef55eae253590f9173d347` setzt die temporären Pfade erst im
unterstützten Step-Kontext. Der kombinierte Quellbaum bleibt unverändert.

Die vorhandene Artifact-Ausgabe enthält pro OS `integration.json`,
`integration-verified.json`, Stereo-JSON, Logs der sieben Testsuiten, Negativkontrolle,
77-BLOCKED-Report und `combined-source.zip` aus genau dem temporären Test-SHA.
Retention: 14 Tage. Der Bericht und die ausgewählten maschinenlesbaren
Nachweise im Repository bleiben darüber hinaus erreichbar.

## Lokal reproduzieren

Aus einem Checkout mit beiden Eingangssnapshots und der veröffentlichten
Instrumentierung; die beiden Zielverzeichnisse müssen neu sein:

```text
python tests/prepare_p220_main_integration.py prepare --repo . --worktree ../p220-combined --out ../p220-evidence
python tests/prepare_p220_main_integration.py self-test --repo . --worktree ../p220-combined --out ../p220-evidence
```

Die bestehenden Tests anschließend **aus `../p220-combined`** starten;
die genauen Befehle und Logdateinamen stehen im vorhandenen Workflow.
Die beiden Inputs und das Auflösungsverfahren sind fest gepinnt. Ändert
sich main, muss dieser Preflight nach neuer Deltaprüfung neu erstellt
werden; er ist kein automatischer Nachweis für einen späteren main-Stand.

## Grenzen und verbleibende Integrationsentscheidung

Dieser Preflight ist eine geprüfte QA-Integrationsvorlage und **keine
Produkt-/FULL-AUDIT-/Echtzeit-/Releasefreigabe**. Reale Original-Creative-
Aufnahmen, vollständiger 77-Preset-Klangvergleich, neuer nativer Windows-
Pluginbuild/Validator/GUI, tatsächlicher REA/Ghidra-Providerlauf, reale DAW
und ASIO-Hardware wurden in diesem Auftrag nicht ausgeführt: **NOT RUN**.
Der Originalklang-Abnahmevertrag bleibt **BLOCKED**.

P196/P198 bleiben für eine spätere AWE-Produktintegration **wartend auf
P232**. Keine Tonhöhen-, Dämpfungs-, Chorus- oder sonstigen Engineänderungen
wurden übernommen. Kein Merge nach `main`, keine Löschung, kein Rebase,
kein Force-Push und keine eigenmächtige Releasefreigabe.
