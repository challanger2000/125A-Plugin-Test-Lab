# P73 — Headless VST3 support and optional automatic technical checks

The P72 onboarding originally required a GUI inspection for every VST3.
This is incorrect for legitimate MIDI/audio processors and effects
that expose a VST3 component/controller but no `IPlugView` editor.

P73 now follows **real P68 native VST3 ABI evidence**. When P68 reports
`reported_editor_available: false`, P72/P73 completes the read-only
onboarding without attempting any GUI construction or visual scanning.
The result says `gui_editor_status: VST3_NO_EDITOR_EXPOSED`;
there are no fabricated GUI candidates. Other discovered parameters,
buses and potential technical tests are reported normally.

When an editor is advertised, P71 read-only GUI discovery is still
required and cannot be skipped or counterfeited.

## One command: inventory + safe technical test

Default **no tests and no clicks**:

```powershell
python tests/run_plugin_onboarding.py --plugin C:\QA\Effect.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\onboarding
```

Enable the existing P66 native audio/render/state-save checks *only
after choosing a disposable isolated test environment*:

```powershell
python tests/run_plugin_onboarding.py --plugin C:\QA\Effect.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --audio-host C:\QA\125A_Test_Lab_Host.exe --stress-host C:\QA\125A_Test_Lab_State_Stress.exe --run-technical-baseline --timeout 110 --out C:\QA\onboarding-test
```

The opt-in runs the native Test Lab `run_plugin_quickcheck` directly on
the exact SHA-256-pinned plugin and hosts. The consolidated handoff
requires independent `PASS` for `api_playback_save`,
`sample_rate_buffer_matrix` and `native_audio_state_capture`; an
actual host error or missing result fails the command and produces
diagnostic artifacts. It must not treat an incomplete technical run
as an approved product.

P73 NEVER enables arbitrary GUI clicks, invokes commercial DAW
software or accesses physical ASIO driver callbacks. A technically
successful check is still **not** a complete product-specific P67
feature inventory, musical audio reference or commercial release:
`required_feature_coverage: NOT DECLARED`,
`full_product_functional_coverage: NOT COVERED`,
`release_approved: false`.

The Windows acceptance job must prove both a genuinely working
source-built headless VST3 and a deliberately defective source-built
headless VST3. Both use the same universal command without any
plugin-specific QA adapter.
