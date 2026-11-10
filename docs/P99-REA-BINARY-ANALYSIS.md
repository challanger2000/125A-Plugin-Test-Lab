# P99 — REA binary observation (opt-in)

The 125A Test Lab can record static binary observations using
[REA](https://github.com/morluto/rea) and an explicitly installed Ghidra.
**Default: NOT RUN; no automatic installation, no downloads, no REA invocation.**

## What this checks

P99 invokes the installed REA CLI's `inspect` operation on the *actual
SHA-256-pinned native VST3 binary*, with provider `ghidra` and JSON output.
It starts only the user-specified Node executable with the user-specified
REA `scripts/rea.mjs`, using subprocess arguments (no shell). Node, entry
script and VST3 binary are hashed both before and after the command.

P99 accepts exit code 0 only with canonical REA Evidence: a valid Evidence ID, outer provider ID `rea-workflow` and a nested, provenance-committed upstream analysis-profile provider ID `ghidra`, target SHA-256 in the subject digest, a named operation and nonempty normalized result. A generic JSON dictionary is a failed analysis.
It records `REA-RAW-OUTPUT.json` and `REA-RESULT.json`; P74 separately
checks the report's schema, source/tool hashes and physical evidence file.
P75 checks the per-plugin P74 result and its physical REA report digest.
The result `OBSERVATION_CAPTURED` means **unreviewed analysis output exists**,
not that Ghidra was right, a reconstructed DSP algorithm is proven,
filter behavior matches hardware, or the plugin passed functional QA.

If REA is requested and fails, times out, returns malformed JSON, or either
analyzed input or tool bytes change, the requested stage is **FAIL**. Failure
never counts as a skipped PASS. In the P75 batch, later selected VST3s
still run after one plugin fails.

## Windows prerequisites

Install trusted Node.js (a supported 22.23.4+/24.22.1+/26.12.1+ build),
REA and Ghidra/JDK yourself and consult their official instructions.
REA 6.8.0 documents experimental Windows Ghidra read-only support for
certain native PE formats; compatibility with Creative Windows 95 VxD
drivers is **NOT VERIFIED**. See
[REA's Windows provider documentation](https://github.com/morluto/rea/blob/main/docs/providers/windows-ghidra-p0.md).

In an **isolated Windows testing environment**, configure the actual
Ghidra/JDK locations in the environment (examples, not detected paths):

```powershell
$env:GHIDRA_INSTALL_DIR = "C:\\tools\\ghidra_12.1.4_PUBLIC"
$env:JAVA_HOME = "C:\\tools\\jdk-21"
$env:REA_ANALYSIS_PROVIDER = "ghidra"
```

### Standalone REA analysis (without P74 VST3 loading)

```powershell
python tests/run_rea_binary_analysis.py --binary "C:\\QA\\MyPlugin.vst3\\Contents\\x86_64-win\\MyPlugin.vst3" --node "C:\\Program Files\\nodejs\\node.exe" --rea-entry "C:\\tools\\rea\\scripts\\rea.mjs" --out "C:\\QA\\REA"
```

### P74 existing one-command QA plus REA

```powershell
python tests/run_universal_qa.py --plugin "C:\\QA\\MyPlugin.vst3" --gui-host "C:\\QA\\125A_Test_Lab_GUI.exe" --out "C:\\QA\\P74" --run-rea-analysis --rea-node "C:\\Program Files\\nodejs\\node.exe" --rea-entry "C:\\tools\\rea\\scripts\\rea.mjs" --rea-timeout 180
```

P74's ordinary VST3 discovery **loads the plugin** in its existing native
test host. REA's selected static inspect operation and this P99 adapter
do not directly execute the target module, but REA/Ghidra **are executable
software** and may spawn processes. P99 does not guarantee all descendant
processes are terminated on timeout. Use trusted software and disposable
test state; never treat reverse engineering as a sandbox.

### P75 per-plugin selection

In `--selection` JSON, set `"run_rea_analysis": true` for only the
approved individual plugins, and provide the P75 CLI paths
`--rea-node <absolute-node.exe> --rea-entry <absolute-rea.mjs>`.
Scanned directories have REA disabled by default.

## Evidence gates and privacy

- Positive and adversarial Python tests use **synthetic REA output**:
  correct evidence, malformed/error JSON, wrong return codes, timeouts,
  changed files, absent tool paths, forged provenance and batch isolation.
- These tests **do not** prove REA or Ghidra successfully ran on Windows.
  Real REA/Ghidra compatibility must be checked separately against a
  trusted native PE file before reporting provider verification.
- Binary-output analysis cannot replace original-reference PCM,
  playable audio, MIDI, GUI, actual DAW or physical ASIO/hardware QA.
- Do not upload private VST3s, proprietary Creative binaries/ROMs,
  SF2s, decompilation evidence, secrets or sensitive file paths to this
  **public** GitHub repository or public CI artifacts.
- The REA process output is capped to 2,000,000 bytes, with a default
  timeout of 120 seconds (30–600 seconds allowed). P75 also has its
  independent per-plugin timeout; configure that budget accordingly.

Current status when first committed: integration candidate awaiting
independent Windows CI and an actual trusted REA/Ghidra installation test.

### P99 actual-provider contract correction

REA `inspect` invokes the `binary_overview` composed workflow. REA 6.8.0
therefore deliberately records the outer Evidence `provider.id=rea-workflow`.
The Ghidra backend is committed separately by
`analysis_profile.parameters.upstream_analysis_profile.provider.id=ghidra`.
A validator that demands the outer ID be `ghidra` would falsely reject
valid REA/Ghidra analysis; accepting only `rea-workflow` without checking
its upstream profile could falsely accept a different analyzer. P99 verifies
**both identities** and source SHA-256, without assuming semantic fidelity.
