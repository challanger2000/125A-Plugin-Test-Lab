# 125A Plugin Test Lab

**Windows x64 · C++23 · Visual Studio 2022 · VST3 · GitHub Actions**

The 125A Plugin Test Lab is an independent functional test host and test-oracle
suite. It supplements the [125A Plugin Tester](https://github.com/challanger2000/125A-Plugin-Tester)
and the Steinberg VST3 validator; it does not replace a complete commercial-DAW
compatibility test.

## What actually passed

All gates below have verified Windows GitHub Actions evidence, not just
source-level assertions. The reproducible pull-request benchmark checks
product commit `eed1bf232b61f6fb725ca00d82a99658cfba07e2`. A **manual
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
| P13 — source | Four actual GUI drag gestures generated and independently verified Pattern/Song MIDI/WAV transient files on the regular Windows CI host |
| P15 — receiver contract | Four native `CF_HDROP` receiver callback/file-copy checks using a synthetic COM data object, run unattended on Windows |
| P16 — real OLE integration | **PASS:** ephemeral Windows VM creates its own active RDP desktop, physically drags all four exports from the real Drumator editor and the separate Windows `IDropTarget` records four real `DragEnter`/`Drop` callbacks; received files pass independent validation |
| P17 — editor lifecycle | 16 actual VST3 editor detach/reattach cycles with valid native HWND each time and byte-identical processor state after every cycle; mandatory Windows P03 integration gate |
| P18 — fresh-process recall matrix | 0/25/50 Swing states each saved and restored through new VST3 host processes; independently verified DM18 CRC and byte-identical non-silent stereo 24-bit PCM after reload |
| P19 — real GUI control stress | 96 actual Win32 editor limiter clicks, 48 alternate-state changes and byte-identical processor-state reversals, required by Windows CI |
| P20 — invalid state matrix | 16 individually corrupted/truncated DM18 project states rejected by the actual VST3 host, no audio files emitted, tested rejection paths |
| P21 — exact-SHA release evidence | Fail-closed `RELEASE-EVIDENCE.json` generated from 13 independent gate log files, exact product commit recorded; separate DAW/OLE workflow coverage explicitly identified |

**Latest P01–P11 and P13 drag-source PASS:** [Windows Actions 41952977868](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41952977868).
**True interapplication COM/OLE reception PASS:** [P16 interactive Windows run 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955).
**Latest P17–P21 mandatory Windows integration PASS:** [Actions 42037199490](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42037199490). The artifact contains `RELEASE-EVIDENCE.json` with 13/13 gate entries PASS for the exact pinned product SHA.

P09 required the second APPLY click because the factory Pattern A is already
occupied. Tests must honor this confirmation rather than bypassing it.

## What this does *not* prove

**The test environment is not a complete automated release certification.**
The following remain separate acceptance requirements:

- P16 proves real cross-window OLE delivery to the independent native Windows
  receiver, but does not exercise any proprietary DAW's drop target.
- Full coverage of all plugin popup menus, sample editors, mouse gestures,
  preset browser navigation, zoom variants and plugin window stress.
- End-to-end compatibility with Fender Studio Pro, including project save,
  automation and actual user workflows inside that proprietary DAW.
- Every conceivable kit, host tempo, sample rate, export combination and
  randomized stress/failure case.

A green result proves the named behaviors at the recorded product revision;
it is not blanket certification of all GUI, host or DAW workflows.

## P14 / P16 actual interactive Windows OLE acceptance

P14 produces the portable acceptance kit. **P16 now automates the native
end-to-end drag-and-drop on GitHub Actions itself**: within the disposable
Windows 2022 VM, it starts a temporary local RDP desktop user, launches
the genuine source-built Drumator editor and separate native COM receiver,
then performs physical mouse drags of Pattern MIDI/WAV and Song MIDI/WAV.
A PASS requires four actual `CF_HDROP` target callbacks, retained source
files and independently verified received files. The test destroys its
temporary Windows user and RDP setup after execution.

**Verified P16 PASS:** [Windows Actions 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955).
Evidence artifact: `125A-Test-Lab-P16-Real-OLE-Evidence`, including
`P16-RESULT.txt`, native OLE output and received-file validation.

The optional P14 portable ZIP remains available for other desktops.
The automated P16 test does **not** require the developer's PC.

P16 is not a test of any particular commercial DAW's proprietary drop target.

## Reproduce

Use the [GitHub Actions workflows](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions):
- `P03 Real Drumator Swing Host Test`: runs P03–P11 plus P13 source tests
  on `windows-2022`. For a manual run, enter a **Drumator branch, tag or full
  commit SHA** in `drumator_ref`; the report identifies the resolved SHA.
  PR checks retain the reproducible pinned baseline.
- `P14 Interactive Windows OLE Acceptance Package`: builds the P14 kit and runs P16 true physical OLE desktop acceptance inside an ephemeral local RDP session on `windows-2022`.
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
