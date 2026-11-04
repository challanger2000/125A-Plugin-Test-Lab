# 125A Plugin Test Lab

**Windows-only VST3 functional integration test host** (C++23, Visual Studio 2022).

The established [125A Plugin Tester](https://github.com/challanger2000/125A-Plugin-Tester)
covers baseline conformance, processor lifecycle, state, I/O and basic editor
lifecycle. **Test Lab** adds actual audio/transport/feature validation,
independently compared with externally defined musical reference values.

## Verified P02: real VST3 infrastructure

- SDK `v3.8.1_build_84`; actual VST3 component/processor and sample-accurate events.
- 44.1 kHz, 120 BPM, 4/4, four-bar render into signed PCM24 stereo WAV.
- Good test VST3 produces exactly 16 known audio impulses, all 352,800
  frames checked by a separate Python oracle.
- Malformed VST3 emits NaN; host must reject **specifically** for bad audio.

## Verified P03: actual Drumator V1.5

Dedicated [P03 Windows workflow](.github/workflows/drumator-p03.yml):
- Checks out exact public Drumator source SHA
  `e22e65517e3e61d5e55e29b0ee7e34ea9b856a3c` (no product modifications).
- Builds the real VST3 on GitHub's Windows 2022 runner.
- Loads two **synthetic** DM18 kit project states by actual
  `IComponent::setState()`; both contain a self-created PCM16 sample.
- Renders internal sequencer audio, not injected host MIDI:
  SWING=0% produces eighth offbeats at frames 11025, 99225, 187425, 275625;
  SWING=50% at frames 14700, 102900, 191100, 279300.
- An independent reference oracle verifies **exact 3,675-frame delay** in
  all four bars (120 BPM, 44.1 kHz; musical 2:1 triplet eighth feel).
- Tests actual `getState()` and fresh-process `setState()`: compares all
  352,800 frames, both channels, byte-for-byte, and validates DM18 CRC.
- Corrupts the saved kit: the plugin must reject it for a state-integrity
  reason, and produce no WAV.

Successful P03 proof: [Windows Actions #41919715104](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41919715104).


## Verified P04: native VST3 editor input, not yet full product GUI QA

The separate [P04 Windows GUI workflow](.github/workflows/gui-p04.yml)
builds `125A_Test_Lab_GUI.exe` and two self-created, native-Win32 VST3s.

- Open real `IPlugView` via `IEditController`, attach a child HWND to
  an actual Win32 host window, pump messages and detach, **twice**.
- Emit native `WM_MOUSEMOVE`, `WM_LBUTTONDOWN` and `WM_LBUTTONUP`
  to the fixture's real child HWND. The click **must** change parameter
  ID 9001 from 0 to 1, and this is verified on both editor cycles.
- Deliberately inert VST3 is rejected **specifically** because the
  parameter did not change; unrelated load errors do not satisfy CI.
- `--probe <plugin.vst3>` performs real editor lifecycle checks for an
  arbitrary Windows VST3. A plugin without an editor is **INCONCLUSIVE**
  (exit 10), not a green PASS.

Evidence: [P04 GitHub Actions SUCCESS](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41921967133).

**P04 boundaries:** This is a native HWND message-dispatch test on a
controlled plugin. It does **not** prove pixel rendering, pointer behavior
through an interactive physical desktop, MIDI/WAV export dialogs, or
correctness of every product control. Do not call it a comprehensive GUI audit.

## Limitations / unfinished tests

**P03/P04 are limited integration proofs, not a Drumator release approval.**
It does not yet click the real GUI, trigger Beat Creator generate/variate/break,
test the UI's preset browser, internal MIDI/WAV export buttons, or reproduce
issues specific to Fender Studio Pro. Do not substitute generic P02/P03
green checks for those future test gates.

See [START-HERE.md](START-HERE.md) for actual CLI and safety notes.
Public repository: no commercial samples, credentials, DAW licenses or private
plugin binaries are included.
