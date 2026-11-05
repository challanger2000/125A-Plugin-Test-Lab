125A Plugin Test Lab — P14 INTERACTIVE OLE ACCEPTANCE KIT
=======================================================

WHAT THIS IS
A ready-to-run, isolated, native Windows test of the actual 125A Drumator
VST3 drag-and-drop source, transferring files into an independent
Win32/COM IDropTarget. The full plugin bundle, test host and rights-free
A/REST/A state are included; no Python, DAW or local C++ compiler needed.

The test is separate from the GitHub-hosted test because non-interactive
Windows Actions sessions could generate correct drag-source MIDI/WAV files
but could not complete a true OLE DragEnter/Drop exchange.

TO RUN ON AN INTERACTIVE WINDOWS 10/11 DESKTOP
1. Extract ALL files and folders from the GitHub Actions ZIP (including
   the complete "125A Drumator.vst3" folder) into one local directory.
2. Log in to a normal Windows desktop session. Keep the screen unlocked.
3. Double-click Run-OLE-Test.cmd.
4. Do not move/click the mouse until the test stops.
5. Open results\<timestamp>\RESULT.txt. PASS only if four real
   CF_HDROP Drop callbacks were accepted by the separate native receiver
   AND four received physical export files passed the second verification.

Exit codes: 0 = PASS, 1 = FAIL, 3 = INCONCLUSIVE (headless/service session).
See results\<timestamp>\OLE-TEST-LOG.txt for full diagnostics.

THIS TEST DOES NOT:
- Import MIDI/WAV into Fender Studio Pro (formerly Studio One), or prove
  proprietary DAW-specific timeline/drop behavior.
- Open your existing Gumroad package or installed VST3; it tests the
  included source-built product, commit logged in
  TESTED-PRODUCT-REVISION.txt.
- Use the user's sound library, presets, license files or purchased samples.
- Change any installed plugins or system VST3 folders.

REQUIREMENTS / SAFETY
- Windows 10 or 11, x64, with an active unlocked interactive desktop.
- Sufficient on-screen resolution for the test host to place its source
  and independent receiving window; 1280x720 or greater preferred.
- A Microsoft Visual C++ 2015–2022 x64 runtime if Windows does not already
  provide it; the package includes executables but not system libraries.
- Only run native executables from sources you trust. Source and pinned
  commit are published in the public 125A Plugin Test Lab repository.

CONTINUED COVERAGE
GitHub Actions verifies P01–P11 and P13 source export already, but true
interapplication OLE target acceptance in a Windows desktop is a separate
test. P14 does not report "PASS" merely because a drag source file was
produced: it requires native receiver callbacks and physical outputs.

See the repository START-HERE.md for more information.
