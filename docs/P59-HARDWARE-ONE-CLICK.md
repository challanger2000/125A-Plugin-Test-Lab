# P59 — One-click ASIO hardware test on a prepared Windows workstation

The P58 native ASIO COM/VST3 callback host can now be built and operated by
one explicit GitHub Actions `workflow_dispatch` action in
`.github/workflows/p59-one-click-asio-hardware.yml`. The workflow:

1. Runs **only** from the trusted `main` branch, with an explicit hardware
   acknowledgement and the `125A-ASIO` Windows x64 self-hosted runner label.
2. Downloads an exact source-pinned ASIO SDK for local compilation only,
   builds the P58 host against the existing pinned VST3 SDK.
3. Uses the selected real local VST3 DLL and exact locally registered ASIO
   driver **name**. It looks up the actual driver CLSID itself and hashes
   the actual built executable and plugin DLL. No manually fabricated
   fingerprints or boilerplate P56 JSON needed.
4. Runs the **real hardware** P56 callback evidence adapter at the selected
   sample rate, buffer size, and callback count.
5. Uploads only a **redacted** summary with callback counts and failure
   metrics. Personal PC paths, ASIO registry CLSIDs, plugin source files and
   complete native logs remain in the workstation's local private directory.

The default selected scenario is 44.1 kHz / 128 frames / 12,000 callbacks;
alternatives allow 48/96 kHz, buffer sizes 64–1024 and 24,000 callbacks.
Unsupported driver modes fail, never silently switch to another rate/buffer.

The independent `tests/generate_physical_asio_plan.py` verifies exact
SHA-256 binary identities and the local Windows registry CLSID. Unit tests
reject false driver names, stale DLL hashes, unsupported scenarios and use on
non-Windows systems. These **cloud regression tests cannot substitute for a
physical ASIO device run**.

## Important security: do not blindly register a runner to a public repository

The 125A Plugin Test Lab is publicly readable. **Attaching a personal
audio workstation as an unrestricted self-hosted Actions runner to a public
repository can expose the machine to untrusted workflow code**, including
potential future contributor changes. Only use a dedicated isolated Windows
testing workstation with no sensitive data, restricted repository/runner
access, and a trusted protected GitHub environment named
`125A-Physical-ASIO` configured with branch restrictions and required
approvals; a separate private repository/workflow for the hardware runner is
preferable. The workflow definition alone does not create such protection.

This is an optional workflow: on GitHub-hosted Windows-2022, no hardware
ASIO callback run is executed and the result remains `NOT RUN`. The test
machine must have its physical audio interface and genuine driver installed,
and must be running with an interactive Windows user session. This is not
equivalent to launching a commercial DAW and saving/reloading projects.

**Audio warning:** the P58 VST3 host generates a deterministic input signal
for insert effects. Use a disposable session, disable monitor speakers
or use a low output volume before authorizing the callback test.

## ASIO SDK license

P59 checks out a source-pinned ASIO SDK solely during the user's local
build, does not copy Steinberg headers into the Test Lab repository and
does not upload the ASIO binary. Confirm GPLv3 compatibility or a valid
proprietary ASIO SDK agreement before redistributing native builds.

Status: `P59 CI PASS` proves only the workflow plan and negative controls.
**Real hardware qualification remains `NOT RUN` until the user actually
dispatches it on a secure hardware-equipped Windows machine.**
