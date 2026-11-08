# P106 – Universal Windows EXE/MSI Installer QA (development)

## Purpose and evidence boundary

P106 exercises an **explicitly approved, SHA-256 pinned local EXE or MSI installer** on a disposable Windows x64 test machine. No installer is automatically downloaded or guessed, no unattended install switches are invented for EXE files, and the default mode is inspection only. This is reusable for existing and future plugins, not tied to Drumator or AWE. **Running an EXE is technically supported**; some installers require interactive Windows desktop, UAC/admin rights, reboot, drivers or a vendor-supported silent command.

**Important:** PowerShell launches processes; it is **not** a sandbox. An untrusted installer can modify the machine and start child processes. Run unknown packages only inside a truly disposable isolated Windows VM or ephemeral test host, not on the user's primary workstation or an unprotected public self-hosted runner.

## CLI (no Python on the user's PC)

Read-only inspect with independently approved SHA-256:

```powershell
powershell.exe -NoProfile -File tests\Invoke-UniversalInstaller.ps1 -Installer 'C:\QA\VendorSetup.exe' -ExpectedSha256 '<64-hex-reviewed-sha256>' -OutputFolder 'C:\QA\Evidence-Inspect'
```

To run on a disposable prepared machine, supply consent and a **fresh** expected file path. Pin an independently known installed artifact SHA for the strongest objective confirmation:

```powershell
powershell.exe -NoProfile -File tests\Invoke-UniversalInstaller.ps1 -Mode Run -ApproveExecution -Installer 'C:\QA\VendorSetup.exe' -ExpectedSha256 '<64-hex-reviewed-sha256>' -ExpectedArtifact 'C:\Program Files\Common Files\VST3\Vendor.vst3\Contents\x86_64-win\Vendor.vst3' -ExpectedArtifactSha256 '<64-hex-reviewed-output-sha256>' -OutputFolder 'C:\QA\Evidence-Install' -InstallerArguments '/S'
```

**The example '/S' is not universal.** Only pass silent flags after reviewing the vendor's exact installer documentation. For MSI P106 uses Windows `msiexec /i "<path>" /qn /norestart`; explicit additional properties are supported in `-InstallerArguments`. An interactive EXE may require a real desktop/UAC; headless CI cannot guarantee it.

Unsigned binaries are refused by default. For a separately reviewed harmless fixture or explicitly authorized unsigned package, `-AllowUnsigned` must be provided **in addition** to the exact SHA-256 and execution approval; this does not confer trust on the unsigned file. Do not give such an opt-in to unknown internet downloads.

## Evidence

Each invocation writes a fresh `P106-INSTALLER-RESULT.json` with:

- independently checked input SHA-256, Authenticode status/signer and installer type;
- opt-in and whether the process was actually launched; real exit code or timeout;
- before/after bounded VST3 path inventory and uninstall registry snapshots (reported changes only);
- requested installed artifact presence and SHA-256, with optional independently pinned expected hash;
- separate `installer_executed`, `installer_verified`, `expected_artifact_verified`, `vst3_qa_executed=false`, `commercial_daw_verified=false`, `release_approved=false`.

The statuses `INSPECTED_NOT_RUN`, `FAIL`, `ARTIFACT_PRESENT_HASH_NOT_VERIFIED` and `INSTALLATION_ARTIFACT_VERIFIED` must **not** be interpreted as a plugin functionality PASS. `installer_verified` means process exit 0, not product correctness. Actual VST3 tests must run subsequently using the existing P74/P75/P89 Windows native host, with the exact installed module fingerprint. Installed file presence alone does not prove DLL can load, UI works or DAW recall.

A timeout attempts to kill the main installer process; independently spawned children and reboot requirements may survive. P106 does not guarantee cleanup, isolation, kernel-driver functionality or rollback. Installer MSI changes may involve Windows Installer service state and must be checked on the disposable machine after the test. Installation side effects outside the observed VST3 and uninstall registry subsets remain **NOT COVERED**.

## Automated Windows regression

`tests/Test-UniversalInstaller.ps1` builds a harmless real C# EXE into `RUNNER_TEMP`, then executes it through the production PowerShell adapter. It checks: inspection without execution; wrong input SHA refusal; unsigned policy refusal; absent consent refusal; actual process launch with exact installed marker bytes; stale marker rejection; zero process exit with no installation artifact rejection; and real nonzero exit rejection.

The GitHub-hosted Windows regression **never installs arbitrary third-party vendor binaries**, and it does not test a real MSI transaction, admin/UAC interaction, registry writes, restart, bundled driver or product VST3. Treat those as explicit `NOT RUN` gates until a trusted source and isolated environment are available.

## P106 minimum evidence matrix

| Contract | CI fixture | Genuine vendor/DAW status |
| --- | --- | --- |
| Exact EXE bytes, signature and consent enforced | Source-built EXE negative controls | NOT RUN |
| Installer process launched, exit recorded | Actual harmless EXE | NOT RUN |
| Declared output bytes verified; no false zero-exit PASS | Actual marker and no-op negative | NOT RUN |
| MSI installation through msiexec | Source reviewed only | NOT RUN |
| Registry / installed VST3 inventory | API executes on Windows fixture | Actual vendor effects NOT RUN |
| Installed VST3 load/GUI/DSP/state | Separate P74/P75 bridge documented | NOT RUN |
| Real user DAW or hardware install | None | NOT RUN |

**No FULL AUDIT, QA PASS, product release or general arbitrary-installer compatibility claim.**
