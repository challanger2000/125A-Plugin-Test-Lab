# P81 — Native GUI WAV/MIDI exports in a real isolated VST3 batch

P79 proved real source-built VST3 export behavior through the P65/P67 adapter. P80 added per-plugin approved plans to P75 batch processing but its dedicated tests used mocked subprocesses. P81 closes that *integration proof* gap.

Windows CI builds a real native GUI host and **four separate Windows VST3 exporters**. Every plugin has its own pinned SHA-256 and approved P65/P67 manifest. The actual P75 batch launches an independent P74 subprocess for each plugin, performs real read-only GUI discovery, invokes the native GUI control and checks the independently declared WAV or MIDI export bytes.

The first batch intentionally checks deliberately wrong PCM and wrong MIDI note fixtures **before** correct WAV and MIDI fixtures. It must report two failures and continue to two independent successes. The second batch contains only correct exporters and must report `BATCH_DECLARED_COVERAGE_PASS`. For positive cases P81 opens the real P46 evidence and independently hashes the retained WAV/MIDI files, checking the expected golden digest. Full P74/P65/P67 evidence is preserved for every plugin.

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release --parallel 4 --target TestLabGUI QAGuiExportGood QAGuiExportBad QAGuiExportMidiGood QAGuiExportMidiBad
python tests/run_p81_native_batch_exports.py --build build --out build/p81
```

No plugin-specific changes to P74 or P75 are needed. This acceptance only establishes the behavior of intentionally constructed source-defined fixtures, **not** the general ability to discover and invoke arbitrary unknown VST3 exporters. It does not identify the individual Windows process that wrote a file, and cannot replace a real commercial DAW session or physical ASIO hardware tests. Release approval is always false.
