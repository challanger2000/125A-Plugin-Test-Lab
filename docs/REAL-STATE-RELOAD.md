# Fresh-process VST3 project-state recall

The test lab can now replay an actual `IComponent::getState()` snapshot into two newly started native host processes. Each process loads the state through `IComponent::setState()`, renders four bars at 44.1 kHz / 120 BPM, then saves state again. A third-party product binary is SHA-256-pinned before any load. Every run clears prior WAV/state artifacts.

Usage:

```powershell
python tests/run_state_reload.py --manifest C:\QA\recall.json --out C:\QA\recall-results
```

Manifest fields: `schema: "125a-state-reload-v1"`, `product.binary`, `product.sha256`, `host`, `initial_state`, and optionally `deterministic_audio: true` or `expected_audio_sha256` (independent trusted WAV digest).

When an independent reference specifies the expected exact serialization,
add `expected_saved_state_sha256` (a lowercase 64-character SHA-256 string)
to the manifest. The checker then hashes both newly saved processor states
after actual `setState` / render / `getState`, and **fails** if either
differs from that externally approved state. This catches silent state
corruption that API success codes alone cannot detect. Use this option only
for plugins with known stable, byte-exact state serialization; do not assume
every valid plugin will reproduce its state bytes after additional rendering.
Without the independent reference, `saved_state_integrity` is `NOT COVERED`,
not PASS. The negative fixture deliberately returns success while saving
wrong bytes, and must be rejected by the independent hash oracle.

The report `RECALL-RESULT.json` separately identifies fresh-host state reload, audio determinism across two runs, and independently checked musical audio correctness. If a known-deterministic product renders unequal WAV files after the same saved-state restore, it is FAIL. An independent trusted reference digest is necessary before musical correctness can be PASS. Without one it is NOT COVERED. Randomized plugins need not declare deterministic audio, and will not be incorrectly certified for it.

The native host's existing `--render-state-save` command processes the supplied state without automatically injecting MIDI notes. It is therefore suitable for processors, internally sequenced instruments and state-validation smoke tests, but cannot certify an arbitrary MIDI-driven instrument's audible presets. Real DAW session recall, GUI state and MIDI export remain separate user-facing coverage requirements.

Windows CI validates an actual state VST3 via two fresh host processes and deliberately bad binary references, missing output, stale output and wrong independent PCM digest. No production-plugin repository is changed.


Native project-state payloads must be nonempty and smaller than 128 MiB.
This cap supports larger instrument/bank states while preventing unbounded
state-file reads. The native host and fresh-process wrapper enforce the
same limit; unsupported larger payloads must not be certified as PASS.
