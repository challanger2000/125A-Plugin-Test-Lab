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

## P46 — Independent functional oracle for GUI-initiated WAV/MIDI exports

Unlike GUI pixel/parameter-only tests, the optional P46 runner joins one
**declared native GUI workflow** to an **independent expected file contract**.
It opens a real Windows VST3 editor, dispatches approved clicks/keys,
then inspects actual files created by that plugin. A correct-looking
GUI is insufficient: wrong PCM samples, incorrect WAV frames or
sample rates, invalid MIDI contents, missing exports and extra files
are all FAIL. This closes one specific user-visible functional gap.

Portable/Windows CI invocation:

\`\`\`powershell
python tests/run_gui_export_contract.py --manifest .\export-contract.json --out .\results
\`\`\`

Contract example (provide actual host and source-built VST3 paths and its
independently computed SHA-256 before running):

\`\`\`json
{
  "schema": "125a-gui-export-contract-v1",
  "workflow": {
    "schema": "125a-gui-workflow-v1",
    "product": {
      "binary": "C:/Build/Plugin.vst3/Contents/x86_64-win/Plugin.vst3",
      "sha256": "<SHA256 of independently pinned real VST3 module>"
    },
    "gui_host": "C:/TestLab/125A_Test_Lab_GUI.exe",
    "initial": [{"param_id": 9001, "normalized": 0.0}],
    "steps": [{
      "id": "export_wav", "action": "click", "x": 160, "y": 90,
      "param_id": 9001, "before_normalized": 0.0,
      "expected_normalized": 1.0
    }]
  },
  "expected_exports": [{
    "filename": "gui-export.wav",
    "type": "wav",
    "sha256": "3c548b8ac23f3be44063b4afce2609137a6e274e409af17f2397f0c95172741b",
    "channels": 1, "sample_rate": 44100,
    "sample_width_bits": 16, "frames": 16
  }]
}
\`\`\`

A MIDI export instead uses \`"type": "midi"\`, and independently supplied
\`sha256\`, \`format\` (0/1), \`tracks\`, \`ticks_per_quarter\`, and
\`note_on_count\` values. The validator parses strict Standard MIDI File
track lengths, running status and End-Of-Track events rather than trusting
the filename or a plugin-generated summary.

The output is checked in an **empty, automatically isolated fresh
directory**. No previous run can satisfy the expected files. The runner
pins the tested binary and GUI host, verifies the complete approved
mouse/keyboard workflow, demands exactly the expected filenames (no extras),
matches independently approved SHA-256 and separately validates native
WAV/SMF structure. A copy of verified files is retained with the Windows
artifact. The \`QA_TEST_LAB_EXPORT_ROOT\` environment variable is provided
as an optional output-directory hint; source-built test fixtures use it,
whereas ordinary plugins must be configured to save into the designated
test folder through their own UI and supported workflows.

**Positive and adversarial real-VST3 proof:** Windows CI builds a fixture
whose genuine GUI click writes a valid 16-frame PCM WAV. Another real VST3
performs exactly the *same correct GUI parameter transition* but writes a
valid WAV with intentionally wrong audio samples; a third transitions the
controller but exports nothing. The independent oracle must pass **only**
the correct file. Python tests also reject a wrong golden checksum, wrong
WAV metadata, malformed MIDI, path traversal, extra outputs and
self-asserted successful GUI events.

This is a **profile/contract mechanism**, not a claim the tester knows what
unknown controls should do. Without a preapproved expected output (or
product-specific adapter), a generated WAV cannot be declared musically
correct merely by observing its existence. Pop-up Save dialogs and full DAW
drag/drop require separate approved workflows; P46 itself does not invent
their automation. A passing P46 contract establishes only its declared
GUI-to-export behavior. **It is not a complete commercial plugin release
approval** and does not automatically cover every product control.


## P45 — Same-editor real GUI two-way observations (A/B/A)

Previously, P44 created candidates only from one attributed click. A
subsequent click could stop working, leave the editor in an inconsistent
state, or trigger a momentary control rather than a toggle. The shared
Windows host now has a third mode:

\`125A_Test_Lab_GUI.exe --gui-observe-roundtrip <bundle.vst3> <x> <y> <native.tsv> <before-a.bmp> <before-b.bmp> <after-first.bmp> <after-second.bmp>\`

The two genuine native mouse clicks occur inside the **same opened VST3
editor instance**, with independent controller snapshots and screenshots
A → B → A. The portable \`tests/run_gui_roundtrip.py\` accepts a previously
sham-checked P44 exploration folder and tests only its unapproved candidate
coordinates; no blind discovery clicks are made without the existing
explicit opt-in. It validates module/host SHA256, the previously captured
native click proof, the original child HWND hit depth, real pixel geometry,
current VST3 parameter identities and every new native evidence row.

Results distinguish:

- \`OBSERVED_REVERSIBLE\`: the second click restored all observed parameter
  values and painted pixels to the same initial state.
- \`OBSERVED_NONREVERSIBLE\`: the first effect was reproduced, but the second
  click did not restore that state. This can be a legitimate momentary
  action, transport, one-shot effect, or real bug; without an independent
  specification it is NOT automatically a release failure.
- \`NOT_REPRODUCED\`: the click-associated first change was not reproduced.
  Treat it as a review finding, never as successful functional coverage.

An unexpected new parameter ID/change, missing second screenshot, changing
native hit-depth or tampered artifact is a hard technical FAIL. The report
always declares \`independent_product_semantics: NOT COVERED\` and
\`release_approved: false\`.

For an existing one-command VST3 test, explicitly choose:
\`--gui-host <gui.exe> --gui-explore --gui-roundtrip --acknowledge-gui-explore\`.
The standalone runner accepts \`--plugin\`, \`--gui-host\`, \`--exploration\`,
\`--out\`, \`--acknowledge-ui-clicks\`. Both operate in GitHub Windows Actions
without local Python installation. Unknown UI actions may have side effects:
use only trusted test plugins and disposable state.

A/B/A observes *reversibility*, not the independently intended function.
It cannot prove drum pattern generation, MIDI/WAV exports, audio processing
or commercial DAW integration. Those require a product-specific approved
reference oracle even if painted state appears to return to A.

## P44 — Find custom-painted changes and prepare reviewable UI test candidates

The shared Windows VST3 explorer now analyzes the **physical before-click
and after-click pixels** after paired sham/no-click controls have established
that the change is click-associated. Instead of merely reporting a total number
of changed pixels, it groups adjacent changed 12×12 pixel tiles and reports
each exact changed-pixel bounding rectangle, physical sample coordinates, and
**RGB before/after values**. A localization report indicates when a broad
repaint (over 25% of the editor) should not be interpreted as a local button.

New per-scan artifacts:

- \`GUI-EXPLORATION-RESULT.json\` contains \`pixel_localization\` for every
  probe, including \`regions\`, \`bbox_xyxy\` (exclusive right/bottom),
  \`changed_pixels\` and \`sample\` physical RGB pairs.
- \`GUI-CONTROL-REVIEW-DRAFT.json\` is generated **only if every sham and click
  probe completed and source-binary hashes remain valid**. It contains
  proposed click actions with the observed VST3 parameter transition, or
  observed before/after pixels for a parameterless, custom-painted control.

These are **unapproved observations**, not independent semantic requirements.
The draft always says \`REVIEW_REQUIRED\`,
\`approved_for_execution: false\`,
\`automatically_approved_oracles: 0\`,
\`executable_workflow_manifest: NOT GENERATED\`,
\`product_gui_controls: NOT COVERED\`, and
\`release_approved: false\`. To convert a suggested interaction into a
release test, an independent product specification or maintainer must confirm
that the expected value/color change actually represents the intended
function. The tester never silently turns its own observations into oracles.

The Windows regression builds a *real native VST3 whose only clickable
element is custom-painted inside one HWND*, with a precise 80×50 pixel
rectangle and **no VST3 parameter change**. P44 verifies that the explorer
locates exactly that rectangle, captures the RGB transition, and proposes
only an unapproved visual oracle. An outside-background click must produce
no candidate. Pure Python adversarial tests separately cover disjoint
changes, incorrect screenshots, broad repainting, truncated region reports,
bad source data and forged approvals.

This is reusable for existing and future plugins using the same opt-in
\`--gui-explore --acknowledge-gui-explore\` workflow; no Drumator/AWE-specific
code or product builds are modified. A custom-drawn button that produces no
detectable pixel/parameter change cannot be automatically judged. Native
file dialogs and audio/MIDI/WAV semantics are not established by pixels.

## P43 — Deep native child-HWND mouse targeting

The generic Windows VST3 test host now dispatches real mouse click/drag
messages to the **deepest visible enabled native child HWND** that contains
the requested point, using Win32 hit-testing and coordinate transformation.
Previously, it sent messages only to the editor's surface, which missed
standard nested `BUTTON` controls and other legitimate child windows.
Drag gestures preserve the actual target selected at mouse-down.

The same pointer routing is used by both `--gui-workflow` (persistent
ordered interaction) and automatic `--gui-explore` (disposable native
test sessions). Every `sham` and actual click must hit the **same native
child depth** or the independently checked result is FAIL; source-built
evidence format is now `125A-GUI-EXPLORE-v3` with `target_depth`.
The observation report retains the original editor-coordinate click and
adds `native_child_depth` and `routed_to_descendant_hwnd`.

**Positive Windows regression:** a genuine VST3 fixture has a nested
standard Win32 `BUTTON` inside its own editor HWND. Only that button's
real `BN_CLICKED` notification changes VST3 parameter 9001. The tester
must click its center and observe a real parameter change; clicking an
editor-background coordinate must do nothing. The same button must
toggle ON then OFF through an approved two-step `--gui-workflow`.

**Hover baseline correction:** the host first sends the same hover
`WM_MOUSEMOVE` to sham and click runs, then captures the two stable
baseline images. Only afterward does the real-click run send
`WM_LBUTTONDOWN/WM_LBUTTONUP`. This avoids labeling legitimate
standard buttons as unstable merely because they visually respond to
hover, while rejecting hover-only false positives.

**Limitations:** Custom-painted VSTGUI/JUCE controls typically exist
inside a single HWND and must still be located through image/parameter
oracles. Native hit-testing does not discover all plugin controls or
verify their intended semantics, and it cannot replace a product-specific
audio/MIDI/DAW verification. Unknown GUI exploration remains opt-in
and can trigger actions; results are `OBSERVATIONS_ONLY`, not release
certification.

## P42 — Matched no-click control for automatic GUI exploration

An unknown GUI control may appear to change because of animation, meters,
randomized starting state, background UI updates, or an unrelated parameter
change. A pixel difference **alone** cannot prove the click caused it.

The universal P41 GUI explorer now performs **two disposable VST3 process
runs per coordinate**:

1. A **sham** run uses the same editor attach, message-pump timing, parameter
   snapshots and three real HWND captures. It sends the **same WM_MOUSEMOVE**
   as the click run (to control for hover-only feedback), but sends **no
   mouse-button down/up**.
2. A separate actual **click** run captures the same evidence after real
   Win32 mouse down/up.

The independent verifier compares the entire parameter inventory and initial
normalized values, both no-click and click pixel baselines, changes over time
in the sham, and post-click-versus-sham pixels. When the sham itself shows
animation or parameter changes, or the starting states disagree, the result
is `UNSTABLE_CONTROL` and **no discovered-control candidate is emitted**.
Otherwise genuine controller/painted transitions are classified as before.

A source-built real VST3 **hover-only** fixture is included in Windows CI:
its painted highlight changes under both sham and click, but no controller
parameter changes, so it must never be reported as a clickable candidate.
Separate adversarial tests model spontaneous animation and background
parameter automation. A mere hover highlight is not button operation.

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

