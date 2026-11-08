# P186 precise ETW diagnosis and evidence-state correction

Task: [AWE issue #92](https://github.com/challanger2000/125A-AWE-Synthesizer/issues/92).
Dedicated branch `fix/p186-etw-diagnostics`, baseline
`1425a5d86aaf228f16e03de55df182f38d990c32`; unchanged native P185 source
`59762ae67a5878f4bade2e000672497acde4f763`. AWE integration baseline
`4d56729788bcf065fbae1c13f5b79b831601d492`. Binding Engineering revision
`bc26392ec7ea9f20f074bff84bbc47ab439d5fe0`, complete same-conversation Guardrails
reading retained at SHA256 `927085434a5b69008ec97b1933cc8c00e07a09cde150b2a2e862d17d83c70ec9`;
START/README/completeness contract, project START, P184/P185 and issues 91/92
reviewed before implementation. This is scoped reporting QA, not FULL AUDIT.

## Owner data / observation versus hypothesis

Issue #92 supplies the owner's old acceptance fields: INCONCLUSIVE,
ETW_NOT_AVAILABLE_OR_UNDECODABLE, default physical_asio=NOT_RUN, eight zero loss
counters, known P185 source/driver. Its code path had already found both raw
JSON files and a native child. That **does not prove no callbacks ran**.
The default NOT_RUN was a reporting defect, not an authoritative device fact.

The owner's actual capture.json/asio.json have not been attached to this chat,
issue or available workspace; searches found only clearly labelled synthetic
P185 fixtures. No owner callback count, PID, decode-error count or CSwitch count
has been inferred. Owner raw analysis: **NOT_PROVIDED / NOT VERIFIED**.
No fresh device test is requested or exposed by the new default BAT. No ETL,
ROM/SF2 or original media is requested. Windows 11 native schema investigation
and any native adaptation remain blocked until these actual counters are known;
`src/` and CMake stay unchanged, enforced by CI against the exact native baseline.

## Reproduced defect and correction

The original P185 analyzer combined marker enable, decoder errors and nonempty
context switches in one assertion. In the runner, later exceptions left the
initial NOT_RUN field intact. Existing positive kernel controls, direct analyzer
negative tests and BAT CheckOnly/cancel did not exercise that failed post-capture
reporting path. P186 executes the original exact source against an independently
specified bad-decode fixture and reproduces the misleading default. The corrected
entry and shared reporting state machine are then challenged with that input.

The original assertion is now three strict assertions: ETW_MARKER_ENABLE_FAILED,
ETW_DECODE_ERRORS and ETW_ZERO_CONTEXT_SWITCHES. Get-P186Assessment returns a
bounded path-free summary even when validation fails, and keeps all simultaneous
objective failure codes. It exports events/cswitches/decode_errors, native PID/exit,
all kernel/user start/stop/open/process/frequency/clock/loss counters and bounded
provider GUID/enable results. Missing/invalid values stay null, never invented
zeros. Arbitrary provider names and extra JSON strings are omitted. At most 32
provider records and 4/8 MiB input JSON are processed; no ETL is parsed by the BAT.

Evidence grades are independent of correlation:

| Grade | Required evidence | What it does not certify |
|---|---|---|
| NOT_RUN | No launched-child or observation claim in the supplied records | Not proof that the owner's historical run never happened when files are absent |
| REFERENCE_ATTEMPTED_UNVERIFIED | A child/observation claim exists; identity/completeness still unvalidated | No trusted callback count or audio PASS |
| REFERENCE_OBSERVED_BUT_ETW_INCONCLUSIVE | Pinned source/binary, matching nonce/PID/driver, actual callback rows/lifecycle/counters validated | No scheduler attribution or realtime approval |
| OBSERVED_REFERENCE_ONLY | All original P185 ETW/callback/correlation gates also pass | Still no AWE hardware/release approval |

Partial callbacks are reported by actual count, not as requested 1000/1000. A
partial/failed ASIO run stays NO_GO. A fully observed original strict-gate failure
still permits valid ETW correlation; it is not mistaken for an absent stream.
No timing threshold, QPC/identity/loss gate, startup exception or DSP behavior
is relaxed. awe_realtime remains NOT_RUN; cause INCONCLUSIVE; release=false.

## Scope / contract matrix

| Requirement | Reviewed implementation | Executable challenge | Current evidence |
|---|---|---|---|
| Split ETW failures | P185-ANALYZE.ps1 | decode only, zero switches only, both, marker/start/stop/open/process failures | Local PowerShell tests; Windows pending |
| Preserve attempt/reference grade | P185-DIAGNOSTICS.ps1 and P185-RUN.ps1 | original broken source, missing ASIO, no child, partial/failed child, nonce/PID/SHA mismatch | Local tests; Windows pending |
| No malformed stream as timing proof | unchanged original full correlation plus new assessment | clock/loss/CSV failures, incomplete slots, bad flags, contradictory counters | Local tests; Windows pending |
| Bounded private-free diagnostics | explicit numeric/GUID whitelist | private paths in unknown/provider/numeric data; 100 provider records | Local tests; Windows pending |
| Reuse saved files without hardware | P186-REANALYZE.ps1 / BAT / package producer | actual entry, original file hashes, cancel, tamper and missing inputs | Local PS entry passed; Windows BAT pending |
| Native/VST3 compatibility | unchanged native hosts, CMake and fixtures | full Windows build, CTest/Python, real reference lifecycle and broken fixture, native ETW controls | Pending new Windows execution |
| AWE integration / provenance | AWE package workflow and original P185 manifest | exact old source/binary profile; ZIP and artifact-service roundtrip | Pending |
| Owner's actual failure / Win11 schema | owner capture.json + asio.json | interpret actual numeric records before any adaptation | NOT_PROVIDED / NOT_RUN |

Self-challenge, not an independent human reviewer. All synthetic fixtures remain
hardware NOT_RUN. New source review scope is these scripts/tests/build integration;
AWE DSP/controller/GUI, proprietary DAW, physical partial-failure injection and
actual Windows 11 schema validation are excluded/NOT_RUN. Existing P184 evidence
and the original strict NO_GO remain intact.

## Runtime / packaging

The new user BAT is P186-EXISTING-RUN.bat. It reads a previously saved P185-LOCAL
or RAW-LOCAL-ONLY directory and emits P186-ACCEPTANCE.json in a new result folder.
It contains no root audio executable or hardware launcher, needs no admin or
Python, writes no original input, starts no driver and performs no recording or
upload. Existing local CSVs may be used for the unchanged original correlation;
with only the two JSONs, it can still establish the exact reported counter failure
and trustworthy reference progress. Profile hashes are pinned to the **original**
P185 package, not to newly rebuilt binaries or claims copied from untrusted input.

Final hardware cause remains INCONCLUSIVE and release NO-GO. Windows results,
source SHAs and artifact links will be filled only after actual execution.
