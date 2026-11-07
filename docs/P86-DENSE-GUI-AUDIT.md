# P86 — Extended unknown-plugin GUI observation coverage

P82–P85 already perform optionally approved, sham-controlled native Win32 GUI observation with fresh-process repeatability, but up to 16 exploratory points per invocation. P86 adds a denser **3×3 or 5×5 actual editor grid**. It measures the real editor window, generates internal grid centers, groups them into native P42 shards of no more than 16 positions, and verifies every coordinate was observed. A full 5×5 sweep has **25** points, with two sharded invocations (**16 + 9**) and optional two independent sham/click observation repetitions per point.

The resulting review evidence gives: actual editor dimensions, every sampled coordinate, parameter IDs changed, before/after normalized values, visual change categories, no-observed-change positions and the complete per-shard native evidence. A failed shard, missing report, wrong module SHA, malformed point or disagreement between repetitions yields FAIL. An unobserved pixel or an untested side effect is never reported as covered.

## Explicit opt-in

Use only on a disposable Windows test VM with disposable non-sensitive files: clicking unknown controls may open dialogs, export files or modify settings.

```powershell
python tests/run_universal_qa.py --plugin C:\QA\Unknown.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\GuiAudit --explore-unknown-gui --dense-gui-grid 5 --exploration-repeats 2
```

The same feature is available in P83's multi-plugin selection manifest through the per-plugin keys `"explore_unknown_gui": true`, `"dense_gui_grid": 5` and `"exploration_repeats": 2`. Non-selected plugins remain read-only. A dense scan intentionally cannot combine with manually supplied coordinates, and rejects unsupported grid sizes, unsupported repetition counts or missing opt-in.

For source-built native acceptance CI, a 3×3 grid is tested against two real Windows VST3 editors: one with an active center GUI button and one deliberately inert. The 5×5 two-shard coverage is additionally exercised in Python tests with adversarial missing/incorrect evidence.

**Scope and limitations:** `SAMPLED_GRID_COMPLETE` proves only that all **sample points** were tested; it never establishes the meaning or correctness of a control, complete control discovery, safe actions, DAW behavior, physical ASIO or release readiness. The report explicitly sets `all_controls_discovered: false`, `control_semantics: NOT ESTABLISHED` and `release_approved: false`. Reviewed P65/P67 functional specifications remain necessary for product-level PASS.
