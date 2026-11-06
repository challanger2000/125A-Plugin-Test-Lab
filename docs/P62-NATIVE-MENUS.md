# P62 — Native Win32 VST3 menu structure and command routing

P62 expands the existing real VST3-owned dialog checks (P60/P61) to a **real
Win32 menu** attached to the dialog window. The host first opens an actual
VST3 editor and clicks a user-approved trigger coordinate. It then
inspects the real Windows `HMENU` by OS APIs (`GetMenu`,
`GetMenuItemCount`, `GetMenuItemID`, `GetMenuState` and
`GetMenuStringW`). For an **explicitly approved fixture contract**, the
host verifies item ID 43062, title `Apply Preset` and enabled state,
dispatches the corresponding `WM_COMMAND` to the actual dialog
window procedure and checks that the dialog closes.

Windows CI compiles two independent actual VST3 plugins: one with that
specific Win32 menu item and command handler, and one with the wrong
native menu ID. The negative must fail. An external Python verifier
rejects missing, altered and forged native observations.

```powershell
python tests/run_gui_owned_dialog.py --plugin "C:\QA\Fixture.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P62" --x 160 --y 90 --acknowledge-ui-clicks --audit-native-menu
```

**Scope:** This verifies a genuine menu's Win32 item metadata and
application command handler; the selection is **command dispatch**, not a
physical mouse selection through Windows' menu-tracking loop. Therefore
`physical_menu_selection: NOT COVERED` remains in the report.
The item ID and title are explicit fixture semantics and MUST NOT be
assumed for arbitrary product menus. In-plugin painted menus, nested
submenus, arbitrary popup-menu navigation and commercial DAW sessions
remain open. No product source files are edited; `release_approved`
remains false.
