# P98 — General Windows Installer Inventory

Purpose: inspect a SHA-256-approved Windows EXE in a deliberately disposable Windows image and record files and uninstall-registry entries before and after execution. This is a general extension of the 125A Plugin Test Lab, **not an Emulator X3 special-case**.

## Security and scope

- Never commit proprietary installers, installed binaries, or extracted assets to a public repository.
- A Windows Actions runner is ephemeral but **is not a security sandbox**. Execute only a trusted, reviewed installer whose execution has been explicitly approved. Never use a personal workstation or unrestricted self-hosted runner for arbitrary installers.
- The script refuses execution unless -ApproveExecution and an exact SHA-256 are supplied. A 240-second timeout is enforced by default.
- The inventory covers Program Files, ProgramData and per-user application-data folders, and standard machine uninstall registry keys. It does **not** assert complete filesystem/registry visibility, a successful interactive setup, or installer child-process exit correctness.
- A report status INSTALLER_EXECUTED_INVENTORY_CAPTURED merely states that the parent installer exited zero and snapshots were collected; it is **not** a product, hardware, VST3, audio, or release PASS.
- Reports may contain usernames and install paths; review/redact before disclosing.

## Manual isolated-machine invocation

```powershell
powershell -NoProfile -File tests/Invoke-InstallerInventory.ps1 -Installer C:\QA\installer.exe -ExpectedSha256 <64_HEX_DIGITS> -OutputFolder C:\QA\results -ApproveExecution
```

## Optional GitHub Actions invocation

Workflow `.github/workflows/p98-installer-inventory.yml` defaults to NOT RUN. A real execution requires all four:

1. Workflow dispatch input `approve_install=true`.
2. Workflow input `installer_sha256` containing the full approved SHA-256.
3. Repository variable `P98_INSTALLER_LAB_ENABLED=YES_DISPOSABLE`.
4. Repository secret `P98_INSTALLER_URL` containing a **short-lived HTTPS download URL** for the installer.

The runner validates the download hash, runs the inventory, deletes the downloaded EXE and retains the results for one day. No vendor installer is checked into Git.

**Known limitation:** ChatGPT conversation uploads are not automatically transferable as GitHub Actions secrets, installer URLs, or artifacts. This change does not by itself bridge that transport gap. The uploaded Emulator X3 EXE has not been installed or tested on a Windows runner.

## Follow-on tests

Once reviewed and independently sourced, application-specific executable and filter-bank extraction / reference checks can be added as approved testing stages. Existing P74 universal VST3 QA remains responsible for technical plugin validation.
