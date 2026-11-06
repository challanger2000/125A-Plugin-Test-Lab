# START HERE — 125A Plugin Test Lab

## Latest P45 — real GUI repeatability A/B/A in one VST3 editor (Windows-verified 6 November 2026)

**Merged and independently verified:** [PR #70](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/70), [P25 Windows run #42187789076](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42187789076). Exact tested revision: `465237e390270f4eda7c9129898aae819070b6ee`. **P02, P03, P04 and P25 Windows workflows all SUCCESS**, including native regression against a source-built custom-painted-only control (without a VST3 parameter) and a nested Win32 BUTTON. The P25 artifact `125A-Universal-VST3-State-Stress-P25` contains the portable Windows host and runners. No production plugin source was modified.

**P45 new capability:** The native `125A_Test_Lab_GUI.exe --gui-observe-roundtrip` now produces real `A→B→A` observations in the **same live editor instance**, after the P44 independent sham-controlled explorer found plausible candidates. `tests/run_gui_roundtrip.py` independently reads and cross-checks native TSV parameters, both pre-click screenshots, first-click and second-click BMPs, real source/host hashes, original sham clicks and physical RGB samples. It distinguishes `OBSERVED_REVERSIBLE`, `OBSERVED_NONREVERSIBLE` and `NOT_REPRODUCED`; malformed/stale/tampered native evidence fails closed. This is available via `--gui-explore --gui-roundtrip --acknowledge-gui-explore --gui-host <native-host>` in the common one-command QA. Native Win32 BUTTON focus outlines are treated separately from controller-state reversal, so a harmless focus artifact is not mislabeled as a faulty controller.

**Semantic limits are explicit:** A/B/A proves only repeatability or reversibility *of the observed UI/controller state*. A drum pattern generator, a WAV export, audible effects, MIDI behavior or a DAW drag/drop can only be certified against independently defined expected outcomes. All new observations preserve `independent_product_semantics: NOT COVERED`, `product_gui_controls: NOT COVERED`, and `release_approved: false`; no discovered color is self-approved as a product oracle. It is a universal VST3 tester improvement, not a claim of full autonomous understanding of every unknown plugin. See `docs/GUI-CONTROL-MATRIX.md` and `docs/ONE-COMMAND-QUICKCHECK.md`.

**Execution/safety:** This is explicitly opt-in because arbitrary GUI actions can cause side effects. Use trusted test VST3s and disposable project state. GitHub Actions includes Python; the end user's PC does not need a Python installation.

## Latest P44 — real custom-painted VST3 controls are localized (Windows-verified 6 November 2026)

**Merged and independently Windows-verified:** [PR #69](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/69), [P25 Windows run #42184625679](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42184625679). The exact feature revision `45ea43d5d19d29f93eb2ac31a1702bc14935c0f7` passed **P02/P03/P04/P25/P29**, including a new real-source-built custom-painted VST3 with an 80×50 pixel button in one HWND and **zero VST3 parameter changes**. The Windows P25 artifact `125A-Universal-VST3-State-Stress-P25` includes the latest source runners and native Windows GUI host.

**P44 shared feature:** after each independently sham-controlled actual GUI click, `tests/gui_change_regions.py` locates physically changed painted regions from genuine Win32 BMP captures. It returns bounded groups of changed pixels, exact bounding rectangles, sample before/after RGB colors, and a `BROAD_CHANGE_REVIEW` classification for diffuse repainting. `run_gui_exploration.py` now writes `GUI-CONTROL-REVIEW-DRAFT.json` with observed parameter or custom-painted pixel transitions to make future per-product GUI test mappings easier. A real custom-painted-only VST3 control was precisely localized and an outside click yielded no candidate in Windows CI. Tests reject malformed physical buffers, spoofed approvals and missing/mismatched native evidence.

**No self-certification:** the generated `GUI-CONTROL-REVIEW-DRAFT.json` is explicitly `REVIEW_REQUIRED`, with `approved_for_execution=false` and `release_approved=false`; it is NOT an independently approved runnable release test. Only an independently confirmed expected musical/product behavior can transform observations into a verified oracle. The same test engine applies to all trusted Windows VST3 plugins, not merely Drumator/AWE, and neither production plugin repository was modified.

**Invocation:** use the existing optional `--gui-explore --acknowledge-gui-explore --gui-host <native-host>` flags in the common one-command technical quickcheck, or `tests/run_gui_exploration.py` directly with explicit consent. On GitHub Actions, Windows runners provide Python; no Python installation is necessary on the user's PC. Native GUI exploration is still opt-in because unknown clicks could activate product actions. Full painted-control discovery, MIDI/WAV or audio semantics, and commercial DAW acceptance remain `NOT COVERED` without independent product evidence. See `docs/GUI-CONTROL-MATRIX.md`.

## Latest P43 — real nested Win32 controls are testable (Windows-verified 6 November 2026)

**Merged and independently Windows-verified:** [PR #68](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/68) and [P25 Windows run #42181664171](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42181664171). Exact tested feature commit: `956de30b4660e67159e7aec1eb3ed2334fe1f245`. All **P02, P03, P04, P25 and P29 Windows workflows completed SUCCESS** on this exact code. The P25 artifact `125A-Universal-VST3-State-Stress-P25` includes the native host and portable test scripts.

**New P43 universal GUI input routing:** Both the isolated sham-controlled explorer and the persistent ordered GUI workflow now locate the deepest enabled, visible **native child HWND** below each requested editor coordinate and send genuine Win32 mouse input directly to that window, converting coordinates correctly. This catches standard Win32 buttons nested inside the plugin editor, which editor-root-only clicking missed. P43 evidence schema is `125A-GUI-EXPLORE-v3`, with `target_depth`, independently checked for identical sham/click dispatch and included in the observation results.

**Proof with a real nested-button VST3:** the new source-built `125A_QA_GUI_Nested.vst3` exposes a true nested Win32 `BUTTON`. Only that child's actual `BN_CLICKED` notification changes VST3 parameter 9001. P25 proves the inside click changes the parameter, outside root-background clicks do not, and two sequential nested-button clicks in the same editor toggle ON→OFF correctly. Prior good/inert/stale-paint and hover-only controls also pass.

**Hover stabilization:** both sham and click first settle their actual mouseover state before baseline captures, preventing hover painting alone from masking legitimate native buttons. No-click controls are still required to reject unrelated visual/parameter effects.

**Important limitations:** Custom VSTGUI/JUCE controls drawn inside one HWND still require independent visual or parameter oracles. Native child targeting is not a magic detector for every button and does not verify product-specific MIDI, WAV, audio or DAW behavior. Unmapped controls remain `NOT COVERED`; exploratory candidates remain `OBSERVATIONS_ONLY`, not release approval. Exploration only runs after explicit opt-in on trusted disposable plugin tests. GitHub Windows runners supply Python, so the end user needs no local Python installation.

## Latest P42 — independently controlled GUI exploration (Windows-verified 6 November 2026)

**Tested and merged:** [PR #67](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/67) and [P25 Windows run #42178099352](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42178099352). Exact tested revision: `8d7a7d4d5a5574d91eba9bdae3f9686d2842dc12`; **P02, P03, P04, P25, P29 all SUCCESS** on that revision. The P25 artifact `125A-Universal-VST3-State-Stress-P25` includes the reusable test scripts and native hosts.

**Improvement over P41:** Each unknown GUI coordinate is now tested twice, in **separate, disposable real VST3 instances**: a sham test receives the same native WM_MOUSEMOVE (hover) but no mouse-button input, and a real click test receives the mouse motion plus down/up. Both take two baseline screenshots, a post-action screenshot and complete controller snapshots. The independent auditor checks all evidence, matching initial parameter and painted values, sham background movement and click-versus-sham results. Hover-only highlights, spontaneous animation and background parameter changes are `UNSTABLE_CONTROL` and never mistaken for confirmed click candidates. Negative tests include a **real source-built VST3 that reacts to mouse hover without changing any controller parameter**.

**Status is observational, not certification:** a correctly paired scan is still `OBSERVATIONS_ONLY`. It cannot discover all hidden controls, infer their intended semantics, or prove sound, MIDI, exports, recall or DAW integration. Exploration **requires explicit opt-in** (`--gui-explore --acknowledge-gui-explore`) because arbitrary clicks may trigger actions. It is a shared testing capability for all 125A Windows VST3s, not a change to Drumator or AWE. GitHub Actions uses runner-provided Python; the user's PC does not need Python.

## Latest universal P41 automatic GUI exploration — 6 November 2026

**Verified source and Windows evidence:** [merged PR #66](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/66), [P25 Windows run 42176006331](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42176006331). The exact PR commit `506cd9118f18b79d32ae122697eac83f8f7357b8` passed **P02, P03, P04 and P25 Windows CI**; the P25 artifact `125A-Universal-VST3-State-Stress-P25` includes the portable GUI explorer runner.

**P41 requires no product-specific control map:** With explicit opt-in, `tests/run_gui_exploration.py` obtains the plugin's actual HWND viewport and tries a bounded 3×3 grid of *real Win32 clicks*, one per fresh disposable VST3 process, while taking two baseline screenshots and one post-click screenshot. It records every controller parameter before and after the click, compares real painted RGB pixels, and flags only **observed interaction candidates**. Distinguishes changes to parameters/pixels, inert or out-of-control coordinates, and unstable painted baselines. Real native positive, inert and stale-paint VST3 fixtures were verified in CI; forged/truncated/stale evidence and timeouts fail. Defaults to nine clicks; maximum sixteen.

**Usage and safety:** this is a deliberate *potentially action-triggering* exploration. In the one-command Windows QA runner use `--gui-host <native-host> --gui-explore --acknowledge-gui-explore`; or run `tests/run_gui_exploration.py --plugin <bundle.vst3> --gui-host <host.exe> --out <results> --acknowledge-ui-clicks`. Only run on trusted, disposable test instances, because an unknown button could open a dialog or write a file. The results are `OBSERVATIONS_ONLY`, **never a green product GUI or release certification**. A click without a visible or parameter change is not proof of a broken button. The core is universal, not Drumator/AWE-specific, and neither product repository was changed.

**GitHub Actions:** no Python installation is required on the user's PC when using the Windows CI runner. The optional local portable launcher still requires Python.

## Current Windows-tested P40 value-label QA — 6 November 2026

**Current verified common test lab:** [merged PR #65](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/65). The exact feature commit `beea15a716240b47d909c2d7639d9bb92f201b94` passed **P02, P03, P04, P25 and P29 Windows CI**. [Windows P25 evidence, including portable test kit](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42174156173) → artifact `125A-Universal-VST3-State-Stress-P25`. No Drumator or AWE production source was modified.

**P40 is now in the default one-command GUI QA:** the native Windows test host probes every advertised *writable automatable* VST3 parameter's textual value representation at endpoints and quartiles using `getParamStringByValue()`, then exercises `getParamValueByString()` when implemented. An independent TSV verifier rejects forged or corrupted test evidence, inconsistent labels, incorrect discrete steps and false PASS reports. Continuous parameters may have deliberately rounded display strings; such roundtrips are validated for stable text instead of requiring exact decimal equality. The native Windows fixtures include a deliberately broken plugin that maps labels to the **wrong** normalized values; CI proves the failure is caught.

**Noncoverage remains explicit:** a plugin without text/reverse API support is `NOT COVERED`; *partial* availability never receives global PASS. The German HTML result separates `native_parameter_text_labels` from `native_parameter_text_reverse` and from actual GUI pixel assertions. **P40 checks the VST3 text API, not custom-painted labels in a plugin screenshot.** Full GUI discovery, product semantics, DAW sessions and independent PCM references are not automatically proven. See `docs/ONE-COMMAND-QUICKCHECK.md` and `docs/GUI-CONTROL-MATRIX.md`.

**No local Python required** when other development chats run it through GitHub Windows Actions. The optional portable drag-and-drop runner is a separate local workflow and still needs its own Python installation.

## Latest universal P39 keyboard user-journey testing — 6 November 2026

**Verified source and Windows evidence:** [merged PR #64](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/64), [P25 Windows run 42171948171](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42171948171). The exact PR commit also passed P02, P03 (real Drumator V1.5 tests) and P04 Windows workflows. The tested commit was `a9445c2dcd50aaba33c4a87e6d10e402515a81a8`.

**P39 available to all VST3 GUI test profiles:** A persistent, genuine native editor workflow now supports declared **keyboard shortcuts** in addition to ordered mouse clicks and drags. Specify `"action": "key"` and an approved `key_code` (Windows virtual-key value) with optional `modifiers` (Ctrl, Shift, Alt). The reusable host delivers Win32 keyboard messages to the actual VST3 HWND. It independently checks requested controller transitions or approved real painted-pixel oracles, and rejects missing actions, invalid shortcut profiles and an unrelated key that has no effect. The Windows positive and deliberately broken VST3 fixtures prove this is executable rather than a simulated success. See `docs/GUI-CONTROL-MATRIX.md`.

**Universal not omniscient:** The tester does not infer all editor shortcuts, unlabeled controls or native dialog meanings. The product/test author must provide expected outcomes; undocumented controls are `NOT COVERED`. GitHub Actions runs these tests on Windows without requiring the user's PC to install Python.

## Latest universal P38 visible-only GUI controls — 6 November 2026

**Latest Windows-verified reusable kit:** [P25 workflow #42169778586](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42169778586), artifact `125A-Universal-VST3-State-Stress-P25` (portable hosts and source runners). [PR #63](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/63) is merged after **P02/P03/P04/P25 Windows SUCCESS**.

**New P38 capability:** A VST3 control need not expose a ParamID to be included in a real ordered GUI test. A `visual_oracle` declares a coordinate and independently approved RGB values **before and after** a mouse click/drag. The shared Win32 editor host captures real painted HWND pixels at both stages, and independent Python analysis rejects unchanged or stale painting and missing/forged screenshots. In CI, genuine VST3 positive, inert and stale-paint fixtures confirm that these controls can be assessed without inventing parameter mappings. The German report distinguishes `native_gui_visual_workflow` from the existing parameter/controller checks.

**Usage:** For any existing/future plugin, give the common `run_plugin_quickcheck.py --gui-host ... --gui-workflow ...` driver a validated `125a-gui-workflow-v1` profile and its independently approved expected pixel colors. Full schema and examples are in `docs/GUI-CONTROL-MATRIX.md`. The GitHub Actions runner supplies Python, so no local Python install is needed for CI.

**Scope remains explicit:** Verified painted feedback is *not* proof of hidden button semantics, MIDI/WAV exports, every GUI control, audio correctness or full DAW interaction. Those need independent product-specific reference oracles. Keep such fields `NOT COVERED`, never silently mark them as PASS.

## Latest universal P37 GUI workflow test infrastructure — 6 November 2026

**Latest independently Windows-verified portable kit:** [P25 run #42168448905](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42168448905) → artifact `125A-Universal-VST3-State-Stress-P25`, `PORTABLE` directory. [PR #62](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/62) merged to `main` after P02/P03/P04/P25 Windows SUCCESS.

**New reusable P37 GUI workflow:** a native Windows VST3 editor can now execute **multiple real mouse clicks and drags in the same plugin window**, in a specified order. Independently supplied per-step controller before/after values are verified; selected steps save actual painted BMP snapshots with optionally approved expected RGB pixels. The test runner pins exact plugin and host binaries and rejects incomplete, stale, reordered or false-positive action evidence. CI exercises a real positive toggle VST3 and separately rejects inert and stale-paint fixtures. Unit tests cover corrupt profiles and spoofed results.

**For existing and future plugins:** this is one shared test host, **not a Drumator/AWE-specific tester**. Supply a `125a-gui-workflow-v1` profile (see `docs/GUI-CONTROL-MATRIX.md`) with real coordinates, VST3 ParamIDs and independent expected values. Use `--gui-workflow` alongside `--gui-host` in `run_plugin_quickcheck.py`. The final German HTML report marks `native_gui_workflow` PASS/FAIL/NOT COVERED separately from overall product UI coverage. No product-specific source code was changed.

**Practical boundary:** undocumentable or non-parameter GUI controls and the semantics of native dialogs/DAW actions still cannot be *blindly* verified. Product releases require independent oracles and DAW acceptance. The GitHub Windows Actions runner supplies Python; no local Python installation is required for CI usage. The optional portable local drag-and-drop package requires Python.

## Latest shared Windows x64 VST3 testing infrastructure — 6 November 2026

**Current validated artifact:** [P25 Windows test run #42164304275](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42164304275), artifact `125A-Universal-VST3-State-Stress-P25` → `PORTABLE`.
[PR #60](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/60) and [PR #61](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/61) are merged. The exact PR #61 test commit passed **P02, P03, P04, P25 and P29** Windows CI, including positive and intentionally defective real VST3 fixtures.

**Universal controller automation (P35):** every writable VST3 parameter explicitly advertised as automatable is tested at normalized endpoints and quartiles (snapped to valid discrete steps), with independently checked observed values and restoration of its original state. Nonautomatable/read-only parameters are explicitly skipped. Missing, corrupted, or falsely green test evidence is rejected. This is controller API testing, *not* proof that all undisclosed buttons have been operated.

**Real bidirectional GUI clicks (P36):** the reusable product-profile GUI driver clicks actual native Win32 editor coordinates and verifies both ON and OFF changes from declared initial normalized values; optionally it compares real painted pixels. A source-built inert VST3 negative control is rejected. An independent per-plugin control map is required for controls that cannot be discovered from the VST3 parameter API. See `docs/GUI-CONTROL-MATRIX.md`.

**GitHub Actions:** these tests execute on Windows GitHub runners with Python supplied by the runner. The end user does not need to install Python to run tests there. The optional local drag-and-drop `PORTABLE` executable package still requires local Python 3.

**Scope:** the reusable technical test suite is developed and verified. Blind discovery of every plugin-specific painted button, musical correctness, full dialog interactions and a commercial DAW session are **NOT COVERED** without independent product-specific test mappings and oracles. Never call a generic technical PASS a product release approval.

**Ready to use (no compiling):** on Windows x64, extract the `PORTABLE` directory and drag a trusted installed `.vst3` folder onto `Run-VST3-Test.cmd` (Python 3 required). The resulting `RESULTS/<Plugin>/TESTERGEBNIS.html` gives German PASS / FAIL / NOT COVERED classifications and includes real native audio, state, GUI, controller inventory and two-instance tests where supported.

**Optional deep checks:** `--active-replay` subjects a genuine plugin to six rate/buffer cases with live `getState()/setState()`; `--dual-state-manifest` additionally requires an independent exact A/B bank+PCM reference. Both options run from the same `run_plugin_quickcheck.py` and contribute to the final report. These are not guessed or silently enabled for all plugins.

**Completion boundary:** the general-purpose test host, regressions, independent positive/negative fixtures, packaged Windows executables and source automation are implemented and Windows-tested. A standalone generic test host **cannot certify every preset, every musical/UI behavior or a commercial DAW session for an arbitrary third-party VST3 without product-specific approved references or the actual DAW**. These intentionally remain `NOT COVERED` and are not open regressions in the generic host. Never label a plugin itself RELEASE GO from a generic TECHNICAL_PASS.

## Previous Windows test kit (historical notes)

**Current validated portable Windows x64 kit:** [P25 Windows CI 42159432741](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42159432741) (download the `125A-Universal-VST3-State-Stress-P25` artifact and open `PORTABLE`).

**Validated and merged corrections:** [PR #55](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/55), [PR #56](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/56), [PR #57](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/57), and [PR #58](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/58). The independent audio oracle now checks **both** fresh-process renders, the active state-replay suite rejects a changing native host or VST3 module, and the default one-command quickcheck pins plugin, host and supplied reference bytes throughout its stages. The German HTML report never displays an unqualified successful headline when any declared coverage gate is FAIL.

The Windows P25 and P02 checks on the #58 test commit passed. **This is a portable technical VST3 test lab, not automatic commercial DAW/product release approval.** The per-product bank/PCM oracle, UI semantics and DAW integration still need independent real-product references.

## Latest verified optional active-playback VST3 state-reload stress

**Current portable artifact:** [Windows P25 build 42159432741](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42159432741).
[Validated and merged PR #54](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/54).

An independent plugin-development chat can use
`PORTABLE/run_live_state_replay.py` for a **real Windows VST3 test of
genuine saved-state reloads during playback**. It takes the plugin's own
pre-playback `getState()` bytes (never a guessed proprietary state),
then proves 500 successful `setState()` calls and 500 saves overlapping
2,500 audio callbacks, repeated in six rate/buffer configurations.
The total is 3,000 actual state reloads, 3,000 saves and 15,000 audio
callbacks, with exact binary SHA-256 and per-case immutable fresh
evidence. Real Windows CI passed all six valid cases and correctly
detected an intentionally broken VST3 that refuses valid active-playback
state reloads, as well as independently corrupted/missing evidence.
The standalone runner is **opt-in**, not a mandatory green criterion for
all VST3s, because plugin contracts may restrict `setState()` to
inactive processing. Product-specific correct bank/PCM semantics and
a commercial DAW session remain `NOT COVERED`.

Run from the extracted `PORTABLE` folder:

```powershell
python run_live_state_replay.py --plugin "C:\VST3\Instrument.vst3" --host ".\125A_Test_Lab_State_Stress.exe" --out ".\REPLAY-ERGEBNISSE"
```

## Latest verified A/B product-state oracle

**Current Windows artifact:** [P25 Windows run 42159432741](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42159432741), containing the portable tester. The corresponding tested changes are merged in [PR #53](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/53).

Other plugin-development chats can now use `run_product_dual_state.py` in the portable kit to test **two different plugin banks/presets in two simultaneously active VST3 instances**. Unlike the standard identical-state drag-and-drop test, this accepts a separately approved A/B manifest pinning the actual module SHA-256, two different saved-state files and approved post-reload state/PCM values. It fails when the observed bank/state or audio does not match the independent reference. A real source-built good plugin passed in Windows CI and a deliberately broken shared-global-state plugin failed the same external oracle, despite successful host API calls.

[Independent A/B manifest and usage instructions](docs/ONE-COMMAND-QUICKCHECK.md). **Distinct-state musical/bank correctness without external product references remains NOT COVERED.** No universal release approval is implied.

## Current checked portable package — real two-instance hosting

**Windows source baseline:** pull requests
[#51](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/51)
and [#52](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/52),
both merged after their applicable Windows validation.

[Latest proven Windows P25 artifact and download](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42159432741)

The `PORTABLE` package contains four native Windows x64 test hosts,
including `125A_Test_Lab_Instance_Isolation.exe`. Drag an installed,
trusted VST3 folder onto `Run-VST3-Test.cmd` for automatic playback,
state-save/recall, native GUI discovery and **two simultaneously
running plugin instances in the same host process**. The HTML result
reports which checks passed and which remain uncovered.

A separate real Windows test uses *different* saved states in two
instances, independently verifies both output states and PCM, and
successfully detects a deliberately faulty VST3 with a shared global bank.
The ordinary drag-and-drop run uses the *same* state in both instances;
therefore it does not establish independent preset/bank behavior.
`distinct_instance_state_isolation` remains `NOT COVERED` until
independent A/B product references are supplied.

**Still no general product release approval**: commercial DAW workflows,
every user-visible control, complete MIDI/WAV export and product-specific
sound/preset semantics cannot be declared tested without their own
real-device or DAW oracles.

## Verified P49: saves must actually overlap audio playback

The native save/playback regression now proves that at least one
successful VST3 `getState()` took place **after audio callbacks started
and before playback stopped**. All 500 saves and 2,500 process callbacks
must still complete in each of six configurations. Previously, a suite
could count all saves after playback and nevertheless report success.
That false positive is now rejected by the C++ host, the independent
TSV verifier, the real-plugin adapter, and deliberate 0/missing/impossible
overlap test cases.

[Windows P25 verified run and portable artifact](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42159432741) ·
[merged source changes](https://github.com/challanger2000/125A-Plugin-Test-Lab/pull/49).

This is measured overlap with a **running** callback thread, not proof
that a save held a mutex within an individual DSP callback. Product-specific
state semantics and commercial DAW saves still require independent tests.

## Current test acceptance and latest proof

**Latest verified Windows quickcheck:** pull requests #47 and #48,
validated in [Windows P25 pipeline](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42159432741).
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
successful [P25 Windows Actions artifact](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42159432741),
open its `PORTABLE` folder, and follow `README.md`. The artifact
contains all four native x64 audio/state/GUI/dual-instance hosts, the drag-and-drop launcher, supporting Python scripts
and SHA-256 checksums. Python 3 on Windows is required.

```powershell
python run_plugin_quickcheck.py --plugin "C:\VST3\Plugin.vst3" --host ".\125A_Test_Lab_Host.exe" --stress-host ".\125A_Test_Lab_State_Stress.exe" --dual-host ".\125A_Test_Lab_Instance_Isolation.exe" --gui-host ".\125A_Test_Lab_GUI.exe" --out ".\QA-Results"
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
