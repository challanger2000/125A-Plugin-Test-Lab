# P63 — Actual Win32 popup mouse selection in a real VST3 editor

P63 closes a gap in P62: the menu entry is now chosen by **actual Win32
menu tracking and injected mouse-button input**, rather than selecting a
predefined command directly.

The Windows native GUI host first attaches a genuine VST3 editor and
opens an owned Win32 dialog. It discovers its real `Actions` submenu
via `GetMenu` and `GetSubMenu`, checks the expected enabled
`Apply Preset` item, and calls `TrackPopupMenuEx` with
`TPM_RETURNCMD`. A bounded helper thread must observe an actual
process-owned `#32768` menu popup and a real menu item rectangle
before it may deliver `SendInput` mouse down/up at that rectangle.
The native menu loop must then return the approved item ID 43064.
Only **after** the OS returns this ID does the host dispatch the command
to the plugin-owned dialog. The dialog must close.

Windows CI builds two genuinely different VST3 binaries from fixture
source: a good popup with the approved action and a broken one with the
wrong command. The good fixture must prove a real mouse-selected menu,
while the broken one must fail. Independent adversarial tests reject
reports substituting a direct `WM_COMMAND`, guessed selection,
incorrect ID, missing mouse operation, or no window close.

```powershell
python tests/run_gui_owned_dialog.py --plugin "C:\QA\Fixture.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P63" --x 160 --y 90 --acknowledge-ui-clicks --select-popup-mouse
```

**Limits:** The ID, menu text and coordinate are approved fixture
oracles, **not** universal semantics for all commercial plugins.
Generic VSTGUI custom-painted menus, nested multi-level navigation,
file-dialog handling, DAW sessions and product release approval are still
not covered. Because this test sends real mouse input to the Windows
desktop, run only on disposable, isolated test machines/sessions
with explicitly approved plugin input. It does not change Drumator/AWE
production code, and every report retains `release_approved: false`.
