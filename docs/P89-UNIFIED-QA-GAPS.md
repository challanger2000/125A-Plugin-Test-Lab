# P89 — One independent consolidated QA result with actionable missing acceptance

P75/P80 already tests and isolates 1–32 VST3 modules, creating a JSON batch report plus per-plugin P74 reports. P89 independently reconciles those reports and produces one readable **UNIFIED-QA-GAPS.md** and machine-readable **UNIFIED-QA-GAPS.json**. An automatically passing inventory is deliberately not confused with verified product-function coverage.

## Usage

After an ordinary universal batch:

```powershell
python tests/run_vst3_batch_qa.py --selection C:\QA\selection.json --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\batch
python tests/run_unified_qa_gaps.py --batch C:\QA\batch --out C:\QA\summary
```

The report independently checks that each plugin's ID, source module hash, result stage, discovery status, P67 coverage and batch totals agree with actual native subprocess evidence. Missing or corrupt child evidence cannot turn a failure into PASS; a failing plugin is still represented in the consolidated report when reliable fault evidence exists.

Every plugin has a list of unresolved acceptance gaps. Even all-green technical QA **does not prove** complete unknown-plugin functional semantics, actual commercial DAW operation or physical ASIO hardware. No release approval is granted by this reporter. Unknown GUI functions still require independently authored musical expectations and approved P65/P67 contracts.

The Windows CI checks successful mixed batches, honest failures, forged identity, missing source reports and false DAW/ASIO assertions.

**Scope:** This is an evidence verification and reporting layer. It does not claim that the current runner gained automatic generic musical oracles, actual DAW software integration, or hardware ASIO audio capture.
