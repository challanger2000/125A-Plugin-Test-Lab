#!/usr/bin/env python3
"""Run each existing Python test as its documented standalone script.

unittest discovery passes its own CLI into argparse-based standalone tests.
The actual native GUI snapshot test needs a real BMP and runs separately in CI.
No source tests are silently discarded: the inventory records the single native
fixture dependency explicitly, and the workflow executes it with the real GUI.
"""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
records = []
for test in sorted(root.glob('test_*.py')):
    if test.name == 'test_native_gui_snapshot.py':
        records.append({'test': test.name, 'mode': 'SEPARATE_NATIVE_GUI_BMP_STEP'})
        continue
    completed = subprocess.run([sys.executable, str(test)], check=False)
    records.append({'test': test.name, 'exit': completed.returncode})
    if completed.returncode:
        raise SystemExit(f'FAILED {test.name}: {completed.returncode}')
print(json.dumps({'python_test_scripts': records, 'physical_asio': 'NOT_RUN'}))
