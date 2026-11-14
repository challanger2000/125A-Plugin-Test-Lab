# P100 — original Win95 Creative ↔ exported VST3 parity

P100 is a specialized owner-local extension of the 125A Plugin Test Lab.
P73/P74 generic VST3 inventory **does not** count as register or PCM parity.

A single run verifies all private source SHA256 identities and the original
Win95 guest session manifest, independently verifies that the trimmed C4/D4
reference WAV is byte-for-byte the matching interval of the full original WAV,
launches the real Windows VST3 host for native and source-clocked takes,
attests their actual output SHA and MIDI clock, and compares four NoteOn/Off
physical EMU8000 port sequences and 44.1kHz stereo signed PCM16 samples.
Any mismatch reports exact first original/native frame/port/value or
frame/channel/sample, without automatic time alignment, gain normalization
or source-derived native port values. Native host stdout/stderr/exit code
are captured separately so Windows diagnostics never mask the real failure.

**One owner command:** use the Windows executable from this workflow:
125A_P100_Original_VST3_TestLab.exe --plan P100-PRIVATE-CONTRACT.json --out P100-NEW-RESULTS

The plan requires all 13 SHA256-pinned private media/inputs, explicit MIDI
sample schedule, source note clock, reference extraction window and original
boot/session manifest. Same golden source remains frozen for each developer
revision; new native VST3/host hashes are pinned for each actual new binary.

Public CI contains synthetic positive/mutant controls ONLY, no Creative ROM,
VXD, private SF2, Win95 disk, PCM or private register data. It builds the
self-contained Windows runner; a CI PASS cannot establish real private parity.

This P100 contract covers *only* the source C4/D4 fixture, not other banks,
controller permutations, FX, DAW, hardware ASIO or general P002 release.
Every report explicitly sets release_approved=false.
