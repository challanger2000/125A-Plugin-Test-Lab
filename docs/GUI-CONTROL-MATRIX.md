# Universal native GUI control matrix

The Windows GUI host can run an externally declared click test on an actual
third-party VST3 HWND. The host clicks the requested physical child-window
pixel and compares the resulting VST3 controller parameter with an explicitly
supplied expected normalized value, in two attach/input/detach cycles.

```powershell
125A_Test_Lab_GUI.exe --prove-click-at Plugin.vst3 9001 160 90 1.0
python tests/run_gui_control_matrix.py --manifest gui-controls.json --out gui-evidence
```

Manifest example:

```json
{
  "schema": "125a-gui-controls-v1",
  "product": {
    "binary": "C:/QA/MyPlugin.vst3/Contents/x86_64-win/MyPlugin.vst3",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "gui_host": "C:/QA/125A_Test_Lab_GUI.exe",
  "controls": [
    {"id": "enable_switch", "param_id": 9001,
     "x": 160, "y": 90, "expected_normalized": 1.0},
    {"id": "disable_switch", "param_id": 9001,
     "x": 160, "y": 90, "initial_normalized": 1.0,
     "expected_normalized": 0.0}
  ]
}
```

Use a trusted independently specified parameter mapping and click position;
do not copy predictions from the same implementation under test. Each
control runs in a separate native host process. The matrix verifies the
declared control in two real Win32 GUI cycles and fails if the controller
parameter does not match. The Windows P04 workflow proves the matrix using
a working genuine VST3 GUI fixture and intentionally inert, wrong-expected
and out-of-bounds negative controls.

**Two-way toggles:** A control profile can now supply `initial_normalized`
(default 0.0) and a distinct `expected_normalized` anywhere in [0, 1].
The Windows GUI host sets the initial VST3 controller state, dispatches a
real native mouse click and checks the resulting controller value in **two**
editor attach/input/detach cycles. This covers both ON and OFF transitions
using exactly the same shared test engine across current and future plugins:

```powershell
125A_Test_Lab_GUI.exe --prove-click-at-from Plugin.vst3 9001 160 90 1.0 0.0
```

Optional painted-pixel checks also accept `initial_normalized` via
`--prove-click-and-snapshot-from`. Invalid or identical initial/final
values and missing native evidence fail closed. The CI verifies an actual
Win32 toggle in both directions and rejects an intentionally inert VST3.

**Explicit limits:** The generic contract does not infer a plugin's complete clickable
control inventory, visual appearance, draw correctness, drag operations,
gesture ranges, parameter persistence in the processor, DAW integration,
or dialog behavior. The report always marks `all_product_controls` as
`NOT COVERED`, even if every *declared* control passes. This must not be
used as a product release certificate. More gesture types and independent
processor/GUI oracles are necessary to cover actual user workflows.

## Correlated native controller and painted visual state

Optionally add an independently expected post-click pixel to an individual
control:

```json
"expected_pixel": {"x": 10, "y": 10, "rgb": [12, 142, 85]}
```

The matrix then runs `--prove-click-and-snapshot`, clicks the real HWND,
checks the VST3 controller parameter in two editor lifecycles, and captures
the actual painted editor BMP after the first click. The existing P33 bitmap
reader verifies that the stated RGB is present at the required physical pixel.
A successful controller value with a stale painted color is **FAIL**, not PASS.

Windows P04 regression includes a deliberately broken VST3 whose controller
parameter changes normally while its painted status remains stale. Only the
external painted-pixel expectation detects it. As before, this is a declared
pixel/control test, not automatic discovery of every product control.


## Ordered user interaction workflows (P37)

The generic Windows VST3 editor host can now execute a bounded multi-step
workflow **without closing the plugin window between actions**. An independent
`125a-gui-workflow-v1` JSON profile lists its initial VST3 controller state,
then each real native mouse click or drag, the expected parameter value before
and after that action, and optional painted-pixel reference snapshots.

The same universal runner works with existing and future VST3 products; it
has **no baked-in Drumator or AWE control coordinates**.

Example (absolute bundle/module/host paths and the actual SHA-256 are needed):

```json
{
  "schema": "125a-gui-workflow-v1",
  "product": {
    "binary": "C:/QA/MyPlugin.vst3/Contents/x86_64-win/MyPlugin.vst3",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "gui_host": "C:/QA/125A_Test_Lab_GUI.exe",
  "initial": [{"param_id": 9001, "normalized": 0.0}],
  "steps": [
    {"id": "activate", "action": "click", "x": 160, "y": 90,
     "param_id": 9001, "before_normalized": 0.0, "expected_normalized": 1.0,
     "screenshot": true, "expected_pixel": {"x": 10, "y": 10, "rgb": [12, 142, 85]}},
    {"id": "deactivate", "action": "click", "x": 160, "y": 90,
     "param_id": 9001, "before_normalized": 1.0, "expected_normalized": 0.0}
  ]
}
```

For a drag instead of a click, use `"action": "drag"` and supply
`"end_x"` and `"end_y"`. The Win32 host dispatches
mouse down, button-held movement, and mouse up. Individual tests run in one
persistent GUI session; an inconsistent next-step precondition therefore
detects unexpected prior action effects. Up to 64 mouse actions and 16
screenshots are supported per manifest. Actions have a bounded native
subprocess timeout.

```powershell
python tests/run_gui_workflow.py --manifest approved-workflow.json --out GUI-RESULTS
```

The independent Python verifier checks the exact native action sequence,
all controller before/after observations, source/host hashes, and requested
painted pixels. Missing, stale, truncated, reordered, or forged PASS records
fail the workflow. The native C++ host emits evidence even on an unexpected
post-click value. The same feature can be requested within the unified
quickcheck using `--gui-host` and `--gui-workflow`.

**Important:** This is a real ordered user-action test, not automatic
discovery of button meanings. Controls not tied to an observable VST3
parameter still require a different independent oracle. Native file dialogs,
keyboard shortcuts, the plugin's true MIDI/WAV outputs, and production DAW
integration are not automatically certified by these click/drag workflows.
No commercial product release is implied by `TECHNICAL_PASS`.


## Visual-only GUI controls without VST3 ParamIDs (P38)

A plugin can have a button, menu or LED that is **not advertised** through
`IEditController`. A declared workflow can now validate that control **without
inventing a parameter ID**, by demanding a real screen-pixel transition
before and after a native click/drag in the same open editor.

Use a `visual_oracle` instead of the three controller fields:

```json
{
  "id": "menu_led_on", "action": "click", "x": 160, "y": 90,
  "screenshot": true,
  "visual_oracle": {
    "x": 10, "y": 10,
    "before_rgb": [30, 36, 48],
    "after_rgb": [12, 142, 85]
  }
}
```

The native host saves **two real Win32 BMP snapshots** for this step:
`<index>.before.bmp` and `<index>.bmp`. The independent Python oracle
reads the exact painted pixels and requires both the approved initial
color and changed final color. A stale display, missing snapshot or
fabricated controller result is FAIL. At most 16 screenshot actions and
64 total steps are permitted per bounded workflow. Real, source-built
positive, inert and stale-paint VST3 fixtures run in Windows CI.

**Important:** Visible feedback alone does not certify a control's hidden
internal effect, audio output, file export, or DAW state. This option
verifies **only independently specified and observed visual transitions**.
The human-readable QA report distinguishes these from controller roundtrips
and keeps overall `product_gui_controls` as NOT COVERED unless a separate
product acceptance gate verifies every intended behavior.


## Native keyboard shortcuts and focused editor input (P39)

A universal workflow action can also send a bounded Win32 keyboard
`WM_KEYDOWN` / `WM_KEYUP` sequence to the actual native VST3 editor HWND,
with optional Ctrl, Shift and Alt modifiers. As with click and drag, every
keyboard step must supply either an independently approved VST3 parameter
before/after transition or a visual-only painted-pixel transition. Merely
dispatching a key is **not** a PASS.

Example in a `125a-gui-workflow-v1` profile:

```json
{
  "id": "shortcut_enable", "action": "key", "x": 160, "y": 90,
  "key_code": 32, "modifiers": ["ctrl", "shift"],
  "param_id": 9001,
  "before_normalized": 0.0, "expected_normalized": 1.0,
  "screenshot": true,
  "expected_pixel": {"x": 10, "y": 10, "rgb": [12, 142, 85]}
}
```

`key_code` is the Win32 virtual-key value 8–255 (e.g. 32 = Space,
13 = Enter, 27 = Esc); Windows logo keys are excluded. Optional modifiers
are `ctrl`, `shift`, `alt`, without repeats. The `x`/`y` position is
an editor pointer position during the keyboard input; if a field must
receive focus, include a separate validated click action first.

The native test plugin responds to Space/Enter and an inert test plugin
does not. P25 Windows CI verifies real key input with and without
modifiers, and proves that an unrelated Escape key **fails** an asserted
state-change oracle.

These are **HWND-directed Win32 messages**, not system-wide synthesized
keystrokes. Text-entry, native popup menus, accessibility navigation,
interacting with a commercial DAW window and arbitrary keyboard shortcuts
cannot be certified in every plugin without a product-specific observable
oracle. The full set of undisclosed controls remains NOT COVERED.

## P42 — Matched no-click control for automatic GUI exploration

An unknown GUI control may appear to change because of animation, meters,
randomized starting state, background UI updates, or an unrelated parameter
change. A pixel difference **alone** cannot prove the click caused it.

The universal P41 GUI explorer now performs **two disposable VST3 process
runs per coordinate**:

1. A **sham** run uses the same editor attach, message-pump timing, parameter
   snapshots and three real HWND captures but does **not send any mouse
   input**.
2. A separate actual **click** run captures the same evidence after real
   Win32 mouse down/up.

The independent verifier compares the entire parameter inventory and initial
normalized values, both no-click and click pixel baselines, changes over time
in the sham, and post-click-versus-sham pixels. When the sham itself shows
animation or parameter changes, or the starting states disagree, the result
is `UNSTABLE_CONTROL` and **no discovered-control candidate is emitted**.
Otherwise genuine controller/painted transitions are classified as before.

The native evidence format is versioned as `125A-GUI-EXPLORE-v2` and names
each run `mode=sham` or `mode=click`; missing, mismatched or forged
pairing is a hard FAIL. Report includes `sham_verified_points`,
`sham_control`, sham motion, cross-instance baseline mismatch and a
click-versus-sham pixel difference. This remains **opt-in only** because
the actual-click run may trigger actions in an unknown plugin.

A passed pairing supports an observation of a click-associated change;
it does **not** establish the product's intended functionality, identify
every clickable area, or authorize release. User interaction should be
tested only on trusted VST3s with disposable state. On GitHub Actions,
Windows Python is supplied by the runner.

## P41 — Optional automatic GUI exploration (no manually mapped controls)

The shared Windows tester can now **automatically probe unknown native
GUI regions**, taking a real initial editor snapshot and choosing
deterministic interior coordinates on a 3×3/4×4 grid. Every click takes
place in a **fresh, disposable plugin instance and process**. At each
point it records:

- All advertised VST3 controller parameter values before/after clicking.
- Two pre-click **real HWND captures** to detect independently changing UI
  pixels, and a third capture after the click.
- Distinctions between `PARAMETER_AND_VISUAL_CHANGE`,
  `PARAMETER_CHANGE`, `VISUAL_CHANGE`, `UNSTABLE_BASELINE` and
  `NO_OBSERVED_CHANGE`.

Candidates are **observations**, not discovered button names or proof of
correct functionality. A change in a painted LED does not establish
correct audio, MIDI, export or recall behavior. A no-change result does
not mean a control is broken: the click may be outside a control or may
have a nonobservable side effect. Animated interfaces can be marked
`UNSTABLE`; their visuals are not certified.

**Explicit opt-in is required** because clicking unknown buttons can
launch dialogs, exports or other plugin actions. Run only with trusted
test bundles and disposable project state. This uses a real Windows
GUI process and never silently runs on new plugins.

Standalone Windows Actions execution:

```powershell
python tests/run_gui_exploration.py --plugin "C:\VST3\MyPlugin.vst3" --gui-host "build\Release\125A_Test_Lab_GUI.exe" --out artifacts/GUI-SURVEY --acknowledge-ui-clicks --max-points 9
```

Within the same ordinary technical quickcheck add `--gui-host`,
`--gui-explore` and `--acknowledge-gui-explore`. Results are saved to
`gui-exploration/GUI-EXPLORATION-RESULT.json` with native TSV, two
baseline screenshots and one post-click screenshot per probe.
A successful scan is `OBSERVATIONS_COMPLETE`, while the human report
shows `OBSERVATIONS_ONLY`, **not** a button-coverage PASS. Missing,
stale or tampered native evidence and timeouts fail closed.

Limit: at most 16 candidate coordinates per scan, up to 4096×4096 HWND
with maximum 4,194,304 analyzed pixels per capture. Native user-action
automation in GitHub Actions uses the runner's Python; no Python
installation is needed on the end user's computer.

