# START HERE — 125A Plugin Test Lab

## P01: scope
Windows x64 console test host. It loads a real VST3, initializes its component and
audio processor, supplies a host transport timeline and 16 NoteOn/NoteOff pairs
(if an input event bus exists), processes four bars, checks finite output,
and exports a stereo 24-bit WAV. This calls the actual plugin DSP process callback.

P01 is NOT a graphical DAW and does NOT prove Swing, Beat Creator, presets,
internal MIDI export, GUI functionality, or musical correctness.

## Usage
1. Download and unzip the P01 Windows-x64 GitHub Actions artifact.
2. In PowerShell run:
   .\125A_Test_Lab_Host.exe --selftest
3. For a trusted installed VST3:
   .\125A_Test_Lab_Host.exe --render "C:\Program Files\Common Files\VST3\YourPlugin.vst3" ".\test.wav"

P01 configuration: Windows x64; 44,100 Hz float32 DSP; 120 BPM; 4/4;
four bars; 512-sample processing blocks; WAV PCM24 stereo.

## Interpret results
- PASS: only that specific operation succeeded; not an overall release approval.
- WARN silent output: the host cannot verify musical/audio behavior.
- FAIL: plugin issue, unsupported host scenario, or test-host defect; investigate.
- INVALID MODULE rejection: a negative test, not a plugin-behavior test.

GitHub CI currently runs only the transport selftest and an invalid-module
test. It does NOT yet render an independently validated real VST3 fixture.

## Required next gates
P02: build a deterministic VST3 fixture from source, render it under this host,
and independently check precise audio timing, amplitude, sample count and
a deliberately broken variant.
P03: compare actual swing and MIDI onset timings against independent expected
values; add transport interruptions and state recall.
P04: actual plugin GUI automation with a proven interactive Windows desktop;
cross-check select outcomes against an established DAW.

## Security
Repository public: never commit DAW licenses, credentials, private VST3s,
sample libraries, or proprietary user presets. Native plugins execute code;
test only trusted binaries. An interactive GUI test cannot be assumed to
work on GitHub-hosted Windows runners.
