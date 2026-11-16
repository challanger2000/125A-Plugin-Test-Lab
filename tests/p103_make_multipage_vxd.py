#!/usr/bin/env python3
"""Public synthetic LE Windows VxD with 512-byte multi-page object and 3 E8 fixups.
Not Creative code. Specifically tests Ghidra LE loader relocation SOURCE addresses.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

PAGE = 512
HEADER = 0x80
OBJECTS = 0xC4
MAP = OBJECTS + 5 * 24
FIXUP_PAGES = MAP + 6 * 4
FIXUP_RECORDS = FIXUP_PAGES + 7 * 4
DATA = 0x400
NAMES = ("LCOD", "MCOD", "PNPC", "PCOD", "PDAT")
OBJECT_SIZES = (PAGE, PAGE, 2 * PAGE, PAGE, PAGE)
OBJECT_PAGES = (1, 1, 2, 1, 1)
OBJECT_START_PAGE = (1, 2, 3, 5, 6)

def generate():
    b = bytearray(DATA + 6 * PAGE)
    def u16(p, v): struct.pack_into("<H", b, p, v)
    def u32(p, v): struct.pack_into("<I", b, p, v)
    b[:2] = b"MZ"
    u16(4, len(b) // PAGE)
    u16(8, 4)
    u16(0x18, 0x40)
    u32(0x3c, HEADER)
    h = HEADER
    b[h:h+2] = b"LE"
    u16(h+8, 2)
    u16(h+10, 4)
    u32(h+0x10, 0x38000)
    u32(h+0x14, 6)
    u32(h+0x18, 0)
    u32(h+0x28, PAGE)
    u32(h+0x2c, PAGE)
    u32(h+0x30, 7*4 + 3*7)
    u32(h+0x38, FIXUP_PAGES - OBJECTS)
    u32(h+0x40, OBJECTS)
    u32(h+0x44, 5)
    u32(h+0x48, MAP)
    u32(h+0x68, FIXUP_PAGES)
    u32(h+0x6c, FIXUP_RECORDS)
    u32(h+0x80, DATA)
    u32(h+0x84, 6)

    for i, name in enumerate(NAMES):
        struct.pack_into("<IIIIII", b, h+OBJECTS+24*i,
                         OBJECT_SIZES[i], (i+1)*0x100000,
                         3 if name == "PDAT" else 5,
                         OBJECT_START_PAGE[i], OBJECT_PAGES[i],
                         int.from_bytes(name.encode(), "little"))
    for i in range(6):
        b[h+MAP+i*4:h+MAP+i*4+4] = (i+1).to_bytes(3, "big")+b"\x00"
    for i, value in enumerate((0,0,0,7,14,21,21)):
        u32(h+FIXUP_PAGES+i*4, value)
    for i, src in enumerate((0x11,0x21,0x31)):
        struct.pack_into("<BBhBH",b,h+FIXUP_RECORDS+i*7,8,0,src,1,0x60)
    def obj(n): return DATA+sum(OBJECT_SIZES[:n-1])
    b[obj(1)+0x60:obj(1)+0x63]=b"\x66\xef\xc3"
    b[obj(3)+0x10:obj(3)+0x16]=b"\xe8\x00\x00\x00\x00\xc3"
    b[obj(3)+PAGE+0x20:obj(3)+PAGE+0x26]=b"\xe8\x00\x00\x00\x00\xc3"
    b[obj(4)+0x30:obj(4)+0x36]=b"\xe8\x00\x00\x00\x00\xc3"
    b[obj(5)+0x30:obj(5)+0x39]=b"P103-TEST"
    return bytes(b)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("output",type=Path)
    a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    blob=generate()
    assert len(blob)==4096 and blob[0x80:0x82]==b"LE"
    a.output.write_bytes(blob)
    print(json.dumps({
        "kind":"synthetic LE dynamic VxD",
        "sha256":hashlib.sha256(blob).hexdigest(),
        "bytes":len(blob),"objects":5,"pages":6,
        "page_size":PAGE,"cross_object_fixups":3
    }))
if __name__=="__main__":
    main()
