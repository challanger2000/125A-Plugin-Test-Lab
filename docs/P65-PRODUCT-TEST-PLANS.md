# P65 — Standard product-specific test plans (shared Test Lab engine)

The **125A Plugin Test Lab** is reusable across different VST3 plugins.
The plugin owner or development chat declares **expected, independently
determined** actions in one versioned JSON file; the existing Test Lab
executes those actions. Product-specific changes do **not** require C++
or Python edits in the Test Lab core.

## Supported V1 case types

- `gui_workflow`: real native ordered VST3 GUI clicks, drags, key events,
  independent normalized parameter or painted pixel before/after oracles
  using the existing P37/P39 native Windows host.
- `gesture_sweep`: repeatable multi-point physical drag and expected
  normalized values in both directions using P51/P52.

- `technical_quickcheck` (P66): executes the existing native real VST3
  playback, state save/load and multiple sample-rate/buffer matrix tests,
  using separately SHA-256-pinned `hosts.audio` and `hosts.stress`
  in the same JSON plan. The case must explicitly list one or more of:
  `api_playback_save`, `sample_rate_buffer_matrix`,
  `native_audio_state_capture`, `fresh_process_project_recall`
  under `contract.required_coverage`. Each listed coverage result must
  equal `PASS`; unlisted product-specific MIDI/export semantics are
  never inferred.

Example technical case and required extra host records (add to the
same `hosts`/ `cases` sections of the complete plan):

```json
{
  "audio": {"path": "C:/QA/125A_Test_Lab_Host.exe", "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},
  "stress": {"path": "C:/QA/125A_Test_Lab_State_Stress.exe", "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"}
}
```

```json
{
  "id": "audio_save_recall",
  "kind": "technical_quickcheck",
  "contract": {
    "required_coverage": [
      "api_playback_save",
      "sample_rate_buffer_matrix",
      "native_audio_state_capture"
    ]
  }
}
```

Each case uses its **existing complete adapter contract**, nested below
`contract`. The product plan validates *all cases* before sending any
click and pins module/GUI-host SHA-256 once across the execution.
Unknown case kinds, plugin identities, duplicate IDs, incomplete GUI
oracles and unsupported instructions are rejected.

### Generic example (replace all paths, hashes and approved expectations)

```json
{
  "schema": "125a-product-test-plan-v1",
  "product": {
    "id": "125a_example",
    "module": "C:/QA/Example.vst3/Contents/x86_64-win/Example.vst3",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "hosts": {
    "gui": {
      "path": "C:/QA/125A_Test_Lab_GUI.exe",
      "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
  },
  "cases": [
    {
      "id": "master_gain",
      "kind": "gesture_sweep",
      "contract": {
        "schema": "125a-gui-gesture-sweep-v1",
        "product": {
          "binary": "C:/QA/Example.vst3/Contents/x86_64-win/Example.vst3",
          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        },
        "gui_host": "C:/QA/125A_Test_Lab_GUI.exe",
        "param_id": 9001,
        "initial_normalized": 0.0,
        "checkpoints": [
          {"start_x": 40, "start_y": 90, "end_x": 220, "end_y": 90, "expected_normalized": 0.75},
          {"start_x": 220, "start_y": 90, "end_x": 40, "end_y": 90, "expected_normalized": 0.0}
        ]
      }
    }
  ]
}
```

The values above are **example fixture values**, not discovered product
values. An owner needs to specify the actual parameter ID, coordinates,
initial state and expected outcomes of their own VST3. Never infer
expected values from the output under test.

Run on Windows 2022 after building the native GUI host and VST3 module:

```powershell
python tests/run_product_test_plan.py --plan C:\QA\approved-plan.json --out C:\QA\results
```

The result is `PRODUCT-TEST-PLAN-RESULT.json` plus native artifacts in
numbered per-case folders. Each reports `PASS`, `FAIL` or
`NOT RUN`. The runner stops subsequent cases on a failure to prevent
unsafe follow-up clicks and prints an explicit untested count. The
independent VST3/host hashes must be unchanged throughout.

**What an individual plugin development chat must provide:** the exact
source-built VST3 module, a verified test-host binary and a JSON plan
containing product-specific expectations. Drumator may describe Beat
Creator controls; AWE may describe Bank/Program controls; future
plugins can declare their own contracts. P65 does not automatically know
what an unlabeled button means.

**Scope and safety:** P65/P66 dispatch stable native GUI adapters and an existing\ntechnical native audio/save/recall quickcheck. It does not automatically test Drumator's exports, AWE
PCM reference matching, preset-file round trips, ASIO hardware or
commercial DAW save/reopen through a common plan. These require more
registered adapter types and independently defined oracles in later
revisions. It must not claim that passing declared cases means all
features have been tested. All reports explicitly retain:
`release_approved: false`,
`full_product_functional_coverage: NOT COVERED`,
`physical_asio_hardware: NOT RUN`,
`real_commercial_daw_session: NOT RUN`.

The Windows CI compiles two genuinely different VST3 binaries, then
feeds the **same standardized plan shape** to P51's existing native
gesture-sweep adapter. The good regulator must PASS and the deliberately
quantized regulator must FAIL. Independent unit tests reject invalid
case contracts, forged success counters, altered DLL or host bytes,
unsupported commands and duplicate case IDs.
