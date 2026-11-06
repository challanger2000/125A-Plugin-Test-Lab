# P61 — Native VST3 dialog button navigation, real Win32

P61 extends P60 from observing owned dialogs to **operating a genuine Win32
button inside the newly opened dialog**. The real test host attaches the
VST3 editor, clicks an independently supplied trigger coordinate, checks
for one process-owned visible `#32770` dialog, obtains the actual child
`Button` with independently approved control ID `43061`, verifies that it
is visible and enabled, dispatches real Windows `BM_CLICK` and checks
that the dialog closes.

Two source-built VST3 test fixtures prove the check:
- Good: actual native dialog, real standard child Win32 `BUTTON` control
  ID 43061, and a popup that closes on `BM_CLICK`.
- NoButton: actual native dialog opens, but the required child button is
  deliberately absent. P61 must fail, not infer an action from controller
  state or from a screenshot.

The Python independent verifier checks the complete native report and
rejects missing, forged, wrong-ID, wrong-class or non-dismissing button
records. Native process failures fail the contract.

```powershell
python tests/run_gui_owned_dialog.py --plugin "C:\QA\Fixture.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P61" --x 160 --y 90 --acknowledge-ui-clicks --exercise-dialog-button
```

The `43061` action ID is an explicitly verified *fixture* contract,
**not a universal assumption for arbitrary VST3 dialogs**. P61 does not
independently discover which buttons should be pressed in other products;
such interactions need separately approved semantic contracts, as
unexpected clicks can change data. Custom-painted UI overlays, blocking
file dialogs, deep nested menus, and real commercial DAW sessions remain
not covered. No Drumator or AWE production code changes are made, and
no release is approved by this test.
