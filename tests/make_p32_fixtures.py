#!/usr/bin/env python3
"""P32 synthetic fixture adapters used solely to prove the universal runner."""
import argparse
import hashlib
import json
from pathlib import Path


def binary(bundle):
    files = [p for p in bundle.rglob("*.vst3") if p.is_file()]
    assert len(files) == 1, "exactly one module binary required"
    return files[0]


def manifest(exe, bundle, expected, identity):
    target = binary(bundle)
    return {
        "schema": "125a-p32-adapter-v1",
        "product": {
            "name": identity, "version": "0.1.0-synthetic",
            "commit_sha": "0" * 40,
            "binary": str(target.resolve()),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        },
        "host": str(exe.resolve()),
        "cases": [
            {"id": "playback_44100", "rate": 44100, "block": 64,
             "iterations": 2500, "mode": "save-only",
             "assertions": {
                "result": {"eq": "PASS"},
                "save_failures": {"eq": 0},
                "process_failures": {"eq": 0},
                "save_success": {"eq": 500},
                "callbacks": {"eq": 2500},
                "domain_correctness": {"eq": "NOT_COVERED"},
            }},
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--good", type=Path, required=True)
    p.add_argument("--bad", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    good = manifest(a.host, a.good, "PASS", "P32 Synthetic Good")
    bad = manifest(a.host, a.bad, "FAIL", "P32 Synthetic Broken Save")
    tampered = json.loads(json.dumps(good))
    tampered["product"]["sha256"] = "f" * 64
    missing = json.loads(json.dumps(good))
    del missing["cases"][0]["assertions"]["save_failures"]
    for name, data in (("good", good), ("broken", bad),
                       ("wrong_hash", tampered), ("missing_oracle", missing)):
        (a.out / (name + ".json")).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("[PASS] P32 fixture-adapters generated with pinned binary digest and explicit oracle")


if __name__ == "__main__":
    main()
