# Native Windows VST3 editor bitmap capture

The test lab can now capture an actual VST3 editor HWND to a 32-bit,
top-down, uncompressed BMP. The pixels come from the Windows device context,
not from a made-up bitmap based on controller parameters.

```powershell
125A_Test_Lab_GUI.exe --snapshot-editor C:\QA\Plugin.vst3 C:\QA\editor.bmp
```

The host constructs the actual VST3 IComponent/IEditController/IPlugView,
attaches it to a native Win32 window, pumps and paints the editor, saves
one full screenshot, and then completes both editor attach/detach cycles.
Captures are limited to 4096 × 4096 pixels to bound memory usage.

The already available P33 independent bitmap oracle can check specific
user-visible colors/pixels from this actual capture. For example, P33
`expected.gui` can contain `{"x": 10, "y": 10, "rgb": [30, 36, 48]}`
and `artifacts.gui_bmp` points to the captured image.

Windows P04 CI uses a real native GUI VST3 fixture and tests the expected
painted RGB, deliberate wrong RGB expectation, and a deliberately corrupted
captured BMP. A mismatch is FAIL.

## Strict limitations

This proves actual Windows HWND painting and a finite set of externally
specified visual assertions. It does not automatically detect every visible
control, label, hover state or dialog; it does not attest visual correctness
without a trusted reference or a per-product layout; and it is not equivalent
to testing in a commercial DAW. If the UI is rendered by a layered, GPU or
out-of-process surface which is not available through its child HWND DC,
capture must fail rather than report a fictional PASS.

The commercial VST3 product source tree is never modified by this capture.
