# P53 – aktueller AWE-Synthesizer P137/V11 im universellen Plugin Test Lab

**6. November 2026.** Das Plugin Test Lab ist der **unabhängige** Windows-VST3-Prüfer für alle 125A-Plugins, nicht nur Drumator. P48 verwendete einen älteren AWE-Quellstand und durfte daher **nicht** die Abnahme von P137 bestätigen.

## Testobjekt und unveränderliche Herkunft

- Produkt: [125A-AWE-Synthesizer](https://github.com/challanger2000/125A-AWE-Synthesizer), exakter bereits dokumentierter P137/P139/P140-Entwicklungsstand `d7f534a5eb44f56942706019a6973ad3c0d5ce40` von `fix/p122-bank-dirty-audit`. Das Test Lab **schreibt nicht** in das Produktrepository.
- Reale Windows-x64-VST3-DLL aus Quelle, Steinberg SDK 3.8.1 Build 84 (SHA-1 `3cdf9ca5d1f5b1b21e0a86832aa4abe55607bd96`), Visual Studio 2022, C++23.
- Alle echten AWE-CTests, darunter V11 FX-Presetwahl `125A_p133_fx_processor_modes`, die reale physische CC120-Regression `125A_p134_cc120_physical_stop`, Program-/Recall- und keine C++-new-im-Audiopfad-Regressionsprüfungen; **mindestens 44 produktive Native-CTests** (der zusätzliche P134-Altdll-Bitvergleich ist nur im Produkt-Audit mit `125A_P134_AB=ON` aktiv). Der tatsächliche Steinberg-VST3-Modulevalidator muss **537/537** bestehen.
- Das Test Lab baut seine **eigenen unabhängigen** `125A_Test_Lab_Host.exe`, `125A_Test_Lab_State_Stress.exe`, `125A_Test_Lab_GUI.exe` und `125A_Test_Lab_Instance_Isolation.exe` und führt `tests/run_plugin_quickcheck.py` gegen die *soeben gebaute AWE-DLL* aus; Code und Binär-SHA müssen genau zum VST3-Bundle und den Verifikationsprotokollen passen.
- Die negative Gegenprobe `tests/test_awe_p53.py` muss falsche Release-, Chorus-, Studio-One-, ROM- und Versionsbestätigungen weiterhin ablehnen. Der positive Gate `tests/verify_awe_p53.py` erzeugt `AWE-REAL-USER-COVERAGE.json` mit ausschließlich technischen Teilnachweisen.
- CI-Windows-Workflow `awe-p53.yml`. P48 wird unverändert als historischer Nachweis erhalten.

## Externe AWE-Echtzeitbeweise (keine neue Test-Lab-Zurechnung!)

Die bereits im **Produktrepository** gelaufenen echten VST3-Tests sind nicht durch die vorliegende P53-Suite „nachgetestet“:
- [P139 A #42236380915](https://github.com/challanger2000/125A-AWE-Synthesizer/actions/runs/42236380915) und [P139 B #42236381113](https://github.com/challanger2000/125A-AWE-Synthesizer/actions/runs/42236381113): beide erfolgreich, zusammen 201.600 `process()`-Callbacks und **0 Budgetüberschreitungen** unter sechs Lastarten, ETW mit/ohne, Heap-Positivkontrolle, MIDI-, Bank-/Projekt- und FX-Automation.
- [P140 #42239176126](https://github.com/challanger2000/125A-AWE-Synthesizer/actions/runs/42239176126): alter P134-V11- gegen neuer P137-V11-Diagnose-VST3 auf demselben Windows-Runner, ABBA-Reihenfolge, 30 Stimmen, 128 Samples, 20.400 Calls je Version: **58 → 0 Überschreitungen**, davon lastgleich **16 → 0**.
- [P137 #42233912768](https://github.com/challanger2000/125A-AWE-Synthesizer/actions/runs/42233912768): P134/P137-Premiere und **11.796.480 Byte PCM bitidentisch**, 64 native Creative-FX-Paarkombinationen, V11-Speicherzustand.

P53 ersetzt nicht diese produktspezifischen ETW-/FX-/SoundFont-Tests; die tatsächlich bestätigten externen Nachweise sind von der **Test-Lab-eigenen** unabhängigen Quickcheck-Prüfung zu unterscheiden.

## Was das Test Lab an einer kommerziellen DAW abdecken kann – und was nicht

Das Test Lab implementiert einen echten Win32-VST3-Host: MIDI/Audio, State-Save/Recall, Sample-Rate/Blockgrößen-Matrix, GUI-Editor-Lifecycle, Parameterkontrollen und parallele Instanzen. So kann es **DAW-nahe Host-Probleme** aufdecken.

Es ist **aber nicht automatisch eine laufende Instanz von Fender Studio Pro/Studio One und nicht der native ASIO-Treiber des realen Audient-Interfaces**. GitHub Windows-2022-Runner verfügen über keine verbindlich konfigurierte physische Zielrechner-ASIO-Kette; selbst ein vollständig erfolgreicher Real-VST3-Test rechtfertigt deshalb **nicht** `ASIO_TARGET_PASS` oder `DAW_SESSION_PASS`. Ein lokal/remote unter dem echten Treiber ausgeführter Test müsste die Audio-Hardware, ASIO/MMCSS-Timing, VST3-Binäridentität und ein vollständiges DAW-Projekt mit realem Save/Reload protokollieren. Die aktuell vorhandene Test-Lab-Version hat für diesen Hardware-Host **keinen vollständig belegten Adapter**.

**Freigabematrix bei grünem P53:**
- `VST3_INDEPENDENT_HOST_TECHNICAL`: PASS (wenn CI erfolgreich).
- `P137_SOURCE_STALE`: NO (durch SHA-Gate).
- `P139_WINDOWS_REALTIME_LAB`: PASS als **externer** Produktbefund.
- `P53_REAL_HARDWARE_ASIO`: NOT RUN.
- `P53_REAL_COMMERCIAL_DAW`: NOT RUN.
- `CREATIVE_CHORUS_PHYSICAL_REFERENCE`: NOT VERIFIED.
- `RELEASE_APPROVED`: FALSE.

**Keine unnötige Handtest-Verpflichtung allein wegen fehlender GitHub-Audiohardware.** Die Test-Lab-Technik ist für möglichst weitgehende automatisierte Vorabtests zuständig. Eine echte Hardware-/DAW-Referenz muss jedoch als gesonderte, nachweisbar tatsächlich durchgeführte Prüfumgebung vorhanden sein, bevor sie als `PASS` ausgegeben wird.
