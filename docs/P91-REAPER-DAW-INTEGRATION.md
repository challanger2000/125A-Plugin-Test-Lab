# P91 — Actual REAPER DAW acceptance for universal Windows VST3 QA

P91 adds a **real REAPER-invoked DAW stage**, rather than just expanding our own VST3 host. The Python launcher creates a bounded ReaScript inside a new isolated output directory, uses the official REAPER command-line interface, and requires evidence from a real REAPER Lua session. The native script:

- Starts in a new, isolated project and inserts one track with the **approved REAPER VST3 FX name**; aborts if the FX cannot be scanned/loaded.
- Creates one MIDI media item and an exact note with approved pitch and velocity at 120 BPM (configurable).
- Configures a bounded, uncompressed stereo WAV render and saves the actual `.RPP` project using REAPER's own API.
- Launches a fresh REAPER process to **reopen that saved project**, reload the FX and assert that the track, MIDI note, pitch and velocity survived.
- Invokes REAPER's documented `-renderproject` command. Checks real output WAV header, duration, sample rate, RMS and clipping.
- Preserves project, scripts, REAPER status reports, output WAV and machine-readable `REAPER-DAW-ACCEPTANCE.json`.

These are genuine DAW process operations only if the script runs on an equipped Windows machine with installed REAPER and the approved plugin. The public GitHub Actions job tests the **adapter logic with mocked processes**, explicitly reports DAW NOT RUN and never pretends it installed or executed REAPER.

## Pre-approved, explicit JSON contract

Replace the paths and SHA-256 values with the **actual** binaries:

```json
{
  "schema": "125a-reaper-daw-test-v1",
  "reaper": {
    "exe": "C:/Program Files/REAPER (x64)/reaper.exe",
    "sha256": "<64 lowercase hex SHA-256>"
  },
  "plugin": {
    "module": "C:/Program Files/Common Files/VST3/YourSynth.vst3/Contents/x86_64-win/YourSynth.vst3",
    "sha256": "<actual module SHA-256>",
    "reaper_fx_name": "VST3: YourSynth (Publisher)"
  },
  "test": {
    "sample_rate": 44100,
    "tempo_bpm": 120,
    "note": 60,
    "velocity": 100,
    "seconds": 2,
    "expect_audio": true,
    "minimum_rms": 0.01
  }
}
```

The `reaper_fx_name` must match a **plugin previously scanned by REAPER**. For an audio effect with no note-generated audio, set `expect_audio: false`. That verifies host loading, MIDI routing, persistence and render execution, **not** a musically valid effect response. For sound-generating instruments, `expect_audio: true` explicitly rejects silent and clipped output.

## Actual local DAW invocation

```powershell
python tests/run_reaper_daw_qa.py --plan C:\QA\approved-reaper-plan.json --out C:\QA\reaper-run-01
```

A *clean empty output directory* is required. No preexisting user REAPER session is intentionally modified. The test launches a fresh instance for creation and reload, and a separate REAPER CLI render. Its own processes are terminated after test completion. Run this only in an isolated disposable Windows test environment; third-party plugins can create dialogs or perform unsafe side effects.

## CI and licensing

The cloud CI runs contract regression and safe failure tests only; it does not download or package REAPER, pirate licenses, or claim that mocked DAW process execution proves REAPER behavior. A separately licensed REAPER installation can be exercised on a **dedicated, isolated self-hosted Windows runner** with labels `self-hosted, Windows, X64, 125A-REAPER`. Explicitly configure repository variables `REAPER_LAB_ENABLED=YES_ISOLATED` and `REAPER_LAB_PLAN_PATH` pointing to a reviewed local manifest before manually dispatching the P91 workflow. Do not attach a personal Windows workstation with private documents to a public GitHub Actions runner.

## Limits that are not hidden

- This does not verify the installed binary **origin** from FX name alone: the manifest SHA-256 pins a plugin module, but REAPER's FX name does not cryptographically tie its loaded module to that path. The report records `loaded_module_file_provenance=NOT INDEPENDENTLY VERIFIED`.
- REAPER's offline rendering works without ASIO hardware. A real DAW test is **not** a physical device test. `physical_asio_hardware=NOT RUN`.
- A successful MIDI-triggered render checks essential loading, note persistence and audio production. It does not validate every plugin-specific UI, DAW audio input routing, musical correctness, preset recall, automation or real-time ASIO performance.
- No REAPER/DAW session has been run merely because the adapter is committed and cloud CI is green. An actual self-hosted run and preserved evidence are mandatory for any real DAW PASS claim.
- The independent generic test lab remains separate from product repositories: no VST3 product source is changed.
 
Official API used: [REAPER ReaScript documentation](https://www.reaper.fm/sdk/reascript/reascripthelp) and [REAPER command line](https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md).
