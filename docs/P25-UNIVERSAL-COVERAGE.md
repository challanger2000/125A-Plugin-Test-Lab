# Universal VST3 stress QA — coverage matrix (P25–P28)

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
| One/max voice and recall audio | Requires musical events, voice capabilities and product adapter | Not executed | Not executed | NOT COVERED |
| Controller recovery and GUI error | Requires controller GUI adapter and fault injector | Not executed | Not executed | NOT COVERED |
| Semantic bank/program legality | Paired fixture oracle only verifies two synthetic tuples | Positive fixture | Torn fixture | NOT COVERED for products absent adapters |
| Reproducible scheduling | Fixed inputs and 2,500 callback / 5,000 writer / 500 save counts; OS interleavings vary | Multiple conditions | Defect fixtures | PARTIAL |
| Exact plugin provenance | GitHub run Test Lab SHA and source-built fixture | Workflow metadata | None | PARTIAL |

The explicit paired and ramp oracles are only appropriate for the synthetic fixtures. An oracle named none records domain correctness NOT_COVERED and cannot prove any musical state semantics.

## Product adapter still required

An independent product adapter must provide a trusted exact VST3 binary/version/commit, valid correlated state tuples, event and voice schedules, relevant state/audio oracles, expected smoothing time, controller fault/recovery actions and GUI confirmation contract. A generic host cannot invent these.

## Evidence

Verified Windows CI run: https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42046335507 . Its bad-torn fixture produced 21 invalid paired snapshots, bad-save-only produced 100 rejected playback saves of 500, and bad-rate produced a 0.25 ramp value where 0.125 was independently required. Valid fixtures passed. These measured results verify test sensitivity on fixtures only, not any product release.

The P25 Windows workflow exports per-scenario TSV and logs with source commit, rate, block, callback count, save attempts, and independently verified acceptance results. Any broken fixture not detected is a test adequacy FAIL. Green compilation alone is not a functional PASS.

## Confirmed measured follow-up runs

- P26: [Windows Actions 42048372929](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42048372929). The positive fixture passed external state SHA256 and 512 exact PCM values. The broken fixture returned an error but silently changed its state; the independent adapter correctly failed at state-after-error.bin. No actual GUI-transport message was injected.
- P27: [Windows Actions 42049745921](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42049745921). Nine good PCM cases matched time reference; three partitions per rate had identical bytes. Negative sample-rate case deviated by 0.1351563, and negative block-dependent case failed exact partition comparison.
- P28: Under implementation. This is an audio-callback elapsed-time/deadline test, **not** proof of allocation freedom, hardware-guaranteed latency, or maximum-voice reliability.

Do not run the fixture-only paired or ramp oracle against a different plugin without an approved adapter. The generic host is portable; its synthetic state schema is not.
