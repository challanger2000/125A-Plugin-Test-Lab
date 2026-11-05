# One-command real VST3 technical quickcheck

Download the latest successful P25 Windows Actions artifact and extract its `PORTABLE` directory. It contains both native hosts, all required Python scripts, a README, and a SHA-256 inventory. Python 3 is required. Run the following from that directory.\n\nOn Windows x64, given two native Test Lab executables and an installed VST3
bundle, this command executes the existing P32 playback-save and P34 native
audio/state capture with no handwritten manifest:

```powershell
python run_plugin_quickcheck.py --plugin "C:\VST3\Plugin.vst3" --host ".\125A_Test_Lab_Host.exe" --stress-host ".\125A_Test_Lab_State_Stress.exe" --out ".\Plugin-QA"
```

If running directly from a source checkout rather than the portable package, use `python tests/run_plugin_quickcheck.py` instead.\n\nIt discovers exactly one .vst3 binary inside the bundle, calculates the
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
