# Universal native GUI control matrix

The Windows GUI host can run an externally declared click test on an actual
third-party VST3 HWND. The host clicks the requested physical child-window
pixel and compares the resulting VST3 controller parameter with an explicitly
supplied expected normalized value, in two attach/input/detach cycles.

```powershell
125A_Test_Lab_GUI.exe --prove-click-at Plugin.vst3 9001 160 90 1.0
python tests/run_gui_control_matrix.py --manifest gui-controls.json --out gui-evidence
```

Manifest example:

```json
{
  "schema": "125a-gui-controls-v1",
  "product": {
    "binary": "C:/QA/MyPlugin.vst3/Contents/x86_64-win/MyPlugin.vst3",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "gui_host": "C:/QA/125A_Test_Lab_GUI.exe",
  "controls": [
    {"id": "enable_switch", "param_id": 9001,
     "x": 160, "y": 90, "expected_normalized": 1.0},
    {"id": "disable_switch", "param_id": 9001,
     "x": 160, "y": 90, "initial_normalized": 1.0,
     "expected_normalized": 0.0}
  ]
}
```

Use a trusted independently specified parameter mapping and click position;
do not copy predictions from the same implementation under test. Each
control runs in a separate native host process. The matrix verifies the
declared control in two real Win32 GUI cycles and fails if the controller
parameter does not match. The Windows P04 workflow proves the matrix using
a working genuine VST3 GUI fixture and intentionally inert, wrong-expected
and out-of-bounds negative controls.

**Two-way toggles:** A control profile can now supply `initial_normalized`
(default 0.0) and a distinct `expected_normalized` anywhere in [0, 1].
The Windows GUI host sets the initial VST3 controller state, dispatches a
real native mouse click and checks the resulting controller value in **two**
editor attach/input/detach cycles. This covers both ON and OFF transitions
using exactly the same shared test engine across current and future plugins:

```powershell
125A_Test_Lab_GUI.exe --prove-click-at-from Plugin.vst3 9001 160 90 1.0 0.0
```

Optional painted-pixel checks also accept `initial_normalized` via
`--prove-click-and-snapshot-from`. Invalid or identical initial/final
values and missing native evidence fail closed. The CI verifies an actual
Win32 toggle in both directions and rejects an intentionally inert VST3.

**Explicit limits:** The generic contract does not infer a plugin's complete clickable
control inventory, visual appearance, draw correctness, drag operations,
gesture ranges, parameter persistence in the processor, DAW integration,
or dialog behavior. The report always marks `all_product_controls` as
`NOT COVERED`, even if every *declared* control passes. This must not be
used as a product release certificate. More gesture types and independent
processor/GUI oracles are necessary to cover actual user workflows.

## Correlated native controller and painted visual state

Optionally add an independently expected post-click pixel to an individual
control:

```json
"expected_pixel": {"x": 10, "y": 10, "rgb": [12, 142, 85]}
```

The matrix then runs `--prove-click-and-snapshot`, clicks the real HWND,
checks the VST3 controller parameter in two editor lifecycles, and captures
the actual painted editor BMP after the first click. The existing P33 bitmap
reader verifies that the stated RGB is present at the required physical pixel.
A successful controller value with a stale painted color is **FAIL**, not PASS.

Windows P04 regression includes a deliberately broken VST3 whose controller
parameter changes normally while its painted status remains stale. Only the
external painted-pixel expectation detects it. As before, this is a declared
pixel/control test, not automatic discovery of every product control.
