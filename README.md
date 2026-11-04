# 125A Plugin Test Lab

Windows-only, C++23 VST3 **functional integration testing** project.

**Status: P01 prototype. Not a release QA approval.**

The existing 125A Plugin Tester covers host conformance, lifecycle, I/O,
state and baseline editor-lifecycle testing. The new Test Lab will focus on
**actual behavior**: DAW-like transport, playback, timing, sound, presets,
swing, export and later GUI interactions, with independent oracles.

## P01 components
- Windows x64 / Visual Studio 2022 / C++23.
- Pinned Steinberg VST3 SDK v3.8.1_build_84 (matching 125A Plugin Tester).
- Real VST3 component/processor instantiation and render pipeline.
- 44.1 kHz, 120 BPM, 4/4, 4-bar host timebase and quarter-note MIDI events.
- 24-bit stereo WAV rendering; finite-output checks and peak reporting.
- CTest transport selftest and invalid-plugin negative test.
- Public GitHub Actions Windows build and artifact.

No current test proves Swing, Drumator Beat Creator, preset saving or GUI
correctness. The host itself requires independent fixture-backed validation.

Read [START-HERE.md](START-HERE.md) for usage, caveats and acceptance gates.

## Future gates
P02 known-good and defective VST3 fixtures. P03 musical timing oracle and
state/preset tests. P04 reliable GUI automation and independent DAW cross-checks.

No licenses, tokens or third-party sound libraries in this public repository.
