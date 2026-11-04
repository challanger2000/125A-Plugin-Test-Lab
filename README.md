# 125A Plugin Test Lab

**Windows-only, C++23, DAW-like VST3 functional integration test host.**

The previously built [125A Plugin Tester](https://github.com/challanger2000/125A-Plugin-Tester)
already checks VST3 conformance, lifecycle, audio I/O, state handling and basic
editor lifecycle. **Test Lab is for independent audio/transport/feature evidence.**

## P02 scope
- Windows x64 / Visual Studio 2022 / C++23; pinned VST3 SDK `v3.8.1_build_84`
- Actual VST3 processor creation, MIDI events, host timebase and audio callbacks
- Four-bar 44.1 kHz, 120 BPM, 4/4 render to PCM24 stereo WAV
- Known-good VST3 fixture generating sample-aligned audio pulses
- Independent Python oracle checks every single frame and channel
- Deliberately broken VST3 injects NaN audio; host must reject it specifically
- GitHub Actions integration, test logs, proof WAV, downloadable Windows exe

**P02 is an infrastructure proof, NOT a Drumator functional approval.**
It does not test SWING, GUI, Beat Creator, state restore or independent DAW
compatibility. These require dedicated follow-on scenarios.

Read [START-HERE.md](START-HERE.md) before running the host.

## Security
GitHub repository is public, without proprietary plugins, user sample kits,
DAW licenses or credentials. Test native VST3 binaries in isolated environments.
