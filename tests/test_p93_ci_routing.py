#!/usr/bin/env python3
"""P93 keep expensive workflow routing bounded and full validation manually available."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"
SPECIALIZED = [
    "awe-p48.yml",
    "awe-p53.yml",
    "drumator-p03.yml",
    "gui-p04.yml",
    "p25-state-stress.yml",
    "p29-voice-stress.yml",
    "p52-analog-gui.yml",
    "p58-native-asio-host.yml",
    "p60-owned-dialog.yml",
    "p61-dialog-button.yml",
    "p62-native-menu.yml",
    "p63-popup-mouse.yml",
    "p64-painted-menu.yml",
    "p65-product-test-plans.yml"
]
BASELINE_PATHS = {
    "CMakeLists.txt", "src/main.cpp", "src/p15_dropfiles.h",
    "tests/signal_fixture.cpp", "tests/verify_render.py",
    "tests/verify_universal_discovery.py", "tests/run_vst3_batch.py",
    ".github/workflows/windows.yml"
}

def event_block(text):
    match = re.search(r"(?m)^on:\s*$", text)
    if not match:
        raise AssertionError("No YAML on: trigger")
    end = re.search(r"(?m)^(?:permissions|concurrency|jobs|env|defaults):", text[match.end():])
    return text[match.end():match.end()+end.start()] if end else text[match.end():]

def paths(events):
    return set(re.findall(r"(?m)^\s{6}- '([^']+)'\s*$", events))

class RoutingPolicy(unittest.TestCase):
    def test_baseline_only_for_shared_host_and_cmake(self):
        events = event_block((ROOT/"windows.yml").read_text(encoding="utf-8"))
        self.assertIn("  push:", events)
        self.assertIn("  pull_request:", events)
        self.assertIn("  workflow_dispatch:", events)
        self.assertEqual(paths(events), BASELINE_PATHS)
        self.assertEqual(events.count("    paths:"), 2)

    def test_no_broad_cmake_fanout_to_expensive_integrations(self):
        for name in SPECIALIZED:
            with self.subTest(workflow=name):
                full = (ROOT/name).read_text(encoding="utf-8")
                events = event_block(full)
                self.assertIn("  pull_request:", events)
                self.assertIn("  workflow_dispatch:", events)
                self.assertIn(".github/workflows/"+name, paths(events))
                self.assertNotIn("CMakeLists.txt", paths(events))
                self.assertIn("concurrency:", full)
                self.assertIn("cancel-in-progress:", full)

    def test_explicit_full_suite_remains_available(self):
        for name in ["windows.yml", *SPECIALIZED]:
            with self.subTest(workflow=name):
                self.assertIn("  workflow_dispatch:",
                              event_block((ROOT/name).read_text(encoding="utf-8")))

if __name__ == "__main__":
    unittest.main()
