# START HERE — 125A Plugin Test Lab

## Established and verified

P01–P09 test infrastructure exists on Windows x64 and all listed test
gates passed in [Actions run 41938707186](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41938707186),
with standalone P02 and P04 regression checks also successful.
The **real-product GUI integration P09** proved Limiter and Beat Creator
state changes, including GENERATE / CANCEL / APPLY / CONFIRM.

Pinned tested product source: `challanger2000/125A-Drumator-Final`,
SHA `6184718dda4a725fe4892a9e76533ec24dfa2f17`.
This is not a floating/latest-commit test. Tests of a newer product commit
must explicitly update the pinned SHA and rerun the acceptance suite.

## Run workflows

From the repository's **Actions** tab, use **Run workflow** for
`P03 Real Drumator Swing Host Test`. The workflow checks out the pinned
product source and creates all test binaries, synthetic drum kits and test
vectors without requiring the user's computer or installed DAW.

The report names the exact commit and gives PASS/FAIL evidence for:
- host VST3 component lifecycle and genuine DSP processing
- 36 combinations of tempo, Swing and audio process-buffer partitions
- real audio, saved state, rejected corrupted state
- MIDI/WAV export core and independent file/timing checks
- Beat Creator A/B/C algorithm stress and five-point Complexity helper
- real Win32 editor, Limiter, Beat Creator GENERATE/CANCEL/APPLY/CONFIRM
- negative audio/MIDI/WAV/GUI fixtures and explicit INCONCLUSIVE cases

The P04 and P02 workflows separately check the GUI-host and audio-host
infrastructure itself.

## Standalone Windows CLI

Extract the corresponding GitHub Actions artifact before running:

```powershell
.\125A_Test_Lab_Host.exe --selftest
.\125A_Test_Lab_Host.exe --render "C:\Path\Plugin.vst3" ".\render.wav"
.\125A_Test_Lab_Host.exe --render-state "C:\Path\Plugin.vst3" ".\kit.bin" ".\render.wav"
.\125A_Test_Lab_Host.exe --render-state-save "C:\Path\Plugin.vst3" ".\kit.bin" ".\render.wav" ".\saved-state.bin"
.\125A_Test_Lab_Host.exe --render-state-at "C:\Path\Plugin.vst3" ".\kit.bin" ".\render.wav" 120 127

.\125A_Test_Lab_GUI.exe --probe "C:\Path\Plugin.vst3"
.\125A_Test_Lab_GUI.exe --prove-click "C:\Path\125A_QA_GUI_Click.vst3" 9001
```

For `--prove-click`, use only a specially prepared VST3 exposing a
documented controller parameter that switches from 0 to 1 when clicked.
The main host's `--render-state-at` supports sample-exact tempos 60–240
and blocks of 16–2048 frames, with audio at 44.1 kHz and a 4/4 host.

The P09 real-product GUI test runs from source under the pinned CI
workflow because it requires a complete VST3 bundle with the actual
`Contents/Resources` tree, a COM-initialized Win32 UI thread, a connected
controller and processor, and a state oracle. Do not point the GUI host
at an unbundled DLL and expect a complete editor.

## Outcome semantics

**PASS** — independent, observed expected behavior under tested conditions.

**FAIL** — test assertion, plugin behavior, environment or test-host error
must be diagnosed; no approval until resolved.

**INCONCLUSIVE** — the scenario was attempted but cannot be determined;
for instance, the plugin does not expose an editor.

**NOT COVERED** — no verified test exists for that behavior.

A green CI run does not imply complete GUI menu, drag-and-drop, file chooser
or proprietary DAW workflow coverage. Export core validation P06/P08 is
**not** proof that a user can trigger those exports from the editor.

## Security and policy

This repository is public. Do not commit purchased samples, user kits,
private plugins, personal data, licenses or credentials. The test kits
are synthesised, and third-party plugins execute as native code.
Use sandboxed runners for untrusted binaries.

Test Lab is a quality-assurance system, **not** the product release
repository or Gumroad release process.
