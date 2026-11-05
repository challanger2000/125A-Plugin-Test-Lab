# START HERE — 125A Plugin Test Lab

## Established and verified

P01–P11 test gates passed in [Windows Actions 41944080762](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41944080762).
P09 proved real editor/Beat Creator interaction, P10 proved native Windows
Save-dialog cancellation, and P11 proved **all four GUI MIDI/WAV Save As
exports** create correct independent music files. P02/P04 host self-tests
also passed.

The verified benchmark source was `challanger2000/125A-Drumator-Final`
SHA `6184718dda4a725fe4892a9e76533ec24dfa2f17`.
**Newer code can be selected manually via GitHub Actions**. PR benchmarks
continue to pin the above SHA; the manual run logs the SHA it actually
checked. Never assume a benchmark PASS proves an untested newer build.

## Run workflows

Go to **Actions → P03 Real Drumator Swing Host Test → Run workflow**.
In the `drumator_ref` field, enter a product branch, tag or complete
40-character commit SHA. Default: `develop/beat-creator-10-styles-20261102`.
Choose the Test Lab `main` branch and start the workflow. This builds the
**selected product revision**, generates synthetic kits and vectors, and
reports the exact resolved SHA in `TESTED-PRODUCT-REVISION.txt`.
No local Windows installation, user sample library or DAW is required.

For pull requests that change the Test Lab itself, the workflow uses the
original pinned product commit instead, to make infrastructure regressions
reproducible.

The report names the exact commit and gives PASS/FAIL evidence for:
- host VST3 component lifecycle and genuine DSP processing
- 36 combinations of tempo, Swing and audio process-buffer partitions
- real audio, saved state, rejected corrupted state
- MIDI/WAV export core and independent file/timing checks
- Beat Creator A/B/C algorithm stress and five-point Complexity helper
- real Win32 editor, Limiter, Beat Creator GENERATE/CANCEL/APPLY/CONFIRM
- four true Win32 Save As dialogs and non-destructive CANCEL
- four actual GUI Pattern/Song MIDI/WAV exports and independent musical checks
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

A green CI run does not imply comprehensive GUI menu/preset behavior,
OLE drag-and-drop acceptance into an external DAW, or proprietary DAW
workflow coverage. **GUI Save As MIDI/WAV has passed P11**, but a drop into
a real DAW track remains **NOT COVERED**.

## Security and policy

This repository is public. Do not commit purchased samples, user kits,
private plugins, personal data, licenses or credentials. The test kits
are synthesised, and third-party plugins execute as native code.
Use sandboxed runners for untrusted binaries.

Test Lab is a quality-assurance system, **not** the product release
repository or Gumroad release process.
