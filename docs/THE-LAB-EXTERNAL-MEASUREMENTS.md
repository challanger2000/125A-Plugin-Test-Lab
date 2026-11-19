# THE_LAB 1.3.4 — optional independent external measurement evidence

THE_LAB by Phil Speiser is a **third-party, Windows/macOS standalone VST3
measurement app**, not a 125A product or part of the 125A Test Lab binary.
The vendor documents manual exports in **JSON/CSV**, but no stable CLI,
headless API, export schema or unattended first-run/authentication contract
has been verified. **Do not execute its installer in public GitHub Actions**,
do not redistribute/bundle it, do not invent hidden CLI flags, and do not
turn its measurements or label `PASS` into a 125A release approval.

A user supplied `THELAB134.exe` on 2026-11-19. Static analysis found an
Inno Setup 6.1.0 Windows installer, embedded version **1.3.4**, and installer
SHA-256 `1ed1de108946ef6c53d2edd3c6cab8f068c5733c7364ab2a9cf25ab8f830223f`.
**This does not verify the program after installation, its origin/signature,
or its measurement accuracy. The executable is not committed here.**

## Useful role

Use THE_LAB locally, separately from 125A Test Lab, as a comparison source
for HP/LP frequency and phase response, group delay, distortion,
automation, CPU and other measurements that the installed version actually
supports. The 125A Test Lab retains its *own* independently specified
oracles, native VST3 host/GUI tests, negative controls, Windows CI,
state/automation/DAW and realtime gates. The two systems' reports are
**complementary**, not interchangeable.

## Manual evidence import (does not launch THE_LAB)

1. On your **own Windows machine** install/open THE_LAB as instructed by its
   publisher; load the **exact candidate VST3** and make the desired measurements.
2. Use THE_LAB's **EXPORT > JSON/CSV** command and preserve the raw export.
   Review it first for any account email or personally identifying path strings.
3. Independently record the SHA-256 of both the *actual VST3 module binary*
   and the export (for example `Get-FileHash -Algorithm SHA256`).
4. Import it without launching THE_LAB or requiring a network connection:

```powershell
python tests/import_the_lab_report.py `
  --module "C:\QA\125A Precision Filter.vst3\Contents\x86_64-win\125A Precision Filter.vst3" `
  --module-sha256 "<64-digit real VST3 module SHA256>" `
  --report "C:\QA\TheLab-export.json" `
  --report-sha256 "<64-digit real export SHA256>" `
  --the-lab-version 1.3.4 `
  --out "C:\QA\TheLab-evidence"
```

The importer checks bounded JSON/CSV structure, missing or malformed files,
source VST3/export SHA-256 matching, and that the exact bytes are preserved
in the evidence directory. It emits `THE-LAB-EXTERNAL-OBSERVATION.json`
and a byte-for-byte copy `THE-LAB-ORIGINAL.json` (or `.csv`). An error
returns nonzero and leaves `status: FAIL` rather than stale success.

**Evidence semantics:**

- `EXTERNAL_REPORT_IMPORTED_SOURCE_UNATTESTED` means *only* the declared
  external file was structurally readable and independently pinned bytes
  match the files examined. It does not certify that THE_LAB produced them.
- THE_LAB's own verdicts and the meaning of its numeric columns are **not
  interpreted** until a real export schema and an independent DSP oracle are
  available. A vendor string `PASS` must not become 125A `PASS`.
- `release_approved: false`, `original_measurements_verified: false`,
  `physical_asio_hardware: NOT RUN`, and `commercial_daw_session: NOT RUN`
  remain explicit even after import.
- Output data are supplementary evidence only; **do not attach the EXE or
  reports containing private account information to public CI artifacts**.

## Current verification / gaps

- Standalone importer's positive and negative synthetic tests can run on
  Windows/Linux using only Python standard library. These are parser tests,
  **not actual THE_LAB measurement verification**.
- **NOT RUN:** actual THE_LAB Windows launch, first-run login, measured VST3
  report generation, real JSON/CSV schema agreement, native CLI automation.
- To promote meaningful spectral assertions, first obtain a genuine export,
  review its documented fields, and preapprove independent sample-rate/
  cutoff/slope-specific numeric tolerances; then test incorrect-filter
  mutants against those expected values.

Vendor documentation: https://www.philspeiser.com/product/the_lab
