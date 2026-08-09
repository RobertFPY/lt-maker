# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 9 — Full validation and release candidate**
- Phases 1–8: **ACCEPTED**
- P9-T01 full PC regression matrix: **ACCEPTED** at `50e7339986d3eff2998d49000c3b61437949e358`
  - initial P9-T01 evidence `dcf9c937a3276109aa9f3ded9f1f7155e6b5377c` was PARTIAL;
  - P9-T01-R1 was controller-authorized at `d54decd31cdd36d8d60f7df669d5b515ccce43f3` using GPT-5.6 Terra / high;
  - R1 closed the aggregate recovery-test leak and representative PC launch blockers.
- Active task: **P9-T02 only — Full Android regression/performance matrix**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- Prerequisite P9-T01: **SATISFIED**
- P9-T03/P9-T04: **UNAUTHORIZED**
- Expected production changes: **NONE — validation/evidence only**
- Controller gate after P9-T02: **YES — STOP FOR CONTROLLER REVIEW**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Merge to `master`: **UNAUTHORIZED**

## P9-T01 acceptance record

The controller accepts `50e7339986d3eff2998d49000c3b61437949e358` (`test(recovery): isolate trace fixture classes`).

Accepted evidence:

- it is exactly one descendant of P9-T01-R1 authorization commit `d54decd31cdd36d8d60f7df669d5b515ccce43f3`;
- execution used the explicitly authorized GPT-5.6 Terra / high R1 escalation;
- changed scope is exactly `app/tests/test_recovery_trace.py` plus `recovery/p9_t01_pc_regression_matrix.md`;
- no production source, project data/assets, Trace V1 schema/comparator/manifest/goldens, Android policy or master changed;
- the aggregate full-suite delta was deterministically traced to recovery-added module-level synthetic `ItemComponent`/`SkillComponent` subclasses `_Uses` and `_Marker` leaking into global recursive subclass discovery before base-project component catalog construction;
- the fix only moves those synthetic classes into the sole test that needs them; assertions, inputs and expected values are unchanged;
- import/cache/order evidence proved the polluter and follower relationship rather than inferring safety from fresh-process passes;
- after the test-only correction, authoritative full discovery returned to the recorded P0 logical failure set: 8 FAIL and 1 ERROR before the same native Windows termination `-1073740791` (`0xC0000409`) near the same workspace test;
- all supported immutable Trace V1 scenarios S1/S2/S4-S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 passed exactly; S3 remains reference-unsupported/N-A;
- focused accepted Phase-3-through-8/recovery, canonical load/restart, fast-forward, debugger, profiler and project/base suites passed, apart from explicitly recorded historical baseline failures;
- a real `default.ltproj` process ran through the existing Windows AppData logger route, metadata validation, resource catalogs, DB deserialization, `driver.start`, engine initialization and title music PLAYING state before deliberate bounded termination;
- runtime importability without PyQt5, compileall, diff/show checks and repository cleanliness passed;
- `mypy` remains unavailable and is classified ENVIRONMENT/TOOLING, with no dependency change made.

P9-T01 is therefore closed. The PC release-validation baseline entering Android validation is the accepted current recovery branch behavior at this point, not a regenerated golden or altered reference.

## Locked contracts entering P9-T02

All prior accepted semantics remain immutable:

1. **INV-01 one gameplay core.** Android may specialize platform policy only; no gameplay fork.
2. **INV-02 PC semantics remain the behavioral reference** except previously accepted later correctness fixes/features.
3. **INV-03 no observable partial gameplay state.** Authoritative load/tilemap/combat/event transactions cannot be split across frames or worker boundaries.
4. **INV-04 Android platform policy cannot change gameplay ordering.**
5. **INV-05 shared optimizations require logical/output equivalence.**
6. **INV-06 fast-forward changes time, not outcomes.**
7. **INV-07 debugger/profiler are observers** absent explicit debugger commands.
8. **INV-08 intended features/fixes remain preserved.**
9. **INV-09 project content/assets are protected.**
10. **INV-10 no performance retention/claim without evidence.**

Additional locked findings:

- canonical save/load/restart remains one authoritative transaction; SAVE != pristine RESTART; snapshot-first restart precedence remains accepted;
- Event wall-clock command scheduling must not return;
- Android work budgeting is limited to accepted off-world preparation and may not yield authoritative gameplay work;
- `_android_tilemap_pending` remains an Event-local correctness barrier with one synchronous live commit/rollback;
- Android streamed audio/resource preload behavior remains platform implementation behind shared semantics;
- P8 cache decisions remain locked: `GC-REGION` NOT CERTIFIED SAFE; battle source-frame caching REJECTED; title smoke KEEP-PLATFORM; styled-text optimization deferred;
- no Android performance number may be inferred from desktop/host simulation.

---

# P9-T02 — Full Android regression/performance matrix

Execute **P9-T02 only** using **GPT-5.6 Terra / medium**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

This is a validation/evidence task. Do not tune production code during P9-T02. If validation exposes a real defect, classify and stop for controller review unless the task explicitly permits a mechanical evidence-only continuation.

## Pre-task requirements

Before work:

1. read root `AGENTS.md` completely;
2. read `AGENTS.override.md` completely;
3. read entire `plan.md`;
4. read this live `recovery/controller_state.md`;
5. read at minimum:
   - `recovery/baseline.md`;
   - `recovery/p6_t01_runtime_capability_map.md`;
   - `recovery/p4_t03_android_board_policy.md`;
   - `recovery/p7_t02_debugger_parity.md`;
   - `recovery/p8_t04_android_performance_retuning.md`;
   - `recovery/p9_t01_pc_regression_matrix.md`;
6. inspect current Android build/runtime entrypoints and existing device/smoke tooling before choosing commands;
7. verify branch `recovery/pc-core-semantics`, exact current HEAD and clean status;
8. print the mandatory task/model report.

Do not substitute a stronger model. If Terra/medium is unavailable, STOP.

## Goal A — Android environment and real-runtime capability

Inventory the actual current validation environment without modifying dependencies:

- host OS/interpreter relevant to Android tooling;
- `adb` availability/version;
- connected device/emulator list and authorization state;
- Android API/device model/ABI if a device is available;
- current APK/build route already supported by this repository;
- whether an installable current recovery build already exists or can be produced through the repository-prescribed build path;
- whether current project content is included through the normal build/runtime route.

Do not claim device validation from `ANDROID_ARGUMENT`, mocked runtime flags, SDL dummy mode, or host unit tests.

If no usable Android device/emulator is available, continue all host-side semantic/platform tests that are still meaningful, but P9-T02 must report **PARTIAL**, not PASS, because real Android launch/performance/audio/lifecycle validation cannot be established.

Do not install arbitrary global dependencies or alter Android SDK/NDK/build configuration unless the repository's existing setup already authorizes/contains them.

## Goal B — Android build/install/launch

When a usable device/emulator and repository-supported build route exist:

- build or use the current recovery APK only through the existing project build pipeline;
- install/update it through the existing supported adb/package route;
- launch the real application/project;
- capture bounded startup logs;
- verify project/resource/DB load reaches normal title/game startup;
- prove the process is not dying on a recovery-specific exception;
- record package/version/build provenance and commit SHA used.

A PASS requires a real Android runtime launch on the tested artifact. Host simulation alone is insufficient.

Do not modify project content merely to make the APK launch.

## Goal C — PC/Android synchronization-point semantic parity

Use the locked Trace V1 semantics and existing accepted harnesses where they can exercise Android policy seams without inventing a second gameplay implementation.

At minimum verify representative synchronization points for:

- level/chapter load complete -> before player control;
- movement commit;
- combat cleanup transaction complete;
- Event command transaction complete;
- tilemap change commit/rollback;
- current SAVE load commit;
- pristine chapter restart;
- phase transition;
- fast-forward representative path;
- debugger idle/shared-controller path;
- profiler disabled/observer path.

Required parity statement:

`same logical seed/input/source/context -> same authoritative transaction order -> same synchronization-point logical state`

Allowed Android differences:

- frame count;
- presentation cadence;
- touch mechanics after they map to the same logical input intent;
- audio backend implementation;
- resource preload timing;
- filesystem location;
- off-world preparation timing;
- render/cache implementation.

Not allowed:

- changed action/Event/RNG/hook order;
- changed combat outcome;
- changed save/restart source/context;
- partial GameState/tilemap/board/world visibility;
- Android-only gameplay mutation path;
- worker-thread authoritative gameplay mutation.

Any unexplained deterministic logical divergence => STOP and report `ESC-03`.

## Goal D — Android tilemap/off-world work-budget contract

Revalidate the accepted P4/P6 platform boundary:

- work budgeting applies only to off-world tilemap preparation;
- Android may spread pending preparation across frames;
- live gameplay remains blocked behind the existing Event-local barrier while pending;
- board/boundary/occupancy/aura/FOW are committed once atomically;
- rollback restores the complete old live world;
- no generic Event command deadline/wall-clock scheduler has returned;
- desktop/default policy remains synchronous.

If device timing data is available, measure representative large tilemap preparation and the final synchronous commit separately. Do not tune the 4,000,000 ns policy value in P9-T02.

## Goal E — Android save/load/restart/debugger parity

Validate current Android entry paths against the accepted canonical contracts:

- current SAVE means current progress;
- RESTART means source-proven pristine chapter start;
- matching in-memory chapter-start snapshot is preferred when applicable;
- persistent matching RESTART fallback remains correct;
- stale/wrong restart source is rejected;
- canonical `load_game_data` remains the one authoritative install transaction;
- Android SaveLoadJob/background work remains read/unpickle only;
- no partial authoritative state appears during load;
- debugger restart uses the shared controller and the same source/difficulty rules;
- touch/UI ownership is released correctly before canonical replacement;
- Game Over/title/debugger restart intents converge on the same logical source rules.

Use existing accepted tests plus real Android interaction/log evidence where available. Do not create a second Android load/restart API.

## Goal F — fast-forward, input, debugger and profiler

Verify Android/default policy preserves:

- fast-forward logical equivalence for representative accepted speeds/paths;
- one logical transient input edge is not replayed across multiple logical substeps;
- touch input maps to the same logical intent without creating duplicate gameplay actions;
- debugger commands converge on one `RuntimeDebuggerController.dispatch(op, args)` semantic boundary;
- debugger idle mode does not mutate gameplay;
- profiler disabled/observer modes do not alter logical state/RNG/order;
- worker profiler sections do not become gameplay scheduling inputs.

Do not treat Android UI presentation differences as semantic failures when the logical command/input is identical.

## Goal G — Android audio/resource behavior

Validate accepted platform policy without changing semantic ownership:

- streamed/cached Android music backend can enter and leave expected playback states;
- battle/title/Sound Room music selection remains caller/gameplay semantic ownership, not backend policy;
- preload/release/fallback paths do not duplicate or reorder gameplay events;
- resource preparation remains immutable/off-world before authoritative use;
- no missing-resource regression is introduced by Android packaging/preload behavior.

On a real device, collect bounded log evidence for representative title/background/battle or other available music transitions. If audio output itself cannot be heard/observed through the environment, distinguish backend state/log validation from acoustic validation.

## Goal H — performance characterization

On a real Android device/emulator, collect current-build evidence for representative workloads without changing knobs:

At minimum where tooling supports it:

- startup/title transition;
- representative map idle/pan/movement;
- representative combat;
- large/representative tilemap change;
- save/load/restart transition;
- fast-forward representative path.

Record, where measurable:

- workload and device/build provenance;
- sample duration/frame count;
- median frame time;
- p95 frame time;
- p99 or worst meaningful stall;
- major stall locations/counters;
- memory/heap or process RSS indication for memory-sensitive paths;
- audio/resource/preload stalls visible in logs/profiler;
- whether measurements are debug/instrumented and therefore not release-FPS claims.

No fabricated threshold is required if the repository has no accepted device baseline. This task is a release characterization plus regression search, not a new optimization round.

A performance observation must never override semantic correctness.

Do not change cache capacities, work-budget constants, renderer policy, audio streaming, or gameplay code in P9-T02.

## Required host-side regression matrix

Regardless of device availability, run relevant accepted suites in fresh processes as appropriate, including at minimum:

- Android render/resource/performance policy suites;
- sound platform policy / Android Sound Room tests;
- P4 tilemap pending/atomic restore tests;
- P5 canonical load/restart/atomic restore tests;
- P6 work-budget/platform boundary tests;
- P7 fast-forward equivalence;
- P7 debugger/controller/parity;
- P7 profiler observer equivalence;
- P7 save/load/restart UX routing where available;
- P8 cache/title/render owner regressions;
- recovery Trace/golden/lifecycle integrity;
- project/base integrity.

Immutable scenarios required at minimum:

- S2 load;
- S4 restart;
- S5 representative gameplay;
- S7/S8 combat paths;
- S12 aura;
- S13 FOW;
- S14 tilemap;
- S15 phase;
- S16 fast-forward;
- S17 disabled/debugger-idle/profiler-idle;
- S18 game-over/restart.

No golden regeneration.

## Change policy

Expected code changes: **NONE**.

Allowed by default:

- `recovery/p9_t02_android_regression_performance.md`.

Do not modify:

- production source;
- tests merely to absorb a failure;
- Trace V1 schema/comparator/manifest/goldens;
- project data/assets;
- Android policy/tuning values;
- build configuration merely to manufacture a passing environment;
- master.

If a mechanical environment-only invocation script already tracked by the repository must be used, use it without behavioral modification. Do not add a new validation-only gameplay path.

## PASS / PARTIAL / FAIL rules

P9-T02 may report **PASS** only if:

1. a real current-recovery Android artifact launches on a real usable Android device/emulator through the existing supported route;
2. host-side Android/platform regression matrix passes aside from explicitly accepted historical baseline issues;
3. required deterministic semantic/parity evidence has no unexplained logical divergence;
4. tilemap/load/restart/fast-forward/debugger/profiler contracts remain intact;
5. representative Android audio/resource behavior shows no new regression;
6. representative Android performance data is collected with device/build provenance, even if only characterization is possible due lack of historical device baseline;
7. no production/project/Trace changes are made;
8. required commands/evidence are not silently skipped.

Report **PARTIAL** when correctness evidence is green but the environment cannot provide a usable Android device/emulator, install/launch route, acoustic observation, or required performance measurement. Clearly distinguish which release gate remains unproven.

Report **FAIL** on a reproduced Android semantic regression, partial authoritative state, broken canonical source/transaction, device startup regression attributable to current recovery code, or other violated locked invariant.

## Escalation / stop rules

Primary: GPT-5.6 Terra / medium.
Escalation target: GPT-5.6 Sol / high.
Escalation pre-authorized: NO.

STOP and request controller authorization before escalation on:

- `ESC-02` nonlocal root cause crossing correctness-critical subsystems;
- `ESC-03` deterministic PC/Android logical trace divergence;
- `ESC-04` competing semantics;
- `ESC-05` invariant/partial-state failure;
- `ESC-06` save compatibility/source conflict;
- `ESC-07` Android performance goal requiring changed gameplay ordering/partial state;
- `ESC-08` repeated bounded local failure;
- `ESC-09` new cross-cutting architecture required.

Do not self-escalate to Sol.

## Final verification

Before commit/report completion:

- inspect complete diff;
- `git diff --check`;
- compile/import checks appropriate to changed scope;
- `git status --short`;
- ensure no generated/debug/device artifacts are tracked accidentally;
- ensure no `.ltproj` or asset changes;
- commit only the bounded evidence report;
- `git show --check`;
- final clean `git status --short`.

## Report

```text
TASK RESULT: PASS | PARTIAL | FAIL
MODEL/EFFORT:
BRANCH:
START HEAD:
FILES CHANGED:

ANDROID ENVIRONMENT:
DEVICE/EMULATOR:
ADB STATUS:
BUILD/APK PROVENANCE:
INSTALL RESULT:
REAL ANDROID LAUNCH RESULT:
PROJECT STARTUP CHECKPOINT:

PC/ANDROID SYNCHRONIZATION PARITY:
IMMUTABLE TRACE MATRIX:
HOST ANDROID/PLATFORM REGRESSION MATRIX:
TILEMAP/WORK-BUDGET RESULT:
SAVE/LOAD/RESTART RESULT:
FAST-FORWARD/INPUT RESULT:
DEBUGGER RESULT:
PROFILER RESULT:
AUDIO/RESOURCE RESULT:

PERFORMANCE WORKLOADS:
FRAME-TIME MEDIAN/P95/P99:
MAJOR STALLS:
MEMORY OBSERVATIONS:
PERFORMANCE CLAIM LIMITATIONS:

PRODUCTION CHANGES:
TEST CHANGES:
PROJECT/TRACE/GOLDEN CHANGES:
COMMANDS RUN:
KNOWN BASELINE ISSUES:
NEW REGRESSIONS:
ENVIRONMENT/TOOLING LIMITS:
ESCALATION TRIGGERS:
COMMIT SHA:
WORKING TREE STATUS:
NEXT ACTION: CONTROLLER REVIEW
```

STOP FOR CONTROLLER REVIEW. Do not begin P9-T03.
