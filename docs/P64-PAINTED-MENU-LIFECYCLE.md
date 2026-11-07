# P64 — Real custom-painted VST3 popup menu lifecycle

P64 tests a **single-HWND, custom-painted dropdown menu** that has no
native Win32 child button or `HMENU` to discover. This complements
P54/P55 (native controls) and P60–P63 (owned dialogs and Win32 menus).

With a real source-built VST3 editor, the common P37 workflow host
opens the painted menu by a genuine mouse click, captures actual
Win32 framebuffer BMPs, selects the painted item through a second
mouse click, verifies that the exposed VST3 parameter changes from
0 to 1, then reopens the menu through a third mouse click.

The independent P64 verifier:

- confirms the plugin editor has one actual HWND, no native child
  controls (P54 inventory)
- checks two independent painted-pixel BEFORE/AFTER transitions
  for menu opening and reopening (P37 visual oracles)
- automatically **localizes the changed visual bounding rectangle**
  from the actual 32-bit Win32 BMP snapshots, rather than relying
  only on a single painted pixel
- verifies that the observed rectangle matches the approved fixture
  dimensions `[90, 82, 230, 135]` and contains at least 7000
  changed pixels
- requires a genuine ordered VST3 parameter transition on the
  selection click and exact binary/host SHA-256 continuity

A source-built defective VST3 visually draws the same dropdown and
allows clicks, but deliberately leaves the advertised parameter
unchanged. It must **FAIL** while the working fixture passes.

Run only with the approved disposable P64 fixture or a separately
adapted, independently specified product contract:

```powershell
python tests/run_gui_painted_menu.py --plugin "C:\QA\Fixture.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P64"
```

**Important:** P64 is a reliable **contract-based** painted-popup test
fixture and a screenshot-difference localization method. It does not
infer arbitrary painted controls' semantics, item names or hitboxes in
commercial VST3s. Unknown complex menus, submenus, dialog file pickers,
commercial DAW save/load, and ASIO hardware qualification remain
separate tasks. All results retain `release_approved: false`.
Drumator and AWE production repositories are untouched.
