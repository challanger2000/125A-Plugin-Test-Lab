# P104 — Private original Creative SBAWE.VXD analyzed in actual Ghidra

**Status:** Original-driver static import and register-independent LE relocation validation **PASS**. Does **not** approve voice selection CPU timing or bit-exact EMU8000 PCM. Verified 2026-11-16, using Ghidra **12.0.1** with locally corrected, rebuilt Apache-licensed `yetmorecode/ghidra-lx-loader v12.0.1`.

## Data handling

The user's original Win95 VM archive was mounted **locally**, and the original `SBAWE.VXD` was extracted to a private temporary workspace. Original file: **77,370 bytes**, SHA-256 `d343f2428ab3e593c9e42a668cf521b7801e1239792eaf7f2b11b5f179bc7c9a`. A second copy from the same original VM had identical SHA-256. LE header module subtype **0x38000**, physical page size **512 bytes**, **five objects**.

The Ghidra 12.0.1 release was retrieved by a short-lived *public-distribution-only* GitHub Actions bootstrap (P104 run #43908474536), SHA-256 verified as `85bd2990945f3a78df4d1e09f1bb1f40ab77be3bac62c6e7678900788c7f0f41`, and transferred to the isolated Linux working environment. The previously patched P103 v12.0.1 LX/VxD extension was similarly transferred. **No Creative byte content, Win95 disk, sound bank, decompiled code or audio was uploaded to any GitHub repo, CI runner, tool artifact or cloud API for this original-driver test.**

## Actual original-driver import and comparison

The real headless Ghidra application was executed against the original private VxD, with `-loader VxDLoader -processor x86:LE:32:default -cspec gcc`. Initially the import failed because the third-party loader assumed **every numbered LE page belonged to an object**; Creative has gaps in the object page table. After fixing two null accesses to these sparse pages, Ghidra imported the 5 real objects. The initial loaded image still had **590/1,020** expected 32-bit relocation values wrong because LE source-list entries were not expanded correctly.

An independent **private** Python LE parser, itself SHA-pinned to the original driver, reconstructed actual object pages, decoded `0x07` / `0x08` direct and `0x27` / `0x28` source-list records and independently calculated the exact x86 32-bit destination bytes. The patched Ghidra loader was rebuilt with the additional list expansion and correct 4-byte relocated-width handling.

**Final real Ghidra original-import result, not a synthetic fixture:**

| Independent cross-check | Observed |
| --- | ---: |
| Original LE objects loaded with expected size/base | **5/5** |
| LE source records | 572 |
| Expanded individual relocation locations | **1,020/1,020** |
| Expanded source-list relocation locations | **588/588** |
| Relocation metadata at correct source addresses | **1,020/1,020** |
| Exact relocated 32-bit values vs independent parser | **1,020/1,020** |
| Incorrect relocated values | **0** |
| Independently rebuilt whole-object SHA-256 matches actual Ghidra loaded image | **5/5** |
| Unique x86 E8 callsite destinations resolved against the patched Ghidra memory | **445/445** |
| Incorrect E8 destinations | **0** |
| Ghidra-discovered functions at end of import | **190** |
| E8 callsites with Ghidra-created outgoing references (without manual seeding) | **400/445** |

Note that the 1,020 relocation entries correspond to **1,015 unique source offsets** because 5 identical duplicate fixups occur in the original file. The independently established 445 E8 callsites refer to **unique call instruction addresses**, not all 0x08 list/direct relocation records. In one preliminary script, the E8 opcode counter totaled 449 when duplicates were included; this is not the unique callsite count.

**Object mapping:** `LCOD` 31,200 B, `MCOD` 55 B, `PNPC` 7,640 B, `PCOD` 23,125 B, `PDAT` 3,560 B. Object base addresses used for this offline Ghidra analysis were default non-overlapping mapped addresses `0x100000` through `0x500000`. These are *analysis addresses*, not original Creative Win95 VMM runtime segment bases.

## Five necessary third-party loader corrections

1. **Actual LE page size (P103):** in `FixupRecord`, use `baseAddress + pageIndex * header.pageSize` instead of `pageIndex * 0x1000`, forwarding `header.pageSize` from `Executable`.
2. **Sparse pages in `Executable.totalFixups`:** an unassigned page index has no `fixups` map entry; skip absent entries instead of dereferencing null.
3. **Sparse pages in `LinearLoader.createEntrypoint`:** skip absent page indices before iterating their fixup lists, again avoiding null.
4. **LE source-list expansion in `Executable`:** each `0x27` or `0x28` fixup has a list of independent source offsets sharing a single target; add one relocated instance per listed offset, while advancing the file parser by the size of the original record only.
5. **Relocation record width in `LinearLoader.createObjectBlock`:** the number of source offsets in a source list is *not* the byte width of one applied LE fixup; use four bytes for source kinds `0x07` / `0x08`, not `FixupRecord.getSize()` (which for a large source-list can be hundreds of bytes, causing Ghidra relocation-table validation to throw `unsupport byte-length`).

The real original Creative VxD was tested before/after these corrections. Initial import failed on a null sparse page; second attempt imported but only **430/1,020** 32-bit fixup bytes agreed; after the five corrections all **1,020/1,020** agree.

## Relevance to AWE64 Gold P003

The original static LE loader + C++23 port now has an **independently cross-validated address map, relocated image and complete 445-E8-target set** suitable for offline Ghidra decompilation and code-flow research. Ghidra currently auto-identifies 190 functions and outgoing references at 400 of those 445 callsites; further guided entry-point / function discovery could help the remaining 45. The existing original Creative P003 code analysis continues to be the source for register event timing; this static result **does not** show 25 stereo allocator traces or CPU/EMU8000 audio parity.

The source fixes must be preserved/rebuilt on the correct upstream loader revision for reproducibility. An isolated source patch reproducing them belongs in this Draft PR; the private driver must remain private. No change has been made to the AWE64-Gold-VST3 product branch, and no Studio-One end test was requested or run.

**User action needed: none.**
