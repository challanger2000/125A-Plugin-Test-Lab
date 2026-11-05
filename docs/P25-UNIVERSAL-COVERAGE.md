# Universal VST3 stress QA — coverage matrix (P25–P28)

Infrastructure tests do not approve any production plugin. All tests use real VST3 component and processor interfaces on Windows x64 / C++23, with a pinned SDK.

| Requirement | Independent observable oracle | Positive case | Deliberately broken case | Coverage |
|---|---|---|---|---|
| Concurrent process/set/getState | 500 saves plus repeated processing and setState; paired bank/program must be one of two transactions | QAStateMode0 atomic pair | QAStateMode1 split writers and torn reads | Windows CI positive/negative PASS, run 42046335507 |
| Playback-save reliability | 500 saves must succeed during active audio callbacks | QAStateMode0 | QAStateMode2 refuses every fifth save | Windows CI positive/negative PASS, run 42046335507 |
| 44.1/48/96 kHz smoothing | PCM at 50 ms must equal 0.125 ±0.002 | Native 0.1 s ramp | QAStateMode3 hard-coded 44.1 kHz | Windows CI positive/negative PASS, run 42046335507 |
| Zero-frame process | Every 19th callback is zero-frame | All positive runs | No negative fixture | PARTIAL |
| Block partition | Host callbacks of 17, 64, 127, 512 | Multiple positive cases | No independent partition equivalence oracle | PARTIAL |
| Real-time deadline | Maximum duration and overrun count recorded | Positive fixture | Deliberately slow split writer | Diagnostic only; not certified |
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
