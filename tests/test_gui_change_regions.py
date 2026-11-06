#!/usr/bin/env python3
"""P44 adversarial pixel localization and draft-only GUI workflow oracles."""
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location(
    "regions", Path(__file__).with_name("gui_change_regions.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def canvas(width, height, background=(30, 36, 48), patches=()):
    # Match the explorer's BGR pixel representation, not an RGB PNG.
    bgr = bytes(reversed(background))
    frame = bytearray(bgr * (width * height))
    for x0, y0, x1, y1, color in patches:
        for y in range(y0, y1):
            for x in range(x0, x1):
                frame[(y * width + x) * 3:(y * width + x) * 3 + 3] = (
                    bytes(reversed(color)))
    return width, height, bytes(frame)


before = canvas(64, 40)
after = canvas(64, 40, patches=[
    (4, 6, 14, 14, (12, 142, 85)), (42, 22, 50, 28, (200, 20, 40))])
regions = mod.locate_change_regions(before, after, tile=8)
assert regions["painted_pixels_changed"] == 128
assert regions["observed_region_count"] == 2
assert regions["reported_region_count"] == 2
assert not regions["truncated"]
assert regions["localization"] == "LOCALIZED_CANDIDATES"
a, b = regions["regions"]
assert a["bbox_xyxy"] == [4, 6, 14, 14] and a["changed_pixels"] == 80
assert b["bbox_xyxy"] == [42, 22, 50, 28] and b["changed_pixels"] == 48
for r in (a, b):
    assert r["independent_oracle"] == "NOT APPROVED"
    assert r["semantic_control"] == "UNKNOWN"
    assert r["sample"]["before_rgb"] == [30, 36, 48]
assert a["sample"]["after_rgb"] == [12, 142, 85]
assert b["sample"]["after_rgb"] == [200, 20, 40]
assert mod.locate_change_regions(before, before)["painted_pixels_changed"] == 0
assert mod.locate_change_regions(before, before)["regions"] == []

single = mod.locate_change_regions(
    canvas(320, 180, patches=[(120, 65, 200, 115, (70, 80, 90))]),
    canvas(320, 180, patches=[(120, 65, 200, 115, (12, 142, 85))]))
assert single["painted_pixels_changed"] == 4000, single
assert single["regions"][0]["bbox_xyxy"] == [120, 65, 200, 115]
assert single["regions"][0]["sample"]["before_rgb"] == [70, 80, 90]
assert single["regions"][0]["sample"]["after_rgb"] == [12, 142, 85]
assert single["localization"] == "LOCALIZED_CANDIDATES"

full = mod.locate_change_regions(before, canvas(64, 40, (10, 20, 30)))
assert full["localization"] == "BROAD_CHANGE_REVIEW"
assert full["painted_pixels_changed"] == 64 * 40

# Separate region cap remains explicit, never silently reports all controls.
limited = mod.locate_change_regions(before, after, tile=8, limit=1)
assert limited["reported_region_count"] == 1
assert limited["observed_region_count"] == 2
assert limited["truncated"] is True

for wrong in (
    lambda: mod.locate_change_regions(before, canvas(32, 40)),
    lambda: mod.locate_change_regions((64, 40, b"x"), after),
    lambda: mod.locate_change_regions(before, after, tile=1),
    lambda: mod.locate_change_regions(before, after, limit=0),
    lambda: mod.locate_change_regions(before, after, limit=100),
):
    try:
        wrong()
    except ValueError:
        pass
    else:
        raise AssertionError("invalid image/limit was accepted")

report = {
    "status": "OBSERVATIONS_COMPLETE", "sham_control": "COMPLETE",
    "requested_points": 1, "completed_points": 1, "sham_verified_points": 1,
    "verified_module_sha256": "0" * 64,
    "verified_gui_host_sha256": "a" * 64,
    "product_gui_controls": "NOT COVERED", "release_approved": False,
    "probes": [{
        "x": 160, "y": 90, "sham_control_attribution": "SUPPORTED",
        "classification": "VISUAL_CHANGE", "changed_parameters": [],
        "pixel_localization": single,
    }],
}
review = mod.create_review_draft(report)
assert review["schema"] == "125a-gui-control-review-draft-v1"
assert review["status"] == "REVIEW_REQUIRED"
assert review["candidate_count"] == 1
assert review["automatically_approved_oracles"] == 0
assert review["executable_workflow_manifest"] == "NOT GENERATED"
assert review["release_approved"] is False
proposed = review["candidates"][0]
assert proposed["approved_for_execution"] is False
assert proposed["requires_independent_product_review"] is True
assert proposed["suggested_test_action"]["action"] == "click"
assert proposed["suggested_test_action"]["visual_oracle"]["before_rgb"] == [70, 80, 90]
assert proposed["suggested_test_action"]["visual_oracle"]["after_rgb"] == [12, 142, 85]

one_parameter = dict(report)
one_parameter["probes"] = [dict(report["probes"][0],
    classification="PARAMETER_AND_VISUAL_CHANGE",
    changed_parameters=[{"param_id": 9001,
                         "before_normalized": 0.0,
                         "after_normalized": 1.0}])]
param_review = mod.create_review_draft(one_parameter)
assert param_review["candidates"][0]["suggested_test_action"]["param_id"] == 9001
assert param_review["candidates"][0]["suggested_test_action"]["expected_pixel"]["rgb"] == [12, 142, 85]

broad = dict(report)
broad["probes"] = [dict(report["probes"][0], pixel_localization=full)]
assert mod.create_review_draft(broad)["candidates"][0]["suggested_test_action"] is None

unresolved = dict(report)
unresolved["probes"] = [dict(report["probes"][0],
                           classification="UNSTABLE_CONTROL",
                           sham_control_attribution="UNSTABLE")]
assert mod.create_review_draft(unresolved)["candidate_count"] == 0

for name, value in (
        ("status", "FAIL"), ("sham_control", "FAIL"),
        ("completed_points", 0), ("sham_verified_points", 0),
        ("release_approved", True), ("product_gui_controls", "PASS"),
        ("probes", [])):
    corrupt = dict(report)
    corrupt[name] = value
    try:
        mod.create_review_draft(corrupt)
    except ValueError:
        pass
    else:
        raise AssertionError("forged or truncated scan produced approved draft: " + name)

print("[PASS] P44 local changes in drawn GUI controls are found but never auto-approved")
