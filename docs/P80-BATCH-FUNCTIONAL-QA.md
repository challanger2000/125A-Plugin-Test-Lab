# P80 — Product-functional plans in multi-VST3 batch QA

P75 already isolates 1–32 Windows VST3 plug-ins into separate bounded subprocesses. P80 adds the previously missing bridge from those batch records to **independently approved P65 product plans and P67 feature matrices**. This permits a single batch to run read-only inventory for some plugins, technical playback/state checks for others, and approved GUI/WAV/MIDI functionality for reviewed products (including P79 `gui_export_contract`).

## Example

```json
{
  "schema": "125a-vst3-batch-selection-v1",
  "plugins": [
    {
      "id": "reviewed_vst3",
      "bundle": "C:/QA/Review.vst3",
      "run_technical_baseline": false,
      "approved_plan": "C:/QA/reviewed-plan.json",
      "feature_matrix": "C:/QA/reviewed-features.json"
    },
    {
      "id": "unknown_vst3",
      "bundle": "C:/QA/Unknown.vst3",
      "run_technical_baseline": false
    }
  ]
}
```

```powershell
python tests/run_vst3_batch_qa.py --selection C:\QA\selection.json --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\BatchResults
```

Every approved plan and matrix must be supplied as a pair. P80 validates all plans, exact module/host SHA-256 and P67 coverage **before executing any selected plugin**. It pins approved manifest bytes, rechecks identities around every subprocess, rejects forged/incomplete child reports, and keeps the other plugins running if one VST3 crashes or fails a functional check.

The report's `verified_stage` distinguishes `INVENTORY_COMPLETE`, `TECHNICAL_BASELINE_PASS` and `DECLARED_COVERAGE_PASS`. Aggregate `BATCH_MIXED_QA_PASS` denotes a successful mixed inventory/product batch, **not** full product coverage. `BATCH_DECLARED_COVERAGE_PASS` requires each selected plugin to have a complete approved feature declaration and a passing child result. Unapproved unknown controls are not clicked. A product's approved feature list does not imply all of its real features have been discovered. Release approval remains false.

P80 Windows CI tests contract preflight, mixed selection, failure isolation and backwards compatibility with P75. Native Windows VST3 GUI-triggered WAV/MIDI positive/negative fixture tests are independently covered by P79 CI. Neither proves physical ASIO or a commercial DAW session.
