# One-command real VST3 technical quickcheck

Download the latest successful P25 Windows Actions artifact and extract its `PORTABLE` directory. It contains both native hosts, all required Python scripts, a README, and a SHA-256 inventory. Python 3 is required. Run the following from that directory.

On Windows x64, given two native Test Lab executables and an installed VST3
bundle, this command executes the existing P32 playback-save and P34 native
audio/state capture with no handwritten manifest:

```powershell
python run_plugin_quickcheck.py --plugin "C:\VST3\Plugin.vst3" --host ".\125A_Test_Lab_Host.exe" --stress-host ".\125A_Test_Lab_State_Stress.exe" --out ".\Plugin-QA"
```

If running directly from a source checkout rather than the portable package, use `python tests/run_plugin_quickcheck.py` instead.

It discovers exactly one .vst3 binary inside the bundle, calculates the
real file SHA-256, generates pinned intermediate manifests, and launches
native VST3 processing. P32 performs **six distinct real VST3 stress runs**, at
44.1, 48 and 96 kHz with both 64- and 512-sample buffers. Each run
requires exactly 2,500 successful audio callbacks and 500 successful
project-state saves, for 15,000 callbacks and 3,000 verified saves in
total. Missing just one case or one saved state makes the result FAIL.
Each case is checked independently against the actual native host report,
not against an overall success string. P34 captures real 24-bit stereo PCM at 44.1 kHz
and real processor-state bytes.

When the captured state has a supported size, the same invocation now
automatically loads it into **two fresh native VST3 host processes**, renders
new WAV evidence from each process, and saves state again. Both fresh
`setState` / `getState` runs must succeed; otherwise the overall
quickcheck is FAIL. This test helps detect broken project restoration
without requiring you to open a DAW manually.

This is an API-level fresh-process recall test, not yet proof that a
presets' audible behavior or full DAW session is correct. Because many
plugins use randomized synthesis, this generic quickcheck does not
require identical PCM across independent runs: repeatable PCM and
musical correctness remain `NOT COVERED` without a trusted
product-specific deterministic reference. The native host rejects empty
component-state streams and state blobs of 128 MiB or more. Such failures
remain **FAIL**, never a green result. Product-specific musical correctness
remains `NOT COVERED` without a trusted external oracle.

`QUICKCHECK-RESULT.json` reports `TECHNICAL_PASS` only when both native
stages pass and their reports identify that exact module. Missing,
out-of-date, wrong-product and ambiguous multi-module evidence is rejected.
The Windows stress workflow exercises this command against a real
source-built VST3, plus negative controls.

**This is not a product release certification.** It records unknown source
commit/version as NOT VERIFIED and marks musical correctness, product GUI,
presets, MIDI/WAV exports and commercial DAW integration as NOT COVERED.
`release_approved` is always false. Unsupported plugin bus layouts or
capture conditions fail instead of generating false green results.

For complete release acceptance, see
[PRODUCT-USER-ACCEPTANCE.md](PRODUCT-USER-ACCEPTANCE.md) and implement
trusted product-specific oracles for all applicable user-facing functions.

## Lesbares Testergebnis statt technischer Protokolle

Nach dem Ablegen eines Plugins auf `Run-VST3-Test.cmd` erstellt das
portable Test Lab automatisch `RESULTS/<Plugin>/TESTERGEBNIS.html` und
oeffnet diese Ergebnis-Seite im Browser. Sie zeigt auf Deutsch klar
unterschiedene Ergebnisse: **BESTANDEN**, **FEHLER** und **NICHT
GEPRUEFT**. Auch bei einem Absturz oder fehlerhaftem technischen Test
wird, sofern Python noch verfuegbar ist, ein Fehlerbericht erzeugt.

Die Seite markiert immer **KEINE PRODUKTFREIGABE**, auch wenn alle
ausgefuehrten technischen Tests bestehen. Ein gruenes technisches
Ergebnis wird nicht als fertige DAW-, Preset- oder GUI-Abnahme
ausgegeben. Die JSON-Datei bleibt die maschinenlesbare Grundlage.

## Drag-and-drop Windows launcher

You can now drag an installed, trusted `.vst3` **folder** onto
`Run-VST3-Test.cmd` inside the extracted PORTABLE folder. The launcher
automatically runs native audio processing, playback saves, state capture
and real editor open/close checks. You do not need to enter a command.
Reports are written under `RESULTS/<plugin-name>/`. Python 3 must be
installed. An absent editor is shown as NOT COVERED rather than success.
The program always refuses to certify the product release without a
product-specific acceptance audit.

## Optional actual Win32 GUI checks in the same command

The portable kit now ships `125A_Test_Lab_GUI.exe` and the independent
bitmap/control checker. Add `--gui-host ".\\125A_Test_Lab_GUI.exe"` to check
that an actual VST3 editor opens, detaches, reopens and closes cleanly.
A plugin with no editor is marked `NOT COVERED`; an editor host failure
is `FAIL`.

For click and post-click painting checks, also supply a separately prepared
mapping file with `--gui-controls ".\\controls.json"`:

```json
{
  "controls": [{
    "id": "limiter_enable",
    "param_id": 9001,
    "x": 160,
    "y": 90,
    "expected_normalized": 1.0,
    "expected_pixel": {"x": 10, "y": 10, "rgb": [12, 142, 85]}
  }]
}
```

**This is an illustrative fixture mapping, not a real commercial plugin
mapping.** Obtain coordinates and expected outcomes independently from the
plugin's specification or approved reference. The runner pins the exact
plugin binary, launches the actual native GUI, clicks the declared controls
and checks the resulting controller parameters and actual painted pixels.
Missing, stale, untestable or wrong results fail. Untested controls remain
`NOT COVERED`; passing declared controls is *not* complete GUI approval.

A commercial DAW's specific interactions, including its own drag/drop and
session save/reload, still require an actual DAW-integration test rather
than an inference from this native GUI host.

## Real-time callback deadlines (measured, not guaranteed)

For each of the six native save/playback conditions, the test host writes
callback deadline overruns, p99 execution time, and nominal block deadline.
The quickcheck includes `realtime_deadline_observation` in its coverage.
Any measured violation is marked **FAIL** (including the overrun count in
the German HTML report), even if the plug-in's `process()` returned success.
Missing measurement fields are not allowed to produce timing PASS.

**Interpretation:** these are measured timings on the current Windows runner,
not a certification of deterministic hard realtime on all hardware. OS
scheduling can cause overrun measurements even in a well-written plugin.
The technical API tests may independently succeed while the timing domain
is FAIL. Inspect the actual callback logs before treating measured overruns
as a definitive plugin defect. The real-time section is never silently
classified as PASS solely from a green technical API result.


## Proved saves during active audio playback

A previously overlooked false-green case was 500 successful calls to
`getState()` that could all happen *after* the audio callback thread had
finished. This does not test the concurrency issue users encounter when
saving while a track is playing.

The native host now counts only successfully captured project saves made
**after audio callbacks have started and before the callback thread
finishes**. Every playback/save scenario requires at least one such
observation, while still requiring all 500 saves and 2,500 callbacks.
`saves_during_playback` is present in native TSV evidence and
`measured_active_playback_saves` in per-case adapter JSON. If all saves
occur after playback, the check is FAIL, even if every save returned
success. Windows CI runs positive real-VST3 observation and intentionally
false evidence containing 0, 501 or missing in-playback saves.

This proves temporal overlap of playback activity with project-state
retrieval, not necessarily that a save blocked an individual `process()`
call. Deadline and state-consistency checks remain separate.

## Automatic controller parameter inventory

With the native GUI host installed, the portable quickcheck now requests
`--inventory-parameters` from the **actual loaded VST3 controller**. No
handwritten GUI control map or preselected parameter IDs are required.
For up to 8,192 advertised VST3 parameters it verifies that:

- Each advertised index returns information and a unique 32-bit parameter ID.
- Default and current normalized values are finite and in the inclusive
  0–1 range, and step counts are valid.
- Native enumeration count matches the independently parsed TSV rows.

A malformed or missing record, a duplicate ID, an invalid value or a
silent host failure is **FAIL**. A plugin with no exposed controller is
`NOT COVERED`, not a fabricated PASS. The actual parameter count is
shown in the JSON result and the human-readable test report includes
the parameter-inventory domain.

The inventory is **read-only**: it does not write parameters, load
banks, reset automation, or pretend to know which on-screen control
belongs to which VST3 parameter. Musical behavior, parameter automation
through `process()`, GUI-click relationships and DAW-specific recall
remain independent product-specific checks. See
`tests/verify_parameter_inventory.py` for the strict external parser.


## Zwei Instanzen in einem Hostprozess (automatisch)

Der Drag-and-drop-Test startet nun auch den mitgelieferten nativen
`125A_Test_Lab_Instance_Isolation.exe`. Dabei werden aus einem frisch
aufgenommenen Projektzustand zwei **gleichzeitig lebende VST3-Instanzen
im selben Windows-Prozess** erzeugt, mit Audioverarbeitung und erneutem
Speichern beider Instanzen. Eine fehlgeschlagene Instanz, ungültige
Audioausgaben oder fehlende Zustandsdaten führen zu FAIL. Der Prüfbericht
zeigt `same_process_dual_instance_lifecycle = PASS`, wenn die
vollständige native Prüfung bestanden wurde. Fehlt das unterstützte
Busformat, wird `NOT COVERED` angezeigt.

**Wichtige Grenze:** Die automatische Prüfung verwendet bewusst
denselben gespeicherten Zustand für beide Instanzen. Dadurch bestätigt
sie die gemeinsame Lebensdauer und die Verarbeitung, **nicht** eine
unabhängige Bank- oder Preset-Auswahl. Das Ergebnis
`distinct_instance_state_isolation` bleibt `NOT COVERED`.

Der separate, ebenfalls mitgelieferte Befehl
`--dual-state Plugin.vst3 A.bin B.bin Ausgabeordner` lädt zwei
**unterschiedliche** Zustände in zwei gleichzeitig geöffnete Instanzen.
Für eine belastbare Produktaussage müssen die erwarteten Zustands- und
Audioresultate dafür unabhängig vorliegen. Die Windows-CI demonstriert
das mit einem korrekt isolierten VST3 und einem absichtlich fehlerhaften
VST3, dessen globale Bank beide Instanzen überschreibt. Der externe
Prüfer erkennt den Fehler sowohl in den neu gespeicherten Zuständen als
auch in der PCM-Ausgabe.

Der native Test ist kein Ersatz für eine echte Mehrspur-DAW-Sitzung,
MIDI-Routing, Songmodus oder plugininterne Preset-Logik.
