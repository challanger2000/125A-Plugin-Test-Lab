# P55 — Automatically probe discovered native Win32 VST3 buttons

P55 connects P54's genuine HWND hierarchy inventory with the existing
P42–P44 matched-sham native GUI click explorer. It identifies visible,
enabled **native Win32 BUTTON** child controls, derives each button center
from independently observed physical rectangles and probes up to 16 in
fresh disposable VST3 processes. No plugin-specific hard-coded coordinates
are needed for supported Win32 BUTTON controls.

```powershell
python tests/run_gui_native_buttons.py --plugin "C:\QA\Plugin.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P55" --acknowledge-ui-clicks
```

**Warning:** Arbitrary plugin buttons can cause destructive actions, saves,
file dialogs, preset changes or other side effects. Use only trusted test
VST3s and disposable data. The CLI requires an explicit opt-in.

The report `NATIVE-BUTTON-PROBES.json` records exact binary/host SHA-256,
actual native control IDs/rectangles, genuine sham-attributed pixel and
controller changes, and explicit coverage gaps. More than 16 native buttons
are reported as truncated and not falsely certified.

Windows CI independently builds two VST3 editors: nested Win32 `BUTTON`
ID 43001 with an actual controller change, and a custom-painted-only
button (with **no HWND BUTTON**). The first must be identified and click
9001 under a matched sham; the second must not invent any native BUTTON.
Adversarial tests reject missing sham evidence and incorrect coordinates.

**Limits:** The tool does not know each button's intended action or test a
hidden menu, custom-painted button, commercial DAW or product release.
All results retain `independent_product_semantics: NOT COVERED`,
`complete_product_gui_controls: NOT COVERED` and
`release_approved: false`. It never updates Drumator or AWE source code.
