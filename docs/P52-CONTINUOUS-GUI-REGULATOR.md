# P52 — Actual continuous GUI controller proof (Windows)

P51 established a native drag sequence, but its end-to-end test fixture was
binary. P52 extends the independent native VST3 fixture with two new **actual
Windows VST3 variants**, both source-built on Windows 2022:

- `125A_QA_GUI_AnalogGood`: an exposed continuously variable VST3 parameter
  with normalized mapping `clamp((mouse_x - 40)/240, 0, 1)`. Its native editor
  responds to button-held mouse movement and release, not just static clicks.
- `125A_QA_GUI_AnalogBad`: exposes the same interface and looks similar, but
  internally quantizes every value to 0 or 1. It must fail the **same**
  independent expected-value contract.

P52 CI drives five sequential native gestures in one live editor window:
`0 → 0.25 → 0.50 → 0.75 → 1.00 → 0`. The existing P51 verifier independently
checks the before and after controller value for each real native Windows drag
and expects the bad fixture to produce native FAIL evidence at an intermediate
checkpoint. A mere green exit code is not considered sufficient: the negative
fixture must fail for an actual parameter mismatch.

This demonstrates detecting a real *continuous-control* defect in the shared
test host. It does not certify arbitrary GUI knobs without a separately
approved mapping of expected values, parameter IDs and physical coordinates,
or smoothness at every point between checkpoints. Menus, file dialogs and
commercial DAW workflows remain outside P52 coverage.

No Drumator, AWE, or commercial plugin source was touched.
