# Prepared draft PR (not created: repository policy blocks Actions PR creation)

Base: `qa/p100-asio-instrument-midi`  
Head: `feature/p185-independent-etw-asio`  
Tested implementation: `8db0bea5d0888324aa4b33af3676d689900f1f2a`

Title: P185: independent native Windows ETW / ASIO diagnosis and BAT package

The existing cold-start callback spacing appears in both the reference and AWE.
P185 collects independently calibrated native kernel/manifest ETW and the actual
ASIO callback/lifecycle observations, rejects missing/lost/mismatched evidence,
and exports a minimal path-free diagnosis beside local raw ETL. It preserves
the existing callback code, full-run spacing gate and AWE sound core.

Validation: [Windows run 42530025112](https://github.com/challanger2000/125A-Plugin-Test-Lab/actions/runs/42530025112),
all targets, 2 CTests, 68 existing Python/native GUI script checks, 36 adversarial
cases, real native ETW/QPC/thread-end/permission controls, actual unpacked BAT
CheckOnly/cancel/tamper. Physical P185 NOT_RUN, cause INCONCLUSIVE, release NO_GO.
Scope and risks: [P185 method](P185-INDEPENDENT-ETW-ASIO.md).

No merge/release requested. Creation attempt failed with the exact GitHub message:
`GitHub Actions is not permitted to create or approve pull requests`.
