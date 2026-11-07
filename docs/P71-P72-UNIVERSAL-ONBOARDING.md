# P71–P72 — One universal VST3 GUI discovery and onboarding workflow

The 125A Plugin Test Lab previously had independent P68 (native VST3
capabilities), P69 (native Win32 HWND candidates), and P70 (static
painted GUI candidates). P71/P72 connect them without embedding
product-specific Drumator, AWE, or other plugin knowledge.

## P71: merged real GUI candidate inventory

Run:

```powershell
python tests/run_gui_unified_discovery.py --plugin C:\\QA\\Plugin.vst3 --gui-host C:\\QA\\125A_Test_Lab_GUI.exe --out C:\\QA\\gui-merged
```

P71 calls **both** existing readers and validates same actual module
and GUI-host hashes, source provenance and actual HWND rectangles.
Real visible/active native Windows Button HWNDs take precedence. Pixel
islands with their observation point inside a detected native button
are deduplicated. Remaining independent painted candidates are
retained, bounded to 16 per run and explicitly labeled
`VISUAL_GUESS_UNVERIFIED`; no element is automatically assigned
a musical function or approved for action.

To test actual controls in a disposable, isolated approved environment,
`--acknowledge-ui-clicks` activates **one combined** P42 sham-controlled
native probing session with a fresh VST3 instance per point. No action is
run by default, and sham checks must all pass. A genuine click is an
observation only, not proof of correct or safe behavior.

## P72: one-command onboarding for all VST3 plugins

```powershell
python tests/run_plugin_onboarding.py --plugin C:\\QA\\Plugin.vst3 --gui-host C:\\QA\\125A_Test_Lab_GUI.exe --out C:\\QA\\onboarding
```

The command obtains:
- Actual VST3 ABI audio/event bus counts, parameter IDs and GUI
  availability using P68.
- Unified native/custom-painted GUI candidate list using P71, no clicks.
- One pinned machine-readable `PLUGIN-ONBOARDING-RESULT.json` review
  handoff; P68/P69/P70 raw evidence remains in nested folders.

The onboarding report includes the discovered capabilities, candidate
click coordinates, proposed technical test cases and concrete owner tasks:
review the complete functional list, approve safe GUI actions, supply
independently measured expected parameter values and audio/MIDI/export
oracles, and then write P65/P66 test plans plus P67 coverage matrices.

**P72 never generates an executable or approved test plan from unknown
observed outcomes**. The report always states
`clicks_performed: 0`, `executable_p65_plan: false`,
`required_feature_coverage: NOT DECLARED`,
`release_approved: false`. A plugin cannot be declared complete from
mere VST3 ABI data or foreground pixel shapes. Complex backgrounds,
transparent and overlapping controls can still be missed or
misidentified. DAW and physical ASIO evidence are still NOT RUN.

The Windows acceptance suite builds both a genuine nested standard
Button VST3 and a genuine one-HWND painted-only VST3. Each must be
recognized by the same generic commands. Negative tests reject
wrong plugin hashes, counterfeit case approvals, invented centers,
duplicate candidates and premature clicks.
