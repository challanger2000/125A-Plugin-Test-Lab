#!/usr/bin/env python3
"""Apply verified LE/VxD loader fixes to official yetmorecode/ghidra-lx-loader tag v12.0.1.

Run against a *separate copy* of the Apache-2.0 upstream source directory.
This tool contains no Creative code, binary, ROM, samples or driver data.
It does not build or execute a VxD. The host must rebuild the extension for Ghidra 12.0.1.

Validation: private original SBAWE.VXD SHA d343f242... imported in actual
Ghidra 12.0.1; all 1020 relocated dwords, all 445 unique E8 targets, and
five whole-object hashes matched an independent original LE parser.
"""
from pathlib import Path
import argparse
import re

FIX = "src/main/java/yetmorecode/ghidra/format/lx/model/FixupRecord.java"
EXE = "src/main/java/yetmorecode/ghidra/format/lx/model/Executable.java"
LDR = "src/main/java/yetmorecode/ghidra/lx/LinearLoader.java"


def replace_once(text: str, old: str, new: str, location: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{location}: expected exactly one old fragment, found {count}")
    return text.replace(old, new)


def patch_source(root: Path) -> None:
    src = {}
    for name in (FIX, EXE, LDR):
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        src[name] = path.read_text(encoding="utf-8")

    fix = src[FIX]
    fix = replace_once(
        fix, "int baseAddress, int page) throws IOException",
        "int baseAddress, int page, int pageSize) throws IOException", FIX
    )
    fix = replace_once(
        fix, "this.pageAddress = baseAddress + page * 0x1000;",
        "this.pageAddress = baseAddress + page * pageSize;", FIX
    )

    exe = src[EXE]
    p = re.compile(r"options\.getBaseAddress\(object\),\s*i\s*\)")
    if len(p.findall(exe)) != 1:
        raise ValueError("Executable: expected exactly one old FixupRecord constructor call")
    exe = p.sub("options.getBaseAddress(object), i, header.pageSize)", exe, count=1)
    exe = replace_once(
        exe, "total += fixups.get(i).size();",
        "if (fixups.containsKey(i)) total += fixups.get(i).size();", EXE
    )
    list_expansion = """fixups.get(page).add(fixup);
                    // LE source-list offsets share a target but each need a real
                    // patch, relocation source, and cross-reference.
                    if (fixup.hasSourceList()) {
                        var offsets = new ArrayList<Short>(fixup.sourceList);
                        if (offsets.isEmpty()) throw new IOException("empty LE fixup source list");
                        fixup.sourceOffset = offsets.get(0);
                        for (int si = 1; si < offsets.size(); si++) {
                            var instance = new FixupRecord(reader,
                                fixupRecordOffset + fixupBegin + current,
                                ++fixupCount, options.getBaseAddress(object), i, header.pageSize);
                            instance.sourceOffset = offsets.get(si);
                            fixups.get(page).add(instance);
                        }
                    }"""
    exe = replace_once(exe, "fixups.get(page).add(fixup);", list_expansion, EXE)

    ldr = src[LDR]
    ldr = replace_once(
        ldr, "for (var fix : exe.fixups.get(i)) {",
        "if (!exe.fixups.containsKey(i)) continue;\n\t\t\tfor (var fix : exe.fixups.get(i)) {", LDR
    )
    old_width = """var addr = space.getAddress(f.getSourceAddress());
\t\t\t\t\tif (f.sourceOffset >= 0 && f.sourceOffset+f.getSize() < pageData.length) {
\t\t\t\t\t\tvar originalBytes = new byte[f.getSize()];
\t\t\t\t\t\tSystem.arraycopy(originalPageData, f.sourceOffset, originalBytes, 0, f.getSize());
\t\t\t\t\t\trelocationTable.add(addr, Relocation.Status.APPLIED, f.getSourceType(), null, originalBytes, null);
\t\t\t\t\t} else {
\t\t\t\t\t\trelocationTable.add(addr, Relocation.Status.APPLIED, f.getSourceType(), null, f.getSize(), null);
\t\t\t\t\t}"""
    fixed_width = """var addr = space.getAddress(f.getSourceAddress());
                    // Source-list record length is NOT the width of a relocated source.
                    int relocatedWidth = (f.getSourceType() == 7 || f.getSourceType() == 8)
                        ? 4 : f.getSize();
                    if (f.sourceOffset >= 0 && f.sourceOffset + relocatedWidth <= pageData.length) {
                        var originalBytes = new byte[relocatedWidth];
                        System.arraycopy(originalPageData, f.sourceOffset, originalBytes, 0, relocatedWidth);
                        relocationTable.add(addr, Relocation.Status.APPLIED, f.getSourceType(), null, originalBytes, null);
                    } else {
                        relocationTable.add(addr, Relocation.Status.APPLIED, f.getSourceType(), null, relocatedWidth, null);
                    }"""
    ldr = replace_once(ldr, old_width, fixed_width, LDR)

    # Validate all preconditions before writing any file.
    for name, value in ((FIX, fix), (EXE, exe), (LDR, ldr)):
        if value == src[name]:
            raise ValueError(f"No change to {name}")
    for name, value in ((FIX, fix), (EXE, exe), (LDR, ldr)):
        (root / name).write_text(value, encoding="utf-8")
    print("P104_SOURCE_PATCH_APPLIED: 3 Java files; LE pageSize, sparse pages, source lists, relocation width")
    print("The extension still needs a Ghidra 12.0.1 rebuild and independent tests.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_source_dir", type=Path)
    args = parser.parse_args()
    patch_source(args.upstream_source_dir)
