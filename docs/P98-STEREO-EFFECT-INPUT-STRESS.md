# P98 — Generic stereo-input VST3 state-stress host regression

**Scope:** source-built independent Test Lab P25/P32/P74 native Windows host handling of *zero-input generators* and *one-stereo-input audio effects*. This does **not** certify full DAW/ASIO functionality, all plugin bus topologies or release readiness.

## Reproduced failure (before repair)

The Test Lab P25 stress host always presented exactly one stereo **output** but `ProcessData.numInputs=0` and `inputs=nullptr`. This was appropriate only for output-only generators. A native Windows insert plug-in requiring one stereo input, `125A Z-Plane FX`, therefore rejected **2,368 of 2,500** process calls, while the 132 zero-frame calls returned success.

- [Red independent Z-Plane P74 Windows run #42538840328](https://github.com/challanger2000/125A-Z-Plane-FX/actions/runs/42538840328), pinned Test Lab main `bc839e345bfc5657f9196f7db8d6945584e1bec7`.
- P32 report: **six of six 44.1/48/96 kHz × 64/512 frame** cases FAIL, each with 2,368 real callback errors. Save/recall succeeded, but inputless processing was invalid for this VST3 effect.
- Secondary audit defect: the old host reported `timing_certification=PASS` merely because those rejected calls completed quickly, despite no valid audio being processed. That is **not** a real-time qualification.

## Correction

On `fix/p98-generic-stereo-effect-p25`, P25 detects the real `IComponent` audio-input topology before activation. For zero-input instruments it keeps zero input buses; for one stereo-input insert it activates and supplies both channels as non-null `AudioBusBuffers` with deterministic, preallocated, non-silent excitation. Neither the host nor the test should claim coverage for 2+ input buses, multi-channel/sidechain-only layouts or other unimplemented topologies; those are explicitly rejected by the scoped test.

Audio buffers are allocated **before** the callback thread. State-save overlap metrics and sample-rate/block tests remain independent of plugin source. The host now records `input_buses` in P25 TSV.

If a plug-in rejects any processing call, the reported realtime status is **NOT COVERED**, never PASS based on extremely short invalid callbacks. The P32 adapter and the independent TSV oracle detect false status claims.

## Adversarial test fixture and evidence

The `QAStateStereoInput` VST3 fixture requires a valid stereo input and renders distinct, deterministically scaled left/right samples. Its companion `QAStateMode0` instrument requires no input bus. A deliberately broken host `TestLabStateStressMissingInput` is a **test-only mutant** that recreates the missing-input defect; it must fail on the real FX fixture while all five positive product cases pass.

- [P98 native Windows #42539934600](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42539934600) **PASS** for four effect configurations (44.1/48 kHz × 64/512 frames), the zero-input generator and detected deliberately broken host.
- [P98 timing/fraud negative tests #42540350532](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42540350532) **PASS**: source-built valid/invalid host/FX checks plus independent mocked P32 evidence rejects both (a) post-playback-only saves and (b) forged timing PASS from failed plugin callbacks.
- [P74 Z-Plane Windows #42540050132](https://github.com/challanger2000/125A-Z-Plane-FX/actions/runs/42540050132) **SUCCESS**, pinned initial corrected Lab source `66ec829f3242e6f84a5ed2b3fef0c35bb4bc7960`. Exact actual VST3 binary hash `13a6f725923a4f7e16e7ec50ce0a93b058940e50e9229a2071c3c316da45b9f0`; P74 status `TECHNICAL_BASELINE_PASS`, independent discovery PASS, P32 **six of six** real playback/save cases PASS with 498 observed active playback saves each, native technical P34 capture PASS; `release_approved=false`. This run does not cover approved product-specific feature cases, live physical ASIO, licensed DAW, complete visual GUI semantics or musical listening.
- [Complete P98 Lab P74 rerun #42540556905](https://github.com/challanger2000/125A-Z-Plane-FX/actions/runs/42540556905) **SUCCESS** with immutable Lab `9d7adcc809b3f8cc4c5a7210213c7e549cd55b9a`: `TECHNICAL_BASELINE_PASS` including the input-bus correction **and** the fail-closed realtime reporting/independent oracle updates; 6/6 product CTests, 47/47 Steinberg Validator, 2,640/2,640 X3 hosted PCM reference renders and native real-GUI gesture/menu checks PASS. Live ASIO and full product feature coverage remain NOT RUN.

## Remaining limitations and release gates

- Input topology is deliberately bounded to zero buses or **one stereo input**; other layouts require their own independently tested host contracts.
- P25 `--save-only` is generic technical evidence, not independent frequency-response reference. Z-Plane-specific original-bank PCM and GUI tests remain separate.
- Hardware ASIO/ETW, genuine user DAW, independent licensed X3 redistribution rights, full product feature matrix, multi-instance cross-thread/GUI extreme conditions and owner sign-off are **NOT RUN/NOT VERIFIED**.
- **This is a development branch, not a merged Test Lab release.** Do not label Test Lab main as fixed based on branch-only evidence.


## Additional adversarial signal-validity oracle

The original P98 stereo effect fixture inspected input pointer presence but would have returned `kResultOk` even if a "correct" host silently filled both input buffers with zeros. This was a **test adequacy defect**: valid pointers are not valid audio stimulus.

For `QA_STATE_MODE=10` only, the independent VST3 fixture now checks physically plausible opposite-signed, non-silent L/R sample ranges on **every processed input sample**, without depending on the host's exact generation formula. A new `TestLabStateStressSilentInput` (test-only, `EXCLUDE_FROM_ALL`) supplies valid input pointers containing only zeros. The Windows P98 matrix must detect it via **more than 2,000 nonzero-frame process failures** and report `timing_certification=NOT COVERED`. The correct host must still pass all four sample-rate/block combinations and preserve the no-input generator behavior.

This is not an absolute reference test for the processed effect's output PCM; the general P25 host never assumes all real products must be non-silent. End-to-end output PCM remains a separate product-specific requirement.

## Zero-frame-only technical-baseline guard

An additional review found that P25 had accepted `block=0` as a legitimate stress scenario, although that generated **no actual audio samples across all 2,500 callbacks**. If the VST3 accepted zero-length flushes, this could misleadingly produce a playback/real-time PASS without any processed audio. The true P25 baseline now rejects zero-block-only runs before constructing or timing the plugin, while keeping the periodic zero-frame flushes **within** all positive nonzero-block matrices. A Windows negative probe requires native exit **3**, the exact diagnostic `P25 cannot certify a zero-only audio callback run`, and **no** candidate PASS evidence file. This is a deliberately bounded technical-baseline rule; it does not prohibit testing zero-frame VST3 flushes within a real audio session.
