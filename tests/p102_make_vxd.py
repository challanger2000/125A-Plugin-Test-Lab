#!/usr/bin/env python3
"""Synthetic public-domain LE VxD fixture for independent loader tests.
NOT Creative code, NOT a functioning driver, and not an AWE timing test.
Five LE objects (LCOD/MCOD/PNPC/PCOD/PDAT), two inter-object E8 fixups.
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
FIXUP_PAGES = MAP + 5 * 4
FIXUP_RECORDS = FIXUP_PAGES + 6 * 4
DATA = 0x400
NAMES = ("LCOD", "MCOD", "PNPC", "PCOD", "PDAT")

def generate():
    b = bytearray(DATA + 5 * PAGE)
    def u16(p,v): struct.pack_into("<H",b,p,v)
    def u32(p,v): struct.pack_into("<I",b,p,v)
    b[:2] = b"MZ"
    u16(4,len(b)//512)
    u16(8,4)
    u16(0x18,0x40)  # conventional new-style MZ header
    u32(0x3c,HEADER)
    h=HEADER
    b[h:h+2] = b"LE"
    u16(h+8,2)  # x86
    u16(h+10,4) # Windows VxD
    u32(h+0x10,0x28000) # virtual device driver
    u32(h+0x14,5) # physical pages
    u32(h+0x18,0) # eipObject=0 (typical VxD)
    u32(h+0x28,PAGE)
    u32(h+0x2c,PAGE)
    u32(h+0x30,6*4+2*7)
    u32(h+0x38,FIXUP_PAGES-OBJECTS)
    u32(h+0x40,OBJECTS)
    u32(h+0x44,5)
    u32(h+0x48,MAP)
    u32(h+0x68,FIXUP_PAGES)
    u32(h+0x6c,FIXUP_RECORDS)
    u32(h+0x80,DATA)
    u32(h+0x84,5)
    for i, name in enumerate(NAMES):
        struct.pack_into("<IIIIII", b, h+OBJECTS+24*i,
                         PAGE, (i+1)*0x100000, 3 if name=="PDAT" else 5,
                         i+1, 1, int.from_bytes(name.encode("ascii"),"little"))
        b[h+MAP+i*4:h+MAP+i*4+4] = (i+1).to_bytes(3,"big")+b"\x00"
    for i, offset in enumerate((0,0,0,7,14,14)):
        u32(h+FIXUP_PAGES+i*4,offset)
    for i, source in enumerate((0x11,0x21)):
        struct.pack_into("<BBhBH",b,h+FIXUP_RECORDS+i*7,8,0,source,1,0x60)
    def obj(n): return DATA+(n-1)*PAGE
    b[obj(1)+0x40:obj(1)+0x42] = b"\xed\xc3"
    b[obj(1)+0x50:obj(1)+0x52] = b"\xef\xc3"
    b[obj(1)+0x60:obj(1)+0x63] = b"\x66\xef\xc3"
    b[obj(3)+0x10:obj(3)+0x16] = b"\xe8\x00\x00\x00\x00\xc3"
    b[obj(4)+0x20:obj(4)+0x26] = b"\xe8\x00\x00\x00\x00\xc3"
    b[obj(5)+0x30:obj(5)+0x39] = b"P102-TEST"
    return bytes(b)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("output",type=Path)
    a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    blob=generate()
    a.output.write_bytes(blob)
    assert len(blob)==3584
    assert blob[0x80:0x82]==b"LE"
    assert hashlib.sha256(blob).hexdigest()=="9a331d3288195cda374a1b42d481dc60cc629379f04330fac5bd11ba8a91dd9d"
    print(json.dumps({"fixture_sha256":hashlib.sha256(blob).hexdigest(),"five_objects":list(NAMES),"fixup_records":2}))
if __name__=="__main__":
    main()
