# P181 — Präzise, zeitlich begrenzte ASIO-Callback-Spuren (diagnostic only)

### Warum

Zwei unabhängige Windows-ASIO-Sitzungen mit dem realen Yamaha Steinberg USB ASIO
meldeten jeweils einen zu großen Abstand zwischen **Callback-Starts**:
maximal 62,6362 ms bzw. 58,8728 ms bei 512 Frames und 44.100 Hz.
Die längste Callback-Rechenzeit betrug nur 5,7598 ms bzw. 6,7364 ms
bei einem Blockbudget von 11,61 ms. Je 1000/1000 Prozesse erfolgreich,
je 12/12 MIDI NoteOn/NoteOff, 0 als solche gemeldete Treiber-XRUNs.

Der P102-Zähler benennt nicht die Position oder Umstände der Anomalie.
P181 bietet deshalb optional:

```
--timing-trace-out C:/local/ASIO-CALLBACK-TIMING-TRACE.json
```

Bei gesetztem `--diagnostic-out` und höchstens 4.096 angeforderten
Callbacks wird **vor Treiberstart** ein fester Arbeitsspeicherpuffer
für alle geplanten Callbacks plus 64 Reserve-Slots angelegt. In der
Audio-Callback-Funktion werden nur vorbereitete Einträge beschrieben:
Callbackindex, Bufferindex, QPC-Start/Ende, Windows-Thread-ID,
Ergebnisflag, Timing-Gap, MIDI-Ereignisstände und ASIO-Meldungszähler.
**Keine Dateizugriffe oder dynamische Allokation auf dem Audiothread**.

Nach dem echten `IASIO::stop()` exportiert P181 ausschließlich die
vier unmittelbaren Callbacks **vor und nach** jeder Verletzung sowie
den auffälligen Callback selbst (überlappende Fenster ohne Duplikate).
Der Bericht dokumentiert die absolute QPC-Tickfrequenz, relative Zeiten,
Zeitabstände und benachbarte Ausführungsdauern. Er erlaubt die Prüfung,
ob die Unterbrechung beim Start, bei einer MIDI-Aktion, beim letzten
Callback oder nach einem Threadwechsel lag. Er **beweist weder** die
Ursache im Windows-Scheduler noch ein physisches Hardware-XRUN.

Strenge Bedingungen: getrennte Ausgabepfade, tatsächlicher Treiber,
dieselbe Sitzung (nonce), gleiche Produkt- und Host-SHA256,
unveränderte originale 0-Fehler-Realtime-Grenze. Der Bericht
`125a-real-asio-callback-window-trace-v1` trägt ausdrücklich
`DIAGNOSTIC_ONLY_NOT_HARDWARE_PASS`, `release_approved=false` und
`physical_asio_verified=false`.

Windows CI prüft den C++23-Build, synthetisch erzeugte Fenster mit
fehlenden/benachbarten/Grenz-Verletzungen sowie das Ausbleiben jeglicher
Hardware-/Trace-Attestation bei fehlendem ASIO-Treiber. Es ersetzt
keine physische Sitzung und keine unabhängige ETW-/USB-Treiberdiagnose.

**Offen:** echte lokale Windows-Zeitspur. Vor Freigabe wird keine
Timingverletzung aus dem Audit entfernt oder ignoriert.
