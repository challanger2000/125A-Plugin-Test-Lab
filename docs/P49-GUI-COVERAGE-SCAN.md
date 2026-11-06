# P49 — bounded multi-pass native GUI sampling

P49 extends the existing P42–P44 sham-controlled GUI probes beyond a single
9/16-point grid. It samples 8×8 physical tile centers by default, in four
isolated passes of at most 16 points using the already verified native host.
Each sampled coordinate is independently clicked and sham-checked in fresh
plugin processes. Host and VST3 DLL SHA-256 identities are checked across
passes; incomplete, stale or forged batch evidence fails closed.

## Run on Windows with a trusted VST3 only

```powershell
python tests/run_gui_coverage_scan.py --plugin "C:\QA\MyPlugin.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P49" --columns 8 --rows 8 --acknowledge-ui-clicks
```

Windows GitHub Actions runners already provide Python. The user's Windows
computer does not need Python if CI performs the execution.

The output `GUI-COVERAGE-SCAN.json` records inspected tile centers, sham
attribution, instability, clickable-change candidates and exact DLL/host hashes.
Each batch keeps its original P42–P44 report, screenshots and logs.

**Important limitations:** Physical tile centers do not prove complete
discovery of controls between centers, in menus, hidden tabs, scroll panes
or dynamically shown content. An observed click, color or VST3 parameter change
is not proof the product does what it should. Some sampled points may trigger
export, erase, load, or other side effects; use disposable trusted test data.
A dense scan can take time because each click and its sham uses fresh processes.
This is **not** an automatic DAW integration test or a release approval.

The report intentionally always says `product_gui_controls: NOT COVERED`,
`independent_product_semantics: NOT COVERED`,
`commercial_daw_integration: NOT COVERED` and
`release_approved: false`.

P49 Windows CI tests sampler invariants and adversarial forged evidence using
a fake native process, **not** a real native VST3 end-to-end run. A successful
P49 unit CI must never be confused with a successful actual-plugin scan.

## Next required work

True universal GUI coverage needs native Windows accessibility/control-tree
inspection where available, dynamic menus and tabs, controlled navigation,
independently approved expected functional outcomes and real host DAW sessions.
Do not mark these as covered from P49 observations.
