# P87 — Native VST3 parameter ABI versus observed GUI coverage gaps

P86 detects changes at the center of a bounded set of real Win32 GUI sample points. P87 correlates those sample observations with **the independent, read-only VST3 ParameterInfo inventory** from P68, without guessing which unlabeled button means what.

The P87 auditor verifies native P68 capability and parameter TSV files (including exact VST3 ParameterIDs and read-only flags), P86's complete 9/25-point native sham observation evidence, and consistency between the observed parameter list and each actual transition. Results preserve SHA-256 fingerprints for all source files. Unknown parameter IDs, missing or mutated records and incomplete samples fail closed.

The resulting `ABI-GUI-COVERAGE-GAPS.json` contains total VST3-exposed parameters, editable parameter count, observed parameter IDs, those not changed by any sampled GUI click, and a numerical **parameter observation ratio**. It is *not* a percentage of all GUI controls: an unobserved parameter may have a working control between grid samples, or no control at all. Custom functions (WAV/MIDI export, presets, browser actions, etc.) are not necessarily represented by VST3 parameters.

## Opt-in native Windows run

```powershell
python tests/run_universal_qa.py --plugin C:\QA\Unknown.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\Result --explore-unknown-gui --dense-gui-grid 5 --exploration-repeats 2 --crosscheck-abi-gui
```

For P83 multi-plugin selection manifests, specify `"explore_unknown_gui": true`, `"dense_gui_grid": 5`, `"exploration_repeats": 2`, and `"crosscheck_abi_gui": true` on the individual selected plugin only. Other plugins remain read-only.

P87 Windows CI runs both a real active GUI fixture and an inert negative VST3. The active fixture must map at least one exact native parameter ID; the inert plugin must report no sampled GUI parameter changes. Both retain the complete P68 native inventory and P86 observation artifacts.

## Important limits

`ABI_AND_SAMPLED_GUI_RECONCILED` means the native ABI and *sampled* GUI observations agree, **not** that every GUI control or product feature has been tested. A parameter not observed during a grid scan is not evidence of a defect, and a parameter that changes is not proof that its musical behavior is correct. Only reviewed product feature oracles (P65/P67) may certify defined functions. This opt-in probes unknown controls and must run only in a disposable isolated Windows VM. Physical ASIO, commercial DAW and release approval remain NOT RUN/false.
