# START HERE — 125A Plugin Test Lab

## Latest usable Windows test kit (6 November 2026)

## Current test acceptance and latest proof

**Latest verified Windows quickcheck:** pull requests #47 and #48,
validated in [Windows P25 pipeline](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42135595956).
The real Drumator product regression remains independently verified in P03.
The complete relevant Windows CI for the latest changes has passed,
including the real production VST3 GUI/exports regression and all 13
independent product-domain evidence gates.

The standalone test can now compare real captured PCM24 against an
**independently supplied golden WAV reference** via `--reference-wav`.
Native Windows CI also independently calculated an expected waveform for a
source-built VST3 and required deliberate wrong/silent recordings to fail.
See [audio reference oracle](docs/AUDIO-REFERENCE-ORACLE.md).

The six-rate/buffer stress measurements now preserve actual audio callback
deadlines, 99th-percentile processing times and overruns. Timing violations
appear explicitly as **FAIL** in the German results report, even when basic
VST3 processing and save APIs succeed. Native Windows runner timing is
observational (OS scheduling can affect results), not a guarantee of
hard-realtime behavior on every workstation.

The one-click Windows test now opens the captured project state in **two
separate newly launched native VST3 host processes** and re-saves the
state; rejected loads or missing evidence produce FAIL. The native state
bounds accept nonempty serialized payloads below **128 MiB**, including
large instrument state data. For products with an approved byte-exact
state reference, `expected_saved_state_sha256` additionally checks both
post-reload state artifacts to catch silent state corruption.

The real Drumator P21 report no longer treats arbitrary `[PASS]` log
text as release evidence. Each of its 13 gates now demands its own
complete independent oracle marker; multi-recall demands three
observations. Wrong, duplicated, incomplete, missing or contradictory gate markers
fail the automated gate. A complete log copied from another run cannot
be cryptographically excluded by marker checks alone. [Verified Windows P03 run](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42102036359).

**Remaining hard boundary:** success in the standalone host does not
prove product-specific musical semantics, every UI control, commercial
DAW session recall, or DAW drag-and-drop. These still require independent
product-specific reference data or real DAW integration. They remain
`NOT COVERED` rather than being called PASS.



The currently verified native Windows x64 quickcheck runs a real third-party
VST3 through six combinations of 44.1/48/96 kHz and 64/512-sample buffers:
**15,000 audio callbacks and 3,000 project-state saves**, plus an
independent native PCM/state capture. It pins the exact VST3 module SHA-256,
rejects missing or stale evidence and never treats technical success as full
product release approval.

**Simplest Windows use:** drag the trusted installed `.vst3` **folder**
onto `Run-VST3-Test.cmd` in the extracted `PORTABLE` package.
The test runs native audio playback, repeated state saves, rendering,
state capture and actual editor open/close checks. It automatically opens
`RESULTS/<Plugin>/TESTERGEBNIS.html`, with simple German
**BESTANDEN / FEHLER / NICHT GEPRUEFT** verdicts. If the plugin has no editor, GUI is `NOT COVERED`.
An external per-product control map can additionally automate click/pixel
checks (see `docs/ONE-COMMAND-QUICKCHECK.md`).

**Use without compiling the test host yourself:** download the latest
successful [P25 Windows Actions artifact](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42135595956),
open its `PORTABLE` folder, and follow `README.md`. The artifact
contains all three native x64 audio/state/GUI hosts, the drag-and-drop launcher, supporting Python scripts
and SHA-256 checksums. Python 3 on Windows is required.

```powershell
python run_plugin_quickcheck.py --plugin "C:\VST3\Plugin.vst3" --host ".\125A_Test_Lab_Host.exe" --stress-host ".\125A_Test_Lab_State_Stress.exe" --out ".\QA-Results"
```

**Native GUI tests:** the same portable artifact contains
`125A_Test_Lab_GUI.exe`. The generic click-coordinate and
painted-pixel test runner lives in
[tests/run_gui_control_matrix.py](tests/run_gui_control_matrix.py) with
[GUI contract](docs/GUI-CONTROL-MATRIX.md). An independently specified
control map is needed; the host cannot automatically infer every knob,
dialog or product-specific action. A real mouse click, normalized controller
value and rendered GUI bitmap can be checked in the same host instance.
A deliberately stale painted UI is detected even when the controller passes.

Real fresh-process state recall is described in
[REAL-STATE-RELOAD.md](docs/REAL-STATE-RELOAD.md); actual Win32 editor
capture in [NATIVE-GUI-CAPTURE.md](docs/NATIVE-GUI-CAPTURE.md).
For the mandatory 18-domain release NO-GO audit, see
[PRODUCT-USER-ACCEPTANCE.md](docs/PRODUCT-USER-ACCEPTANCE.md).

**Important:** These are infrastructure and user-workflow building blocks.
Some production-specific MIDI/WAV operations, complete control inventories,
preset semantics and commercial DAW acceptance still require trusted
product-specific adapters or a DAW-equipped runner. Missing checks are
`NOT COVERED`, and no technical quickcheck alone authorizes a release.
All older milestones below are historical snapshots and their original
coverage limitations must be read alongside the newer capabilities above.

## Established and verified

P01–P11 plus the P13 **GUI drag-source** test passed in
[Windows Actions 41952977868](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41952977868).
**P16 real interapplication OLE acceptance passed** in [Windows Actions 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955): four native `CF_HDROP` receiver callbacks and independently validated Pattern/Song MIDI/WAV files in a genuine temporary RDP desktop.
P09 proved real editor/Beat Creator interaction, P10 proved native Windows
Save-dialog cancellation, and P11 proved **all four GUI MIDI/WAV Save As
exports** create correct independent music files. P02/P04 host self-tests
also passed.

The verified benchmark source was `challanger2000/125A-Drumator-Final`
SHA `eed1bf232b61f6fb725ca00d82a99658cfba07e2`.
**Newer code can be selected manually via GitHub Actions**. PR benchmarks
continue to pin the above SHA; the manual run logs the SHA it actually
checked. Never assume a benchmark PASS proves an untested newer build.

## Run workflows

Go to **Actions → P03 Real Drumator Swing Host Test → Run workflow**.
In the `drumator_ref` field, enter a product branch, tag or complete
40-character commit SHA. Default: `develop/beat-creator-10-styles-20261102`.
Choose the Test Lab `main` branch and start the workflow. This builds the
**selected product revision**, generates synthetic kits and vectors, and
reports the exact resolved SHA in `TESTED-PRODUCT-REVISION.txt`.
No local Windows installation, user sample library or DAW is required.

For pull requests that change the Test Lab itself, the workflow uses the
original pinned product commit instead, to make infrastructure regressions
reproducible.

The report names the exact commit and gives PASS/FAIL evidence for:
- host VST3 component lifecycle and genuine DSP processing
- 36 combinations of tempo, Swing and audio process-buffer partitions
- real audio, saved state, rejected corrupted state
- MIDI/WAV export core and independent file/timing checks
- Beat Creator A/B/C algorithm stress and five-point Complexity helper
- real Win32 editor, Limiter, Beat Creator GENERATE/CANCEL/APPLY/CONFIRM
- four true Win32 Save As dialogs and non-destructive CANCEL
- four actual GUI Pattern/Song MIDI/WAV Save As exports and independent musical checks
- P13 genuine GUI drag-source gesture: four independently validated retained files
- P15 synthetic receiver contract for four COM CF_HDROP callbacks
- P16 actual physical drag-and-drop into separate native COM receiver, four files PASS
- P17 16 real Drumator editor detach/reattach cycles, each with valid HWND and unchanged processor state
- P18 three separate Swing 0/25/50% project state save/restore roundtrips in fresh VST3 host processes, with sample-exact stereo PCM and state CRC checks
- P19 96 real GUI limiter clicks, 48 exact processor state reversals
- P20 16 corrupted/truncated project states safely rejected without audio
- P21 fail-closed machine-readable release evidence JSON with 13/13 independent gates and exact product SHA
- negative audio/MIDI/WAV/GUI fixtures and explicit INCONCLUSIVE cases

The P04 and P02 workflows separately check the GUI-host and audio-host
infrastructure itself.

## Machine-readable release evidence

The P03 workflow now creates `artifact/P03/RELEASE-EVIDENCE.json`, uploaded
as part of `125A-Test-Lab-P03-Drumator-Audio-Evidence`. It asserts that every
expected per-gate log exists and contains PASS without FAIL; otherwise the
P21 step fails. It records the exact 40-character tested product commit.
The current verified run is [42037199490](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42037199490):
all 13 listed integration gates PASS for product SHA
`eed1bf232b61f6fb725ca00d82a99658cfba07e2`.

This file does not falsely import P02/P04 or P15/P16 results from separate
workflows. Check those runs separately when assessing a full release.
A manual P03 run can select a newer product SHA.


## P25 — Universal concurrency and playback-save stress

The independent Windows x64 C++23 state-stress executable is
`125A_Test_Lab_State_Stress.exe`; use
`.github/workflows/p25-state-stress.yml` for its verified positive and
negative fixtures. The host invokes real VST3 process()/setState()/getState(),
including 500 saves during playback, 44.1/48/96 kHz processing, zero-frame
calls, and sample-rate-sensitive reference measurements.
[Verified Windows run 42046335507](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42046335507).

The built-in paired/ramp oracles are synthetic test-fixture-specific.
Production plugins need separate approved state and audio oracles; without
one, domain correctness is NOT COVERED. P25 does not yet include maximum
voices or GUI/controller failure-recovery acceptance. Details and the
requirement-to-evidence table: docs/P25-UNIVERSAL-COVERAGE.md.

## P26–P28 — Universal recovery, PCM equivalence and callback deadlines

P26 records a genuine VST3 control/audio sequence: load valid state A,
process audio, reject an invalid state, verify byte-identical state and PCM
after the failed operation, load valid state B, then restore A. Expected
state SHA-256 and expected 128 stereo float samples per stage are supplied
by an independent JSON adapter, **not guessed by the host**. A deliberately
broken VST3 that changes its state despite returning an error is rejected.
Verified: [P26 Windows run 42048372929](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42048372929).

P27 records 250 ms of native VST3 stereo PCM for each sample rate
44.1/48/96 kHz and host partition 17/127/512, including zero-frame calls.
The independent oracle validates the sample-accurate time curve and exact
PCM identity between block partitions. Both intentionally incorrect
sample-rate and block-count smoothing fixtures are detected.
Verified: [P27 Windows run 42049745921](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42049745921).

P28 adds preallocated callback timing instrumentation, p95/p99/max and
an opt-in strict audio-deadline gate. A defective VST3 intentionally sleeps
inside process() to prove that this is not silently reported as PASS.
Consult the P25 Windows workflow for its actual run result; CI timing is
not equivalent to a certified low-latency DAW machine.

The portable native hosts are general-purpose VST3 executables, but their
synthetic paired-state and envelope reference functions apply **only**
when an external product adapter supplies the matching contract.
Maximum-voice event orchestration and controller/GUI transport-recovery
remain NOT COVERED. The complete matrix is in
docs/P25-UNIVERSAL-COVERAGE.md.

## Generic plugin discovery

```powershell
.\125A_Test_Lab_Host.exe --inspect "C:\\VST3\\SomePlugin.vst3" > capabilities.log
python tests/verify_universal_discovery.py capabilities.log capabilities.json
```

P22 requires no Drumator-specific source, project state or DAW. It reports
audio classes, processing sample formats, audio/event bus topologies and which
test families may apply. An `ELIGIBLE` result means the capability exists,
**not** that an interactive, audio or state test was executed. Unsupported
or unmeasured operations remain NOT_APPLICABLE or NOT_YET_DETERMINED.
The GitHub P02 workflow tests P22 with two independent VST3 fixtures
and a malformed-module negative control.

## P23 — Batch inspection of arbitrary VST3 plugins

```powershell
python tests/run_vst3_batch.py --host "C:\\TestLab\\125A_Test_Lab_Host.exe" --root "C:\\MyVST3" --out "C:\\TestLabResults" --timeout 30
```

Run only with VST3 modules you trust: each native plugin executes in
a separate subprocess. A crash, timeout, invalid binary or failed
VST3 initialization is isolated and recorded without losing the
results for the remaining plugins. The final `BATCH-RESULT.json`
lists every discovered bundle and its class/bus capabilities,
explicitly marking audio, GUI and state tests as NOT_EXECUTED.
A bad module produces an overall FAIL but never a false PASS.
P23 verified Windows run: [42041631444](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42041631444).

## Standalone Windows CLI

Extract the corresponding GitHub Actions artifact before running:

```powershell
.\125A_Test_Lab_Host.exe --selftest
.\125A_Test_Lab_Host.exe --render "C:\Path\Plugin.vst3" ".\render.wav"
.\125A_Test_Lab_Host.exe --render-state "C:\Path\Plugin.vst3" ".\kit.bin" ".\render.wav"
.\125A_Test_Lab_Host.exe --render-state-save "C:\Path\Plugin.vst3" ".\kit.bin" ".\render.wav" ".\saved-state.bin"
.\125A_Test_Lab_Host.exe --render-state-at "C:\Path\Plugin.vst3" ".\kit.bin" ".\render.wav" 120 127

.\125A_Test_Lab_GUI.exe --probe "C:\Path\Plugin.vst3"
.\125A_Test_Lab_GUI.exe --prove-click "C:\Path\125A_QA_GUI_Click.vst3" 9001
```

For `--prove-click`, use only a specially prepared VST3 exposing a
documented controller parameter that switches from 0 to 1 when clicked.
The main host's `--render-state-at` supports sample-exact tempos 60–240
and blocks of 16–2048 frames, with audio at 44.1 kHz and a 4/4 host.

The P09 real-product GUI test runs from source under the pinned CI
workflow because it requires a complete VST3 bundle with the actual
`Contents/Resources` tree, a COM-initialized Win32 UI thread, a connected
controller and processor, and a state oracle. Do not point the GUI host
at an unbundled DLL and expect a complete editor.

## P14 / P16 native interactive OLE acceptance

The P14 workflow builds the full source-built Drumator VST3 and synthetic
A/REST/A test kit. **P16 additionally performs true desktop-native
Drag-and-Drop inside GitHub Actions**. It provisions a temporary local
RDP user on the disposable Windows 2022 runner, keeps an interactive
desktop connected, launches the actual editor and an independent Win32
COM `IDropTarget`, and uses physical mouse input to deliver all four
Pattern/Song MIDI/WAV exports via `CF_HDROP`.

Verified: [P16 Windows Actions 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955),
including the `125A-Test-Lab-P16-Real-OLE-Evidence` artifact. Recorded
`P16-RESULT.txt` reports PASS for four received callbacks and four
independently checked files. No developer Windows installation is needed.

The optional P14 portable ZIP and `Run-OLE-Test.cmd` remain available for
manual reproduction. The native receiver acceptance does not assert
compatibility with a specific commercial DAW's internal drop target.

## P29 — Universal instrument voice/playback-save and fresh recall

The source-built generic MIDI instrument host `125A_Test_Lab_Voice_Stress.exe`
uses real VST3 `IEventList` note-on messages, `IComponent::getState`,
`setState`, and `IAudioProcessor::process` for adapter-approved voice
tiers of 0, 1, 8 and 32. For each case it executes 2500 audio callbacks,
500 state saves **while playback is still active**, and recalls the final
state in a new component instance. An independent Python oracle checks
the instrument's expected audio values before and after recall.

Two deliberately defective VST3 instruments are required to fail domain
checks: one refuses 100 of 500 saves; another silently caps active voices
at four instead of the fixture's declared maximum of 32.

[Verified P29 Windows run](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42054620680) and
[PR #26](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/26).

This validates a reusable MIDI/voice **test harness** and synthetic oracle.
It does not verify arbitrary production synthesizers, infer their maximum
polyphony or establish their musical output without a separate product adapter.
GUI/controller transport fault recovery is still NOT COVERED.

## Outcome semantics

**PASS** — independent, observed expected behavior under tested conditions.

**FAIL** — test assertion, plugin behavior, environment or test-host error
must be diagnosed; no approval until resolved.

**INCONCLUSIVE** — the scenario was attempted but cannot be determined;
for instance, the plugin does not expose an editor.

**NOT COVERED** — no verified test exists for that behavior.

A green CI run proves the explicitly tested behaviors and source
revision. P11 Save As, P13 GUI source generation, P15 receiver contract,
and P16 actual interapplication OLE reception are PASS. Proprietary DAW
integration and untested GUI workflows are tracked separately.

## P30 — Universal controller connection recovery

The source-built `125A_Test_Lab_Controller_Recovery.exe` runs actual VST3
`IConnectionPoint::connect/disconnect` on a separate processor and controller,
rejects an invalid component state while disconnected, reconnects the
component/controller, restores component state, checks controller parameters
and renders actual processor PCM. The independent oracle
`tests/verify_controller_recovery.py` checks four snapshots, including
normalized controller values, processor state and audio amplitude.

A deliberately faulty controller returns success but retains stale
parameters. Its API execution succeeds, yet the independent oracle
detects the erroneous state after reconnection. The positive fixture
and negative control both passed the [P30 Windows run](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42057621836).
PR #27 was merged at commit `de4964f937c551717e86ba491c947da67b21744d`.

**Coverage boundary:** this verifies a VST3 connection-point and
controller-state synchronization scenario, not physical GUI pixels,
visual status indicators or arbitrary product-specific connection
errors. Those need a product controller/GUI adapter with its own
independent oracle; mark such checks NOT COVERED until executed.

## P31 — Native GUI status recovery

The P31 fixture opens a real VST3 editor through IPlugView on a
Win32 child window. It samples the *painted* indicator pixel after
state rejection, controller disconnect/reconnect and valid recovery.
The independent oracle checks actual RGB, controller values,
processor state and rendered PCM. A deliberately stale visual indicator
must be detected despite successful API return codes.

Windows PASS: https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42060095211
PR #28 merged in main.

A generic host does not know arbitrary product indicator geometry or
semantics. Those visual checks require a product-specific oracle and
remain NOT COVERED otherwise.

## P32 — External product adapters (fail closed)

Run `python tests/run_product_adapter.py --adapter adapter.json --out results`
on Windows x64 with the approved native Test Lab host and an exact trusted
VST3 module. [Adapter schema, usage and limitations](docs/P32-PRODUCT-ADAPTERS.md).

The independent JSON manifest declares product name/version/source commit,
pins the actual module binary's SHA-256, and supplies expected native API
evidence for the supported stereo playback/save scenario. The runner uses
`--save-only`: **no synthetic bank/program state writes** to an unknown
product. Missing oracle entries, failed saves, incorrect binary hashes,
missing host evidence and timeouts all reject the test.

[Verified Windows run 42063464726](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42063464726):
good VST3 PASS, intentionally broken playback-save VST3 FAIL with 100
rejected saves out of 500, wrong hash and missing oracle both rejected.
The declared product version and commit are metadata, not cryptographically
verified build provenance; the binary file's SHA-256 is verified.

Do not interpret technical API PASS as semantic correctness. Product
bank/program constraints, audio identity, voice limits and GUI status
remain NOT COVERED until an approved separate oracle actually runs.

## Security and policy

This repository is public. Do not commit purchased samples, user kits,
private plugins, personal data, licenses or credentials. The test kits
are synthesised, and third-party plugins execute as native code.
Use sandboxed runners for untrusted binaries.

Test Lab is a quality-assurance system, **not** the product release
repository or Gumroad release process.
