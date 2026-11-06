# One-command real VST3 technical quickcheck

## P41 — Optional automatic GUI exploration (no manually mapped controls)

The shared Windows tester can now **automatically probe unknown native
GUI regions**, taking a real initial editor snapshot and choosing
deterministic interior coordinates on a 3×3/4×4 grid. Every click takes
place in a **fresh, disposable plugin instance and process**. At each
point it records:

- All advertised VST3 controller parameter values before/after clicking.
- Two pre-click **real HWND captures** to detect independently changing UI
  pixels, and a third capture after the click.
- Distinctions between `PARAMETER_AND_VISUAL_CHANGE`,
  `PARAMETER_CHANGE`, `VISUAL_CHANGE`, `UNSTABLE_BASELINE` and
  `NO_OBSERVED_CHANGE`.

Candidates are **observations**, not discovered button names or proof of
correct functionality. A change in a painted LED does not establish
correct audio, MIDI, export or recall behavior. A no-change result does
not mean a control is broken: the click may be outside a control or may
have a nonobservable side effect. Animated interfaces can be marked
`UNSTABLE`; their visuals are not certified.

**Explicit opt-in is required** because clicking unknown buttons can
launch dialogs, exports or other plugin actions. Run only with trusted
test bundles and disposable project state. This uses a real Windows
GUI process and never silently runs on new plugins.

Standalone Windows Actions execution:

```powershell
python tests/run_gui_exploration.py --plugin "C:\VST3\MyPlugin.vst3" --gui-host "build\Release\125A_Test_Lab_GUI.exe" --out artifacts/GUI-SURVEY --acknowledge-ui-clicks --max-points 9
```

Within the same ordinary technical quickcheck add `--gui-host`,
`--gui-explore` and `--acknowledge-gui-explore`. Results are saved to
`gui-exploration/GUI-EXPLORATION-RESULT.json` with native TSV, two
baseline screenshots and one post-click screenshot per probe.
A successful scan is `OBSERVATIONS_COMPLETE`, while the human report
shows `OBSERVATIONS_ONLY`, **not** a button-coverage PASS. Missing,
stale or tampered native evidence and timeouts fail closed.

Limit: at most 16 candidate coordinates per scan, up to 4096×4096 HWND
with maximum 4,194,304 analyzed pixels per capture. Native user-action
automation in GitHub Actions uses the runner's Python; no Python
installation is needed on the end user's computer.

## P40: Automatic display-text/value conversion for every VST3

The regular one-command Windows quickcheck now exercises **every
advertised automatable, writable VST3 parameter** through two controller
interfaces that are distinct from normalized value get/set:

- `IEditController::getParamStringByValue()` — value → user-facing label.
- `IEditController::getParamValueByString()` — label → normalized value.

The native test engine uses valid endpoints/quartiles (snapped to
discrete steps), records exact UTF-16 labels as unambiguous hexadecimal
text, tests optional reverse parsing, and independently reconstructs all
cases from a fresh evidence file. A **discrete** parameter must convert
back to its original normalized step; a continuous value may have
intentionally rounded display text, so the parsed value must reformat
to the **identical** label. A false-successful conversion is a FAIL.
The test fixture includes a *real VST3 plugin deliberately returning
incorrect reverse values*.

Some VST3 plugins do not implement reverse text parsing. In that case
`native_parameter_text_reverse` is explicitly `NOT COVERED`, not
a failure or a fake PASS. No text API at all is likewise `NOT COVERED`.
The German report separates label reading, reverse parsing, and actual
GUI pixel checks. **This test does not visually read the plugin's
custom-painted value labels**: those need an independently approved
GUI screenshot profile. See `docs/GUI-CONTROL-MATRIX.md`.

## Automatic universal controller value sweeps

The native GUI host now probes **every VST3 parameter marked automatable
and not read-only**, at normalized 0%, 25%, 50%, 75% and 100% points
(or the corresponding discrete steps), then restores its original value
in a disposable plugin instance. Duplicate step positions are tested once.
Each requested/returned value is independently verified from the native
TSV evidence; missing cases, silent parameter write failures and
incorrect restorations make the quickcheck **FAIL**. Parameters which
cannot legally be edited are explicitly **NOT COVERED** rather than
guessing their behavior.

This feature is part of the normal `Run-VST3-Test.cmd` flow whenever a
native VST3 controller is available. The report distinguishes
`native_parameter_sweep` from `product_gui_controls`: controller
automation does not simulate the location or mouse behavior of an
undocumented plugin button. An additional product-specific GUI click
profile is still needed to test controls not exposed as VST3 parameters.
No DAW installation or end-user Python installation is needed when
running these checks in GitHub Actions.

## Optional ordered user journeys on the real VST3 GUI

In addition to the independent controller sweep and isolated GUI clicks,
the shared Windows editor now supports a real **ordered click/drag/keyboard workflow
in one persistent native VST3 window**. Use an independently approved JSON
profile described in `docs/GUI-CONTROL-MATRIX.md` (P37).

```powershell
python run_plugin_quickcheck.py --plugin "C:\\VST3\\Instrument.vst3" --host ".\\125A_Test_Lab_Host.exe" --stress-host ".\\125A_Test_Lab_State_Stress.exe" --gui-host ".\\125A_Test_Lab_GUI.exe" --gui-workflow ".\\approved-workflow.json" --out ".\\Instrument-QA"
```

The quickcheck runs the normal native audio/save/GUI/parameter checks,
then the independently asserted GUI journey. It records
`native_gui_workflow` as PASS only when **every declared step and requested
painted-pixel oracle** succeeds; on errors it produces FAIL.

**GUI-only buttons** that are not exposed as VST3 parameters may use
`visual_oracle` with independent before/after RGB snapshots instead of
fabricating a ParamID (see P38 in `docs/GUI-CONTROL-MATRIX.md`). Such
verified visible-only steps are reported separately as
`native_gui_visual_workflow`. This confirms painted visual transitions,
**not hidden plugin functionality**. Without an approved profile the
coverage is `NOT COVERED`.

## Optional deep checks in the same report

The default drag-and-drop runner is safe for arbitrary Windows VST3 plugins.
The same one-command runner now supports two **explicit opt-in** deep checks
with their own native evidence and fail-closed `QUICKCHECK-RESULT.json` coverage.

For an instrument whose VST3 contract supports loading a valid saved state
while processing is active, enable the real six-case live-state stress:

```powershell
python run_plugin_quickcheck.py --plugin "C:\\VST3\\Instrument.vst3" --host ".\\125A_Test_Lab_Host.exe" --stress-host ".\\125A_Test_Lab_State_Stress.exe" --out ".\\Instrument-QA" --active-replay
```

This additional test performs 3,000 genuine `setState()` operations and
3,000 saves alongside 15,000 audio callbacks; it must report six separately
verified rate/buffer cases with observed in-playback overlap. A failing
requested deep test produces **FAIL**, not an unqualified technical PASS.
Not all plugins support concurrent `setState()`, so it is **not** enabled
automatically for an arbitrary dropped plugin.

If you have two **independently approved** product bank/preset states and
their saved-state and PCM references, provide a
`125a-product-dual-state-oracle-v1` JSON manifest and the native dual host:

```powershell
python run_plugin_quickcheck.py --plugin "C:\\VST3\\Instrument.vst3" --host ".\\125A_Test_Lab_Host.exe" --stress-host ".\\125A_Test_Lab_State_Stress.exe" --dual-host ".\\125A_Test_Lab_Instance_Isolation.exe" --dual-state-manifest ".\\approved-AB.json" --out ".\\Instrument-QA"
```

The manifest format and independent-oracle requirements are described in
`tests/run_product_dual_state.py`, `tests/make_qa_dual_manifest.py`, and
`docs/P32-PRODUCT-ADAPTERS.md`. Both state streams, the manifest, the tested
VST3 and all native hosts are fingerprinted across the complete run.
`distinct_instance_state_isolation` and `reference_pcm_isolation` become
PASS only after both the real native two-instance test and the approved
A/B oracle succeed. The generic **identical-state** two-instance smoke test
must never imply different banks/presets are independently correct.

Both deep switches can be used together. Without them, their coverage is
**NOT COVERED**, not PASS. Even with them, full musical sound quality, every
product control and a commercial DAW session remain **NOT COVERED** unless
there is separate independent product evidence. The HTML result uses FAIL
as the top-level outcome if any measured coverage gate fails, including
audio callback deadline overruns. Host/OS deadline observations are not
formal hard-real-time guarantees on other computers.

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


## Eigene A/B-Bankzustände tatsächlich unabhängig prüfen

Der optionale Runner `run_product_dual_state.py` ermöglicht einem
produktverantwortlichen Chat einen echten **Zwei-Instanzen-Test mit
verschiedenen Presets/Bänken**, ohne den Plugin-Quellcode zu verändern.
Er wird mit dem portablen Paket ausgeliefert, gehört aber nicht zum
automatischen Drag-and-drop-Kurztest, weil dafür zwei unabhängig
freigegebene Ausgangszustände und die erwarteten Resultate nötig sind.

Die JSON-Datei mit Schema `125a-product-dual-state-oracle-v1` verlangt:

- `product.bundle` (VST3-Ordner), `product.binary` (Moduldatei)
  und deren unabhängig festgelegten `sha256`;
- `host` und zwei verschiedene, extern bereitgestellte
  `initial_states.A/B` mit jeweils `path` und `sha256`;
- `reference.expected_saved_sha256.A/B` (erwartete
  Zustände **nach** den beiden Audioaufrufen);
- `reference.expected_pcm` für `A_first_pcm`, `B_first_pcm`,
  `B_second_pcm`, `A_second_pcm` sowie die absolute
  `abs_tolerance` im Bereich 0 bis 0,01.

Aufruf im Paketordner:
```powershell
python run_product_dual_state.py --manifest A-B-Referenzen.json --out A-B-Ergebnisse
```

Der Host öffnet A und B **gleichzeitig in einem Windows-Prozess**,
verarbeitet A/B/B/A, speichert beide Instanzen und vergleicht
ihre tatsächlichen Resultate gegen die separat vorgegebenen Werte.
Ein falsch gespeicherter Zustand, falscher Klang, fehlende Datei,
vertauschte Zustände, falscher Plugin-Binary-Hash oder ein nur
scheinbar erfolgreicher Host-Aufruf ergeben **FAIL**. Die JSON-Ausgabe
heißt `PRODUCT-DUAL-STATE-RESULT.json`.

Die Windows-CI beweist das an einem echten korrekt isolierten VST3
und einem absichtlich fehlerhaften VST3, dessen gemeinsame globale
Bank den Zustand beider Instanzen vermischt. Die bekannten QA-Sollwerte
werden **nicht** aus der gemessenen Audioausgabe gewonnen. Für andere
Plugins müssen neue Referenzen ausdrücklich genehmigt werden.
Bei fehlenden Referenzen bleibt Produkt-Bank-Isolation `NOT COVERED`
und die Produktfreigabe `false`; vier einzelne PCM-Messpunkte
können nicht die vollständige musikalische Korrektheit beweisen.


## Echte Projektzustände während aktiver Wiedergabe wiederherstellen

Für den zuständigen Plugin-Chat steht zusätzlich die **optionale**
Prüfung `run_live_state_replay.py` bereit. Anders als das normale
`--save-only` wird damit getestet, ob der konkrete VST3-Prozessor
während laufender Audio-Callbacks wiederholt seinen eigenen zuvor
gespeicherten Zustand annimmt.

```powershell
python run_live_state_replay.py --plugin "C:\VST3\Instrument.vst3" --host ".\125A_Test_Lab_State_Stress.exe" --out ".\REPLAY-ERGEBNISSE"
```

Die Native Engine ruft zuerst **ein echtes `getState()` am Plugin** auf,
verwendet ausschließlich diese vom Plugin selbst erzeugten Zustandsbytes
und ruft danach **500 `setState()` und 500 `getState()` während 2500
Audio-Callbacks** auf. Für sechs Kombinationen aus 44,1/48/96 kHz und
64/512 Samples ergeben sich 3.000 Wiederherstellungen, 3.000 Saves und
15.000 Audioaufrufe. Positive Ergebnisse müssen eine gemessene
Überlappung sowohl der Loads als auch der Saves mit laufender Wiedergabe
belegen. Fehlende, unvollständige, alte oder falsch zugeordnete
Berichte gelten als FAIL; die Fingerabdrücke von Plugin und Host werden
mitgeschrieben.

Die Prüfung ist bewusst ein **zusätzlicher Stresstest, kein universell
verlangter VST3-Host-Lebenszyklus**. Manche Plugins unterstützen
`setState()` ausdrücklich nur bei pausierter Verarbeitung. Ein
negatives Ergebnis erfordert daher eine Bewertung des jeweiligen
Plugin-Vertrags, nicht automatisch eine Produktfreigabe-Absage.
Die Prüfung garantiert auch keine musikalische Bank-Richtigkeit:
`bank_program_correctness = NOT COVERED`, sofern keine eigene
unabhängige Klang- und Presetreferenz vorliegt.

Die Windows-CI führt diese Funktion an einem echten korrekt
implementierten VST3 sowie einem absichtlich fehlerhaften VST3 aus,
der gültige Zustands-Restores während der Wiedergabe zurückweist.
Bei beiden werden 500 echte State-Replays pro Testfall versucht.
