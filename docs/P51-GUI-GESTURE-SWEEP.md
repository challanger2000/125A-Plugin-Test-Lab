# P51 — Independently approved multi-point GUI gesture sweep

The universal GUI test host already supports real Win32 dragging and
independent VST3 parameter-before/after checks inside one live editor (P37).
P51 adds strict, repeatable **bidirectional multi-checkpoint contracts**.

The externally approved JSON contains `product` (actual DLL path and SHA-256),
`gui_host`, `param_id`, initial normalized value, and 2–32 drag checkpoints
with start/end coordinates and **independently specified** expected normalized
VST3 values. All checkpoints execute in the *same* actual native editor and
must match their previous postcondition exactly. Missing, nonfinite, stale or
incorrect values fail. At least two distinct endpoints, 25% normalized
parameter range, and both value directions are mandatory.

Example (substitute real DLL identity, host and independently calibrated
coordinates/values):

```json
{
  "schema": "125a-gui-gesture-sweep-v1",
  "product": {"binary": "C:/QA/Plugin.vst3/Contents/x86_64-win/Plugin.vst3",
              "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  "gui_host": "C:/QA/125A_Test_Lab_GUI.exe",
  "param_id": 9001,
  "initial_normalized": 0.0,
  "checkpoints": [
    {"start_x": 100, "start_y": 70, "end_x": 140, "end_y": 90,
     "expected_normalized": 0.5},
    {"start_x": 140, "start_y": 90, "end_x": 180, "end_y": 90,
     "expected_normalized": 1.0},
    {"start_x": 180, "start_y": 90, "end_x": 100, "end_y": 70,
     "expected_normalized": 0.0}
  ]
}
```

Run on a trusted Windows VST3:

```powershell
python tests/run_gui_gesture_sweep.py --manifest approved-sweep.json --out P51-evidence
```

**Evidence scope:** A green P51 on a real product proves that declared native
drag actions caused the preapproved VST3 controller transitions, including
reverse movement, for those coordinates and that exact binary. It does not
prove smooth continuous motion between checkpoints, intuitive knob scaling,
all hidden/painted-only controls, processor DSP correctness or any DAW
integration. The sample Windows CI fixture is a **binary toggle that reacts
to drag mouse-up**, proving the drag protocol, ordered state and independent
oracle. It is not represented as proof of a continuously variable knob.
Separate positive and adversarial Python tests enforce the contract.

A standalone Windows CI artifact retains workflow's actual native evidence.
No production plugin repository or customer release files are changed.
