# P75 — Crash-isolated multi-VST3 batch QA

P74 supplied one command per plugin. P75 runs the *same universal
command* for a bounded set of Windows x64 VST3s and delivers one
consolidated machine-readable report. The Test Lab core has no special
code for Drumator, AWE, synthesizers, reverbs, or any other product.

## Scan an entire testing directory (read-only default)

```powershell
python tests/run_vst3_batch_qa.py --plugins-root C:\QA\VST3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\AllResults
```

Discovers 1–32 real unique VST3 bundle directories, verifies the
unique internal native VST3 binary, pins its SHA-256, and runs each
through the P74 inventory pipeline in a separate bounded Python
subprocess. It does not click GUI candidates.

## Select technical tests only on approved plugins

A plain JSON file allows a safe subset of plugins to receive the
existing P73 native audio/Save/Recall baseline while others receive
read-only discovery:

```json
{
  "schema": "125a-vst3-batch-selection-v1",
  "plugins": [
    {
      "id": "example_fx",
      "bundle": "C:/QA/Effects/Example.vst3",
      "run_technical_baseline": true
    },
    {
      "id": "unknown_synth",
      "bundle": "C:/QA/Synth/Unknown.vst3",
      "run_technical_baseline": false
    }
  ]
}
```

Then:

```powershell
python tests/run_vst3_batch_qa.py --selection C:\QA\selection.json --gui-host C:\QA\125A_Test_Lab_GUI.exe --audio-host C:\QA\125A_Test_Lab_Host.exe --stress-host C:\QA\125A_Test_Lab_State_Stress.exe --out C:\QA\BatchResults
```

P75 does not require plugins to declare the same parameter IDs or
control layout. Use P65/P67 approved contracts for the additional
product-specific expectations; these are *not* inferred by a batch
directory scan.

## Isolation and evidence

Every plugin is given its own bounded P74 child process and evidence
folder. An individual nonzero exit, child timeout, missing file, wrong
hash, invalid JSON or failed native technical test is `FAIL`, but the
batch continues to subsequent selected VST3s and reports all failures.
At most 32 VST3s are accepted in one batch; default per-plugin process
timeout is 600 seconds, configurable from 45 to 1800 seconds.

The top-level `BATCH-QA-REPORT.json` includes per-plugin
`PASS`/`FAIL`, exact original plugin SHA-256 identities, aggregate
counts and the original individual `UNIVERSAL-QA-RESULT.json` and
native artifacts nested below. When *all selected* checks pass, status
is `BATCH_TECHNICAL_PASS`. **This is not commercial release approval,
full feature coverage, measured ASIO driver performance or DAW testing.**
The report never sets `release_approved` true.

**Process security limitation:** Each VST3 is loaded as native code,
and child timeout handling cannot be assumed to terminate all
grandchild processes or contain a malicious DLL. Use an isolated,
disposable Windows VM/CI runner and only trustworthy plugins. P75
reduces contamination of subsequent tests by isolating each Python
invocation; it is not an operating-system security sandbox.

Windows CI source-builds four real VST3 fixtures: a native Button GUI,
a custom-painted GUI, a valid headless audio/state plugin and an
intentionally defective headless audio/state plugin. A read-only
batch must inventory all four; a second batch with the defective VST3
**first** must report its failure and then independently PASS the good
VST3 without stopping early.
