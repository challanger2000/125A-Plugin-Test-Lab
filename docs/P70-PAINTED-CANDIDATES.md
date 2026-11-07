# P70 — Universal custom-painted VST3 GUI candidate discovery

P69 finds actual Win32 child BUTTON controls. Modern VSTGUI interfaces
often paint all controls into **one HWND**, so no Windows child hierarchy
reveals their locations.

P70 uses the existing native Windows `--snapshot-editor` capture and
the P42 BMP parser. It detects bounded, high-contrast foreground pixel
"islands" against a stable corner background. Each island produces a
**possible** custom-painted GUI click coordinate, without making any
claims about its semantic identity.

## Read-only default

```powershell
python tests/run_gui_painted_candidates.py --plugin C:\QA\Synth.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\p70
```

The output `PAINTED-CANDIDATES.json` contains actual measured regions
and their midpoint, the exact pinned VST3/host SHA-256 identities,
`approved_to_click: false`, `control_semantics: UNKNOWN`, and
`exploration: NOT RUN`. No mouse events are issued by default.

## Explicit opt-in, isolated CI machine only

```powershell
python tests/run_gui_painted_candidates.py --plugin C:\QA\Synth.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\p70-probe --acknowledge-ui-clicks
```

This hands candidates to the **existing** P42 fresh-instance
sham-vs-click exploration: independent "do nothing" baselines must
remain unchanged and actual clicks must produce attributable parameter
or visual observations. The result remains an observation, not a
correctness or musical meaning oracle. Never run arbitrary discovered
clicks on user data or a production DAW.

**Limits:** The foreground-color heuristic is deliberately
conservative. Complex wallpaper, gradients, overlapping controls,
text labels, live meters and faint/transparent elements may produce
false candidates or no candidates. A single region can cover several
controls. Nothing can establish from pixels alone that a candidate is
clickable or that the action is safe. There is no universal automatic
semantic identification or full GUI coverage certification.

The P70 Windows workflow builds a real one-HWND custom-painted VST3,
verifies the button is detected at its actual native pixel geometry
**without hardcoded coordinates in the detector**, and runs the
explicit opt-in probe to confirm a visual change while the sham run
does not change. Product repositories remain untouched.
