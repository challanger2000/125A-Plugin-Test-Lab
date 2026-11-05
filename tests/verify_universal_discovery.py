#!/usr/bin/env python3
"""Independent, product-agnostic VST3 capability parser/oracle for P22."""
import argparse
import json
import pathlib
import sys

def check(text: str, expected_min_classes: int = 1):
    classes = {}
    bus_counts = {}
    buses = {}
    formats = []
    total = None
    for raw in text.splitlines():
        if not raw.startswith("P22_"):
            continue
        cols = raw.split("\t")
        tag = cols[0]
        if tag == "P22_FORMAT":
            assert len(cols) == 2 and cols[1] == "1", "unknown format"
            formats.append(tag)
        elif tag == "P22_CLASS":
            assert len(cols) == 5, "invalid class row"
            n = int(cols[1])
            assert n not in classes and n > 0
            assert all(c in ("0", "1") for c in cols[2:])
            classes[n] = dict(processor=bool(int(cols[2])), sample32=bool(int(cols[3])), sample64=bool(int(cols[4])))
        elif tag == "P22_BUS_COUNT":
            assert len(cols) == 5, "invalid bus count row"
            n = int(cols[1])
            kind, direction = cols[2:4]
            assert kind in ("audio", "event") and direction in ("input", "output")
            key = (n, kind, direction)
            assert key not in bus_counts
            num = int(cols[4])
            assert 0 <= num <= 64
            bus_counts[key] = num
        elif tag == "P22_BUS":
            assert len(cols) == 7, "invalid bus row"
            n = int(cols[1])
            kind, direction = cols[2:4]
            i, channels, enabled = map(int, cols[4:7])
            assert 0 <= channels <= 64 and enabled in (0, 1)
            key = (n, kind, direction)
            buses.setdefault(key, {})
            assert i not in buses[key]
            buses[key][i] = dict(channels=channels, default_active=bool(enabled))
        elif tag == "P22_TOTAL":
            assert len(cols) == 2 and total is None
            total = int(cols[1])
        else:
            raise AssertionError("unknown P22 row " + tag)
    assert len(formats) == 1, "missing or repeated format declaration"
    assert total is not None and total == len(classes) and total >= expected_min_classes
    assert sorted(classes) == list(range(1, total + 1)), "class indices not consecutive"
    out = []
    for n in sorted(classes):
        item = {"class_index": n, **classes[n], "buses": {}}
        assert item["processor"], "audio class without processor interface"
        for kind in ("audio", "event"):
            for direction in ("input", "output"):
                key = (n, kind, direction)
                assert key in bus_counts, "missing bus category: " + str(key)
                n_buses = bus_counts[key]
                found = buses.get(key, {})
                assert sorted(found) == list(range(n_buses)), "bus enumeration mismatch " + str(key)
                item["buses"][kind + "_" + direction] = [found[i] for i in range(n_buses)]
        item["recommended_gates"] = {
            "host_lifecycle": "ELIGIBLE",
            "sample32_processing": "ELIGIBLE" if item["sample32"] and item["buses"]["audio_output"] else "NOT_APPLICABLE",
            "midi_input": "ELIGIBLE" if item["buses"]["event_input"] else "NOT_APPLICABLE",
            "external_audio_input": "ELIGIBLE" if item["buses"]["audio_input"] else "NOT_APPLICABLE",
            "gui_automation": "NOT_YET_DETERMINED",
            "state_recall": "NOT_YET_DETERMINED",
        }
        out.append(item)
    return {"schema": "125a-vst3-universal-discovery-v1", "status": "PASS", "classes": out,
            "disclaimer": "Eligibility is not execution; no render, GUI or recall PASS claimed."}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=pathlib.Path)
    ap.add_argument("output", type=pathlib.Path)
    ap.add_argument("--minimum-classes", type=int, default=1)
    args = ap.parse_args()
    try:
        data = check(args.log.read_text(encoding="utf-8-sig"), args.minimum_classes)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("[PASS] P22 universal VST3 discovery:", len(data["classes"]), "audio class(es)")
    except (AssertionError, ValueError, OSError) as error:
        print("[FAIL] P22 universal discovery oracle:", error, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
