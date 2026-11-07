# P88 — Owner review queue for unknown VST3 UI functionality

P68 reads an actual VST3's controller parameter inventory. P86 uses sham-controlled native clicks to measure changes at a bounded set of editor coordinates. P87 compares both independent sources. P88 turns the raw observations into a **review queue** listing every native VST3 ParameterID, current and default normalized values, and locations where a sham-controlled click changed that parameter. It separately lists sampled visual-only effects.

This reduces the manual work required to document unfamiliar plugins without falsely assuming what a control means. A product owner can use the queue to identify controls and supply independent expected values, WAV/MIDI/audio reference material, and semantic requirements for future approved P65/P67 tests.

## Generate

On an isolated disposable Windows environment, run:

```powershell
python tests/run_universal_qa.py --plugin C:\QA\Unknown.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\Result --explore-unknown-gui --dense-gui-grid 5 --crosscheck-abi-gui
python tests/run_gui_owner_review_queue.py --capabilities C:\QA\Result\discovery\vst3-inventory\native-capabilities.tsv --parameters C:\QA\Result\discovery\vst3-inventory\native-parameters.tsv --dense-report C:\QA\Result\unknown-gui-dense-sweep\DENSE-GUI-AUDIT-RESULT.json --out C:\QA\Result\review
```

The output `OWNER-GUI-REVIEW-QUEUE.json` has exact source SHA-256 fingerprints and separate entries for **observed** and **unobserved** ABI parameters. A parameter not observed at the grid positions may nevertheless work perfectly. Multiple positions affecting one ParameterID are explicitly marked ambiguous. Visual-only controls remain unlabelled, and their independent pixel oracle must be supplied before executable verification.

**Crucial:** Every proposed control name, functional expected state, and audio reference is deliberately `null`. The output contains `approved_to_execute: false` for all parameter entries, `executable_p65_plan_generated: false`, and `release_approved: false`. It never automatically runs or approves newly discovered GUI controls. This is review preparation, not semantic or musical verification.

Windows CI validates source-built interactive/inert VST3 fixtures, source identity, parameter gap reconciliation and fail-closed malformed evidence. Product-specific acceptance, commercial DAW sessions and physical ASIO hardware are still separate requirements.
