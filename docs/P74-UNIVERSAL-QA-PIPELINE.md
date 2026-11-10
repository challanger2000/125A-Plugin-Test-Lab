# P74 — One-command end-to-end universal VST3 QA

**P99 opt-in:** `--run-rea-analysis --rea-node <node.exe> --rea-entry <rea.mjs>`
captures a separate, SHA-pinned REA/Ghidra binary observation. The default
is NOT RUN. This is NOT musical correctness, DAW acceptance or release
approval. See [P99](P99-REA-BINARY-ANALYSIS.md).

P68–P73 implemented individual discoveries and test adapters. P74
exposes one top-level tool for **any source-defined or independently
approved Windows x64 VST3**. It supports both VST3s with GUI (native
Win32 or painted, read-only discovery) and GUI-less processors.

## Phase 1 — Always-on verified discovery

```powershell
python tests/run_universal_qa.py --plugin C:\QA\MyPlugin.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\QA
```

The runner invokes P68 ABI inventory and P71 native + custom-painted
GUI discovery via P72/P73 onboarding. It compares independent VST3 and
native host SHA-256 before and after the run. The resulting
`UNIVERSAL-QA-RESULT.json` reports `INVENTORY_COMPLETE`. This status
**does not mean a test has passed**, merely that real capabilities were
read. No buttons are clicked.

## Phase 2 — Automatically test independent native technical checks

```powershell
python tests/run_universal_qa.py --plugin C:\QA\MyPlugin.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --audio-host C:\QA\125A_Test_Lab_Host.exe --stress-host C:\QA\125A_Test_Lab_State_Stress.exe --run-technical-baseline --timeout 110 --out C:\QA\QA
```

If native playback/save, sample-rate and audio state capture evidence
is complete, result is `TECHNICAL_BASELINE_PASS`. Known-bad fixture
modules must instead return FAIL. The technical checks **can execute
native DSP, save/recall and other test actions**; use a disposable,
isolated test Windows machine for unknown third-party code.

## Phase 3 — Run independently approved product contracts

```powershell
python tests/run_universal_qa.py --plugin C:\QA\MyPlugin.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --approved-plan C:\QA\plan.json --feature-matrix C:\QA\feature-matrix.json --out C:\QA\QA
```

P74 checks *both* files before executing any approved GUI clicks or
technical product contracts. The P65/P66 plan pins the exact VST3 DLL
and host hashes and contains explicitly safe actions and independent
expected values. The P67 separate product inventory enumerates
mandatory features and links them to corresponding case IDs. Missing
or failed required feature coverage returns FAIL. Only after
a complete successful native P65/P66 plan and P67 matrix does this
pipeline label the result `DECLARED_COVERAGE_PASS`, which is **not**
a certification of every product feature. Add both audio/stress hosts
for contracts requiring `technical_quickcheck`.

Any unapproved product action, one-sided plan/matrix, wrong hashes,
false GUI output, partially passed technical baseline or missing
mandatory feature causes FAIL or is explicitly NOT DECLARED.

## Report semantics

- `INVENTORY_COMPLETE`: read-only examination passed, no technical QA claim
- `TECHNICAL_BASELINE_PASS`: general native technical baseline passed
- `DECLARED_COVERAGE_PASS`: every *declared* required feature has
  associated successful approved native tests
- `FAIL`: evidence missing, inconsistent, altered or a real test failed

The top-level JSON report never grants release approval and never
infers musical audio truth from plugin output under test. Independent
reference PCM, DAW-reopen project integration, physical ASIO driver,
complex file exports and missing product feature declarations remain
outside the currently proven generic end-to-end coverage.

Use `UNIVERSAL-QA-RESULT.json` plus the nested original onboarding,
quickcheck and approved-case evidence as the full audit trail.
Windows CI exercises the exact same command on two genuinely different
GUI VST3s and good/broken audio-state native VST3s. No product-specific
test laboratory code is required.
