# P103 — Ghidra LE/VxD 512-byte page relocation source fix

## Completed real Windows experiment

The public upstream [yetmorecode/ghidra-lx-loader](https://github.com/yetmorecode/ghidra-lx-loader) Ghidra extension v12.0.1 has a **provable bug** for LE files whose `header.pageSize` is not 4096 bytes.

Tested on actual **Windows Server 2022**, official Ghidra **12.0.1** and the **unmodified** upstream `v12.0.1` extension, followed by a locally rebuilt patched extension. **No Creative binary is ever uploaded** to public GitHub Actions.

[First successful genuine two-phase Windows test #43902432556](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/43902432556)

The 4,096-byte **entirely synthetic** LE dynamic-VxD fixture has 5 objects, 6 physical pages, a 512-byte `header.pageSize`, and 3 cross-object E8 PC-relative fixups. One source on PNPC's **second page** is decisive.

| Observation | Upstream v12.0.1 | Patched and rebuilt v12.0.1 |
| --- | --- | --- |
| LE loader successfully imports | Yes | Yes |
| All 5 objects mapped | Yes | Yes |
| All 3 applied E8 displacement values resolve to LCOD target | Yes | Yes |
| PNPC page 2 Ghidra relocation-table **source address** | **0x301021 — wrong** | **0x300221 — correct** |
| Relocation-table entries validated against expected sources | FAIL (by design, recorded as baseline bug) | PASS |
| Unexpected extra or missing relocation metadata | None | None |

The Ghidra postscripts confirm the actual in-memory E8 displacement and also iterate Ghidra's `RelocationTable`, verifying **relocation source metadata**; Ghidra process exit code alone is not accepted. The baseline and patched passes use the same synthetic input SHA-256, separately instantiated Ghidra projects, and an independently compiled extension.

## Exact correction (Apache 2.0 upstream source)

Published source tag [`v12.0.1`](https://github.com/yetmorecode/ghidra-lx-loader/tree/v12.0.1), commit `d64fca5e22665571aec050c6804c27359dab2167`.

In `src/main/java/yetmorecode/ghidra/format/lx/model/FixupRecord.java`:

```diff
- public FixupRecord(BinaryReader reader, long l, int number, int baseAddress, int page) throws IOException {
+ public FixupRecord(BinaryReader reader, long l, int number, int baseAddress, int page, int pageSize) throws IOException {
...
- this.pageAddress = baseAddress + page * 0x1000;
+ this.pageAddress = baseAddress + page * pageSize;
```

In `src/main/java/yetmorecode/ghidra/format/lx/model/Executable.java`, forward the **actual LE header** page size while constructing each `FixupRecord`:

```diff
  options.getBaseAddress(object),
- i
+ i, header.pageSize
```

The corrected extension is rebuilt with **Gradle 8.14.3** against **Ghidra 12.0.1**. A compiled ZIP is published as a public CI artifact **only after** the real patched Ghidra postscripts PASS. Its checksum is retained in the summary artifact.

## What this means for the original Creative driver

A **separate, private** checksum check on user-supplied Windows 95 image already identified `SBAWE.VXD` (77,370 bytes), SHA-256 `d343f2428ab3e593c9e42a668cf521b7801e1239792eaf7f2b11b5f179bc7c9a`. It is LE subtype `0x38000`, 512-byte pages and 5 objects. Private P003 parsing had confirmed 1,020 expanded fixups and 445 relocated `E8` callsites; the **new P103 Ghidra runtime check is still synthetic, not a Creative-driver import**.

**Consequence:** We can now rely on the patched loader's 512-byte page-stride handling for the tested inter-object relocation cases. We **cannot** yet claim perfect original `SBAWE.VXD` callgraph reconstruction, timing or bit-identical audio. A private Ghidra import of that exact SHA-256 original, with comparison against all 1,020 expanded fixups and representative 445 E8 sites, remains the next AWE-specific analysis step. At no point should proprietary Creative binaries, driver code or ROM data enter the public testlab repository.

P103 changes only the independent tool-testing PR branch, not the AWE64 Gold production VST3. No automatic merge or release approval.
