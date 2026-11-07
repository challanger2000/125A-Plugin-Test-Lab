# P67 — Required product-feature coverage matrix (fail-closed)

A technically green VST3 test run proves **only what it tested**.
P67 adds a separate independent product-owner feature inventory that maps
every declared required feature to one or more explicitly approved P65/P66
test-case IDs. It cannot infer the *complete* feature list from the VST3
binary, its controller parameters, the UI screenshot, or a GitHub workflow.

## Add the coverage matrix to a product-specific test plan run

Use the existing versioned P65 product test plan unchanged, and a separately
reviewed feature matrix:

```json
{
  "schema": "125a-product-feature-matrix-v1",
  "product_id": "drumator",
  "module_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "features": [
    {
      "id": "beat_creator",
      "title": "Beat Creator generates and applies an expected groove",
      "criticality": "required",
      "case_ids": ["beat_creator_generate"],
      "waiver": null
    },
    {
      "id": "midi_export",
      "title": "MIDI export matches expected timeline and event content",
      "criticality": "required",
      "case_ids": [],
      "waiver": null
    },
    {
      "id": "optional_debug",
      "title": "Non-shipping debug view is not part of the product",
      "criticality": "optional",
      "case_ids": [],
      "waiver": {
        "disposition": "not_applicable",
        "reason": "This test-only debug view is not shipped in the product"
      }
    }
  ]
}
```

These IDs are **illustrative**, not a claim that the Drumator Beat Creator
or export checks are already available in the generic P65/P66 runner.
The plan must actually declare any listed `case_ids`. Unimplemented
features are declared with empty `case_ids`, which yields
`NOT COVERED` and blocks required coverage completion. Do not invent a
PASS result for a test adapter that does not exist.

Run on Windows with the exact pinned VST3/host executables:

```powershell
python tests/run_product_test_plan.py --plan C:\QA\plan.json --coverage-matrix C:\QA\features.json --out C:\QA\results
```

P67 produces `PRODUCT-FEATURE-COVERAGE.json` and adds these fields to
the regular `PRODUCT-TEST-PLAN-RESULT.json`:
`required_feature_coverage` and `required_feature_gaps`.

Each feature is classified as:
- `PASS`: all linked native cases actually passed with complete action counts
- `FAIL`: any linked case failed
- `NOT RUN`: linked cases exist but were skipped or incomplete
- `NOT COVERED`: no available approved test case was linked
- `NOT APPLICABLE`: a specifically justified **optional** feature does not apply

Every **required** feature must be `PASS` for
`REQUIRED_COVERAGE_COMPLETE`. Any required gap yields
`REQUIRED_COVERAGE_INCOMPLETE` and a nonzero exit code, **even when all
executed technical checks are green**. Required features cannot be waived.
Wrong hashes, wrong/duplicate/unrecognized case IDs, malformed waivers,
mismatched products or forged per-case counts are rejected.

Without a separate approved matrix, existing P65/P66 tests remain
backward compatible, but the summary explicitly reports
`required_feature_coverage: NOT DECLARED`; such a report never
constitutes complete coverage.

## Responsibility and limits

Each product-owning development chat must maintain a reviewable list of
features for its product and link each requirement to independent native
test evidence. **The feature list is user/product-author supplied, not
automatically discovered or certified complete by P67.** A required
feature omitted from the entire matrix cannot be detected merely by a
green technical test. Product release processes should independently
review this inventory before treating coverage as adequate.

Passing declared required features **does not** set
`full_product_functional_coverage` to complete and never sets
`release_approved` to true. Native hardware ASIO and commercial DAW
session validation remain `NOT RUN`. As additional standardized
adapters become available, new required cases can be linked without
modifying the coverage engine.

The P67 Windows CI demonstrates the critical counterexample with a
genuine source-built VST3: bidirectional controls PASS, but an explicitly
declared, untested MIDI export requirement remains NOT COVERED and the
coverage gate FAILS.
