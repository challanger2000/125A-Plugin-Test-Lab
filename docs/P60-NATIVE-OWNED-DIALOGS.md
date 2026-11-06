# P60 — Real owned Windows dialog discovery after VST3 GUI click

P60 adds a **native** `--observe-owned-dialog` command to the existing
Windows VST3 GUI host. It attaches a real `IPlugView` editor, checks the
process-owned Win32 dialog inventory before clicking, sends a physical
Win32 mouse click and re-inventories process-owned top-level `#32770`
windows whose owner belongs to the attached editor.

An independently approved UI coordinate is required. The report enforces
no preexisting dialog, exactly one newly opened visible native dialog, actual
owning-process/Win32 owner relationship, clean close on the GUI host and
consistent product/host SHA-256 identity. The good source-built VST3 fixture
opens the actual native dialog. The deliberately broken VST3 changes its
controller state but opens **no dialog**; this must fail the same external
oracle. A forged or missing native event sequence is rejected.

Run with a disposable VST3 fixture or independently trusted plugin only:

```powershell
python tests/run_gui_owned_dialog.py --plugin "C:\QA\Fixture.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P60" --x 160 --y 90 --acknowledge-ui-clicks
```

**Limits:** P60 currently verifies **nonblocking, process-owned Win32
`#32770` dialog windows**. It does not claim generic modal file-dialog
operation, save/load semantics, arbitrary popup menus, a custom-painted
in-plugin overlay, or full commercial DAW automation. Plugins may execute
destructive actions on clicks: only use trusted disposable test projects.
The earlier P10 test has a separate real native Save dialog cancellation
path for the specific Drumator integration. P60 does not assume every
instrument exposes standard HWND windows.

Every P60 report preserves `release_approved: false`.
No production Drumator or AWE code is modified.
