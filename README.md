**P99 optional REA binary analysis:** The P74/P75 pipeline can now request
SHA-pinned REA/Ghidra native VST3 observations. **Default: NOT RUN**;
results are unreviewed static observations, never a DSP, GUI or release
PASS. REA/Node/Ghidra are not automatically installed. See
[docs/P99-REA-BINARY-ANALYSIS.md](docs/P99-REA-BINARY-ANALYSIS.md).

# 125A Plugin Test Lab

**P91 actual REAPER DAW integration:** Independent [Windows Actions run #42391164169](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42391164169) ran real REAPER 7.83 with a source-built VST3, created MIDI, saved and reopened the `.RPP` project and rendered a genuine 44.1 kHz/24-bit stereo WAV. The fixture is intentionally silent: this proves basic DAW workflow, **not** instrument sound, complete product coverage, loaded-module path attestation or physical ASIO hardware. A separate explicit self-hosted REAPER adapter can test reviewed installed plugins. [Instructions](docs/P91-REAPER-DAW-INTEGRATION.md).

**P76 universal WAV/MIDI export evidence:** P65/P67 test plans may now include a generic `export_artifact` case checking real WAV PCM frame format, SMF MIDI note-on timeline and independently approved exact output SHA256. Any missing, truncated or mismatching file blocks required coverage. A standalone oracle cannot itself trigger the plugin's exporter, and CI distinguishes independently generated fixture files from genuine product output. [P76 scope](docs/P76-WAV-MIDI-ORACLES.md).


**P75 universal multi-VST3 batch QA:** Read-only inventory of up to 32 real VST3s in separate bounded processes, or a single per-plugin selection file activating the native technical audio baseline only for reviewed plugins. Defective/timeout child results remain FAIL while later plugins continue. One aggregate report, no product-specific QA code or release approval. [P75 usage](docs/P75-UNIVERSAL-BATCH-QA.md).


**P74 single-command universal VST3 QA:** Run `tests/run_universal_qa.py` to combine automatic ABI/GUI inventory, optional real audio/state stress tests, and strictly approved P65/P66 + P67 feature verification in one fail-closed report. The report distinguishes `INVENTORY_COMPLETE`, `TECHNICAL_BASELINE_PASS`, `DECLARED_COVERAGE_PASS`, and `FAIL`; never asserts full commercial release. [Details](docs/P74-UNIVERSAL-QA-PIPELINE.md).


**P73 headless and technical onboarding:** The same P72 one-command discovery handles plugins that expose no VST3 editor without fabricating GUI controls, and an explicit `--run-technical-baseline` option runs the existing general native playback, sample-rate, state save/recall checks after accepting both audio and stress host executables. No hardware/DAW or product approval claims. [Headless/technical details](docs/P73-HEADLESS-AUTOCHECK.md).


**P71/P72 one-command onboarding:** Unified native HWND and custom-painted VST3 GUI discovery (deduplicated candidates, no clicks by default), plus one read-only command combining P68 plugin ABI metadata with GUI candidates and a concrete product-owner review task list. No product-specific Test Lab code or automated release claims. [Universal onboarding](docs/P71-P72-UNIVERSAL-ONBOARDING.md).


**P70 universal custom-painted GUI candidates:** Static native editor BMP foreground-region discovery proposes possible click targets even for one-HWND painted UIs, with **no click by default**. Explicit opt-in can feed candidates into existing sham-controlled P42 native GUI exploration. The detector cannot know control semantics or certify complete coverage. [P70 limitations and tests](docs/P70-PAINTED-CANDIDATES.md).


**P69 native HWND-guided GUI exploration:** Discover visible/enabled standard button HWNDs in the real VST3 editor, suggest native center click points without using a generic grid, and optionally run the existing P42 sham-controlled real-click analyzer only after explicit opt-in. Default remains read-only. [P69 scope](docs/P69-HWND-GUIDED-EXPLORATION.md).


**P68 automatic read-only VST3 inventory:** The common Windows GUI host now detects actual audio/event buses, parameter counts, automation flags and editor availability from the plugin ABI and produces a **non-executable** proposed P65/P66 plan. It does not invent GUI positions or musical reference values; each plugin chat reviews expectations before activation. See [P68 discovery](docs/P68-VST3-AUTO-DISCOVERY.md).


**P67 mandatory product-feature coverage:** The versioned P65/P66 test-plan runner now accepts a separately reviewed `--coverage-matrix` containing required and optional product features with exact linked native test cases. Green VST3 results **do not** imply complete coverage: any declared required feature without passing native case evidence becomes `NOT COVERED`, `NOT RUN` or `FAIL`, blocks the coverage gate, and appears by name in `PRODUCT-FEATURE-COVERAGE.json`. Without a matrix, coverage is explicitly `NOT DECLARED`. This does not certify the product's entire feature inventory, hardware ASIO, DAW or commercial release. [P67 specification](docs/P67-REQUIRED-FEATURE-COVERAGE.md).


**P65 standard plugin-specific test plans:** All 125A plugin development chats can now supply a single versioned JSON plan with exact VST3/host hashes, named real GUI-workflow and bidirectional knob-sweep expectations. The shared Test Lab runs the existing native Windows engines without per-plugin code changes; case-level PASS/FAIL/NOT RUN, immutable fingerprints, and explicit ASIO/DAW/whole-product NOT COVERED remain enforced. [Specification and handoff](docs/P65-PRODUCT-TEST-PLANS.md).


**P59 hardware one-click workflow:** A protected/explicitly opted-in self-hosted Windows Actions workflow can now build P58, detect the selected installed ASIO driver's registry CLSID, hash the actual VST3/executable and run the P56 physical callback matrix without manual hash/plan entry. Only redacted callback statistics are uploaded. It requires a dedicated isolated Windows machine, secure runner configuration and explicit consent; **the public GitHub cloud CI still reports real ASIO hardware NOT RUN.** [Instructions and public-runner security caveats](docs/P59-HARDWARE-ONE-CLICK.md).


**P58 native real ASIO callback host:** The Test Lab now contains an optional source-built Windows x64 `125A_Test_Lab_Physical_ASIO.exe`: it instantiates the real registered ASIO COM driver, creates genuine device buffers, runs native VST3 `process()` from hardware driver callbacks, and measures callback overruns/XRUN signals. Source-built Windows CI can compile the host using a separately obtained ASIO SDK and reject unregistered-driver scenarios. **GitHub Windows-2022 has no physical device: hardware ASIO remains NOT RUN, and commercial DAW coverage remains NOT RUN.** Documentation: [P58](docs/P58-NATIVE-ASIO-HOST.md).


**Historical P56 hardware-ASIO qualification (superseded by P58/P95):** `tests/run_physical_asio.py` validates an explicitly approved native ASIO-executor contract (exact DLL/executor hashes, actual local ASIO driver registration, per-run nonce, callback counts, XRUNs/deadline errors). An opt-in `self-hosted, Windows, X64, 125A-ASIO` GitHub workflow is available. **The P56 milestone originally did not include the executor; P58 later added a native Windows ASIO host. Actual hardware/DAW sessions remain `NOT_RUN`, not PASS.** Cloud Windows CI verifies only fail-closed contracts and reports `NOT_RUN`. See [P56 details](docs/P56-PHYSICAL-ASIO-GATE.md).


**Windows x64 · C++23 · Visual Studio 2022 · VST3 · GitHub Actions**

**P53 latest independent current AWE P137/V11 acceptance — PASS:** [merged PR #80](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/80), [real Windows source-built AWE + independent Test Lab #42242609568 SUCCESS](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42242609568) and [universal P02 #42242609478 SUCCESS](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42242609478). Tested exact current product source `d7f534a5eb44f56942706019a6973ad3c0d5ce40` (P137 optimizations, P133 8×8 original Creative FX/V11 state, P134 CC120) **read-only**: **44/44 native product CTests, 537/537 real VST3 module validator, independent Lab-host playback/save/GUI/multi-instance `TECHNICAL_PASS`**, strict negative verification against fictitious ASIO/DAW/ROM/chorus/release approvals. Artifact: `125A-AWE-P53-Actual-VST3-Independent-Test-Lab`. The AWE repository's *separate* P139/P140 Windows ETW results are 0/201,600 real audio deadline misses across both Windows runners and same-runner 58→0/20,400 old/new. **No real physical ASIO hardware, no commercial DAW playback/save/reload session, no physical Creative Chorus reference were executed by the Lab:** `NOT RUN`, `release_approved=false`; technical Lab PASS must not be advertised as a full commercial release. [Current handoff](START-HERE.md) · [Detailed P53 coverage](docs/P53-AWE-P137-TEST-LAB-ACCEPTANCE.md).

**Historical P48 AWE independent product integration (earlier source):** [merged PR #73](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/73), [successful Windows #42195168336](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42195168336), [P02 #42195168406](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42195168406). The real source-built current AWE VST3 (pinned `c7d803c1...`) passes full native CTests plus the independent generic Test Lab playback/save/GUI/dual-instance acceptance. The artifact records exact source/binary identities and honest **ROM/SF2, Chorus, ASIO, DAW and all-GUI NOT COVERED** fields. AWE remains **GUI-/RELEASE-NO-GO**. No AWE production code was modified. [P47 current Drumator V1.5](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/72) remains green. See [START-HERE.md](START-HERE.md).

**Latest P47 real Drumator V1.5 release source integration:** [merged PR #72](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/72), [successful real Windows P03 #42193595397](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42193595397). Source-built the exact independently checked 6 Nov V1.5 revision `3f1e82c...` and reran swing, ten-style Beat Creator, GUI generate/apply/cancel, actual Windows Save As and musical WAV/MIDI exports, multi-state recall, 96 GUI clicks and adversarial gates. Strictly enforce one **SMF Type-1 MIDI file with 17 tracks and 960 PPQ**. A `V15-REAL-USER-COVERAGE.json` identifies untested GUI/DAW features, so green CI never implies all buttons or an actual customer ZIP/Studio One release approval. No production source changed. See [START-HERE.md](START-HERE.md).

**P46 independently checked GUI-triggered WAV/MIDI exports (latest):** [merged PR #71](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/71), [P25 Windows run #42190468048](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42190468048) plus P02/P03/P04/P29 green on the same source. Declared real VST3 GUI actions are now independently checked against *preapproved exact WAV/SMF references*. Source-built fixtures prove identical GUI values can hide bad audio samples, wrong MIDI notes or missing exports; the tester catches all three. Portable Windows artifact includes `run_gui_export_contract.py`. **Product-specific golden outputs are still required; no full product release or universal self-understanding is claimed.** See [START-HERE.md](START-HERE.md).

**P45 full native GUI A/B/A observation (latest):** [merged PR #70](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/70), [green P25 Windows run #42187789076](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42187789076) with P02/P03/P04/P25 also successful on the same revision. The shared GUI host now makes two genuine sequential clicks in one open VST3 editor and independently compares before/after/repeat pixels and controller state against P44 sham-backed candidates. Real parameterless painted toggles and nested Win32 buttons are covered by CI, with forged observations rejected. `run_gui_roundtrip.py` is part of the portable kit. Opt in with `--gui-explore --gui-roundtrip --acknowledge-gui-explore` plus `--gui-host`. **A/B/A only supports observed UI repeatability, not independently verified product semantics or release approval.** See [START-HERE.md](START-HERE.md) and [GUI-CONTROL-MATRIX.md](docs/GUI-CONTROL-MATRIX.md).

**P44 GUI painted-region detection (latest):** [merged PR #69](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/69), [P25 Windows run #42184625679](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42184625679). The shared sham-controlled Windows VST3 GUI explorer now locates physical changed-pixel regions and sample before/after RGB colors even when a custom-painted button exposes **no VST3 parameter**. A real source-built VST3 with an 80×50 painted-only control passed localization and out-of-control negative-click tests; all P02/P03/P04/P25/P29 Windows CI passed. The new `GUI-CONTROL-REVIEW-DRAFT.json` contains **review-only, unapproved** action proposals; it is never product-release proof. Details: [START-HERE.md](START-HERE.md) and [GUI-CONTROL-MATRIX.md](docs/GUI-CONTROL-MATRIX.md).

**P43 genuine native child-button targeting (latest):** [merged PR #68](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/68), [successful P25 Windows run #42181664171](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42181664171). The shared VST3 GUI host can now identify and click **nested native Win32 child controls**, not just the plugin editor surface. Click and sham use the same deepest visible enabled child HWND, transform mouse coordinates, and independently verify target depth. A real source-built plugin with a nested Windows BUTTON proved inside-click activation, outside-click nonactivation, and genuine ON/OFF toggling in one editor. **P02/P03/P04/P25/P29 SUCCESS** on the same feature revision. Custom-drawn controls are not all automatically discovered; exploratory observations remain `OBSERVATIONS_ONLY`, not a product release approval. See [START-HERE.md](START-HERE.md) and [P43 docs](docs/GUI-CONTROL-MATRIX.md).

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
