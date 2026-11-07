# P84 — Reproducible native unknown VST3 GUI observations

P82 and P83 can perform explicitly approved exploratory clicks on previously unknown controls with sham runs. P84 addresses a key remaining reliability risk: **a single observation may be transient, unstable or accidental**.

P84 repeats the entire native P42 sham/click protocol in **2–5 new independent VST3 instances**, comparing exact observed parameter transitions and their before/after values, control position, target HWND depth and visual change classification. Differing results produce `FAIL`; no control is automatically accepted as a known function. An inert native GUI control is consistently classified `NO_OBSERVED_CHANGE`, never a functional PASS.

P84 works via P74 and is configurable per plugin in P83 batches:

```powershell
python tests/run_universal_qa.py --plugin C:\QA\Unknown.vst3 --gui-host C:\QA\125A_Test_Lab_GUI.exe --out C:\QA\evidence --explore-unknown-gui --exploration-max-points 4 --exploration-repeats 2
```

Or in a P83 selection record, add `"exploration_repeats": 2` alongside `"explore_unknown_gui": true`. Existing single-run and read-only modes remain backward-compatible.

The P84 report retains native evidence for every repetition and writes `GUI-REPEATABILITY-RESULT.json` with exact source identities and comparable control signatures. P74 exposes `unknown_gui_repeatability`, `unknown_gui_completed_repetitions` and the actual total number of exploratory clicks.

**Boundaries:** Reproducibility is evidence of repeatable GUI behavior, **not** a semantic, sonic or safety oracle. A control can act consistently while being incorrect, destructive, or musically wrong. Only reviewed P65/P67 assertions can verify named product features. These probes can activate side effects and should run only on an isolated disposable Windows test VM. No physical ASIO, DAW or release approval is inferred.

Windows CI builds real Win32 VST3 fixtures and checks two independent complete sham/click repetitions for a functional control and an inert control. Automated regressions also reject different observations across instances, forged identity, unstable sham controls, invalid replay count and missing repetition evidence.
