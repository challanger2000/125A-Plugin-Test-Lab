#!/usr/bin/env python3
"""P44: Bounded pixel-change localization for custom-painted VST3 GUI controls.

Only locate changes already attributed by independent sham-vs-click runs.
The output is evidence for human review, not an approved GUI oracle.
"""
from collections import deque

MAX_CHANGED_PIXELS = 4_194_304
TILE = 12
MAX_REGIONS = 12


def locate_change_regions(before, after, *, tile=TILE, limit=MAX_REGIONS):
    """Locate connected painted-change tiles, with exact pixel bounding boxes.

    BMP channels are B,G,R in the existing native exploration reader.
    The sample supplied to independently approved GUI workflow profiles
    must be converted to R,G,B.
    """
    if (not isinstance(before, tuple) or not isinstance(after, tuple) or
            len(before) != 3 or len(after) != 3 or
            before[:2] != after[:2]):
        raise ValueError("incompatible real GUI pixel snapshots")
    width, height, original = before
    _, _, changed = after
    if (type(width) is not int or type(height) is not int or
            width < 1 or height < 1 or width * height > MAX_CHANGED_PIXELS or
            len(original) != width * height * 3 or
            len(changed) != width * height * 3 or
            not isinstance(original, bytes) or
            not isinstance(changed, bytes)):
        raise ValueError("invalid bounded Win32 BGR frame data")
    if type(tile) is not int or not 4 <= tile <= 64:
        raise ValueError("invalid GUI change region tile size")
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("invalid change region report limit")

    # Each tile stores exact changed-pixel bounds and a physical RGB pair.
    # Do not allocate a full Python object per pixel in a 4MP GUI.
    bins = {}
    total = 0
    for pixel in range(width * height):
        offset = pixel * 3
        a = original[offset:offset + 3]
        b = changed[offset:offset + 3]
        if a == b:
            continue
        total += 1
        x = pixel % width
        y = pixel // width
        key = (x // tile, y // tile)
        data = bins.get(key)
        if data is None:
            bins[key] = [x, y, x, y, 1, x, y,
                         [a[2], a[1], a[0]], [b[2], b[1], b[0]]]
        else:
            data[0] = min(x, data[0])
            data[1] = min(y, data[1])
            data[2] = max(x, data[2])
            data[3] = max(y, data[3])
            data[4] += 1

    regions = []
    pending = set(bins)
    # Eight-neighbour tiles group contiguous painted fragments, but never
    # claim the boxes correspond to semantic widget boundaries.
    while pending:
        seed = min(pending, key=lambda v: (v[1], v[0]))
        pending.remove(seed)
        stack = deque([seed])
        xmin, ymin = width, height
        xmax = ymax = 0
        count = 0
        samples = []
        while stack:
            cx, cy = stack.popleft()
            a = bins[cx, cy]
            xmin = min(xmin, a[0])
            ymin = min(ymin, a[1])
            xmax = max(xmax, a[2])
            ymax = max(ymax, a[3])
            count += a[4]
            samples.append((a[5], a[6], a[7], a[8]))
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if (nx, ny) in pending:
                        pending.remove((nx, ny))
                        stack.append((nx, ny))
        samples.sort(key=lambda p: (
            abs(p[0] - ((xmin + xmax) // 2)) +
            abs(p[1] - ((ymin + ymax) // 2)), p[1], p[0]))
        x, y, before_rgb, after_rgb = samples[0]
        regions.append({
            "bbox_xyxy": [xmin, ymin, xmax + 1, ymax + 1],
            "changed_pixels": count,
            "sample": {"x": x, "y": y,
                       "before_rgb": before_rgb, "after_rgb": after_rgb},
            "semantic_control": "UNKNOWN",
            "independent_oracle": "NOT APPROVED",
        })
    regions.sort(key=lambda region: (
        -region["changed_pixels"], region["bbox_xyxy"][1],
        region["bbox_xyxy"][0]))
    if sum(region["changed_pixels"] for region in regions) != total:
        raise ValueError("lost GUI pixels in candidate region inventory")
    observed = regions[:limit]
    for region in observed:
        xmin, ymin, xmax, ymax = region["bbox_xyxy"]
        if (xmin < 0 or ymin < 0 or xmax > width or ymax > height or
                not xmin < xmax or not ymin < ymax):
            raise ValueError("invalid local visual change bounds")
        sample = region["sample"]
        if (not xmin <= sample["x"] < xmax or
                not ymin <= sample["y"] < ymax or
                sample["before_rgb"] == sample["after_rgb"]):
            raise ValueError("invalid proposed physical pixel sample")
    return {
        "painted_pixels_changed": total,
        "observed_region_count": len(regions),
        "reported_region_count": len(observed),
        "truncated": len(observed) < len(regions),
        "tile_size": tile,
        "regions": observed,
        "localization": (
            "NO_VISUAL_CHANGE" if total == 0 else
            "BROAD_CHANGE_REVIEW" if total > width * height // 4 else
            "LOCALIZED_CANDIDATES"),
    }


def create_review_draft(report):
    """Make a review-only document, NEVER an approved executable manifest."""
    if (not isinstance(report, dict) or
            report.get("status") != "OBSERVATIONS_COMPLETE" or
            report.get("sham_control") != "COMPLETE" or
            report.get("requested_points") != report.get("completed_points") or
            report.get("completed_points") != report.get("sham_verified_points") or
            report.get("product_gui_controls") != "NOT COVERED" or
            report.get("release_approved") is not False):
        raise ValueError("cannot draft GUI controls from incomplete or falsely approved scan")
    if len(report.get("probes", [])) != report["completed_points"]:
        raise ValueError("GUI candidate draft missing native exploration observations")
    candidates = []
    for number, observation in enumerate(report["probes"]):
        if (observation.get("sham_control_attribution") != "SUPPORTED" or
                observation.get("classification") in (
                    "NO_OBSERVED_CHANGE", "UNSTABLE_CONTROL")):
            continue
        pixel = observation.get("pixel_localization", {})
        has_pixel = (pixel.get("localization") == "LOCALIZED_CANDIDATES" and
                     pixel.get("reported_region_count", 0) > 0)
        parameters = observation.get("changed_parameters", [])
        # Do not claim to have identified a control when a large part of the
        # UI repaints, or when no single observed parameter/pixel can describe
        # the result. Such areas need explicit product investigation.
        suggestion = None
        if len(parameters) == 1:
            p = parameters[0]
            suggestion = {
                "action": "click",
                "x": observation["x"], "y": observation["y"],
                "param_id": p["param_id"],
                "before_normalized": p["before_normalized"],
                "expected_normalized": p["after_normalized"],
            }
            if has_pixel:
                sample = pixel["regions"][0]["sample"]
                suggestion["screenshot"] = True
                suggestion["expected_pixel"] = {
                    "x": sample["x"], "y": sample["y"],
                    "rgb": sample["after_rgb"],
                }
        elif not parameters and has_pixel:
            sample = pixel["regions"][0]["sample"]
            suggestion = {
                "action": "click", "x": observation["x"], "y": observation["y"],
                "screenshot": True, "visual_oracle": {
                    "x": sample["x"], "y": sample["y"],
                    "before_rgb": sample["before_rgb"],
                    "after_rgb": sample["after_rgb"],
                },
            }
        candidates.append({
            "probe_index": number,
            "click": [observation["x"], observation["y"]],
            "classification": observation["classification"],
            "pixel_localization": pixel,
            "parameters_changed": parameters,
            "suggested_test_action": suggestion,
            "approved_for_execution": False,
            "requires_independent_product_review": True,
        })
    return {
        "schema": "125a-gui-control-review-draft-v1",
        "status": "REVIEW_REQUIRED",
        "verified_module_sha256": report["verified_module_sha256"],
        "verified_gui_host_sha256": report["verified_gui_host_sha256"],
        "source_exploration_status": report["status"],
        "candidate_count": len(candidates),
        "candidates": candidates,
        "product_gui_controls": "NOT COVERED",
        "release_approved": False,
        "automatically_approved_oracles": 0,
        "executable_workflow_manifest": "NOT GENERATED",
    }
