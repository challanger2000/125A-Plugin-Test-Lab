# P69 — Native HWND-guided GUI exploration (universal VST3)

Existing P42–P45 sham-controlled click exploration probes a generic 3×3
or 4×4 grid. P69 adds **real, read-only native Win32 control-center
discovery** using the existing P54 HWND control-tree evidence.

P69 examines the VST3 editor's actual Win32 child hierarchy and
proposes the center coordinates of visible, enabled, **standard
Button/Checkbox/RadioButton HWND** controls only. It excludes native
text/edit fields, lists, unknown classes, hidden/disabled children,
off-editor controls, repeated click coordinates and anything exceeding
the fixed 16-point budget. The output contains observed real control
IDs and the source HWND indices rather than guessed GUI coordinates.

## Default: no clicks

```powershell
python tests/run_gui_hwnd_guided.py --plugin "C:\QA\Plugin.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\gui-candidates"
```

Produces `HWND-GUIDED-RESULT.json` and the original P54
`HWND-CONTROL-TREE.json`. Report state
`actual_exploration_status: NOT RUN` means no controls have been
clicked; proposed button centers have **no approved product semantics**.

## Explicitly acknowledged, bounded native test

**Only on disposable, isolated test environments** with a plugin
whose GUI actions have been reviewed as safe:

```powershell
python tests/run_gui_hwnd_guided.py --plugin "C:\QA\Plugin.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\gui-probes" --acknowledge-ui-clicks --max-points 9
```

P69 delegates actual clicks to the existing P42 sham-controlled
exploration: each click and its sham comparison run in fresh real VST3
instances; pre/post plugin state and genuine Win32 screenshots determine
whether a change can be attributed to the click. No isolated click
observation constitutes a claim of correct business or musical
semantics. P45 same-instance round-trip can be applied later when
appropriate.

**Coverage limit:** Native HWND controls are not the same as all VSTGUI
custom-painted controls. Unexposed buttons and popup items require
visual change-region discovery and independent product expectations.
P69 does not click arbitrary grid positions in its guided mode and
does not auto-operate file dialogs, hidden actions, destructive controls
or external export destinations. Its default is always **read-only**.
No product release, ASIO, DAW, export or full GUI coverage is certified.

Real Windows CI proves that P69 finds the nested 43001 BUTTON at
(160,90) inside an actual source-built VST3 editor **without hardcoded
fixture coordinates in the detector**, then separately verifies the
opt-in click with a sham-control probe and VST3 parameter observation.
No product code is modified.
