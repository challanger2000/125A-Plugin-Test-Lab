# P79 — Native Windows VST3 GUI-to-export integration in universal product QA

P46 already implemented a **real source-built VST3 GUI exporter fixture**, including positive WAV/MIDI and deliberately incorrect PCM/note variants. P77 added a separate orchestrator, but P78 correctly refused to equate file appearance with independently verified process authorship.

P79 reuses the existing native P46 mechanism instead of inventing another simulated output producer. The P65 plan now accepts `gui_export_contract` whose contract is exactly the P46 `125a-gui-export-contract-v1` object. P67 must independently declare the required export feature. The runner executes the real Windows editor, tests the approved coordinate/parameter action, creates a clean output directory with `QA_TEST_LAB_EXPORT_ROOT`, checks expected files and SHA-256 plus WAV/MIDI metadata, and keeps evidence.

Run P79 fixture proof in Windows Actions or:

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release --parallel 4 --target TestLabGUI QAGuiExportGood QAGuiExportBad QAGuiExportMidiGood QAGuiExportMidiBad
python tests/run_p79_native_export_fixtures.py --build build --out build/p79-results
```

The CI runs four actual source-built Windows VST3s: WAV good, WAV wrong PCM, MIDI good and MIDI wrong note. In each, a native click reaches the VST3 GUI. A passing VST3 produces the exact independently declared bytes; a broken VST3 has a *correctly observed GUI parameter change* but fails the file oracle. The integrated P65/P67 plan must pass both good modules and reject both broken modules.

P74 can dispatch this P65 case when a reviewed product plan and P67 feature matrix are supplied. The old `export_action_chain` kind stays fail-closed where provenance is not established.

## What is and is not proven

**Proven on source-defined native fixtures:** a real VST3 editor invokes a file export in an isolated Windows test host, and P65/P67 validates output under a pre-approved independent oracle.

**Not proven:** automatic discovery and activation of *arbitrary unknown* commercial GUI exporters, OS-level writer/process provenance, exported files from real 125A production plugins, DAW session interaction, physical ASIO hardware, or automatic release approval. Those require separate adapters or manual/physical acceptance. Do not extrapolate fixture PASS into an unknown plugin's functional PASS.
