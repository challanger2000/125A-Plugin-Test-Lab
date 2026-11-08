# P183 — Real VST3 processing lifecycle acceptance before ASIO

## Failure reconstructed from physical workstation evidence

The first owner-run P182 three-way comparison stopped in `REFERENCE-A`
before the ASIO device began audio callbacks. The verified native
error was:

```text
[P58 HARDWARE NO-GO] VST3 setProcessing failed
```

The local comparison report had `classification=INCOMPLETE`,
`trials=[]`, and `REFERENCE-A: ... no complete diagnostic/trace; native
exit=1`. The physical driver capability probe itself had successfully
selected Yamaha Steinberg USB ASIO at exactly 512 frames / 44100 Hz.
**This is not a repeat of the AWE startup gap**; the AWE DLL was not
tested in the comparator at all.

The source-built reference fixture `tests/asio_reference_midi_fixture.cpp`
previously inherited its `setProcessing` behavior instead of explicitly
satisfying the VST3 host's `kResultOk` contract. P183 implements an
explicit success return for this truly trivial generator. The existing
native host remains **fail-closed** for a missing/failed
`setProcessing(true)`; it is **not** changed to accept errors.

## Independent Windows-run lifecycle acceptance

The real `TestLabPhysicalASIO.exe` now provides an **offline**
diagnostic option:

```text
--vst3-reference-lifecycle-selftest --plugin <exact-compiled-VST3-DLL>
```

It uses the **same** Steinberg VST3 module factory and host interfaces
as the physical callback mode, but it never looks up or instantiates
an ASIO device. It rejects invalid DLLs and requires one real audio
class; runs initialize, setupProcessing(512/44100/float32),
setActive(true), **setProcessing(true)**, verifies silence without MIDI,
audible non-finite-free 220Hz PCM after NoteOn 48, silence after NoteOff
48, and checks successful setProcessing(false), setActive(false),
terminate.

An additional **deliberately broken VST3 DLL** built from the same
source returns `kResultFalse` from `setProcessing` and must fail
the exact real host lifecycle test, including the expected error
message. This adversarial A/B positive+negative proves that the new
test does not merely accept any installed VST3 or a static source
string.

The P100 native Windows CI runs both exact x64 DLLs and the
original absent-ASIO-driver negatives. The AWE P182 packaging CI
must also run this lifecycle acceptance on the **exact good reference
DLL packaged for the owner** and the broken negative fixture; a
green source compile alone is insufficient.

This is a **host-independent VST3 lifecycle check, NOT
a physical ASIO PASS**. The original AWE hardware output, Windows
scheduler attribution, independent FULL AUDIT and release remain open.
