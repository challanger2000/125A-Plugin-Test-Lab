# P100 — SF2/FluidSynth compatibility reference (optional, read-only)

Development issue: [#147](https://github.com/challanger2000/125A-Plugin-Test-Lab/issues/147).

The reusable runner is [`../tests/run_sf2_reference.py`](../tests/run_sf2_reference.py). It **does not emulate AWE32 or prove EMU8000 hardware fidelity**. It uses FluidSynth as one additional SoundFont-compatibility comparator; real AWE64 hardware recordings remain the primary reference. This component changes **no AWE product DSP/GUI, saved state or parameter IDs**.

## Inventory (no binary, installer or DAW required)

```powershell
python tests/run_sf2_reference.py --mode inventory --sf2 "C:\QA\Synth 512 Bank.sf2"
```

The script parses genuine RIFF `sfbk` > `LIST pdta` > `phdr` preset records with the terminal EOP record excluded. It preserves the actual bank/program addresses, **does not synthesize absent 0–127 entries**, and rejects invalid chunks, corrupted sizes, missing EOP or duplicate bank/program keys. It does not assert the whole SoundFont is loadable merely from inspecting `phdr`.

Validated against the owner's original 555,754-byte `Synth 512 Bank.sf2` locally: **77 records, all bank 0, missing program 63, program 7 `TX81Z Lately Bass`**. This proves the inventory parser works for these data; it is not evidence that FluidSynth or the product VST3 rendered those 77 sounds.

## Dry reference renders

Install a trusted **FluidSynth CLI version 2.4.5 or newer** separately on the approved Windows machine. The script verifies executable version via `-V`, pins the binary and input SF2 by SHA-256, and supplies a new empty destination.

```powershell
python tests/run_sf2_reference.py --mode render --sf2 "C:\QA\Synth 512 Bank.sf2" --fluidsynth "C:\Tools\FluidSynth\bin\fluidsynth.exe" --out "C:\QA\P100-Fluid"
```

For each **real melodic bank-0** preset, create a separate genuine SMF format-0 MIDI fixture (C4/60 at velocity 100, CC7 100, CC10 64, 120 BPM, note-on 0.25 s, note-off 1.25 s, end at 2.25 s). Use `fluidsynth -i -n -C 0 -R 0 -r 44100 -g 0.2 -T wav -O s16 -F output.wav bank.sf2 input.mid`. Both effects must be explicitly off; no inference from a GUI control value. The renderer is bounded by a per-case timeout and rejects bad WAV format, near-silent cases, clipped PCM, output before MIDI onset and nonzero subprocess exit. Every source/SMF/WAV hash and PCM metric is recorded in `SF2-REFERENCE-RESULT.json`.

Version 1 intentionally **does not guess MIDI bank selection behaviour for nonzero SF2 banks**; these entries are `NOT_RUN`. Presets not sounding at the default note are `NOT_SOUNDED`, not falsely marked PASS. Further notes and velocity ranges require separate runs using `--note` and `--velocity`; use an empty new output directory for every run.

### Optional comparison with independently captured real AWE WAVs

```powershell
python tests/run_sf2_reference.py --mode render --sf2 "C:\QA\Synth 512 Bank.sf2" --fluidsynth "C:\Tools\FluidSynth\bin\fluidsynth.exe" --out "C:\QA\P100-Comparison" --awe-dir "C:\QA\AWE-Actual-VST3-WAV"
```

The AWE directory must contain **actual** audio rendered by a separately source-identified AWE VST3 host using exactly the **same** MIDI program, sample rate, note timing, velocity, gain/pan and dry-effect contract. Each optional WAV must be named `b000-p007-n060-v100.wav` (substitute program/note/velocity) and be stereo PCM16/24 at 44.1 kHz. No `--awe-dir` means `awe_comparison=NOT_RUN`. Missing files stay `NOT_RUN` case by case; never assume they were rendered.

The output includes early/sustain/release level differences as **observations**, not automatic corrections or a fidelity score. The test cannot determine algorithmic identity (FluidSynth is not EMU8000), reconstruct missing AWE source provenance, or prove that effective filter and FX register settings matched real hardware. P90 remains separate, with its own purpose-specific external-capture contract; this runner does not reclassify P90 evidence.

## Evidence and QA scope

Run synthetic regressions without proprietary files or external binaries:

```powershell
python -m unittest discover -s tests -p "test_sf2_reference.py" -v
```

They check precise preset count and holes, bad RIFF/EOP and duplicate program rejection, SMF timing and bytes, version/chorus/reverb CLI contract, malformed/silent/early PCM detection and mandatory `OBSERVATION_ONLY` classification. Synthetic tests passing **do not** indicate any real FluidSynth audio or current AWE VST3 audio was rendered. No licensed SF2, ROM or reference WAV is committed to this public repository.

The hardware baseline must also verify actual AWE filter/FX sends: 125A P190 0% effect controls are dry by product design, while older Creative hardware reference captures may retain original wet sends. Never compare DRY software to WET hardware and call it a filter mismatch. Hardware reference is `NOT_COVERED`, native AWE VST3 rendering is `NOT_RUN` unless real files and provenance exist, and `release_approved=false` throughout P100.