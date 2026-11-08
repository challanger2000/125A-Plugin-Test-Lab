# P185 independent ETW / ASIO investigation (checked Windows tooling)

Task: [AWE issue #91](https://github.com/challanger2000/125A-AWE-Synthesizer/issues/91).
Engineering rules fully read at `bc26392ec7ea9f20f074bff84bbc47ab439d5fe0`, including
START, all 2680 guardrail lines and AUDIT-COMPLETENESS-CONTRACT. This is scoped
instrumentation QA, **not FULL AUDIT or release certification**.

## Exact baseline and constraints

Test Lab starts at `b2f06baf9a0734132228abc67f1da7576357f694` on the current
`qa/p100-asio-instrument-midi` lineage, including P183/P184. AWE integration starts
at P184 `3aaa2f736535dde3642ab7cea11d919059ff12bb`. Separate P185 branches;
no merge. SDKs: ASIO `496a0765b8bb9c26f764f22f9a9712a937177db2`, VST3
`3cdf9ca5d1f5b1b21e0a86832aa4abe55607bd96`. All implementation is in the universal
Test Lab. No AWE DSP, PCM generator, GUI, filter, ROM/SF2 or existing gates changed.
The reference fixture is unchanged, needs no private media, and emits amplitude
0.05 sine only under the existing real VST3 MIDI Note 48 pattern.

P184 is completed evidence, not rerun: reference/AWE/reference at 44.1k/512,
1000 callbacks each, startup gaps at index 2 of 58.4385/63.1304/56.3673 ms,
maximum callback execution 0.0916/5.9249/0.0967 ms. No execution overruns or ASIO
XRUN messages. This disproves an exclusive AWE DSP explanation, but establishes
no Windows/USB/driver root cause. The existing **entire-run NO-GO stays intact**.

## Source examination

`Engine::callback()` stores the previous **start** in the misleading historical
`lastEndNs` variable. It compares start-to-start spacing against two buffer periods;
it does not compare previous end to next start. P185 preserves that implementation,
exports both quantities, includes callback zero/startup, and reproduces its integer
nanosecond rounding in the independent gate reconciliation. Callback execution is
wall time including the real VST3 host, conversion and possible preemption, **not
isolated Processor::process() DSP CPU time**. Scheduled time after subtracting
context-switch intervals still includes interrupt/DPC work; it is an upper bound.

`createBuffers`, VST3 activation/processing, callback arming, IASIO start before/after
and stop before/after now have additive control-thread QPC observations. A driver
may invoke callbacks before `IASIO::start()` returns. Earlier callbacks while
`activeEngine` is null are not processed or recorded by the existing adapter; this
boundary remains explicitly unobserved, not declared clean. The callback body is
unchanged: the observer reuses the existing bounded P181 preallocated slots, adds
no heap operation, file I/O, ETW publication, lock or new atomic there. P185 JSON,
hashing and two ETW calibration markers run on the control thread.

## Collection and time correlation

Native StartTrace/ControlTrace creates two uniquely named nonce-owned sessions.
Windows 8+ `EVENT_TRACE_SYSTEM_LOGGER_MODE` uses its own generated session GUID,
not the global NT Kernel Logger GUID/name. Kernel flags request process/thread,
CSwitch, dispatcher ReadyThread, DPC, interrupt and image events. A second session
enables the P185 marker provider and actually enumerated Microsoft USB/Audio
manifest providers. Every attempted provider and enable result is recorded.
Provider availability does not imply device activity. No provider-name or temporal
coincidence is promoted to causation. Full payloads remain in local ETL for WPA.

Both sessions request QPC (`ClientContext=1`), bounded 256 MiB sequential ETLs,
64–128 preallocated 256 KiB ETW buffers and no live JSON analysis. The controller
starts the actual reference ASIO host suspended **after** ETW starts, then resumes
it and bounds runtime to 60 seconds. It stops only sessions it successfully created,
then decodes ETL using OpenTrace/ProcessTrace RAW_TIMESTAMP and documented TDH
fields. Thread start/end ownership binds callback PID/TID and rejects thread reuse.
Missing schemas increment an explicit decode error, never invent private offsets.

The host's control-thread marker EventWrite is bracketed by QPC reads. The decoder
requires exactly two actual provider events with matching nonce, sequence, PID,
TID, and timestamps within both QPC brackets. PerfFreq and clock type must match
both ETL headers and the callback clock. Maximum bracket width is 10 ms; otherwise
correlation is INCONCLUSIVE. Both startup and end markers must bound all callbacks.
Kernel thread-end coverage must also extend beyond the last marker, independently
of the user-provider trace. A deliberately truncated kernel tail is rejected.
There is no empirical offset fitted to make a trace appear aligned.

ETW APIs are built into Windows; ADK/WPR is not required by this implementation.
Access denied, missing API/provider support or exhausted system logger slots gives
ETW_NOT_AVAILABLE; no physical stream is started if trace setup fails. Any ETW
loss in session counters or file headers, decode failure, missing marker, wrong
identity, incomplete callback slots or unmatched strict counters invalidates the
analysis. Optional USB/audio providers remain explicitly listed as absent/disabled
where unavailable; scheduler correlation cannot certify USB coverage.

## Workflow, privacy and result meaning

Unpack ZIP; close DAW, reduce interface volume; run P185-ETW-ASIO.bat as admin.
Driver selection and typed START consent precede any driver initialization/capture.
One physical reference-only stream uses 44.1k/512/1000; no A/B/A repetition, ROM or
SF2 prompt. Driver capabilities/identity/granularity are checked; configuration
is never silently changed. `-CheckOnly` verifies hashes and enumerates capabilities
without creating an ASIO device, trace or tone. `-Cancel` exercises the abort path.
No installers, manual Python or driver changes; user runtime is Windows PowerShell
5.1 plus native tools. No unattended local audio or auto-upload.

P185-ACCEPTANCE.json is a whitelist of source identities, nonce, summary statistics,
strict-gate outcome and conservative status; no paths, media or ETW payloads.
Detailed callback wall/upper-bound/off-CPU intervals, start spacing, end-to-start,
ready/wait/unknown intervals and nearby-event counts are separate local aggregate
JSON. All callback QPC rows, raw metadata/CSV and ETL stay RAW-LOCAL-ONLY. Even a
clean reference run cannot prove AWE realtime; cause stays INCONCLUSIVE without
stronger device-specific evidence. Captured ready/wait intervals are explanatory
observations, not proof of scheduler/USB responsibility for an unobserved gap.

## Requirements-to-test inventory

| Requirement | Executable evidence | Limit |
|---|---|---|
| Windows native host / all Lab targets | MSVC x64 Release build, entire CTest and Python discovery | CI hardware ASIO NOT_RUN |
| Actual ETW collection and TDH fields | native sleep/busy child, real CSwitch waiting interval, ETL headers | Synthetic workload, not audio driver |
| Common QPC / identities | actual two provider events within QPC brackets, PID/TID and file frequency | Physical host markers NOT_RUN until local BAT |
| Permission failure | actual restricted token with admin SID disabled and privileges removed | Never substitutes for target capture |
| Missing physical driver | real reference VST3 with unregistered driver must produce no ASIO/observer proof | No simulator |
| Lifecycle / PCM / MIDI | existing real reference positive, independently broken setProcessing negative; existing ASIO selftests | AWE DSP unchanged; integration regressions separate |
| False claims / corrupted evidence | independent arithmetic fixtures and destructive nonce/SHA/PID/TID/QPC/loss/provider/rights mutations | Fixtures always hardware NOT_RUN |
| Scheduler vs wait vs USB proximity | independent 49.9ms ready / waiting / ready-transition oracles, fake USB event | No root-cause claim from coincidence |
| Package actually runnable | ZIP unpack in path with spaces, real cmd/BAT CheckOnly, cancel exit 2, tamper exit 3 | No audio CI opt-in |
| AWE / prior physical results unchanged | integration hashes and preserved P178 original module | P185 target machine NOT_RUN |

Self-challenge review, not an independent human or second-agent audit. Native
runtime permissions/ETW success and actual package tests must complete before a
Windows package is described as checked. **Executed:** final code `59762ae67a5878f4bade2e000672497acde4f763`,
[Windows Actions 42531360274](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42531360274),
all native targets compiled, both CTests passed; 67 existing Python scripts plus
one actual native HWND/BMP regression passed. The real reference lifecycle and
its broken setProcessing control, existing ASIO conversion/buffer/trace selftests,
unregistered-driver rejection, actual two-session ETW capture, QPC brackets,
CSwitch sleep interval, post-marker kernel thread end, restricted-token denial
stale-directory refusal, and an executed unknown-opcode negative preventing false DPC/ISR labels passed. All **36** positive/adversarial cases passed
under Windows PowerShell 5.1; their fixture results remain hardware NOT_RUN.
The real unpacked package BAT passed from a path with spaces; cancellation
returned 2, altered source failed integrity with 3. No local ASIO device or
physical hardware was exercised by those controls.

Also executed locally: 67 standalone Python scripts, PowerShell parser checks
for all 24 workflow script blocks after GitHub expression substitution, all 36 arithmetic/adversarial cases under a
checksum-verified portable Microsoft PowerShell 7.4.6. These supplement the
actual Windows PowerShell 5.1 evidence, not replace it.

The existing ASIO callback body is byte-for-byte unchanged from Test Lab baseline
`b2f06baf9a0734132228abc67f1da7576357f694`; extracted-body SHA256
`a31e4c7ee22f9943c58e99db2bb0ca7f6a662cafa8a5d6545539450d4f6906fa`.
AWE `src/` and CMake are unchanged from P184. The exact bundled ASIO SDK source
archive and tracked Test Lab source contain no ROM, SF2 or installer executables.

Corrected test/instrumentation issues: standalone argparse tests cannot be run
through indiscriminate unittest discovery; expected native negative exits must
be cleared after verifying them; binary/source/nonce/PID/TID/clock identity and
kernel end coverage are required before reconciliation. These are tooling fixes;
unknown kernel opcodes remain unclassified rather than being labelled DPC/ISR. No AWE audio-engine defect or device-specific root cause is claimed.

Draft PR creation was actually attempted. GitHub returned
`GitHub Actions is not permitted to create or approve pull requests`.
The local GitHub API route is also unavailable (`Forbidden`); no repository
permission was changed. The branch and concrete review body remain available.
No PR has been represented as created or merged.

## Primary API references

Microsoft Win32 ETW: Configuring and Starting a SystemTraceProvider Session;
Configuring and Starting an Event Tracing Session; Consuming Events; CSwitch;
Thread_V2_TypeGroup1; DPC; ISR; TRACE_LOGFILE_HEADER (ReservedFlags clock,
PerfFreq, EventsLost/BuffersLost). Read from MicrosoftDocs/win32 and
MicrosoftDocs/sdk-api sources. Existing ASIO API reviewed against the pinned SDK,
not an invented replacement. Exact documentation URLs are reproducible from
https://github.com/MicrosoftDocs/win32/tree/docs/desktop-src/ETW and
https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/evntrace/ns-evntrace-trace_logfile_header.md.

## Remaining limits / decision

Physical P185 at the Yamaha Steinberg interface: **NOT_RUN**. Device-specific
scheduler/DPC/ISR/USB/ASIO attribution: **INCONCLUSIVE**. AWE target-machine
realtime: **NOT_RUN**, existing P184 strict full-run **NO-GO** unchanged.
A second independent human review, proprietary DAW and analog output remain
**NOT_RUN**. FULL AUDIT and release approval have not been granted.

ETW and added control-thread observations can perturb a cold start. Absence of a
gap in one observed reference run is no fix proof. Optional provider availability
and driver schemas vary by machine; proximity or a waiting state is insufficient
for root-cause attribution. Raw ETLs may contain system/private path information
and stay local. Force-killing the recorder can leave an owned ETW session until
logoff/reboot; normal completion/handled Ctrl+C stops owned sessions, and an owned
job object prevents the child audio stream surviving the controller.

The original callback QPC start follows entry atomics; its end precedes trace
bookkeeping and final deadline counters. Those small adapter intervals are not
isolated by this unchanged probe. No hardware interrupt-arrival time is claimed.
Default optional provider policy enables enumerated Microsoft USB/Audio providers;
proprietary/vendor-specific provider interpretation remains **NOT_RUN**. Real
DPC routine/image attribution requires additional evidence; event proximity in
P185-ACCEPTANCE.json never establishes it.

Final AWE integration: source `22d08278a20d9989e71393944bfbc31d640bf231`,
[Windows package run 42531433260](https://github.com/challanger2000/125A-AWE-Synthesizer/actions/runs/42531433260).
The actual uploaded user artifact was downloaded again and its own BAT passed
all package hash checks. The final report records all 36 adverse cases correctly
under PowerShell 5.1. AWE full regression at `37e6294672b13ae7064fb8f4f79633aec8cfffb3`:
66 CTests, 537 module validator tests, 3 EditorHost smokes and 99 GUI checks.
