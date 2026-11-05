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
     "x": 160, "y": 90, "expected_normalized": 1.0}
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

**Explicit limits:** This first generic contract works for click-to-parameter
controls resettable to zero. It does not infer a plugin's complete clickable
control inventory, visual appearance, draw correctness, drag operations,
gesture ranges, parameter persistence in the processor, DAW integration,
or dialog behavior. The report always marks `all_product_controls` as
`NOT COVERED`, even if every *declared* control passes. This must not be
used as a product release certificate. More gesture types and independent
processor/GUI oracles are necessary to cover actual user workflows.
