# P100 — Native multibus VST3 state stress

The original P25 state-stress host rejected any VST3 with more than ONE
audio output bus. The Akai P013 independently advertises exactly
**9 audio outputs (MAIN stereo + 8 mono)**, but P014 could only inventory it.
Every P32 profile exited with native code 3 and no process callback
(`P25 host: this stress scenario requires exactly one output bus`).

P100 supplies real preallocated buffers for every declared output (1–16,
mono/stereo, max 32 total channels); activates all declared output buses,
passes the original advertised topology to every `IAudioProcessor::process`,
checks all output PCM for nonfinite samples, and records output bus count.
It retains the original 0/1 stereo-input topology contract and refuses
unknown unsupported topologies. No output buffers are allocated on the
audio callback.

Independent Windows VST3 fixtures:
- Good nine-bus, 500 actual active-playback state saves, zero process errors.
- Defective nine-bus, MAIN L/R still valid but the seventh mono bus emits
  nonfinite PCM: the native host must FAIL and timing is NOT COVERED.
- Original stereo fixture must still PASS unchanged.

The fixture and actual P013 module are distinct: **a positive fixture is
not evidence that the Akai firmware boots, imports WAV or produces audio**.
Follow up by pinning the tested P100 Test Lab revision in the Akai P014
workflow and repeating against the exact original P013 ROM-free artifact.
Only native read-only/technical host claims are possible without private ROM.
