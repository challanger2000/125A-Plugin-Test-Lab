# P32 — Independent production-plugin adapters

P32 is a fail-closed, **product-neutral** gateway for the existing native VST3
playback/save stress host. An external adapter names an **exact VST3 module
binary** and pins its SHA-256, declares the manufacturer's version and source
commit, and specifies independent observable acceptance conditions.

It does **not** assume that every plugin has the synthetic bank/program
state layout used by P25 fixtures. The P32 runner always invokes
`--save-only` with `oracle=none`: actual `getState()` calls while native
`process()` runs, without synthetic `setState()` data or automation.

## Adapter format

```json
{
  "schema": "125a-p32-adapter-v1",
  "product": {
    "name": "Example VST3",
    "version": "1.2.3",
    "commit_sha": "0000000000000000000000000000000000000000",
    "binary": "C:/Trusted/Example.vst3/Contents/x86_64-win/Example.vst3",
    "sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
  },
  "host": "C:/TestLab/125A_Test_Lab_State_Stress.exe",
  "cases": [{
    "id": "playback_44100",
    "rate": 44100,
    "block": 64,
    "iterations": 2500,
    "mode": "save-only",
    "assertions": {
      "result": {"eq": "PASS"},
      "save_failures": {"eq": 0},
      "process_failures": {"eq": 0},
      "save_success": {"eq": 500},
      "callbacks": {"eq": 2500},
      "domain_correctness": {"eq": "NOT_COVERED"}
    }
  }]
}
```

The sample binary hash and source SHA above are placeholders and **must be
replaced with the exact approved build**. The `version` and `commit_sha`
fields are supplied by the adapter author; P32 cryptographically verifies
**the module file**, not those declarations. A product's version/SHA requires
an independent trusted build-provenance chain for verification.

Run on Windows x64, with a trusted installed VST3 module:

```powershell
python tests/run_product_adapter.py --adapter C:\\QA\\adapter.json --out C:\\QA\\reports --timeout 120
```

The result file `ADAPTER-RESULT.json` lists each case and explicit
`PASS/FAIL/NOT COVERED`. A failing native host, lost/malformed report,
timeout, missing expectation, changed binary SHA, missing evidence,
or violated assertion cannot be accepted as PASS.

**Coverage limitation:** the present generic native host requires a VST3
audio processor with one stereo output and 32-bit processing. An incompatible
plugin does not gain PASS; its host scenario fails and needs a separate
capability-aware adapter. Product-specific state snapshots, polyphony,
actual musical output and visual GUI semantics remain `NOT COVERED`.
An approved product-specific oracle must supply those expectations separately.

## Demonstrated negative controls

[Windows Actions 42062760517](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42062760517)
validated actual native playback/save calls on one correct VST3 fixture
(PASS), one defective VST3 fixture with 100/500 refused saves (FAIL),
a deliberately wrong SHA-256 (rejected), and a missing required save
oracle (rejected). All pre-existing P25–P31 steps in that workflow passed.

Only `125A-Plugin-Test-Lab` is changed by P32; production repositories
and their builds are not modified. Native VST3 binaries run arbitrary
code: run only approved/trusted modules in an isolated runner.
