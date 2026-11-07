# P76 — Universal exported WAV / SMF MIDI file oracle

An arbitrary VST3 or DAW-driven workflow may export WAV and MIDI files.
P76 adds an independent reusable **file evidence adapter** to the
P65/P66 versioned product plan. No 125A plugin-specific code exists in
this adapter. Product-owning chats define the expected output evidence
and reference SHA-256 before execution.

An approved `export_artifact` case requires:

```json
{
  "id": "verify_exports",
  "kind": "export_artifact",
  "contract": {
    "schema": "125a-export-artifact-oracle-v1",
    "module_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "outputs": [
      {
        "id": "rendered_audio",
        "path": "C:/QA/exports/render.wav",
        "kind": "wav",
        "expected_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "format_expectations": {
          "channels": 2, "sample_rate": 48000,
          "sample_width_bytes": 3, "frames": 96000
        }
      },
      {
        "id": "rendered_midi",
        "path": "C:/QA/exports/render.mid",
        "kind": "midi",
        "expected_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "format_expectations": {
          "format": 1, "tracks": 2, "ppq": 960,
          "note_ons": [
            {"track": 1, "tick": 0, "channel": 9,
             "note": 36, "velocity": 100}
          ]
        }
      }
    ]
  }
}
```

The placeholder hashes and events above are **NOT actual product
reference data**. Replace them with independently specified correct
outputs and the exact VST3 DLL SHA-256, then include the case in the
existing P65 `plan.json` and link it in the P67 `features.json`.
Run via the existing P74 universal command or P65 test plan runner.

The WAV parser checks real PCM file channels, sample rate, bit-depth
(1–4 bytes per sample), frame count and the exact SHA-256 of every
output byte. The SMF parser independently validates the MIDI header,
format 0/1, number of tracks, ticks per quarter note, running status,
channel note-on events (track, absolute tick, channel, note and velocity),
legal event lengths and correctly terminated tracks. Exact output
byte hashes prevent changed events or audio samples from going
unnoticed even when global metadata happens to match.

Missing outputs, corruption, unexpected lengths or wrong musical
events become **FAIL**. The generic P65 runner fails closed on an
artifact mismatch and P67 reports the linked required features as
not verified; the output itself never sets `release_approved` true.

**Critical qualification:** P76 only verifies files that actually exist.
It does **not** activate a plugin's export button, construct arbitrary
OS Save dialogs, cause an unknown plugin to render files, or infer a
true oracle by copying the output under test. That activity requires
an explicitly approved preceding GUI/host test plan. If outputs are
pre-created or independently synthesized, passing P76 verifies the
file validator, **not a plugin's own export implementation**.

The P76 Windows CI builds a genuine VST3 module and runs the new
P65/P67 adapter with separate independent WAV/MIDI fixtures; it proves
both correct-asset PASS and deliberately corrupted PCM FAIL. The
CI report expressly records `actual_plugin_export_tested: false`.
Current generalized evidence cannot claim any proprietary VST3's
MIDI/WAV exporter passed without a real triggering workflow.
