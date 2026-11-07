# P93 — Targeted GitHub Actions, instead of rebuilding everything

**Problem:** Updating `CMakeLists.txt` previously triggered roughly 15 expensive Windows workflows at once, including product-specific Drumator and AWE acceptance, GUI integration and ASIO host checks. The baseline Windows P02 workflow also ran on every pull request.

**New automatic routing:** For ordinary pull requests and main pushes, `windows.yml` runs on CMake, the native base host/fixture, the independent core audio/VST3 oracle scripts, or edits to its own workflow. Product/GUI/ASIO integration workflows still run when their **own source, tests, or workflow file** changes. The shared `CMakeLists.txt` entry has been removed from 14 expensive workflows. Unrelated CMake edits therefore no longer trigger 14 complete builds. New changes to a specialized fixture or implementation continue to trigger its corresponding workflow.

**Manual complete verification is preserved:** All 15 affected workflows retain `workflow_dispatch` in Actions. For a release candidate, manually run the desired full suite, including product-specific tests, and review the preserved individual results. A green core build must never be interpreted as proof that the full test lab ran.

**Stale-run cancellation:** Affected expensive workflows without pre-existing concurrency now cancel older runs on the same PR (but do **not** cancel manually requested release/hardware tests). Existing workflow-specific concurrency settings stay intact. On the P93 routing changes themselves, workflow files intentionally match their own path filters; a one-off validation fan-out is expected, but later ordinary CMake edits should run only the core P02 gate.

A lightweight, separate Linux P93 job validates these routing invariants without compiling or downloading any VST3 plugin or DAW. Product-source repositories remain untouched.

**Limitations:** GitHub Actions triggers follow file paths, not an actual C++ dependency graph. A core CMake change can affect multiple targets; before a release, manually run all relevant integration suites. If shared host/GUI source changes, affected workflows will still run by design. No CI optimization may be considered a replacement for missing feature, REAPER, or physical-ASIO evidence.
