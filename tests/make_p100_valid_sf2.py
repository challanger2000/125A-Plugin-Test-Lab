#!/usr/bin/env python3
"""P100: deterministic redistributable SF2 one-preset fixture; no owner or E-MU ROM data."""
from __future__ import annotations

import math
from pathlib import Path
import struct
import sys


def chunk(tag: bytes, payload: bytes) -> bytes:
    assert len(tag) == 4
    return tag + struct.pack('<I', len(payload)) + payload + (b'\0' if len(payload) & 1 else b'')


def name20(s: bytes) -> bytes:
    if len(s) >= 20:
        raise ValueError('name too long')
    return s + bytes(20 - len(s))


def generate(path: Path) -> None:
    # One-second, exactly periodic 441 Hz tone; 46 SF2 guard samples.
    rate = 44100
    length = 44100
    pcm = b''.join(struct.pack('<h', round(10000 * math.sin(2 * math.pi * i / 100)))
                   for i in range(length))
    pcm += bytes(46 * 2)
    info = chunk(b'LIST', b'INFO' +
                 chunk(b'ifil', struct.pack('<HH', 2, 1)) +
                 chunk(b'INAM', b'125A P100 synthetic sine\0\0') +
                 chunk(b'isng', b'EMU8000\0'))
    sdta = chunk(b'LIST', b'sdta' + chunk(b'smpl', pcm))
    # SoundFont 2.01 preset 0 / bank 0 / one instrument / one sample.
    phdr = (struct.pack('<20sHHHIII', name20(b'P100 Sine'), 0, 0, 0, 0, 0, 0) +
            struct.pack('<20sHHHIII', name20(b'EOP'), 0, 0, 1, 0, 0, 0))
    pbag = struct.pack('<HHHH', 0, 0, 1, 0)
    pgen = struct.pack('<HHHH', 41, 0, 0, 0)  # instrument 0 + terminal
    inst = (struct.pack('<20sH', name20(b'P100 Instrument'), 0) +
            struct.pack('<20sH', name20(b'EOI'), 1))
    ibag = struct.pack('<HHHH', 0, 0, 1, 0)
    igen = struct.pack('<HHHH', 53, 0, 0, 0)  # sample ID 0 + terminal
    shdr = (
        struct.pack('<20sIIIIIBbHH', name20(b'P100 Sample'), 0,
                    length, 100, length - 100, rate, 69, 0, 0, 1) +
        struct.pack('<20sIIIIIBbHH', name20(b'EOS'), length + 46,
                    length + 46, length + 46, length + 46, rate, 0, 0, 0, 1))
    pdta = chunk(b'LIST', b'pdta' +
                 chunk(b'phdr', phdr) + chunk(b'pbag', pbag) +
                 chunk(b'pmod', bytes(10)) + chunk(b'pgen', pgen) +
                 chunk(b'inst', inst) + chunk(b'ibag', ibag) +
                 chunk(b'imod', bytes(10)) + chunk(b'igen', igen) +
                 chunk(b'shdr', shdr))
    data = info + sdta + pdta
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'RIFF' + struct.pack('<I', len(data) + 4) + b'sfbk' + data)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: make_p100_valid_sf2.py OUTPUT.sf2')
    generate(Path(sys.argv[1]))