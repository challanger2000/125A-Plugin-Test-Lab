# One-command real VST3 technical quickcheck

Download the latest successful P25 Windows Actions artifact and extract its `PORTABLE` directory. It contains both native hosts, all required Python scripts, a README, and a SHA-256 inventory. Python 3 is required. Run the following from that directory.

On Windows x64, given two native Test Lab executables and an installed VST3
bundle, this command executes the existing P32 playback-save and P34 native
audio/state capture with no handwritten manifest:

```powershell
python run_plugin_quickcheck.py --plugin "C:\VST3\Plugin.vst3" --host ".\125A_Test_Lab_Host.exe" --stress-host ".\125A_Test_Lab_State_Stress.exe" --out ".\Plugin-QA"
```

If running directly from a source checkout rather than the portable package, use `python tests/run_plugin_quickcheck.py` instead.

It discovers exactly one .vst3 binary inside the bundle, calculates the
real file SHA-256, generates pinned intermediate manifests, and launches
native VST3 processing. P32 performs 2500 audio callbacks with 500
project-state saves. P34 captures real 24-bit stereo PCM at 44.1 kHz
and real processor-state bytes.

`QUICKCHECK-RESULT.json` reports `TECHNICAL_PASS` only when both native
stages pass and their reports identify that exact module. Missing,
out-of-date, wrong-product and ambiguous multi-module evidence is rejected.
The Windows stress workflow exercises this command against a real
source-built VST3, plus negative controls.

**This is not a product release certification.** It records unknown source
commit/version as NOT VERIFIED and marks musical correctness, product GUI,
presets, MIDI/WAV exports and commercial DAW integration as NOT COVERED.
`release_approved` is always false. Unsupported plugin bus layouts or
capture conditions fail instead of generating false green results.

For complete release acceptance, see
[PRODUCT-USER-ACCEPTANCE.md](PRODUCT-USER-ACCEPTANCE.md) and implement
trusted product-specific oracles for all applicable user-facing functions.

## Drag-and-drop Windows launcher

You can now drag an installed, trusted `.vst3` **folder** onto
`Run-VST3-Test.cmd` inside the extracted PORTABLE folder. The launcher
automatically runs native audio processing, playback saves, state capture
and real editor open/close checks. You do not need to enter a command.
Reports are written under `RESULTS/<plugin-name>/`. Python 3 must be
installed. An absent editor is shown as NOT COVERED rather than success.
The program always refuses to certify the product release without a
product-specific acceptance audit.

## Optional actual Win32 GUI checks in the same command

The portable kit now ships `125A_Test_Lab_GUI.exe` and the independent
bitmap/control checker. Add `--gui-host ".\\125A_Test_Lab_GUI.exe"` to check
that an actual VST3 editor opens, detaches, reopens and closes cleanly.
A plugin with no editor is marked `NOT COVERED`; an editor host failure
is `FAIL`.

For click and post-click painting checks, also supply a separately prepared
mapping file with `--gui-controls ".\\controls.json"`:

```json
{
  "controls": [{
    "id": "limiter_enable",
    "param_id": 9001,
    "x": 160,
    "y": 90,
    "expected_normalized": 1.0,
    "expected_pixel": {"x": 10, "y": 10, "rgb": [12, 142, 85]}
  }]
}
```

**This is an illustrative fixture mapping, not a real commercial plugin
mapping.** Obtain coordinates and expected outcomes independently from the
plugin's specification or approved reference. The runner pins the exact
plugin binary, launches the actual native GUI, clicks the declared controls
and checks the resulting controller parameters and actual painted pixels.
Missing, stale, untestable or wrong results fail. Untested controls remain
`NOT COVERED`; passing declared controls is *not* complete GUI approval.

A commercial DAW's specific interactions, including its own drag/drop and
session save/reload, still require an actual DAW-integration test rather
than an inference from this native GUI host.
