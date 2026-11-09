# P189 – Offline-Nachdecodierung bereits gespeicherter ETW-Dateien

**Nächster Schritt ohne Wiederholung eines Hardwarelaufs:** Das neue
native Test-Lab-Werkzeug hat einen zusätzlichen Befehl
`--decode-existing RAW-LOCAL-ONLY FRESH_OUTPUT TARGET_PID`.
Es liest ausschließlich die bestehenden `kernel.etl` und
`providers.etl` eines P188-Laufs, startet weder ETW-Sessions noch
ASIO/DAW und erzeugt `P189-DECODE.json` mit CSwitch-Ereigniszahlen
und bis zu 32 whitelisten TDH-Feld-/Windows-Statussignaturen.
Die Original-ETLs werden nicht verändert.

`tools/p189/P189-REPLAY.ps1` ist der universelle, allein lesende
Windows-BAT-Einstieg für Nutzer, inklusive geprüftem Paket-Manifest,
eingeschränkter Quell/PID-/Nonce-Verknüpfung, kopierter Diagnose-JSON
und garantiert **keiner** Veröffentlichung der ETL-Nutzdaten.
Ergebnis `P189-RESULT.json` ist ausdrücklich nur Diagnose und
nie Hardware-/Release-Nachweis. Die Originalordner nicht löschen,
solange die P189-Auswertung noch aussteht.

Eine echte Windows-CI-Gegenprobe führt die Offline-Nachdecodierung
eines zuvor **real** per Kernel-ETW-Selftest geschriebenen
ETL-Dateipaars durch und prüft die gezählten Ereignisse
gegen die ursprüngliche native Erfassung. Gegenproben prüfen,
dass ungeprüfte/Nicht-ETL-Eingaben nicht zu PASS werden.

---

# P189 – Windows-ETW-Parserdiagnose ohne vorschnelle Filterkorrektur

## Belegter Fehler am Windows-Zielrechner

Der Benutzer lieferte zwei echte, verschiedene Windows-Referenz-ASIO-Messungen
aus dem P186/P188-Lauf:
- Vorheriger Lauf: 1.000/1.000 richtige Referenz-Callbacks,
  1 strenge Startabstandslücke, 0 Prozess-/Execution-Overruns,
  189.704 ETW-Ereignisse, 72.039 Decodierfehler,
  0 verwertbare Kontextwechsel.
- Aktueller Lauf: 1.000/1.000 Referenz-Callbacks,
  1 Startabstandslücke, 0 Ausführungs-Overruns, 0 XRUN,
  125.671 ETW-Ereignisse, 43.425 Decodierfehler,
  0 verwertbare Kontextwechsel.

Beide Kernel-/User-ETW-Sitzungen: Start/Stop/Open/Process 0,
QPC-Frequenz 10 MHz, Clock-Flag 1, keine gemeldeten ETW-Verluste.
Referenz-Identität/Nonce/Driver/PID wurden geprüft.
Damit ist die *genaue* ETW-Decoderfehlerquelle nicht nachgewiesen:
`cswitches=0` bezeichnet bisher nur vollständig decodierte,
dem Zielprozess zugeordnete CSwitch-Ereignisse. Es beweist
keineswegs, dass Windows keine Kontextwechsel aufgezeichnet hätte.
Ursache der einzelnen echten ASIO-Startlücke bleibt **INCONCLUSIVE**.

## Ein nachweisbarer Quellen-/Diagnose-Mangel

`src/p185_etw.cpp` zählte vorher jeden TDH-Metadatenfehler bloß als
`decodeErrors++`, ohne Ereignistyp, Feldname oder TDH-Fehlercode.
Die Statistik `cswitches` stieg erst nach Zuordnung zu
`targetThreads`. So konnte das Test Lab nicht zwischen
(1) fehlendem CSwitch-Event, (2) einem Windows-Schema-/TDH-Feldfehler,
(3) fehlender Thread-Lifecycle-Zuordnung oder
(4) einem akzeptierten, aber nicht dem Zielprozess zugeordneten
Kontextwechsel unterscheiden. Das ist der behobene Berichtsdefekt;
keine unbelegte Reparatur des Windows-11-Parsers.

Der C++-Consumer notiert jetzt **ausschließlich offline nach
`ProcessTrace`**, ohne Änderung am ASIO-Audiothread:
`cswitch_events_seen`, `cswitch_events_decoded`,
`thread_events_seen`, `thread_events_decoded`,
`ready_events_seen`, `target_thread_count` sowie bis zu 32
`decode_failure_kinds` mit `CSWITCH/THREAD/READY/MARKER`,
whitelistet Feldnamen und numerische Windows-TDH-Statuscodes.
`decode_errors`, strenge Reject-Gates, QPC, PID, Nonce und
reale ASIO-Callbackmessung bleiben unverändert. Es werden keine
Kernel-Nutzdaten, Pfade, Benutzer-, ROM- oder SF2-Daten exportiert.

`P185-DIAGNOSTICS.ps1` nimmt nur formatgeprüfte numerische
Statuswerte und begrenzte Fehlerkategorien in die kompakte
`P185-ACCEPTANCE.json` auf. Unbekannte/ungültige Felder
werden markiert und abgewiesen, nicht gefällig ergänzt.

## Quellen / keine spekulative Parserkorrektur

Microsoft dokumentiert `Thread_V2` mit GUID
`{3d6fa8d1-fe05-11d0-9dda-00c04fd7ba7c}`,
CSwitch als Eventtyp 36 mit den
`NewThreadId`, `OldThreadId`, `OldThreadState`,
`OldThreadWaitReason`-Eigenschaften, sowie
`Thread_V2_TypeGroup1` mit Eventtypen 1–4 und
`ProcessId`/`TThreadId`:
- https://learn.microsoft.com/en-us/windows/win32/etw/thread-v2-typegroup1
- https://learn.microsoft.com/en-us/windows/win32/etw/cswitch
- https://learn.microsoft.com/en-us/windows/win32/etw/thread-v2

Diese Dokumentation beweist nicht, welches
`TdhGetProperty(Size)` auf dem Zielrechner tatsächlich fehlschlug.
Es wurde **kein** freizügiger Rohdatendecoder und kein Feldnamen-Fallback
auf Verdacht aktiviert.

## Abnahmevertrag

- Native echte Kernel-CSwitch-/Thread- und QPC/Marker-Kontrollen
  unter Windows-2022; keine synthetische Hardwarefreigabe.
- 42 bestehende Berichts-Gegenproben dürfen nicht regressieren.
- Neue adversariale Fälle: typisierte und begrenzte
  TDH-Fehlermetadaten sowie absichtliche private Feldnamen,
  überlange Signaturlisten und falsche Zählertypen
  werden abgewiesen. Keine Quelle behauptet Windows-11-CI.
- Kein neuer ASIO-Gerätelauf, ohne dass vorher ein verbessertes
  Windows-BAT-Paket mit tatsächlichem Download/CheckOnly bestätigt ist.
- Neuer zielrechnerseitiger Report kann den Decoderfehler konkret
  auf Event/Feld/Windows-Status eingrenzen; er wird den ursprünglichen
  ASIO-Gap nicht automatisch erklären.
- **Keine FULL-AUDIT-Freigabe, ASIO-Gesamtabnahme NO-GO,
  Ursache INCONCLUSIVE**, keine Änderung von Produkt-AWE-DSP
  oder Timing-Grenzwerten.
