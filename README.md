# 125A Plugin Test Lab

**Windows x64 · C++23 · Visual Studio 2022 · VST3 · GitHub Actions**

**P42 matched no-click GUI exploration (latest):** [merged PR #67](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/67), [five successful Windows workflows including P25 #42178099352](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42178099352). Every opt-in P41 automatic GUI click is now paired with a fresh **sham run using the same WM_MOUSEMOVE, timing, screenshots and controller snapshots but no mouse-button press**. The independent report distinguishes true click-associated parameter or visual changes from hover-only highlighting, animated backgrounds and unrelated state changes. A genuine VST3 hover-only negative fixture is correctly rejected. **Findings remain OBSERVATIONS_ONLY, not complete product UI coverage.** Native Windows CI requires no local Python. See [START-HERE.md](START-HERE.md) and [P42 docs](docs/ONE-COMMAND-QUICKCHECK.md).

**Latest P41 automatic GUI candidate exploration:** [Windows P25 run #42176006331](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42176006331), [merged PR #66](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/66). The shared Test Lab can now probe a bounded set of unknown Win32 VST3 GUI coordinates automatically, without a hand-written button map. It compares two real before-click snapshots and one after-click snapshot and every reported controller parameter from **fresh disposable plugin processes**, and distinguishes responsive, inert and visually stale surfaces. Real positive/negative VST3 fixtures pass Windows CI. **Explicit opt-in required** (`--gui-explore --acknowledge-gui-explore` with `--gui-host`); arbitrary clicks can trigger plugin actions. Findings are only `OBSERVATIONS_ONLY`, **never confirmation of intended functionality or product-release readiness**. See `START-HERE.md` and `docs/ONE-COMMAND-QUICKCHECK.md`.

**New P38 independent visual-only GUI checks:** [Windows CI 42169778586](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42169778586), [merged PR #63](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/63). The common GUI action workflow now verifies declared native mouse-click/drag transitions from real before/after Win32 painted pixels **even without a VST3 ParamID**. It catches inert or visually stale buttons, validated against independently defective source-built VST3s. A visual change is not proof of all underlying product semantics, and overall `product_gui_controls` remains `NOT COVERED` unless separately proven.

**Latest verified reusable GUI action driver (P37):** [P25 Windows run #42168448905](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42168448905), [merged PR #62](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/62). The shared Win32 VST3 test host now executes ordered multi-step click/drag sequences in one real editor window, validates before/after controller parameters and optionally real painted BMP pixels, and rejects deliberately broken native plugin/visual evidence. Use an independently approved `125a-gui-workflow-v1` profile and `--gui-workflow` with `--gui-host`. **This does not discover every undocumented button or certify full DAW behavior.**

**Latest validated shared tester:** [Windows P25 run #42164304275](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42164304275). [PR #60](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/60) adds automatic boundary/restore tests for all advertised automatable VST3 parameters, with an independently verified deliberately broken plugin; [PR #61](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/61) adds real Win32 editor mouse-click tests for both ON and OFF transitions from declared GUI profiles. The same source commit passed Windows P02, P03, P04, P25 and P29. Default QA and the optional `--active-replay` / `--dual-state-manifest` advanced suites remain available. **GUI controls not exposed as VST3 parameters still require mapped profiles; a technical PASS is not product release approval.** GitHub runners provide Python automatically; no installation is needed on the user's computer for GitHub CI.

The 125A Plugin Test Lab is an independent functional test host and test-oracle
suite. It supplements the [125A Plugin Tester](https://github.com/challanger2000/125A-Plugin-Tester)
and the Steinberg VST3 validator; it does not replace a complete commercial-DAW
compatibility test.

## Universal VST3 inspection (P22)

Run `125A_Test_Lab_Host.exe --inspect "<path-to-plugin.vst3>"` for
**any Windows x64 VST3 module**, without a Drumator-specific fixture.
The host enumerates all audio classes, processor interfaces, 32/64-bit
processing support and audio/event inputs/outputs with bus/channel counts.
`tests/verify_universal_discovery.py` independently validates its machine
records and produces JSON with applicable test families. Capability
discovery is **not** a claim that an unexecuted DSP, GUI or recall test passed.
The Windows P02 workflow proves P22 against two distinct real VST3
fixtures and rejects a deliberately invalid module.

## Universal multi-plugin batch inspection (P23)

The CLI `python tests/run_vst3_batch.py --host "<125A_Test_Lab_Host.exe>" --root "<VST3 folder>" --out "<report folder>"`
discovers all `.vst3` files and bundles recursively, with each plugin loaded
**in its own child process and a bounded timeout**. It produces
`BATCH-RESULT.json`, individual module logs, discovered audio/event
capabilities and explicit PASS/FAIL per plugin. If even one module fails,
the batch exits nonzero; successfully inspected modules retain their
independent results. This is universal capability discovery, not a claim
that every plugin's audio or GUI behavior passed.

[Verified P23 Windows Actions run](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42041631444):
two real, unrelated VST3 test fixtures PASS together, while a malformed
module is correctly isolated as FAIL alongside an otherwise healthy one.

## Universal VST3 concurrency and sample-rate stress (P25)

P25 adds a separate C++23 Win32 VST3 host exercising real process() on the
audio thread while getState()/setState() remain serialized on the main
control thread, consistent with Steinberg's VST3 threading contract.
The real VST3 state fixture suite verifies 500 saves per scenario, 2,500
process callbacks (including zero-frame calls), competing control/RT state
writers, a save-only normal playback mode, and 44.1/48/96 kHz timing.

The Windows evidence [P25 Actions 42046335507](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42046335507)
shows 11/11 expected outcomes: all positive fixtures PASS, 21 torn snapshots
detected in the deliberately defective fixture, 100/500 save failures
detected in the broken-playback-save fixture, and a wrong 96 kHz timed ramp
rejected. P25 does not certify production plugins without adapters,
instrument voice-limit tests, proprietary GUI recovery or DAW integration.
See docs/P25-UNIVERSAL-COVERAGE.md for every NOT COVERED item.

## Universal MIDI instrument voice/save/restore stress (P29)

P29 provides a standalone, product-neutral Windows VST3 host that delivers
actual MIDI note events, performs 500 `getState()` saves during active
playback (without parameter automation), and verifies fresh-instance
`setState()` recall against an independent audio oracle. Four approved
synthetic voice tiers (0, 1, 8, 32) are covered. Two deliberately defective
test instruments verify that missing voices and save failures are detected.

[Windows CI P29 PASS](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42054620680).
The new test is not specific to Drumator or AWE. **For a production
instrument, a separate adapter must declare its supported voice limits and
expected audio**; the synthetic 32-voice limit is not universal.

## Universal VST3 controller reconnect regression (P30)

P30 tests **actual VST3** processor-controller `IConnectionPoint`
connections and disconnections, invalid component state rejection,
reconnection, controller `setComponentState`, independent normalized
parameter values, and processed PCM. A deliberately stale controller
is required to fail the independent semantic oracle even when its
VST3 API calls return success.

[Verified P30 Windows CI](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42057621836).
The same commit passed the existing P02, P03, P04, P25–P28 and P29
regressions. This verifies the **connection/control-state contract**,
not arbitrary GUI pixels or product-specific error semantics. Those
remain NOT COVERED without their own independent adapter.

## P31 native GUI recovery

P31 uses a real VST3 IPlugView on Win32 HWND, samples actual painted RGB
after controller disconnect/reconnect and checks it against an independent
processor/controller/PCM oracle. A deliberately stale indicator is detected.
[Windows P31 PASS](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42060095211).
Other product editor semantics remain NOT COVERED without adapters.

## P32 — External adapters for real production plugins

P32 pins the exact VST3 module by SHA-256 and accepts an independent JSON
adapter with a declared product version and source commit. It invokes
the native stress host **without synthetic state injection** and checks
500 project saves against externally specified expectations while audio
callbacks run. Missing expectations, altered modules and bad saves fail closed.

[Verified P32 Windows suite](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42063464726):
one good real VST3 fixture PASS, a broken-save VST3 FAIL (100/500
rejections), and wrong-hash/missing-oracle adapters rejected. See
[adapter format and exact coverage](docs/P32-PRODUCT-ADAPTERS.md).
Product-specific bank/program correctness, musical PCM, polyphony, and
GUI status are explicitly **NOT COVERED** without their own oracles.

## What actually passed

All gates below have verified Windows GitHub Actions evidence, not just
source-level assertions. The reproducible pull-request benchmark checks
product commit `eed1bf232b61f6fb725ca00d82a99658cfba07e2`. A **manual
Actions run can select another Drumator branch, tag or exact SHA** and records
the resolved tested commit in its artifact.

| Gate | Real evidence |
| --- | --- |
| P01 / P02 | Genuine VST3 host/process callbacks, transport + MIDI, 44.1 kHz PCM24 WAV; independent full-frame audio oracle; deliberately broken NaN plugin detected |
| P03 | Actual Drumator SWING 0/50% matches independent triplet timing; fresh process/component state save/reload produces bit-identical stereo audio; corrupt project state rejected |
| P04 | Win32 VST3 GUI host on a controlled click-enabled plugin, two editor cycles, inert negative control, and explicit editorless INCONCLUSIVE |
| P05 | 36 real Drumator VST3 renders (90/120/150 BPM × Swing 0/25/50 × 64/127/512/1024-frame blocks), with independent onset and byte-for-byte block partition checks |
| P06 | 18 real MIDI exporter file outputs validated by an independent Standard MIDI File parser; corrupt MIDI inputs rejected |
| P07 | 1,280 real Beat Creator A/B/C vectors across 10 genres, two pattern lengths, two complexities and 32 seeds; five-point Complexity helper, protected pattern data and independent negative cases |
| P08 | 18 real offline WAV exporter outputs, stereo PCM24 format, exact duration and sample-level onset matching to independently validated MIDI timeline; corrupt WAV inputs rejected |
| P09 | **Actual Drumator editor** attached to a Win32 HWND, real mouse clicks toggle and restore Limiter, GENERATE→CANCEL preserves component state, GENERATE→APPLY→CONFIRM changes three distinct A/B/C patterns, D–H and hidden rows remain unchanged |
| P10 | All four actual GUI export options open a real Windows Shell Save dialog; CANCEL writes no file and keeps the processor's project state identical |
| P11 | All four GUI Save As options genuinely write pattern/song MIDI/WAV files; independent parsers verify note timing, A/REST/A song, stereo PCM24 audio format, sample-exact attack positions, and immutable project state |
| P13 — source | Four actual GUI drag gestures generated and independently verified Pattern/Song MIDI/WAV transient files on the regular Windows CI host |
| P15 — receiver contract | Four native `CF_HDROP` receiver callback/file-copy checks using a synthetic COM data object, run unattended on Windows |
| P16 — real OLE integration | **PASS:** ephemeral Windows VM creates its own active RDP desktop, physically drags all four exports from the real Drumator editor and the separate Windows `IDropTarget` records four real `DragEnter`/`Drop` callbacks; received files pass independent validation |
| P17 — editor lifecycle | 16 actual VST3 editor detach/reattach cycles with valid native HWND each time and byte-identical processor state after every cycle; mandatory Windows P03 integration gate |
| P18 — fresh-process recall matrix | 0/25/50 Swing states each saved and restored through new VST3 host processes; independently verified DM18 CRC and byte-identical non-silent stereo 24-bit PCM after reload |
| P19 — real GUI control stress | 96 actual Win32 editor limiter clicks, 48 alternate-state changes and byte-identical processor-state reversals, required by Windows CI |
| P20 — invalid state matrix | 16 individually corrupted/truncated DM18 project states rejected by the actual VST3 host, no audio files emitted, tested rejection paths |
| P23 — universal folder batch | Recursively discovers arbitrary VST3s; independent child-process inspection, timeout and isolated per-plugin JSON/errors; Windows positive and mixed-negative fixture tests PASS |
| P22 — universal class/bus discovery | Product-neutral inspection of VST3 processor sample formats and all audio/event buses; independent eligibility JSON and invalid-module negative control in Windows CI |
| P21 — exact-SHA release evidence | Fail-closed `RELEASE-EVIDENCE.json` generated from 13 independent gate log files, exact product commit recorded; separate DAW/OLE workflow coverage explicitly identified |

**Latest P01–P11 and P13 drag-source PASS:** [Windows Actions 41952977868](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41952977868).
**True interapplication COM/OLE reception PASS:** [P16 interactive Windows run 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955).
**Latest P17–P21 mandatory Windows integration PASS:** [Actions 42037199490](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42037199490). The artifact contains `RELEASE-EVIDENCE.json` with 13/13 gate entries PASS for the exact pinned product SHA.

P09 required the second APPLY click because the factory Pattern A is already
occupied. Tests must honor this confirmation rather than bypassing it.

## What this does *not* prove

**The test environment is not a complete automated release certification.**
The following remain separate acceptance requirements:

- P16 proves real cross-window OLE delivery to the independent native Windows
  receiver, but does not exercise any proprietary DAW's drop target.
- Full coverage of all plugin popup menus, sample editors, mouse gestures,
  preset browser navigation, zoom variants and plugin window stress.
- End-to-end compatibility with Fender Studio Pro, including project save,
  automation and actual user workflows inside that proprietary DAW.
- Every conceivable kit, host tempo, sample rate, export combination and
  randomized stress/failure case.

A green result proves the named behaviors at the recorded product revision;
it is not blanket certification of all GUI, host or DAW workflows.

## P14 / P16 actual interactive Windows OLE acceptance

P14 produces the portable acceptance kit. **P16 now automates the native
end-to-end drag-and-drop on GitHub Actions itself**: within the disposable
Windows 2022 VM, it starts a temporary local RDP desktop user, launches
the genuine source-built Drumator editor and separate native COM receiver,
then performs physical mouse drags of Pattern MIDI/WAV and Song MIDI/WAV.
A PASS requires four actual `CF_HDROP` target callbacks, retained source
files and independently verified received files. The test destroys its
temporary Windows user and RDP setup after execution.

**Verified P16 PASS:** [Windows Actions 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955).
Evidence artifact: `125A-Test-Lab-P16-Real-OLE-Evidence`, including
`P16-RESULT.txt`, native OLE output and received-file validation.

The optional P14 portable ZIP remains available for other desktops.
The automated P16 test does **not** require the developer's PC.

P16 is not a test of any particular commercial DAW's proprietary drop target.

## Reproduce

Use the [GitHub Actions workflows](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions):
- `P03 Real Drumator Swing Host Test`: runs P03–P11 plus P13 source tests
  on `windows-2022`. For a manual run, enter a **Drumator branch, tag or full
  commit SHA** in `drumator_ref`; the report identifies the resolved SHA.
  PR checks retain the reproducible pinned baseline.
- `P14 Interactive Windows OLE Acceptance Package`: builds the P14 kit and runs P16 true physical OLE desktop acceptance inside an ephemeral local RDP session on `windows-2022`.
- `P04 Native VST3 GUI Input Test`: validate independent GUI-host fixtures.
- `125A Test Lab - Windows P02`: build the console test host and render
  deterministic VST3 audio fixtures.

CI artifacts include diagnostics, selected WAV/MIDI/GUI evidence and a test host.
See [START-HERE.md](START-HERE.md) for executable CLI usage, safeguards and
interpretation.

## Public repository and licensing

No DAW licenses, personal presets, third-party samples or secrets belong here.
Synthetic sample content is generated during CI, not shipped commercially.
Native VST3 modules execute code; use trusted binaries and isolated runners.
