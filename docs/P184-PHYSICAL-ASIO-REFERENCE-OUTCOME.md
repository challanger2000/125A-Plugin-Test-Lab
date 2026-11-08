# P184 — Independent physical ASIO reference A/B/A result

Date: 2026-11-08. Project: `125A-AWE-Synthesizer`, locally
executed AWE-side P182 control launcher, exact
`P182-LOCAL-RESULT-20261108-221242-090ab1f8.zip`.
The source-built **QAASIOReferenceMidi** good module, corrected
and adversarially lifecycle-tested in P183, was used on
the owner's real **Yamaha Steinberg USB ASIO** hardware
(512 frames, 44,100 Hz) on both sides of the real AWE VST3.

| Physical run | Reference-A | Real AWE | Reference-B |
|---|---:|---:|---:|
| IASIO callbacks, processed | 1000/1000 | 1000/1000 | 1000/1000 |
| VST3 process errors | 0 | 0 | 0 |
| Gap index (zero based) | 2 | 2 | 2 |
| One excessive callback start interval | 58.4385 ms | 63.1304 ms | 56.3673 ms |
| Max callback execution | 0.0916 ms | 5.9249 ms | 0.0967 ms |
| Callback execution deadline overruns | 0 | 0 | 0 |
| Driver overload/resync messages | 0 | 0 | 0 |
| MIDI NoteOn / NoteOff | 12/12 | 12/12 | 12/12 |
| Nonzero internally rendered PCM | 528144 | 1019251 | 528144 |
| Original strict ASIO gate | NO-GO | NO-GO | NO-GO |

`P182-COMPARISON.json` asserts
`THREE_REAL_ASIO_SESSIONS_VERIFIED_DIAGNOSTIC_ONLY`,
`REFERENCE_AND_AWE_GAPS_NON_EXCLUSIVE`, `errors=[]`,
and **still** `physical_asio_verified=false`,
`release_approved=false`. All three P181 QPC traces contain
1000/1000 recorded callback slots and exactly one gap on index 2,
without overflow, missing ASIO buffers or timestamp windows.

**Technical consequence:** The startup gap is independently
observed even when the AWE DSP is absent, with a lightweight
reference callback completing in under 0.1 ms. Do not attribute
this common anomaly exclusively to AWE DSP processing. A
shared device/driver/host/scheduler startup factor is consistent
with the observation, **but no particular root cause is proven**.
No real analog loopback, USB hardware data, DAW timing, Windows
ETW/DPC trace or vendor driver event log was supplied.

**Audit policy:** Keep the **existing full-run zero-gap**
pass/fail requirements intact, preserving NO-GO for all three
sessions. Do not silently ignore an initial callback, inflate
thresholds, fabricate physical ASIO PASS or repeat the same
local experiments without a distinct causal question. If
startup is assessed separately from steady state in a *future*
new test methodology, show two independent outcomes and
retain the original full-run gate as a separate unchanged metric.

The corresponding AWE project has the fuller result:
`docs/P184-REAL-ASIO-THREE-WAY-REFERENCE-RESULT.md`
at source commit
`3aaa2f736535dde3642ab7cea11d919059ff12bb`.
This document contains no owner's ROM/SF2 or audio files.
