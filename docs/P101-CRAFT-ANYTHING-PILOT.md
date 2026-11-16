# P101 — Craft Anything 0.6.1 versus REA/Ghidra (independent experimental pilot)

**Scope:** one publicly source-built **Windows x64 VST3 PE dynamic library**, obtained from the Test Lab's own `QAGuiNested` fixture. This is the **same binary and SHA-256** already analyzed in P99 through REA/Ghidra. Never publish or install Creative firmware, VXD, sample ROM, SoundFont or proprietary drivers in public CI.

## Goals

1. Download the fixed Craft Anything v0.6.1 Windows x64 portable ZIP; require SHA-256 `bd370fbaa2b44dbc13581db5ffd2bf66924ed40e433c7902212aa17ca781de54` (GitHub published release asset digest).
2. Run the actual `craft-anything-cli.exe` with `--deep native-functions-list` on the PE binary and attempt `native-function-pseudocode` for a real discovered function. **No agent or account is required** for this static observation.
3. Run the proven P99 REA/Ghidra Windows analysis on the very same binary, with Ghidra 12.1.4 and REA 6.8.0; verify the nested original provider is `ghidra`.
4. Preserve **only redacted analysis metadata** in the public artifact: identical binary hash, Craft function count, Ghidra provider, and whether pseudocode was available. Never equate a nonempty decompiler output or similar counts with program equivalence.

## Execution

Run the `P101 experimental Craft Anything vs REA-Ghidra PE comparison` GitHub Actions workflow on `windows-2022`; its PR path trigger applies only to the pilot workflow file. The job reuses the tested P99 fixture and source verification. All native outputs stay on the ephemeral runner; public logs/artifacts contain counts and hashes, no extracted native code.

## Decision gate for AWE64 Gold P003

* **GO for additional private diagnostic research only** if the actual Windows workflow succeeds and Craft's native inventory is nonempty; this is *not* a GO for integrating generated code.
* **No GO for Creative driver emulation or VST3 functional approval** from this test alone. The next, separately authorized private experiment would run Craft on user-owned `SBAWE.VXD` with SHA-256, file header/format recognition, callable function inventory, and cross-reference/disassembly observations. Compare only against the existing pinned Windows 95/REA findings, without publishing binary contents.
* Windows 95 VxD / ring-0 semantics, register-event order and CPU-timing reconstruction are **not demonstrated by normal PE DLL analysis**; in particular, P003's stereo allocator timing must still match captured original register traces and audio.
* Existing P99 REA/Ghidra remains primary unless Craft proves novel evidence or greater accuracy on the same original, preferably independently reviewed against real x86 instructions.

## Important format assessment — Creative Windows 95 VxD files

**Source-verified limitation in Craft Anything 0.6.1:** its `crates/formats/src/binary.rs` enumerates PE, ELF, Mach-O, COFF, DOS MZ/COM and raw binaries, **but not Windows VxD LE/LX**. In `parse_binary`, an `MZ` file with no PE header falls through to the DOS MZ parser. The DOS parser recognizes `LE/LX` only as an *extended-header label* and constructs a **16-bit DOS load-module image**, not a relocated 32-bit LE driver. Thus, even if an `SBAWE.VXD` command exits successfully, it could inspect only the DOS stub. **Do not interpret that as successful Creative driver disassembly.**

Exact upstream sources:
- https://github.com/storytold/craft-anything/blob/main/crates/formats/src/binary.rs
- https://github.com/storytold/craft-anything/blob/main/crates/formats/src/dos.rs
- https://github.com/yetmorecode/ghidra-lx-loader

For a genuine VxD study, first identify the original private file's LE/LX signature and SHA-256. Analyze with Ghidra plus a tested LE/LX/VxD loader, or extract mapped 32-bit executable sections and their relocations using a trustworthy LE loader; only then consider Craft's `raw-binary` x86 mode as a **secondary unrelocated instruction-level aid**. Verify relocation, address mapping and x86 references independently. Native P101 **PE-only** success is not proof of VxD support.

## Known limitations

Craft Anything is early alpha; native decompilation can be partial or incorrect. Its self-reported function count differs from Ghidra due to discovery heuristics. The automatic *build* workflow needs an external agent; this experiment uses **inspection only**. Only official public vendor releases are installed in ephemeral CI and their SHA-256 is verified; no remote source is run on the user's DAW machine.

This P101 pilot is opt-in and does not change P74/P75, existing QA gates, Studio One, or the AWE64 Gold repo.
