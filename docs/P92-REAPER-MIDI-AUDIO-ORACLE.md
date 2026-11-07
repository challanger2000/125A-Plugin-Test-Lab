# P92 — Actual audible MIDI-generated REAPER render and no-note negative control

P91 verified that real REAPER 7.83 can host a VST3, create MIDI, save/reopen a project, and render a valid but intentionally silent WAV. P92 adds an entirely independent, source-built **audible** VST3 MIDI instrument for a genuine positive/negative acceptance pair, on an isolated Windows GitHub Actions runner.

The P92 instrument (internal **125A QA REAPER MIDI Audible**) generates a stereo 220 Hz sine tone at up to 0.2 peak **only while MIDI note 36 is held**, with no audio input, and remains digitally silent when not triggered. We do not need or use proprietary samples or product-plugin code.

The Windows test creates two separate real REAPER projects using the same independently hashed plugin binary and same REAPER version:
- **MIDI-positive:** note 36, velocity 102. The REAPER CLI WAV must contain real audible PCM (RMS at least 0.01 and peak at least 0.05), project MIDI must survive save/reload, output format 44.1 kHz stereo.
- **No-MIDI negative control:** zero MIDI notes inserted into another independently saved/reloaded REAPER project, same VST3 and render settings. Its WAV must have RMS no greater than 0.0001 and peak no greater than 0.001.

Both results must have the same plugin/executable SHA256 but different WAV SHA256. Any silence on the positive path, audible output on the negative path, missing FX, wrong MIDI after project reload, or file mismatch is a hard failure.

Each run generates `REAPER-DAW-ACCEPTANCE.json` and the associated real `.RPP` project. The positive/no-note WAV source files are **not** presented as simulated: they are rendered by the actual REAPER executable on the Windows runner.

The generic P91 runner remains backwards-compatible; only optional explicit plan keys `insert_note` and `expect_silence` have been added, and validated. Product owners may use a no-note baseline to identify self-triggering instruments or effects, but this artificial test fixture is only an infrastructure proving ground, **not** a claim that all future VST3 products make identical audio.

**Still outside scope:** physical ASIO input/output hardware, studio monitor routing, real-time low-latency recording, unknown plugin functional semantics or general commercial release approval.

Run: [P92 Windows workflow](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/workflows/p92-reaper-real-midi-audio.yml) (only claim acceptance for an actual green run). See [P91](P91-REAPER-DAW-INTEGRATION.md) for setup and original DAW workflow.
