# P100 SF2 preset matrix — extension of the existing 125A Test Lab

**Status: matrix tooling and synthetic mutation tests, not a real 77-preset PASS.**
The proven P100 C4/D4/Reset golden remains unchanged. This extension is
additive; it must never weaken the original P100 source/clock/hash contract.

## Coverage

`tests/p100_preset_matrix.py plan --sf2 PRIVATE/Synth-512-Bank.sf2 --out PRIVATE/P100-MATRIX-PLAN.json`

The parser reads the actual SoundFont RIFF `pdta/phdr` records (without
assuming bank/programs are consecutive) and, by default, **requires exactly
77 real presets**. It plans for each preset:

- Keys **48, 60, 72** (C3, C4, C5), velocity **1, 64, 127**: 9 single-note cases.
- One **three-note chord** (60+64+67), with individual velocities and note-offs.
- One **overlapping retrigger** of key 60 at velocities 64 and 127.
- Each case includes explicit note-off and MIDI reset events and 44.1 kHz
  sample-frame positions. No timing or gain auto-alignment is allowed.

**Total for 77 presets: 693 singles + 77 chords + 77 retriggers = 847 cases.**
The tooling also supports other SF2 banks with the explicit `--expected-presets`
argument. A multi-bank campaign is a collection of separate, individually
hash-pinned per-SF2 plans; never silently combine or renumber preset banks.

## Essential difference between PLAN and real PARITY

`plan` only creates a **deterministic workload**, not reference audio. A real
PASS requires the owner-private calibrated Win95 Creative environment to run
*each* case through the original driver, plus an independently executed
Windows VST3 host with the exact same MIDI/program/velocity sequence. The
current exported P002 evidence host hardcodes C4/D4 at velocity 100 and
**must be extended before it can supply these cases**. Do not pretend the
present C4/D4 result validates the remaining presets or velocities.

For a genuine capture campaign, the private owner evidence bundle must include:

- `P100-MATRIX-EVIDENCE.json`, with SHA256 identities for every input;
- SHA-pinned original Win95 session manifest, complete driver guest log,
  full original register trace (including READ records), and unmodified
  original PCM16 WAV. That source session must authenticate every case ID
  and the exact matrix plan SHA, not just the earlier C4/D4 sequence;
- actual exported native VST3 DLL and native Windows host binaries;
- per-case native OUT and PCM16 WAV, plus native host-clock manifest binding
  the exact preset, events and actual binaries to their output hashes;
- declared original/native sample origins and a bounded comparison window
  for every case, with independent audio and register outputs.

The offline verifier reuses `run_p100_original_vst3_parity.compare_pcm` and
accepts only **44.1 kHz stereo signed PCM16** audio. It rejects missing cases,
ambiguous/duplicate IDs, wrong SoundFont/session/plan SHA, wrong MIDI events,
missing native run identity, non-monotonic physical OUT timestamps, mismatched
register values, timing differences, PCM sample differences, and all-silent
source or native captures. It reports the first differing register and PCM
sample; even one mismatch makes the entire campaign fail. Missing evidence
returns a nonzero exit code. It never manufactures or normalizes goldens.

Offline verification, only once the full private campaign exists:

`python tests/p100_preset_matrix.py audit --plan PRIVATE/P100-MATRIX-PLAN.json --bundle PRIVATE/P100-MATRIX-CAPTURES`

**The audit does NOT generate Windows 95 or native VST3 captures.**
No actual 847-case owner-private Win95 recording or matching exported-VST3
renders have been produced as part of this change. Until they exist, the
correct result is **NOT RUN / NO-GO**, not PASS. Existing Windows public CI
runs synthetic positive/mutant checks for the matrix tooling only.

## Implementation milestones still required for real coverage

1. Extend the genuine Win95 Creative guest generator/attestor to execute the
   exact frozen matrix while capturing a full 44.1 kHz pre-card source WAV,
   original register trace, and WinMM guest log, with case-ID timestamps.
2. Extend the **real exported Windows VST3** evidence host beyond its current
   four fixed C4/D4 events to drive bank/program changes, arbitrary notes,
   velocity and polyphony, and to sign off each actual sample-clocked run.
3. Run the same matrix with real source/native binaries, review every
   nonzero difference, fix only verified root causes (original EMU8000
   synthesizer code remains unchanged), and repeat within P100.
4. Repeat the authenticated campaign for additional independently provided
   SF2 files; the number of presets is read from each bank's *actual* phdr.

The release gate remains `release_approved=false` even after this one bank's
coverage, pending the remaining product, GUI, real DAW and ASIO requirements.
