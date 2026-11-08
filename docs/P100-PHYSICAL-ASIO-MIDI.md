# P100 — Native ASIO musical MIDI instrument callback extension

Additive optional input to the existing P58 IASIO hardware callback runner:

`--midi-note 48 --midi-out path/to/INSTRUMENT-PCM.json`.

This mode supplies actual VST3 `IEventList` NoteOn/NoteOff events to the
plug-in from the real driver callback. It uses a once-allocated SDK
`EventList(4)` and reuses its storage without heap allocation on callback.
A note-on is emitted at the start of approximately every second, a note-off
half a second later. The host observes actual nonzero PCM produced by the
VST3 processor **before** the output-safety clamp to 0.1 peak (-20 dBFS).

The native P56 evidence JSON schema remains unchanged, so existing hardware
adapters retain their exact expected fields. The additional opt-in proof
is a separately stored JSON with binary hashes, session nonce, real callback
note counts, nonzero PCM sample count, and observed peak. Missing notes,
silent PCM, nonfinite PCM, deadline misses or ASIO XRUNs fail closed.
An absent ASIO driver or plug-in must not produce any PASS evidence.

**No physical ASIO device is attached to GitHub Windows runners.** The P100
cloud workflow verifies C++23 build, sample conversion self-tests and
missing-device negatives, never hardware PASS. Real ASIO must be tested
on an explicitly approved device-equipped local Windows workstation.

The executable still needs a separately loaded instrument media state
(e.g. via the AWE plug-in's `AWE32_ROM_PATH` and `AWE32_SF2_PATH`
environment variables, set only for its local child process). It does not
open or automate a commercial DAW; **DAW/ASIO integration and full
release acceptance remain distinct and unverified**.

Licensing: the Steinberg ASIO SDK headers are sourced from exact pinned
`audiosdk/asio@496a0765b8bb9c26f764f22f9a9712a937177db2`
under the upstream license, and must not be mirrored or redistributed
without satisfying its applicable terms. The P100 host source is public.
