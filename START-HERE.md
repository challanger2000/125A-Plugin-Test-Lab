# START HERE — 125A Plugin Test Lab

## Current status: P02 validation

Windows x64 console VST3 functional host. It loads real VST3 modules, initializes
processors, supplies PPQ and sample-accurate MIDI events, processes four bars,
and exports signed 24-bit stereo WAV files at 44.1 kHz.

The **P02** CI acceptance gate compiles two actual VST3 fixtures:
- **Known-good:** MIDI NoteOn events trigger exactly 128 samples at amplitude
  0.25 at the start of every quarter note. A separate Python script analyzes
  every single 24-bit sample across both WAV channels without reusing the
  fixture's audio processing code.
- **Deliberately bad:** injects a NaN sample, which must fail specifically
  because non-finite audio was detected. Unrelated failure does not pass CI.

CI also runs the transport selftest and invalid-module negative check.

## Commands
Run the artifact's executable under Windows x64:
```powershell
.\125A_Test_Lab_Host.exe --selftest
.\125A_Test_Lab_Host.exe --render "C:\Program Files\Common Files\VST3\YourPlugin.vst3" ".\test.wav"
```

Host settings in P02 are fixed: 44.1 kHz / 120 BPM / 4/4 / 4 bars,
512-sample blocks / 24-bit WAV stereo.

## Truthful QA interpretation
- A green P02 proves that the host processed a **controlled test VST3** and
  rendered that particular known-good waveform accurately. It does NOT yet
  prove that Drumator, Swing, Beat Creator, presets, export, or the GUI work.
- A silent render is reported as **inconclusive** for audible behavior.
- FAIL may mean a plugin bug, unsupported host scenario, or a test-host bug;
  findings need reproduction and classification.
- Test fixtures are CI-only and do not ship with the user-facing host.

## Next gates
P03: run actual Drumator functional test cases with independent onset timing,
SWING, tempo changes, transport interruptions, preset/project state roundtrips.
P04: verified real interactive Windows GUI automation plus cross-checks in a
separate DAW (REAPER) where useful. GUI runtime on hosted CI cannot be assumed.

## Security
The repository is public. Never commit third-party plugins, DAW license files,
samples, secrets, or user presets. VST3s are native executable modules; test
only trusted plugins and prefer isolated test environments.
