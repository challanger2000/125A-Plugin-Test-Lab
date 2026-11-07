# P83 — Optional exploration of unknown controls per VST3 in isolated batches

P82 added an explicit opt-in for native Win32 VST3 GUI exploration in the P74 single-plugin runner. P83 makes this available to **selected plugins only** in the P75/P80 crash-isolated batch interface. The default directory scan remains read-only; no implicit clicking is ever enabled.

An approved **test-environment** selection may contain:

```json
{
  "schema": "125a-vst3-batch-selection-v1",
  "plugins": [
    {
      "id": "explore_this",
      "bundle": "C:/QA/Unknown.vst3",
      "run_technical_baseline": false,
      "explore_unknown_gui": true,
      "exploration_points": "160,90",
      "exploration_max_points": 1
    },
    {
      "id": "leave_untouched",
      "bundle": "C:/QA/Another.vst3",
      "run_technical_baseline": false
    }
  ]
}
```

Run with the existing P75 command:

```powershell
python tests/run_vst3_batch_qa.py --selection C:\QA\selection.json --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\results
```

The explicit `explore_unknown_gui: true` is required for each plugin to receive exploratory clicks; coordinates and 1–16-point budget are validated before **any** plugin is loaded. If no coordinates are specified, P82's existing native/painted GUI candidate priority and bounded grid fallback apply. The sham-versus-real-click comparison records changed VST3 parameters and pixels while rejecting unstable backgrounds. Each plugin runs in a separate bounded subprocess.

`BATCH_EXPLORATORY_OBSERVATIONS_COMPLETE` means all selected probes and inventory tasks ran successfully, **not** that product functionality or safety was verified. For an approved P65/P67 functional batch, the existing `BATCH_DECLARED_COVERAGE_PASS` and `BATCH_MIXED_QA_PASS` apply and remain limited to declared requirements. Results include per-plugin `exploration_requested`, `exploratory_clicks_performed` and `unknown_gui_exploration`. Default read-only entries must have zero exploratory clicks.

P83 Windows CI tests the actual source-built interactive VST3 editor against an inert negative control, both in a two-plugin opt-in batch and in a selectively opted-in batch. This is not evidence that arbitrary previously unknown commercial product controls can be semantically interpreted or tested safely.

**Safety and limitations:** Exploratory clicks can activate arbitrary plugin side effects, including dialogs and exports. Only run them in a disposable isolated Windows test VM, never with sensitive files. Product behavior, audio truth, all controls, writer provenance, DAW/ASIO hardware and release approval remain outside the exploratory observation claim.
