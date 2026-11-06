#!/usr/bin/env python3
"""P59 read-only physical ASIO registry discovery and pinned P56 plan creation.

Used ONLY on an explicitly opted-in, local interactive Windows workstation.
Never runs a device, installs drivers or returns hardware qualification.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from run_physical_asio import SCHEMA, digest, validate, CLSID

ASCII_NAME = re.compile(r"^[^\\/\x00-\x1f]{1,128}$")


def registry_clsid(name):
    if not isinstance(name, str) or not ASCII_NAME.fullmatch(name):
        raise ValueError("invalid single registered ASIO driver name")
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\ASIO\\" + name) as key:
        value, kind = winreg.QueryValueEx(key, "CLSID")
    if kind != winreg.REG_SZ or not isinstance(value, str) or not CLSID.fullmatch(value):
        raise ValueError("ASIO driver registry CLSID missing or malformed")
    return value


def generate(plugin, executor, driver_name, *, rate=44100, frames=128,
             callbacks=12000, registry_reader=registry_clsid, platform=sys.platform):
    if platform != "win32":
        raise ValueError("P59 needs a real Windows ASIO driver registry")
    if not isinstance(driver_name, str) or not ASCII_NAME.fullmatch(driver_name):
        raise ValueError("invalid ASIO driver registry key")
    plugin = Path(plugin).resolve(strict=True)
    executor = Path(executor).resolve(strict=True)
    clsid = registry_reader(driver_name)
    if not isinstance(clsid, str) or not CLSID.fullmatch(clsid):
        raise ValueError("local ASIO registry produced invalid CLSID")
    plan = {
        "schema": SCHEMA,
        "product": {"path": str(plugin), "sha256": digest(plugin)},
        "executor": {"path": str(executor), "sha256": digest(executor)},
        "asio_driver": {"name": driver_name, "clsid": clsid},
        "scenarios": [{"sample_rate": rate, "buffer_frames": frames,
                       "callbacks": callbacks}]
    }
    validate(plan)
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin", type=Path, required=True)
    p.add_argument("--executor", type=Path, required=True)
    p.add_argument("--driver-name", required=True)
    p.add_argument("--rate", type=int, default=44100)
    p.add_argument("--frames", type=int, default=128)
    p.add_argument("--callbacks", type=int, default=12000)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--acknowledge-hardware", action="store_true")
    args = p.parse_args()
    try:
        if not args.acknowledge_hardware:
            raise ValueError("P59 hardware selection requires explicit approval")
        plan = generate(args.plugin, args.executor, args.driver_name,
                        rate=args.rate, frames=args.frames,
                        callbacks=args.callbacks)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print("[PASS] P59 pinned local ASIO plan created; hardware NOT RUN")
        return 0
    except (ValueError, TypeError, OSError) as exc:
        print("[NO-GO] P59 ASIO plan not generated: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
