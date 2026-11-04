#!/usr/bin/env python3
"""Independent Standard MIDI File verifier for P06 product-core exports.

No Drumator headers or encoder implementation are imported. The parser
validates chunk lengths, VLQ boundaries, end-of-track, event channels/pitches,
tempo metadata, note timing, and notes offs against a fixed musical spec.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import struct
import sys
from dataclasses import dataclass


class MidiRejected(ValueError):
    pass


def check(value: bool, message: str) -> None:
    if not value:
        raise MidiRejected(message)


def be16(data: bytes, pos: int) -> int:
    check(pos + 2 <= len(data), "truncated BE16")
    return struct.unpack_from(">H", data, pos)[0]


def be32(data: bytes, pos: int) -> int:
    check(pos + 4 <= len(data), "truncated BE32")
    return struct.unpack_from(">I", data, pos)[0]


def vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        check(pos < len(data), "truncated MIDI VLQ")
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7f)
        if not (byte & 0x80):
            return value, pos
    raise MidiRejected("unbounded VLQ")


@dataclass
class Parsed:
    division: int
    format: int
    tracks: int
    tempo: list[tuple[int, int]]
    timesig: list[tuple[int, bytes]]
    on: list[tuple[int, int, int, int]]
    off: list[tuple[int, int, int]]
    eot: list[int]


def parse(data: bytes) -> Parsed:
    check(len(data) >= 14, "SMF too short")
    check(data[:4] == b"MThd", "missing MThd")
    header_length = be32(data, 4)
    check(header_length == 6, "unexpected SMF header size")
    form, tracks, division = struct.unpack_from(">HHH", data, 8)
    check(form in (0, 1), "unsupported MIDI file format")
    check(tracks > 0 and tracks <= 256, "impossible MIDI track count")
    check(division == 960, "incorrect 960 PPQ timeline")
    if form == 0:
        check(tracks == 1, "format zero requires one track")
    result = Parsed(division, form, tracks, [], [], [], [], [])
    pos = 14
    for track_id in range(tracks):
        check(pos + 8 <= len(data), "truncated track header")
        check(data[pos:pos + 4] == b"MTrk", f"track {track_id}: missing MTrk")
        length = be32(data, pos + 4)
        pos += 8
        check(length <= len(data) - pos, f"track {track_id}: length exceeds file")
        track = data[pos:pos + length]
        pos += length
        at = 0
        tick = 0
        running: int | None = None
        found_eot = False
        while at < len(track):
            delta, at = vlq(track, at)
            tick += delta
            check(tick <= 2_000_000, "unreasonable MIDI tick")
            check(at < len(track), f"track {track_id}: dangling delta")
            status_byte = track[at]
            if status_byte >= 0x80:
                at += 1
                status = status_byte
                running = status if status < 0xf0 else None
            else:
                check(running is not None, "data byte without running status")
                status = running
            if status == 0xff:
                check(at < len(track), "missing MIDI meta type")
                meta_type = track[at]
                at += 1
                size, at = vlq(track, at)
                check(size <= len(track) - at, "meta event exceeds track")
                payload = track[at:at + size]
                at += size
                if meta_type == 0x51:
                    check(size == 3, "wrong tempo metadata length")
                    result.tempo.append((tick, int.from_bytes(payload, "big")))
                elif meta_type == 0x58:
                    check(size == 4, "wrong timesig metadata length")
                    result.timesig.append((tick, payload))
                elif meta_type == 0x2f:
                    check(size == 0, "end of track payload not empty")
                    result.eot.append(tick)
                    check(at == len(track), "data after end-of-track")
                    found_eot = True
                    break
                continue
            if status in (0xf0, 0xf7):
                size, at = vlq(track, at)
                check(size <= len(track) - at, "sysEx exceeds track")
                at += size
                continue
            kind = status & 0xf0
            check(kind in (0x80, 0x90, 0xa0, 0xb0, 0xc0, 0xd0, 0xe0),
                  "unsupported MIDI channel message")
            width = 1 if kind in (0xc0, 0xd0) else 2
            check(width <= len(track) - at, "truncated channel event")
            values = track[at:at + width]
            check(all(v < 0x80 for v in values), "non-data byte in channel event")
            at += width
            channel = status & 0x0f
            if kind == 0x90 and values[1] != 0:
                result.on.append((tick, channel, values[0], values[1]))
            elif kind == 0x80 or (kind == 0x90 and values[1] == 0):
                result.off.append((tick, channel, values[0]))
            else:
                raise MidiRejected("unexpected non-note MIDI event in minimal groove")
        check(found_eot, f"track {track_id}: missing end-of-track")
    check(pos == len(data), "trailing bytes after MIDI tracks")
    check(len(result.eot) == result.tracks, "MIDI end-of-track count mismatch")
    return result


def validate(data: bytes, mode: str, bpm: int, swing: int) -> dict:
    p = parse(data)
    target_tempo = round(60_000_000 / bpm)
    check(p.tempo == [(0, target_tempo)],
          f"tempo metadata mismatch {p.tempo} != {[(0, target_tempo)]}")
    check(p.timesig == [(0, bytes([4, 2, 24, 8]))],
          f"wrong 4/4 signature {p.timesig}")
    check(mode in ("pattern", "song"), "unknown test mode")
    expected_end = 16 * 240 if mode == "pattern" else 48 * 240
    check(all(t == expected_end for t in p.eot), f"incorrect EOT ticks {p.eot}")
    # One row 0 Kick on step 3 (offset 480 ticks). Swing 50% shifts the
    # eighth offbeat to 640 ticks: 2/3 of a quarter. Swing 25% -> 560.
    offbeat = 480 + (swing * 16 // 5)
    expected_onsets = [offbeat] if mode == "pattern" else [
        offbeat, 32 * 240 + offbeat
    ]
    expected_on = [(tick, 9, 36, 110) for tick in expected_onsets]
    expected_off = [(tick + 60, 9, 36) for tick in expected_onsets]
    check(sorted(p.on) == expected_on,
          f"bad note-on events: actual {sorted(p.on)}, expected {expected_on}")
    check(sorted(p.off) == expected_off,
          f"bad note-off events: actual {sorted(p.off)}, expected {expected_off}")
    return {
        "mode": mode, "tempo_bpm": bpm, "swing_pct": swing,
        "midi_format": p.format, "tracks": p.tracks, "ppq": p.division,
        "eot_ticks": expected_end, "onsets": expected_onsets,
        "sha256": hashlib.sha256(data).hexdigest(), "result": "PASS",
    }


def expect_rejected(data: bytes, mode: str, bpm: int, swing: int, label: str) -> None:
    try:
        validate(data, mode, bpm, swing)
    except MidiRejected:
        print(f"[PASS] P06 negative oracle rejected {label}")
        return
    raise MidiRejected(f"oracle incorrectly accepted {label}")


def verify(directory: pathlib.Path) -> None:
    entries = []
    for bpm in (90, 120, 150):
        for swing in (0, 25, 50):
            for mode in ("pattern", "song"):
                path = directory / f"{mode}-bpm{bpm}-swing{swing}.mid"
                check(path.is_file(), f"expected MIDI file missing: {path.name}")
                entry = validate(path.read_bytes(), mode, bpm, swing)
                print(f"[PASS] P06 {path.name}: {entry['onsets']} ticks, "
                      f"tempo={bpm}, tracks={entry['tracks']}")
                entries.append(entry)
    check(len(entries) == 18, "wrong number of MIDI scenarios")

    valid = (directory / "pattern-bpm120-swing0.mid").read_bytes()
    expect_rejected(valid[:-2], "pattern", 120, 0, "truncated MIDI track")
    needle = bytes([0x99, 36, 110])
    check(needle in valid, "negative test cannot locate kick note-on")
    expect_rejected(valid.replace(needle, bytes([0x99, 37, 110]), 1),
                    "pattern", 120, 0, "wrong MIDI note mapping")
    tempo_mark = valid.index(bytes([0xff, 0x51, 3]))
    tempo_mutation = bytearray(valid)
    tempo_mutation[tempo_mark + 3] ^= 1
    expect_rejected(bytes(tempo_mutation), "pattern", 120, 0,
                    "wrong MIDI tempo metadata")

    result = directory.parent / "p06-independent-midi-report.json"
    result.write_text(json.dumps({"overall": "PASS", "count": 18,
                                  "scenarios": entries}, indent=2) + "\n",
                      encoding="utf-8")
    print("[PASS] P06: 18 real product MIDI exports parsed independently; "
          "timing, tempo, mapping, note-off, EOT and negative mutations validated")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: verify_midi_export.py <directory-with-mid-files>",
              file=sys.stderr)
        raise SystemExit(2)
    try:
        verify(pathlib.Path(sys.argv[1]))
    except (MidiRejected, OSError, ValueError, IndexError) as exc:
        print(f"[FAIL] P06 independent MIDI export oracle: {exc}", file=sys.stderr)
        raise SystemExit(1)
