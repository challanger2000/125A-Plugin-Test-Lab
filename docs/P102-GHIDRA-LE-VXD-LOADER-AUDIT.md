# P102 — Real Ghidra LE / Windows 95 VxD loader acceptance

## Motivation and actual Creative evidence

P101 confirmed that Craft Anything 0.6.1 performs real 64-bit PE inspection but **does not correctly map LE/LX Windows 95 VxD objects**. For the AWE64 Gold P003 driver reconstruction, the important original input is the private Creative `SBAWE.VXD` 4.38.0.2, expected size **77,370 bytes**, SHA-256 **d343f2428ab3e593c9e42a668cf521b7801e1239792eaf7f2b11b5f179bc7c9a**.

The original-user supplied `125A-P003-Konsolidierte-Creative-Originaltreiber-Kontrolle-V2-20261116.zip` (not added to GitHub) documents **five original LE objects**: LCOD 31,200 B; MCOD 55 B; PNPC 7,640 B; PCOD 23,125 B; PDAT 3,560 B. It independently reconstructed **1,020 expanded LE fixup occurrences**, including **445 valid E8 32-bit targets**. The real recorded 86Box/Win95 run supported 816,583/816,594 directly attributed physical port events. These findings remain valid **original-trace evidence**, not new Ghidra results.

## Isolated, source-owned VxD LE test

Workflow: `.github/workflows/p102-ghidra-le-vxd-loader.yml` on **windows-2022**.

Published, SHA-256-pinned provider versions:
- Official Ghidra **12.0.1**, `ghidra_12.0.1_PUBLIC_20260114.zip`, SHA-256 `85bd2990945f3a78df4d1e09f1bb1f40ab77be3bac62c6e7678900788c7f0f41`.
- yetmorecode **ghidra-lx-loader v12.0.1**, `ghidra_12.0.1_PUBLIC_20260129_ghidra-lx-loader.zip`, SHA-256 `8b7e7461bd48621faa5e32c27a2c7ff8b17b82c7b765c8c6afe2cee8db693cec`.

They are installed together in a **separate** temporary Ghidra installation. Our existing P99/P101 REA/Ghidra 12.1.4 is deliberately unchanged.

`tests/p102_make_vxd.py` deterministically writes a synthetic, freely generated 3,584-byte `LE` Windows VxD fixture with five 512-byte objects called LCOD, MCOD, PNPC, PCOD and PDAT, mirroring only the **names and multiobject structure** of the driver. The module subtype is **0x38000 (dynamic VxD)**, matching this extension's VxD recognition rule (source: `yetmorecode/java-file-formats` `LinearHeader.MODULE_VXD`). A separate, valid 0x28000 static virtual-driver subtype was **not** recognized as a VxD by this specific loader; that limitation must be checked against the original SBAWE header privately.

It embeds **two synthetic E8 cross-object self-relative fixups** (PNPC+0x10 and PCOD+0x20 both target LCOD+0x60); it has no Creative binary content or functioning driver algorithm. Fixture SHA-256 is `9f8476b223eb392868928eaeeeff158e5a2c165d341cddb7b87fad0e77173e1e`.

The CI launches the **real** `analyzeHeadless.bat`, explicitly selects `yetmorecode.ghidra.lx.loader.VxDLoader`, runs the `P102VerifyVxd.java` Ghidra postscript, checks five correctly mapped Ghidra `.object1` to `.object5` memory blocks with correct locations and payloads, **checks that both E8 displacements were patched to the expected loaded LCOD target**, and fails unless the result file contains a documented success marker. Ghidra exit 0 by itself is deliberately not sufficient.

The workflow publishes only a short, redacted synthetic test summary; it cannot export private Creative bytecode or decompilation.

## Executed real Windows result — 2026-11-16

**SUCCESS (synthetic input only)** on [GitHub Actions run #43899054587](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/43899054587).

- Actual launched tool: Ghidra 12.0.1, Java 21, published matching LE/VxD loader extension v12.0.1 (both archives SHA-256 verified).
- Imported image: 3,584-byte synthetic LE dynamic-VxD, SHA-256 `9f8476b223eb392868928eaeeeff158e5a2c165d341cddb7b87fad0e77173e1e`.
- All five `.object1` to `.object5` mapped at expected `0x00100000` ... `0x00500000`, 512 bytes each. LCOD and PDAT samples verified.
- Both E8 patch bytes were read back from Ghidra's **loaded memory**, and resolved to the correct cross-object target `LCOD+0x60`.
- Ghidra postscript success marker: `P102_VXD_IMPORT_PASS objects=5 self_relative_fixups=2 target=LCOD+0x60 language=x86:LE:32:default`.
- The earlier failures showed (1) wrong headless loader argument syntax (must specify `VxDLoader`, not its fully qualified Java name), and (2) the extension's narrow VxD module subtype recognition. Both are reproducibly corrected.
- No original Creative content has been processed by the loader. This result has **not** validated any AWE-specific logic, original relocation mapping, physical register traces or PCM.

## Product applicability gate

- Positive synthetic results demonstrate that the standalone loader can map **LE-style VxD objects and fixups** in genuine Ghidra headless execution. This eliminates a tool-format obstacle seen in P101.
- It **does not** demonstrate correct parsing of the original Creative VxD 77,370-byte file; a private SHA-pinned import is still necessary.
- It **does not** demonstrate reconstruction of all 1,020 original fixups, 445 relocated E8 sites, or the original CPU register/voice-allocation timing. An actual AWE P003 acceptance would require cross-checking precisely those original fixed offsets and trace events.
- For a private test, verify the original VxD SHA-256 locally, import it under this matching Ghidra/extension pair, export **only aggregate metadata to a private workspace**, and independently compare original object sizes, page maps, relocation count and representative cross-object call targets from the existing P003 verifier. Do not transfer private drivers/ROM/SF2/PCM to this public Test Lab or CI.

This is a diagnostic experiment, **not** a request to change or merge the AWE64 Gold product code or alter existing P74/P75 requirements.
