# Native VST3 offline and paced host modes (general-purpose Test Lab extension)

This extension is **universal**, not linked to or hard-coded for any product. It augments the existing native `125A_Test_Lab_Host.exe` without changing the behavior of its existing `--render` and `--capture` modes.

## New command modes

| Mode | VST3 process setup/callback | MIDI stimulus | Host scheduling |
| --- | --- | --- | --- |
| `--render-offline Plugin.vst3 Output.wav` | kOffline | default 16 note-on/off pairs (32 events) | CPU-fast, no frame-clock pacing |
| `--render-offline-no-midi Plugin.vst3 Output.wav` | kOffline | **none**, including no event list | CPU-fast |
| `--render-realtime-paced Plugin.vst3 Output.wav` | kRealtime | same default 16 note pairs | sleep until nominal 44.1 kHz block deadline |

All three produce 44.1 kHz, 24-bit integer stereo WAV and keep the established 4-bar 120 BPM pattern and 512-frame block size.

## Why it exists

The generic unpaced `--render` uses kRealtime callbacks run as fast as the host's CPU can process them. This is valid for ABI exercising but **not a faithful simulation of realtime wall-clock availability** when a plugin delegates DSP to an asynchronous helper. A plugin may yield nonzero PCM while skipping entire blocks of actual playback.

Use `--render-offline` to verify whether the plugin correctly honors the *host's offline request*, including any separately isolated worker synchronization that is disallowed on a realtime callback. `--render-realtime-paced` is a synthetic wall-clock timing demonstration and is **not** an ASIO/ETW deadline certification. No host sleep occurs inside the plugin callback. Different output modes should never be mixed in a claimed same-condition comparison.

## Mandatory evidence interpretation

- A WAV with some nonzero samples is not continuous or musical PCM proof.
- `--render-offline-no-midi` is a useful negative for spontaneous audio; some generative/sustained instruments legitimately produce sound without MIDI, so the expected result is **product-specific**, not a universal FAIL.
- The caller must provide product-approved waveform oracles: audible-note windows, note-off behavior, dropout boundary measurement, and independent reference comparisons. The host only reports actual data; it does **not** automatically assert SoundFont fidelity or complete product behavior.
- File existence, VST3 `process()` success, and quiet output are not release approvals.
- This change does not install, launch, download, bundle or analyze untrusted third-party DLLs. Perform those actions only within an appropriately isolated authorized environment.

## Validation

The integration project `challanger2000/125A-Fruity-SoundFont-Player` independently compiles this native host pinned to commit `018b4a18479a79980dbbdcc80c9c9a8a6ed54cda` and verifies all three modes against a source-built proprietary-free VST3/engine fixture in GitHub Actions run `42541701486`. It asserts nonzero MIDI audio, zero audio without MIDI/engine and zero full-block dropouts under paced callback scheduling. The genuine external original DLL is not run in public CI.

This is a development branch. Do not merge without full 125A Engineering QA and regression checks.
