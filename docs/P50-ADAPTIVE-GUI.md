# P50 — Adaptive GUI follow-up

The generic Windows VST3 GUI sampler now performs a second, **bounded**
search around P49 click-associated change candidates. A normal P49 grid is
first executed against the same real source-built plugin and native Win32 GUI
host. P50 then checks up to **four** previously observed candidates and
samples at most **32** nearby, previously untested coordinates (eight per
candidate). Each new coordinate uses the P42 sham/click two-process evidence
from the existing shared native GUI explorer.

Run only against a trusted plugin and disposable state; arbitrary clicks can
change samples, settings, files or presets:

```powershell
python tests/run_gui_adaptive.py --plugin "C:\QA\Plugin.vst3" --gui-host "C:\QA\125A_Test_Lab_GUI.exe" --out "C:\QA\P50" --columns 8 --rows 8 --max-candidates 4 --acknowledge-ui-clicks
```

The report is `ADAPTIVE-GUI-REPORT.json` with separate P49 baseline and
P42 native sham evidence for every follow-up batch. Plugin and host binaries
are identified by SHA-256 at start, between batches and at end. A mismatch,
a forged success report, or missing sham evidence fails closed.

**No claim of autonomous GUI understanding:** neighboring click-associated
changes are observations, not proof of a working knob, button, menu, dialog,
musical behavior or complete user interaction. P50 cannot discover functions
never displayed in the current editor state, navigate arbitrary tab/menu
hierarchies, establish correct parameter scaling, or drive a commercial DAW.
No customer Gumroad ZIP or plugin release is approved by this suite.

P50 Windows CI contains both adversarial Python runner tests and a separate
real Win32 native VST3 editor test. No Python installation is required on the
user's PC to use GitHub Actions.
