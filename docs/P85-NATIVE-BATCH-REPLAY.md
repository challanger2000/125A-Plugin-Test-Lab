# P85 — Full multi-plugin native acceptance of GUI reproducibility

P84 introduced independently repeated sham/click GUI exploration in fresh native VST3 instances, including fail-closed P74 and P83 dispatch. Its Windows tests exercised single-plugin native behavior; P85 extends the practical acceptance through the **whole crash-isolated multi-plugin pipeline**.

The Windows acceptance compiles two real Win32 VST3 plugins, one with a working GUI control and the other deliberately inert. It performs:

1. A two-plugin batch in which only the working GUI is explicitly opted in for two independent probe repetitions. The other plugin must remain strictly read-only.
2. A second two-plugin batch in which both plugins receive two fresh native sham/click repetitions. The working control must have identical parameter/visual observations, and the inert one must consistently report no observed change.

The runner independently reads the nested P74, P84 and native P42 JSON reports plus all preserved per-repetition native evidence. It rejects missing observations, incorrect aggregate click counts, mismatched control signatures, or any claim of approved product behavior.

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release --parallel 4 --target TestLabGUI QAGuiClick QAGuiInert
python tests/run_p85_native_batch_replay.py --build build --out build/p85
```

The report `P85-ACCEPTANCE.json` and nested artifacts provide evidence that opt-in per-plugin repeatability actually works end-to-end on Windows. This is source-built fixture proof, **not** semantic interpretation of arbitrary plugin controls, verification of audio or exported bytes, physical ASIO integration, DAW session verification or release certification.
