#!/usr/bin/env python3
"""P11 real GUI Save-As end-to-end oracle.

The native VST3 GUI generates FOUR disk files via the real Windows Shell
FileSaveDialog. Independent Python parsers verify the Standard MIDI File
and PCM24 WAV files, including musical agreement, song REST and duration.
No Drumator code is imported.
"""
from __future__ import annotations

import pathlib
import sys
import wave
from verify_midi_export import parse

RATE = 48000
BPM = 120
THRESHOLD = 250000


def assert_good(ok, why):
    if not ok:
        raise ValueError(why)


def wav_info(path: pathlib.Path, length: int, target_onsets: list[int]):
    with wave.open(str(path), "rb") as r:
        assert_good(r.getnchannels() == 2, f"{path.name}: not stereo")
        assert_good(r.getsampwidth() == 3, f"{path.name}: not PCM24")
        assert_good(r.getframerate() == RATE, f"{path.name}: not 48 kHz")
        assert_good(r.getnframes() == length,
                    f"{path.name}: duration {r.getnframes()} != {length}")
        data = r.readframes(length)
        assert_good(not r.readframes(1), f"{path.name}: extra samples")
    assert_good(len(data) == 6 * length,
                f"{path.name}: truncated stereo PCM24")
    onsets = []
    was_on = False
    peak = 0
    for i in range(length):
        p = i * 6
        l = int.from_bytes(data[p:p+3], "little", signed=True)
        r = int.from_bytes(data[p+3:p+6], "little", signed=True)
        a = max(abs(l), abs(r))
        peak = max(peak, a)
        on = a >= THRESHOLD
        if on and not was_on:
            onsets.append(i)
        was_on = on
    assert_good(peak > 700000, f"{path.name}: exported silent audio")
    assert_good(len(onsets) == len(target_onsets),
                f"{path.name}: unexpected audio attacks {onsets}")
    assert_good(all(abs(x-y) <= 96 for x,y in zip(onsets,target_onsets)),
                f"{path.name}: actual attacks {onsets} != {target_onsets}")
    print(f"[PASS] P11 GUI WAV {path.name}: exact PCM24 duration, "
          f"attacks={onsets}, peak={peak}")


def run(path: pathlib.Path):
    expected = {
        "pattern-midi.mid", "pattern-wav.wav",
        "song-midi.mid", "song-wav.wav",
    }
    names = {f.name for f in path.iterdir() if f.is_file()}
    assert_good(names == expected,
                f"GUI export created wrong files: {names ^ expected}")
    for kind in ("pattern", "song"):
        midi_path = path / f"{kind}-midi.mid"
        wav_path = path / f"{kind}-wav.wav"
        midi = parse(midi_path.read_bytes())
        assert_good(midi.division == 960, "unexpected MIDI PPQ")
        assert_good(midi.tempo == [(0, 500000)], "wrong MIDI tempo metadata")
        assert_good(midi.timesig == [(0,bytes([4,2,24,8]))], "wrong MIDI 4/4")
        on = sorted(midi.on)
        target_ticks = [480] if kind == "pattern" else [480, 8160]
        assert_good(on == [(x,9,36,127) for x in target_ticks],
                    f"{kind} wrong GUI MIDI notes: {on}")
        assert_good(sorted(midi.off) == [(x+60,9,36) for x in target_ticks],
                    f"{kind} wrong GUI MIDI note-offs: {midi.off}")
        expected_eot = 3840 if kind == "pattern" else 11520
        assert_good(all(t == expected_eot for t in midi.eot),
                    f"{kind} wrong MIDI EOT: {midi.eot}")
        # V1.5 release contract: one SMF Type-1 file with a conductor
        # plus exactly 16 independent instrument tracks. Passing Format 0
        # or a collapsed single-track file would be a user-visible regression.
        assert_good(midi.format == 1 and midi.tracks == 17,
                    f"V1.5 MIDI contract violated: SMF format={midi.format}, "
                    f"tracks={midi.tracks}; expected Format 1 / 17 tracks")
        print(f"[PASS] P11 actual GUI MIDI {midi_path.name}: "
              f"ticks={target_ticks}, tracks={midi.tracks}")
        expected_audio = [x*25 for x in target_ticks]
        frames = 96000 if kind == "pattern" else 288000
        wav_info(wav_path, frames, expected_audio)
    print("[PASS] P11: four genuine GUI Save As exports verified independently; "
          "MIDI/WAV identical musical timing, Song REST and format correct")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: verify_gui_save_as.py <gui-output-dir>")
    try:
        run(pathlib.Path(sys.argv[1]))
    except (ValueError, OSError, wave.Error) as e:
        print(f"[FAIL] P11 independent GUI export oracle: {e}", file=sys.stderr)
        sys.exit(1)
