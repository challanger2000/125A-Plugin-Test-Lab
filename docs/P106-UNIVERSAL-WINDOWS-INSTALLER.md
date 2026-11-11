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

The GitHub-hosted Windows regression **never installs arbitrary third-party vendor binaries**. It builds a harmless real per-user MSI using pinned WiX 6.0.2 and runs the genuine Windows Installer (`msiexec`) transaction. Four additional controls verify MSI inspection, execution consent, exact newly-installed bytes and stale-file rejection. It does **not** establish a manufacturer's MSI compatibility, UAC interaction, reboot, device drivers or real customer-VST3 installer behavior; those remain `NOT RUN`.

## P106 minimum evidence matrix

| Contract | CI fixture | Genuine vendor/DAW status |
| --- | --- | --- |
| Exact EXE bytes, signature and consent enforced | Source-built EXE negative controls | NOT RUN |
| Installer process launched, exit recorded | Actual harmless EXE | NOT RUN |
| Declared output bytes verified; no false zero-exit PASS | Actual marker and no-op negative | NOT RUN |
| MSI installation through msiexec | Genuine inert per-user MSI installation; four Windows tests | Vendor MSI NOT RUN |
| Registry / installed VST3 inventory | API executes on Windows fixture | Actual vendor effects NOT RUN |
| Installed VST3 load/GUI/DSP/state | P106 → P74 genuine host handoff implemented; requires successful Windows execution | Customer plugin NOT RUN |
| Real user DAW or hardware install | None | NOT RUN |

**No FULL AUDIT, QA PASS, product release or general arbitrary-installer compatibility claim.**

## P106 genuine install → existing universal VST3 QA

`tests/Invoke-InstalledVst3QA.ps1` is the fail-closed handoff. It accepts only a **successful P106 Run report** with verified installed artifact SHA-256, the exact installed module path, the actual Windows VST3 directory-bundle layout, and independent expected module hash. Only then does it invoke the existing `tests/run_universal_qa.py` P74 runner, using supplied real native GUI/audio/state hosts. It verifies the P74 result's exact module hash, required native coverage and no-release-approval flag, then checks the installed DLL hash once more after testing. Without audio and stress hosts it only establishes a read-only VST3 inventory, not audio functionality.

On an isolated Windows build machine containing the native P74 hosts and Python provided by the CI runner:

```powershell
powershell.exe -NoProfile -File tests\Invoke-InstalledVst3QA.ps1 -InstallationReport 'C:\QA\InstallEvidence\P106-INSTALLER-RESULT.json' -Vst3Bundle 'C:\QA\Installed\Plugin.vst3' -InstalledModule 'C:\QA\Installed\Plugin.vst3\Contents\x86_64-win\Plugin.vst3' -ExpectedModuleSha256 '<64-hex-output-sha256>' -GuiHost 'C:\QA\125A_Test_Lab_GUI.exe' -AudioHost 'C:\QA\125A_Test_Lab_Host.exe' -StressHost 'C:\QA\125A_Test_Lab_State_Stress.exe' -PythonExecutable 'C:\Path\To\python.exe' -RunTechnicalBaseline -OutputFolder 'C:\QA\NativeAfterInstall'
```

No Python is needed on the **owner's PC** when QA is executed entirely by GitHub Windows Actions; the connected P74 runner itself uses Python on the test runner.

`tests/Test-InstalledVst3Handoff.ps1` compiles a **real Windows VST3 with genuine audio and project-state paths** (the existing source-built `QAStateMode0` fixture), invokes the harmless P106 installer to copy the *entire bundle* to a fresh location, then runs **P74 against that installed copy, not the build output**. The final case deliberately supplies an incorrect installed-module SHA and requires rejection **before** P74 starts.

**Scope:** Installer controls + actual P74 tests of the source-built plugin can demonstrate the generic infrastructure. A customer/product installer, every GUI control, licensed DAW, actual ASIO hardware and commercial release are NOT RUN. A standalone JSON installation report is an auditable handoff, not a tamper-proof certificate against an adversary able to edit files on the local machine. Run the entire chain only in a trusted, disposable Windows test environment.

## P107 – Evidence-chain adversarial audit

The original P106 bridge rejected wrong DLL SHA but did not check several contradictory fields in a supplied install report. P107 now requires the report to be internally consistent: successful exit 0, no faults, no asserted DAW or VST3 execution by the installer, exact independently checked module identity, and the original installer path still containing the reported original SHA-256 bytes. An installer changing its own on-disk bytes before termination is rejected as well. It also checks P74's actual source-derived `discovery=PASS`, empty faults, unchanged GUI host hash, `NOT RUN` ASIO/DAW claims, and the fact that no optional product feature inventory was silently declared.

The Windows handoff regression deliberately alters six previously accepted P106 JSON report fields (installer exit, fake VST3 execution, fake DAW coverage, buried fault, wrong installer SHA, wrong installed module SHA) and requires every such record to fail **before launching P74**. These are controlled consistency checks against accidental or stale/contradictory reports. They do **not** turn a mutable JSON file into cryptographic or remote attestation and cannot protect against a malicious actor with authority over the installer process, file system, test executable and reports.

## P108 – Installer failure and file-evidence counterexamples

Three additional executed EXE fixture scenarios extend the original eight: (1) a real zero-exit process installs files with the **wrong independently approved output SHA-256** and must FAIL; (2) a real correctly installed but **un-pinned** output is explicitly `ARTIFACT_PRESENT_HASH_NOT_VERIFIED`, never `expected_artifact_verified=true`; and (3) an installer that sleeps beyond the configured **five-second process deadline** is terminated and recorded as FAIL, without a newly installed artifact. A source-built eight-second delay fixture is used exclusively inside the disposable Windows runner. These tests establish the intended handling of these bounded failures; they do **not** prove reliable termination of installer child processes, reboot-pending work, system-wide rollback or UAC-dependent installers.

## P109 – Full VST3 bundle resources (conditional proof)

Prior P106/P108 evidence authenticated the installed **DLL** but did not certify other files in the VST3 directory bundle. A plugin can load successfully even if an included configuration, preset or graphics asset is corrupted or missing. P109 adds `tests/Get-Vst3BundleManifest.ps1` to construct a separately reviewable SHA-256 manifest from the **complete approved source bundle before installation**, including hidden resource files. The new `tests/Test-Vst3BundleManifest.ps1` verifies the installed bundle against its independently pinned manifest SHA-256: every file path and content hash must match exactly; missing/extra resources and directory/file reparse points cause FAIL. A relative bundle resource path may not escape the bundle.

The existing `Invoke-InstalledVst3QA.ps1` accepts optional `-ExpectedBundleManifest` and `-ExpectedBundleManifestSha256` arguments. If both are supplied, exact whole-bundle validation is mandatory **before and after** P74 native testing. It then reports `whole_bundle_integrity=VERIFIED`. If they are absent, the report explicitly says `NOT VERIFIED`: a correct module SHA alone does not prove packaged resources. Supplying only one of the arguments fails closed.

CI creates a harmless independent resource inside its real source-built VST3 fixture, manifests it, installs the entire bundle through the source-built EXE, and checks all files before/after native P74. Additional negatives mutate the installed resource's bytes, remove the resource, add an unexpected resource, and supply a wrong source-manifest SHA. All four must fail **before P74 executes**.

A self-generated source manifest is suitable for testing installation integrity against the approved source state, but is **not a signature from a vendor**. For third-party packages it must be generated from a separately trusted known-good source, and its own SHA pinned independently. The verification is bounded to a non-hostile local Windows environment; NTFS hardlinks, adversarial file races, installer child processes and external resources outside the VST3 bundle require separate controls. FULL AUDIT and release approval remain NO-GO.

## P110 – NTFS hardlink and adversarial manifest-path controls

P109's reparse-point checks do **not** detect an NTFS hardlink: a second file path outside the VST3 bundle can reference the very same content while the installed DLL, resource SHA and file count remain identical. The `tests/P109-LinkCount.ps1` helper uses Windows `GetFileInformationByHandle` to read `nNumberOfLinks` for each enumerated file. Both the source manifest generator and installed-bundle verifier reject files with more than one hardlink, in addition to their existing symlink/junction rejection. This is deliberately conservative and may refuse legitimately hardlinked shared resources in a vendor package; such exceptions require separate investigation, not silent acceptance.

The real Windows fixture creates a byte-identical hardlink to an **outside-bundle** file, then confirms **both** source manifest generation and P109 handoff reject it. An independently rehashed malicious manifest with a parent traversal (`../outside-resource.txt`) also fails before P74. These are not simulated JSON-only checks: Windows creates a real hardlink with distinct filesystem paths to the same NTFS file.

This gate does not prove isolation from a malicious Windows administrator or kernel, race-free file opening, absence of alternate NTFS streams, or completeness of files installed **outside** the VST3 bundle. Such scopes remain NOT VERIFIED. The P106/P110 runner continues to use harmless compiled fixtures, not arbitrary vendor installers.

## P112 – NTFS alternate data stream oracle (red / green)

A real Windows adversarial regression created the named stream `P112Hidden` on an existing installed VST3 resource **without changing the file's ordinary SHA-256 hash**. P109/P110 and the file/directory manifest v2 initially accepted this altered bundle. [RED Windows run #42497526541](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42497526541) failed exactly with `P109 modified alternate-ntfs-stream falsely accepted`.

The shared `tests/P109-LinkCount.ps1` NTFS helper now also defines `Assert-P112NoAlternateStreams`: Windows PowerShell enumerates every file's FileSystem-provider stream using `Get-Item -Stream *` and rejects any stream other than the sole unnamed `:$DATA`, refusing ambiguous/empty stream enumeration. Both **source manifest creation** and **installed-bundle verification** enforce this check alongside hardlink detection.

[GREEN Windows run #42497870451](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42497870451): true EXE/MSI, installed source-built VST3/P74, and all prior negatives PASS. The new real ADS mutation is independently rejected by **both** the installed oracle before P74 and the source manifest generator; log contains `P112 unapproved NTFS alternate data stream found: P112Hidden`.

This conservative policy can reject files that legitimately contain named streams (including `Zone.Identifier`), so the package must be reviewed rather than silently exempted. ADS test evidence is Windows NTFS-scoped and does not provide remote attestation, physical ASIO, a vendor installer pass or whole-machine filesystem isolation.
