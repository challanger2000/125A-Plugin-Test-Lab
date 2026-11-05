# START HERE — 125A Plugin Test Lab

## Established and verified

P01–P11 plus the P13 **GUI drag-source** test passed in
[Windows Actions 41952977868](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41952977868).
**P16 real interapplication OLE acceptance passed** in [Windows Actions 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955): four native `CF_HDROP` receiver callbacks and independently validated Pattern/Song MIDI/WAV files in a genuine temporary RDP desktop.
P09 proved real editor/Beat Creator interaction, P10 proved native Windows
Save-dialog cancellation, and P11 proved **all four GUI MIDI/WAV Save As
exports** create correct independent music files. P02/P04 host self-tests
also passed.

The verified benchmark source was `challanger2000/125A-Drumator-Final`
SHA `eed1bf232b61f6fb725ca00d82a99658cfba07e2`.
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
- four actual GUI Pattern/Song MIDI/WAV Save As exports and independent musical checks
- P13 genuine GUI drag-source gesture: four independently validated retained files
- P15 synthetic receiver contract for four COM CF_HDROP callbacks
- P16 actual physical drag-and-drop into separate native COM receiver, four files PASS
- P17 16 real Drumator editor detach/reattach cycles, each with valid HWND and unchanged processor state
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

## P14 / P16 native interactive OLE acceptance

The P14 workflow builds the full source-built Drumator VST3 and synthetic
A/REST/A test kit. **P16 additionally performs true desktop-native
Drag-and-Drop inside GitHub Actions**. It provisions a temporary local
RDP user on the disposable Windows 2022 runner, keeps an interactive
desktop connected, launches the actual editor and an independent Win32
COM `IDropTarget`, and uses physical mouse input to deliver all four
Pattern/Song MIDI/WAV exports via `CF_HDROP`.

Verified: [P16 Windows Actions 41964558955](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/41964558955),
including the `125A-Test-Lab-P16-Real-OLE-Evidence` artifact. Recorded
`P16-RESULT.txt` reports PASS for four received callbacks and four
independently checked files. No developer Windows installation is needed.

The optional P14 portable ZIP and `Run-OLE-Test.cmd` remain available for
manual reproduction. The native receiver acceptance does not assert
compatibility with a specific commercial DAW's internal drop target.

## Outcome semantics

**PASS** — independent, observed expected behavior under tested conditions.

**FAIL** — test assertion, plugin behavior, environment or test-host error
must be diagnosed; no approval until resolved.

**INCONCLUSIVE** — the scenario was attempted but cannot be determined;
for instance, the plugin does not expose an editor.

**NOT COVERED** — no verified test exists for that behavior.

A green CI run proves the explicitly tested behaviors and source
revision. P11 Save As, P13 GUI source generation, P15 receiver contract,
and P16 actual interapplication OLE reception are PASS. Proprietary DAW
integration and untested GUI workflows are tracked separately.

## Security and policy

This repository is public. Do not commit purchased samples, user kits,
private plugins, personal data, licenses or credentials. The test kits
are synthesised, and third-party plugins execute as native code.
Use sandboxed runners for untrusted binaries.

Test Lab is a quality-assurance system, **not** the product release
repository or Gumroad release process.
