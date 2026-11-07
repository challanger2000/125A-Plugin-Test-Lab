# P82 — Explicitly opted-in exploration of previously unknown VST3 GUI controls

The P74 universal pipeline now provides a bounded exploratory GUI mode.
This reuses P42's genuine native Win32 VST3 GUI probe engine and compares
every real click against an independent sham (identical capture, no click).
The default remains **read-only** and never explores unknown controls.

```powershell
python tests/run_universal_qa.py --plugin C:\QA\Unknown.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\unknown-explore --explore-unknown-gui --exploration-max-points 4
```

With this explicit opt-in, P82 preferentially probes up to four read-only discovered
native/painted GUI candidate coordinates. If no candidates have been found, it
uses a deterministic editor grid. An optional `--exploration-points '160,90;240,90'`
uses explicit coordinates; native bounds validation still applies. Change
`--exploration-max-points` for 1–16 probes. Each probe launches a fresh VST3
process and compares sham-versus-click controller values and BMP pixels. It
rejects unstable baselines and spontaneous animations as evidence of a click.

**Security:** Unknown plugin buttons may open modal dialogs, overwrite files,
initiate exports, or perform other unsafe actions. Only enable this on a
disposable isolated Windows VM with non-sensitive test assets. P82 does
not execute arbitrary shell commands and does not automatically reclassify
previously unknown controls as safe.

The result `INVENTORY_WITH_EXPLORATORY_OBSERVATIONS` is intentionally
distinct from read-only `INVENTORY_COMPLETE`. The JSON includes
`exploratory_clicks_performed`, `exploratory_candidates_observed`,
`unknown_gui_exploration`, and `unknown_gui_semantics`. The nested
`GUI-EXPLORATION-RESULT.json` and `GUI-CONTROL-REVIEW-DRAFT.json`
retain observed parameter transitions and visual changes with no approved
semantic oracle. A headless VST3 returns "NOT APPLICABLE - NO EDITOR".

**Not proven:** Automatically knowing what an unknown control means,
whether it is safe, its expected sonic result, a complete product control
inventory, physical ASIO, commercial DAW behavior or release readiness.
An observed click never becomes a `CONTRACT_PASS` for a product feature
without independent reviewed P65/P67 assertions. Release approval stays false.

Windows CI tests opt-in semantics, bad/sham evidence and real source-built
interactive versus inert VST3 editor controls.
