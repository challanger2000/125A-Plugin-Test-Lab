# P68 — Universal VST3 ABI discovery and safe test-plan preparation

P68 adds **read-only inspection of an arbitrary Windows x64 VST3 binary**.
It does not hard-code Drumator, AWE or any other plugin's function names.

The native GUI host now provides `--inventory-capabilities`. It reports:
the unique VST3 audio processor class, real audio/event bus layout
(including input/output and channel count), number of controller parameters,
writable/read-only flags, bypass and program-change flags, and whether the
plugin offers an editor supporting Win32 HWND.

P68 also reuses the existing native `--inventory-parameters` command to
collect verified parameter IDs, discrete step counts, declared defaults,
current normalized values and flags. Both reports are parsed independently,
cross-checked and pinned to the exact plugin and host binary SHA-256 hashes.

## Usage

On Windows after building `125A_Test_Lab_GUI.exe`:

```powershell
python tests/run_vst3_auto_discovery.py --plugin "C:\QA\AnyPlugin.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P68"
```

Optionally supply `--audio-host` and `--stress-host` together with the
two existing native test executables to propose the standard P66 technical
quickcheck case.

The output includes:

- `DISCOVERY-RESULT.json`: machine-readable verified inventory counts,
  actual module SHA-256, host identity, fail-closed discovery result
- `native-capabilities.tsv`: raw native VST3 bus/controller evidence
- `native-parameters.tsv`: raw parameter inventory
- `PROPOSED-TEST-PLAN.json`: **non-executable plan draft**, concrete
  discovered parameter IDs and capabilities, and which requirements still
  need explicit owner approval / independent expectations

## Why the draft cannot execute automatically

No VST3 ABI query tells us the intended musical effect of an unknown
parameter, which pixel controls it, what MIDI/WAV export semantics should
be, or whether a custom GUI button is destructive. Therefore P68 does
not guess coordinates, generate expected output values, claim functional
coverage or activate the plugin's editor controls. Its draft contains
`executable_p65_plan: false`,
`required_feature_inventory: NOT DECLARED`,
`musical_oracles: NOT DISCOVERED` and
`release_approved: false`.

The responsible plugin development chat converts the proposed cases
into a full **approved** P65/P66 `125a-product-test-plan-v1`, supplies
independent GUI and signal expectations, and maintains the P67 required
feature matrix. The existing Test Lab executes those confirmed contracts.

The discovery result is NOT a release gate. Physical ASIO hardware,
commercial DAW sessions and unexposed GUI/export/product features
remain untested. A plugin advertising multiple audio processor classes
must be explicitly selected in a future extension instead of picking
the first class silently.

P68 Windows CI builds multiple genuine independent VST3 fixtures,
checks that real ABI metadata is discovered and that a passing inventory
**does not accidentally approve an unreviewed test plan**. Negative
regressions reject duplicates, inconsistencies, truncation, wrong counts
and binaries modified during discovery.
