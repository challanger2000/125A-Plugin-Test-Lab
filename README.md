# 125A Plugin Test Lab

**Windows x64 · C++23 · Visual Studio 2022 · VST3 · GitHub Actions**

The 125A Plugin Test Lab is an independent functional test host and test-oracle
suite. It supplements the [125A Plugin Tester](https://github.com/challanger2000/125A-Plugin-Tester)
and the Steinberg VST3 validator; it does not replace a complete commercial-DAW
compatibility test.

## What actually passed

All gates below have verified Windows GitHub Actions evidence, not just
source-level assertions. The reproducible pull-request benchmark checks
product commit `6184718dda4a725fe4892a9e76533ec24dfa2f17`. A **manual
Actions run can select another Drumator branch, tag or exact SHA** and records
the resolved tested commit in its artifact.

| Gate | Real evidence |
| --- | --- |
| P01 / P02 | Genuine VST3 host/process callbacks, transport + MIDI, 44.1 kHz PCM24 WAV; independent full-frame audio oracle; deliberately broken NaN plugin detected |
| P03 | Actual Drumator SWING 0/50% matches independent triplet timing; fresh process/component state save/reload produces bit-identical stereo audio; corrupt project state rejected |
| P04 | Win32 VST3 GUI host on a controlled click-enabled plugin, two editor cycles, inert negative control, and explicit editorless INCONCLUSIVE |
| P05 | 36 real Drumator VST3 renders (90/120/150 BPM × Swing 0/25/50 × 64/127/512/1024-frame blocks), with independent onset and byte-for-byte block partition checks |
| P06 | 18 real MIDI exporter file outputs validated by an independent Standard MIDI File parser; corrupt MIDI inputs rejected |
| P07 | 1,280 real Beat Creator A/B/C vectors across 10 genres, two pattern lengths, two complexities and 32 seeds; five-point Complexity helper, protected pattern data and independent negative cases |
| P08 | 18 real offline WAV exporter outputs, stereo PCM24 format, exact duration and sample-level onset matching to independently validated MIDI timeline; corrupt WAV inputs rejected |
| P09 | **Actual Drumator editor** attached to a Win32 HWND, real mouse clicks toggle and restore Limiter, GENERATE→CANCEL preserves component state, GENERATE→APPLY→CONFIRM changes three distinct A/B/C patterns, D–H and hidden rows remain unchanged |
| P10 | All four actual GUI export options open a real Windows Shell Save dialog; CANCEL writes no file and keeps the processor's project state identical |
| P11 | All four GUI Save As options genuinely write pattern/song MIDI/WAV files; independent parsers verify note timing, A/REST/A song, stereo PCM24 audio format, sample-exact attack positions, and immutable project state |

**Latest P01–P11 complete PASS:** [Windows Actions 41944080762](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41944080762).

P09 required the second APPLY click because the factory Pattern A is already
occupied. Tests must honor this confirmation rather than bypassing it.

## What this does *not* prove

**The test environment is not a complete automated release certification.**
The following remain separate acceptance requirements:

- **OLE drag-and-drop acceptance into an external DAW** (unverified); only
  normal Save As MIDI/WAV export and cancellation have passed real GUI tests.
- Full coverage of all plugin popup menus, sample editors, mouse gestures,
  preset browser navigation, zoom variants and plugin window stress.
- End-to-end compatibility with Fender Studio Pro, including project save,
  automation and actual user workflows inside that proprietary DAW.
- Every conceivable kit, host tempo, sample rate, export combination and
  randomized stress/failure case.

A green P11 must **not** be presented as blanket Drumator release approval.
For tests not executed in a real interactive desktop or DAW, report
**INCONCLUSIVE / NOT COVERED**, never PASS.

## Reproduce

Use the [GitHub Actions workflows](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions):
- `P03 Real Drumator Swing Host Test`: runs P03–P11 genuine product tests
  on `windows-2022`. For a manual run, enter a **Drumator branch, tag or full
  commit SHA** in `drumator_ref`; the report identifies the resolved SHA.
  PR checks retain the reproducible pinned baseline.
- `P04 Native VST3 GUI Input Test`: validate independent GUI-host fixtures.
- `125A Test Lab - Windows P02`: build the console test host and render
  deterministic VST3 audio fixtures.

CI artifacts include diagnostics, selected WAV/MIDI/GUI evidence and a test host.
See [START-HERE.md](START-HERE.md) for executable CLI usage, safeguards and
interpretation.

## Public repository and licensing

No DAW licenses, personal presets, third-party samples or secrets belong here.
Synthetic sample content is generated during CI, not shipped commercially.
Native VST3 modules execute code; use trusted binaries and isolated runners.
