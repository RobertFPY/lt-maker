# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 9 — Full validation and release candidate**
- Phases 1–8: **ACCEPTED**
- P8-T01 cache/memoization audit: **ACCEPTED** at `1d40f89cf33008e0592c35ef9ab094c4cc9d0b5d`
- P8-T02 render/cache/batching audit: **ACCEPTED** at `3d8624136ce58e8dfb7c576515d8e4585ca79ae0`
- P8-T03 allocation/redundant-work audit: **ACCEPTED** at `869e30d66f8005ef088f85083dce05cea661876a`
- P8-T04 Android-only performance retuning: **ACCEPTED** at `849bf75443e0c31121c9f080da2c0afa2e879b3e`
- Active task: **P9-T01 only — Full PC regression matrix**
- Primary model: **GPT-5.6 Luna / medium**
- Escalation target: **GPT-5.6 Terra / high**
- Escalation pre-authorized: **NO**
- P9-T02/P9-T03/P9-T04: **UNAUTHORIZED**
- Expected default production changes: **NONE — validation/evidence only**
- Controller gate after P9-T01: **YES — STOP FOR CONTROLLER REVIEW**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Merge to `master`: **UNAUTHORIZED**

## P8-T04 acceptance record / Phase-8 closure

The controller accepts `849bf75443e0c31121c9f080da2c0afa2e879b3e` (`docs(recovery): audit android retuning`).

Accepted evidence:

- it is exactly one descendant of P8-T04 authorization commit `a65dbceebec8b43ecb13f300ca8bf453d1462ebe`;
- scope is audit-only: `recovery/p8_t04_android_performance_retuning.md`;
- no production source, tests, Trace V1 artifact, project data, assets, Android policy values, cache capacities, work-budget constants, scheduler, combat, load/restart, fast-forward, debugger or profiler behavior changed;
- the execution environment had host Python/pygame only; `adb` existed but no bounded Android device response was available, so the task made no Android FPS/frame-time/heap claim;
- the existing Android off-world tilemap budget remains exactly `4_000_000 ns`; without real Android evidence it was correctly classified `KEEP-AS-IS`;
- Event-local `_android_tilemap_pending` remains a correctness barrier, not a throughput knob; off-world construction and one synchronous live commit/rollback remain protected;
- owner-local render-cache capacities remain unchanged, including unit-menu cap 4 and accepted combat UI bounds; capacity changes were correctly deferred without Android hit/miss/memory evidence;
- streamed audio/preload/flush behavior and fallback ownership remain unchanged;
- title smoke remains the already-accepted P8-T03 presentation optimization and was not reopened;
- MockCombat/BattleAnimation timing-sensitive presentation paths, source-frame caching and `GC-REGION` remain rejected as retuning targets;
- styled-text remains deferred because its isolated font-registry baseline is not a valid performance-proof environment;
- required immutable S5/S7/S8/S12/S13/S14/S15/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 were reported exact;
- focused P8/Phase-3-through-7/recovery suites were reported green in isolated processes;
- known shared-registry/import-isolation/native Windows termination remains baseline debt, not repaired in P8-T04.

Phase 8 is therefore closed. Safe optimizations are retained only where dependency, output/presentation ownership, measurement and logical equivalence were proven. No extra Android retune was invented without device evidence.

## Locked findings entering Phase 9

1. **One gameplay core.** Android policy remains presentation/resource/off-world-preparation only.
2. **No partial live gameplay state.** Load, tilemap, combat and other authoritative transactions retain their accepted atomic boundaries.
3. **Combat ordering is locked.** Solver/action/RNG/hooks/cleanup/state-stack/end-combat order may not change.
4. **Save/load/restart is locked.** One canonical transaction; SAVE != pristine RESTART; snapshot-first restart precedence remains accepted.
5. **Fast-forward is locked.** Host/presentation timing may differ, logical outcome/order/input-edge semantics may not.
6. **Debugger/profiler are locked observers** except explicit debugger commands through the shared controller.
7. **P6 platform boundaries are locked.** Event wall-clock command scheduling must not return.
8. **P8 cache decisions are locked.** `GC-REGION` remains NOT CERTIFIED SAFE; battle source-frame caching remains REJECTED; styled-text optimization remains DEFERRED; title smoke remains KEEP-PLATFORM.
9. **Immutable recovery traces/goldens are read-only release oracles.**
10. **Project data/assets remain protected.** Validation failure in project content must be reported rather than modified merely to make the engine matrix pass.

---

# P9-T01 — Full PC regression matrix

Execute **P9-T01 only** using **GPT-5.6 Luna / medium**.

Escalation target: **GPT-5.6 Terra / high**, not pre-authorized.

This is a validation task, not a repair task. Luna should run the prescribed PC matrix mechanically, classify results against the recorded recovery baseline and accepted invariants, and stop for controller review.

## Required environment / baseline comparison

Read `recovery/baseline.md` before execution.

The recorded baseline interpreter is:

`utilities\enemy_event_generator\.python\python.exe`

The recorded full-suite command is:

`utilities\enemy_event_generator\.python\python.exe -m unittest discover -s app/tests -p 'test*.py' -v`

The historical baseline ended abnormally with native Windows exit `-1073740791` (`0xC0000409`) after 311 observed `ok`, 8 `FAIL`, 1 `ERROR` and before a normal unittest summary.

Do not silently replace the baseline interpreter for the authoritative full-suite comparison. Additional commands may use the same interpreter unless an existing repository command requires otherwise.

Classify every observed failure as one of:

- `KNOWN-BASELINE-SAME`
- `KNOWN-BASELINE-CHANGED`
- `NEW-REGRESSION`
- `ENVIRONMENT/TOOLING`
- `NOT-REPRODUCED`

A known baseline failure becoming different/worse is not automatically safe; record exact delta.

## Required PC matrix

### 1. Full unit-test discovery

Run the exact baseline full-suite command above.

Capture:

- exit code;
- last completed test;
- all FAIL/ERROR names;
- observed pass count if the process dies before summary;
- whether native termination reproduces;
- exact differences from `recovery/baseline.md`.

Do not repair failures in P9-T01.

### 2. Focused accepted-regression matrix

Run accepted focused suites in fresh/isolated processes where shared global state is known to contaminate aggregate runs.

At minimum cover:

- recovery trace/golden/lifecycle integrity;
- Phase-3 combat lifecycle/transaction ordering;
- Phase-4 tilemap pending build/barrier/commit/rollback;
- Phase-5 canonical load, atomic restore, restart and compatibility;
- Phase-6 platform policy/audio/work-budget boundaries on desktop/default path;
- P7 fast-forward equivalence;
- P7 debugger parity/shared controller;
- P7 profiler observer equivalence;
- P7 save/load/restart UX routing;
- P8 cache/memoization tests;
- P8 render/cache owner regressions that are runnable;
- P8 title smoke contract;
- current project/base integrity tests.

Do not treat an isolated pass as erasing a real full-suite ordering failure; report both.

### 3. Immutable deterministic scenario matrix

Run all available immutable recovery scenarios, not only a subset, unless the manifest marks a scenario reference-unsupported.

At minimum this must include the accepted S1-S18 set with S3 remaining reference-unsupported/N-A according to the frozen recovery contract, and S17 in disabled/debugger-idle/profiler-idle modes where the harness defines those variants.

Use the locked Trace V1 comparator.

Allowed provenance differences remain only those already approved by the comparator/manifest.

No golden regeneration.

Any unexplained logical checkpoint delta => STOP and report `ESC-03`.

### 4. PC save/load/restart feature flows

Exercise representative desktop pathways for:

- new game / chapter start;
- current SAVE load;
- tactical restart from pristine source;
- overworld special restart/save behavior;
- game-over -> title restart route;
- debugger restart route;
- invalid/legacy load atomic failure where the focused harness supports it.

Reuse existing automated feature-level tests/harnesses when they exercise the real route. Do not create a second validation-only implementation.

### 5. Fast-forward/debugger/profiler feature checks

Verify on PC/default runtime:

- fast-forward OFF vs ON logical equivalence;
- representative speed multipliers already accepted by P7;
- debugger hotkeys/controller routing remains shared and single-dispatch;
- profiler disabled mode remains inert;
- profiler observer-on test paths remain logically equivalent where supported.

### 6. Representative project launch

A P9-T01 PASS requires a representative PC engine launch, not only unit tests.

Follow `AGENTS.md` and current repo/project layout.

At minimum:

- identify the `.ltproj` project that `run_engine.py` would launch in this checkout;
- run the engine through an existing bounded smoke/launch route if available;
- verify project validation reaches normal engine startup without a new exception caused by recovery code;
- if a fully interactive GUI loop would block, use an existing test/smoke seam or a bounded process launch that captures startup output and exits intentionally without modifying project data.

Do not invent a fake project launch by importing one module and calling that a launch.

If no bounded representative launch can be executed in the environment, P9-T01 must be `PARTIAL`, not `PASS`, and report the exact blocker.

### 7. Type/static checks

Run the repository-prescribed applicable check:

`mypy app/`

using the environment/tooling available in the checkout.

If `mypy` is unavailable or current baseline has pre-existing failures, record exact tool/version/output and classify; do not install/change dependencies unless already authorized by repository setup.

Do not repair unrelated typing debt in P9-T01.

### 8. Importability / compile checks

Run at minimum:

- `python -m compileall -q app` with the baseline interpreter;
- a bounded engine import smoke proving engine-side modules do not require PyQt5 merely to import;
- `git diff --check`;
- final `git status --short`.

## PC logical acceptance criteria

P9-T01 can PASS only if all are true:

1. no new unexplained deterministic Trace V1 divergence;
2. no new focused regression in accepted Phase-3-through-8 contracts;
3. full-suite differences from baseline are completely classified;
4. representative PC project launch requirement is actually exercised;
5. save/load/restart and fast-forward/debugger representative feature paths remain valid;
6. no project data/assets were modified;
7. no production fix was made;
8. required commands were not silently skipped.

A reproduced historical native Windows crash may coexist with PASS only if:

- it matches the recorded baseline class/location closely enough to classify `KNOWN-BASELINE-SAME`;
- the focused accepted matrix and deterministic oracles remain green;
- no new tests fail before the native termination;
- the representative PC launch succeeds.

If the crash/failure signature has materially changed, report `KNOWN-BASELINE-CHANGED` or `NEW-REGRESSION` and do not PASS without controller review.

## Production / test change policy

Expected code changes: **NONE**.

P9-T01 may create only a validation evidence report, preferably:

`recovery/p9_t01_pc_regression_matrix.md`

Do not add or modify production behavior merely because validation found a defect.

Do not modify tests to hide a failure.

If a new deterministic regression is found, STOP and report the first failing semantic boundary. Diagnosis beyond a mechanical local classification requires escalation authorization.

## Escalation

Primary: **GPT-5.6 Luna / medium**.
Escalation target: **GPT-5.6 Terra / high**.
Pre-authorized: **NO**.

Escalate only to diagnose failures, not to run known tests.

STOP/report on:

- `ESC-03` immutable trace divergence;
- `ESC-05` invariant failure / partial state;
- `ESC-06` save compatibility conflict;
- `ESC-07` platform-boundary conflict exposed by desktop validation;
- `ESC-08` repeated local validation failure requiring diagnosis;
- `ESC-09` apparent architecture-level contamination;
- any new regression whose root cause is not mechanically obvious.

Do not self-escalate.

## Explicitly forbidden

Do not:

- begin P9-T02/P9-T03/P9-T04;
- fix production code;
- regenerate traces/goldens;
- modify comparator/manifest/normalization;
- modify project data/assets;
- change Android policy;
- change test expectations to absorb a regression;
- merge to `master`.

## Report

TASK RESULT: PASS | PARTIAL | FAIL
FILES CHANGED
MODEL/EFFORT
BRANCH / START HEAD
FULL SUITE RESULT
FULL SUITE BASELINE DELTA
FOCUSED REGRESSION MATRIX
IMMUTABLE TRACE MATRIX
PC PROJECT LAUNCH RESULT
SAVE/LOAD/RESTART RESULT
FAST-FORWARD RESULT
DEBUGGER RESULT
PROFILER RESULT
TYPE CHECK RESULT
IMPORT/COMPILE RESULT
PROJECT-DATA INTEGRITY
PRODUCTION CHANGES
COMMANDS RUN
KNOWN-BASELINE-SAME
KNOWN-BASELINE-CHANGED
NEW REGRESSIONS
ENVIRONMENT/TOOLING LIMITS
ESCALATION TRIGGERS
COMMIT SHA
WORKING TREE STATUS
NEXT ACTION: CONTROLLER REVIEW

STOP FOR CONTROLLER REVIEW.
