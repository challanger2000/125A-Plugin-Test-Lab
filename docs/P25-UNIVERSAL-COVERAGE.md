# Universal VST3 stress QA — coverage matrix (P25–P30)

Infrastructure tests do not approve any production plugin. All tests use real VST3 component and processor interfaces on Windows x64 / C++23, with a pinned SDK.

| Requirement | Independent observable oracle | Positive case | Deliberately broken case | Coverage |
|---|---|---|---|---|
| Concurrent process/set/getState | 500 saves plus repeated processing and setState; paired bank/program must be one of two transactions | QAStateMode0 atomic pair | QAStateMode1 split writers and torn reads | Windows CI positive/negative PASS, run 42046335507 |
| Playback-save reliability | 500 saves must succeed during active audio callbacks | QAStateMode0 | QAStateMode2 refuses every fifth save | Windows CI positive/negative PASS, run 42046335507 |
| 44.1/48/96 kHz smoothing | Independent PCM time-ramp oracle at all rates, 250 ms full trace | QAStateMode0 | QAStateMode3 hard-coded 44.1 kHz | Windows CI positive/negative PASS, runs 42046335507 and 42049745921 |
| Zero-frame process | Every 19th callback is zero-frame | All positive runs | No negative fixture | PARTIAL |
| Block partition | Exact stereo PCM across 17/127/512 block sizes at 44.1/48/96 kHz, with zero-frame process() calls | QAStateMode0 | QAStateMode6 block-count smoothing | Windows CI positive/negative PASS, run 42049745921 |
| Real-time deadline | Preallocated callback durations, p95/p99/max, 1024-frame 44.1k deadline, strict overrun gate | QAStateMode0 | QAStateMode7 sleeps 50ms inside process() | P28 implemented; CI evidence required; shared-runner timing is not a certified DAW guarantee |
| Failed state rollback and subsequent recovery | Exact SHA-256 of saved state and all 512 stereo PCM values across valid A → invalid → valid B → restored A | QAStateMode4 with external JSON adapter | QAStateMode5 changes state despite reported error | Windows CI positive/negative PASS, run 42048372929 |
| 0/1/8/32 voices + playback saves + fresh recall | Real VST3 MIDI events; 2500 audio callbacks and 500 successful in-playback saves; independent expected per-voice amplitude before/after new-instance setState | QAVoiceMode0 | QAVoiceMode1 refuses 100 saves; QAVoiceMode2 caps at 4 voices | P29 synthetic adapter PASS, Windows run 42054620680; production plugin voice limits NOT COVERED without independent adapter |
| Controller disconnect/reconnect and stale state | Native VST3 `IConnectionPoint::connect/disconnect`, processor `setState/getState`, controller `setComponentState/getParamNormalized`, PCM; independent expected A/B tuples | QAControllerMode0 | QAControllerMode1 reports successful synchronization but retains stale controller values | P30 Windows PASS run 42057621836; real GUI pixels and product-specific controller faults NOT COVERED |
| Controller recovery and GUI error | Requires controller GUI adapter and fault injector | Not executed | Not executed | NOT COVERED |
| Semantic bank/program legality | Paired fixture oracle only verifies two synthetic tuples | Positive fixture | Torn fixture | NOT COVERED for products absent adapters |
| Reproducible scheduling | Fixed inputs and 2,500 callback / 5,000 writer / 500 save counts; OS interleavings vary | Multiple conditions | Defect fixtures | PARTIAL |
| Exact plugin provenance | GitHub run Test Lab SHA and source-built fixture | Workflow metadata | None | PARTIAL |

The explicit paired and ramp oracles are only appropriate for the synthetic fixtures. An oracle named none records domain correctness NOT_COVERED and cannot prove any musical state semantics.

## Product adapter still required

An independent product adapter must provide a trusted exact VST3 binary/version/commit, valid correlated state tuples, event and voice schedules, relevant state/audio oracles, expected smoothing time, controller fault/recovery actions and GUI confirmation contract. A generic host cannot invent these.

## Evidence

Verified Windows CI run: https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42046335507 . Its bad-torn fixture produced 21 invalid paired snapshots, bad-save-only produced 100 rejected playback saves of 500, and bad-rate produced a 0.25 ramp value where 0.125 was independently required. Valid fixtures passed. These measured results verify test sensitivity on fixtures only, not any product release.

P29 separately runs .github/workflows/p29-voice-stress.yml and writes independent per-tier state/PCM evidence. Its 32-voice ceiling is **synthetic fixture-specific**, not a universal maximum. For production instruments a trusted adapter must declare the real polyphony cap and expected PCM behavior.

The P25 Windows workflow exports per-scenario TSV and logs with source commit, rate, block, callback count, save attempts, and independently verified acceptance results. Any broken fixture not detected is a test adequacy FAIL. Green compilation alone is not a functional PASS.

## Confirmed measured follow-up runs

- P26: [Windows Actions 42048372929](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42048372929). The positive fixture passed external state SHA256 and 512 exact PCM values. The broken fixture returned an error but silently changed its state; the independent adapter correctly failed at state-after-error.bin. No actual GUI-transport message was injected.
- P27: [Windows Actions 42049745921](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42049745921). Nine good PCM cases matched time reference; three partitions per rate had identical bytes. Negative sample-rate case deviated by 0.1351563, and negative block-dependent case failed exact partition comparison.
- P28: VERIFIED in Windows Actions run 42051397047. The actual 1024-sample / 44.1-kHz callback test recorded p95, p99, maximum time and deadline overruns over 2500 callbacks. A valid VST3 passed while the intentionally blocking VST3 failed the deadline oracle. This does not prove allocation freedom, universal hardware latency, or maximum-voice reliability.

- P29: [Windows Actions 42054620680](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42054620680). All four polyphony tiers (0, 1, 8, 32) passed 500 saves during active playback, 2500 real VST3 audio callbacks and fresh-instance recall. The broken-save instrument reported 100 failed playback saves; the broken-polyphony instrument rendered 0.04 instead of the independent expected 0.32 for 32 voices. No production instrument was certified.

- P30: [Windows Actions 42057621836](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42057621836). Valid VST3 controller disconnect/reconnect kept processor state, normalized parameters and PCM consistent across invalid-state rollback, B recovery and A restoration. A broken controller retained stale values despite successful API returns; the independent oracle rejected it. This does not certify the rendered graphical editor or arbitrary production-parameter semantics.

Do not run the fixture-only paired or ramp oracle against a different plugin without an approved adapter. The generic host is portable; its synthetic state schema is not.
