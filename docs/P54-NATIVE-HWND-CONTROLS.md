# P54 — Genuine Win32 VST3 editor control-tree inventory

P54 adds a **read-only** `--inventory-hwnd-tree` command to the shared Windows native GUI host. It attaches an actual VST3 editor, traverses the native Win32 child HWNDs, and records their native class name, parent hierarchy, visible/enabled state, bounding rectangle (relative to the editor), and Win32 control ID.

Run with a Windows native VST3 and previously built `125A_Test_Lab_GUI.exe`:

```powershell
python tests/run_gui_hwnd_tree.py --plugin "C:\QA\Plugin.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P54"
```

This produces `native-hwnd-tree.tsv` and `HWND-CONTROL-TREE.json`. The Python verifier independently checks the ordered hierarchy, dimensions, module/host SHA-256 identities, completeness markers and strict node counts. No input clicks occur.

The Windows CI tests two source-built, real VST3 editors. The first contains a nested native `BUTTON` with ID 43001, which **must** be discovered. The second paints a clickable button inside a single HWND and **must not** be misrepresented as a native BUTTON child.

**Scope boundary:** Standard Win32 controls can be enumerated, but VSTGUI/other frameworks often paint many controls in a single HWND. P54 cannot infer these painted controls, their intended behavior or hidden menus. Neither an HWND list nor a screenshot represents complete GUI coverage. The report retains `complete_product_gui_controls: NOT COVERED` and `release_approved: false`. No commercial DAW session is involved and no product source is changed.
