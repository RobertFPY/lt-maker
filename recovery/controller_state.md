# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 9 — Full validation and release candidate**
- Phases 1–8: **ACCEPTED**
- P9-T01 full PC regression matrix: **ACCEPTED** at `50e7339986d3eff2998d49000c3b61437949e358`
- P9-T02 full Android regression/performance matrix: **PARTIAL / NOT ACCEPTED** from the execution started at controller commit `4c7f418f43d9d8dd2541c9a6b408d63b26cd1ca5`
  - host Android/platform semantics passed;
  - required immutable Android-relevant Trace V1 scenarios passed;
  - no usable Android device/emulator was connected;
  - the available APK was historical and not provenance-valid for current recovery HEAD;
  - executor could not commit the local report because the local Git environment denied creation of `.git/index.lock`;
  - the uncommitted local report is not controller-reviewed evidence and does not itself advance the gate.
- Active task: **P9-T02-R1 only — Android device completion and evidence finalization**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P9-T03/P9-T04: **UNAUTHORIZED**
- Expected production/test changes: **NONE**
- Allowed evidence change: `recovery/p9_t02_android_regression_performance.md`
- Controller gate after P9-T02-R1: **YES — STOP FOR CONTROLLER REVIEW**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Android tuning/build-config changes merely to manufacture validation: **UNAUTHORIZED**
- Merge to `master`: **UNAUTHORIZED**

## P9-T02 partial evidence record

The controller does **not** accept P9-T02 yet. The reported execution is a valid environment-gated PARTIAL result.

Accepted carry-forward evidence, provided source/test behavior remains unchanged:

- execution used the authorized P9-T02 primary `GPT-5.6 Terra / medium`;
- branch/start point was `recovery/pc-core-semantics` at `4c7f418f43d9d8dd2541c9a6b408d63b26cd1ca5`;
- `adb` 37.0.0 was available but `adb devices -l` returned no connected/authorized target;
- the only available APK was from 2026-08-07 and therefore cannot prove the current recovery HEAD;
- required host-side Android render/resource/platform/audio/work-budget/load/restart/fast-forward/debugger/profiler/cache/recovery contracts were reported green;
- immutable S2/S4/S5/S7/S8/S12/S13/S14/S15/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 were reported exact;
- compileall and diff checks passed;
- no production source, test, project data/assets, Trace V1 schema/comparator/manifest/golden, Android policy values or master changed.

These results may be carried forward into P9-T02-R1 without mechanically rerunning the entire host matrix if the only intervening changes are controller documentation and the P9-T02 evidence report. Any source/test/build-policy change invalidates that carry-forward and requires relevant revalidation.

P9-T02 remains PARTIAL because the release gate still lacks real current-build Android evidence for install/launch, runtime lifecycle, audio/resource behavior and representative performance characterization.

## Locked contracts during P9-T02-R1

All accepted Phase-1-through-8 and P9-T01 semantics remain immutable:

1. One shared gameplay core; Android policy may not fork gameplay semantics.
2. No observable partial authoritative gameplay state.
3. Combat action/RNG/hook/cleanup/state-stack ordering remains locked.
4. Canonical save/load/restart remains one authoritative transaction; SAVE != pristine RESTART.
5. Fast-forward changes time/presentation only, not logical outcomes or input-edge semantics.
6. Debugger/profiler remain observers absent explicit debugger commands.
7. No Event wall-clock command scheduler may return.
8. Android work budgeting remains limited to accepted off-world tilemap preparation; the `4_000_000 ns` value is not a P9-T02 tuning target.
9. `_android_tilemap_pending` remains an Event-local correctness barrier with one synchronous live commit/rollback.
10. P8 cache decisions remain locked: `GC-REGION` NOT CERTIFIED SAFE; battle source-frame cache REJECTED; title smoke KEEP-PLATFORM; styled-text optimization deferred.
11. No Android FPS/device-performance claim may be inferred from host simulation.
12. Trace/goldens and project content/assets remain protected.

---

# P9-T02-R1 — Android device completion and evidence finalization

Execute **P9-T02-R1 only** using **GPT-5.6 Terra / medium**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

This is a narrow continuation of P9-T02. Do not begin P9-T03.

## Pre-task

Before work:

1. read `AGENTS.md`, `AGENTS.override.md`, entire `plan.md`, and this file;
2. verify branch `recovery/pc-core-semantics` and current HEAD;
3. preserve the existing untracked `recovery/p9_t02_android_regression_performance.md` if present;
4. verify no production/test/project/Trace changes are present;
5. print the mandatory task/model report.

## Git report finalization

The prior executor stopped because Git could not create `.git/index.lock`.

This is a local Git/environment issue, not authorization to modify repository behavior.

Allowed handling:

- inspect whether a stale `.git/index.lock` exists and whether another Git process owns it;
- if the Codex execution sandbox cannot write `.git`, leave the report intact and have the user perform the Git add/commit from a normal writable terminal;
- after any controller fast-forward, preserve the untracked report and commit it on top of the current controller HEAD.

Do not broadly rewrite repository ACLs, disable security controls, force-reset, or delete a lock owned by an active Git process merely to make Codex commit.

P9-T02 cannot receive final controller acceptance until its report exists in a committed diff that can be reviewed.

## Real Android gate

A P9-T02 PASS still requires a usable real Android device or emulator.

When a target becomes available:

- capture `adb devices -l` and target authorization;
- record device/emulator model, API, ABI and relevant runtime/build details;
- build/use an artifact provenance-valid for the current recovery source through the existing supported Android build pipeline;
- record exact build commit/provenance;
- install/update using the existing supported route;
- launch the real application/project;
- capture bounded startup/runtime logs;
- verify project/resource/DB load and normal title/game startup;
- prove no recovery-specific startup exception;
- do not use the historical 2026-08-07 APK as current validation evidence.

If no target is available, report PARTIAL again. Do not manufacture a device result with host flags or mocks.

## Android logical/runtime checks on target

Using current accepted gameplay semantics, gather real-runtime evidence where the existing app/tooling supports it for:

- representative level/chapter startup;
- movement/input/touch intent without duplicate action;
- combat completion;
- tilemap pending preparation and blocked live gameplay until atomic commit;
- current SAVE load and pristine RESTART source behavior;
- fast-forward representative path;
- debugger idle/shared-controller behavior;
- profiler disabled/observer behavior;
- representative title/background/battle or other available streamed audio/resource transitions.

Do not invent a second gameplay harness inside the Android app.

Any deterministic logical divergence from accepted PC synchronization semantics => STOP and report `ESC-03`.

## Performance characterization

On the real device/emulator, characterize the current build without changing knobs.

Where tooling supports it, collect representative evidence for:

- startup/title;
- map idle/pan/movement;
- combat;
- representative tilemap change;
- save/load/restart;
- fast-forward.

Record device/build provenance and, where measurable:

- sample duration/frame count;
- median frame time;
- p95 frame time;
- p99 or worst meaningful stall;
- major stall locations/counters;
- process memory/heap/RSS indication;
- audio/resource/preload stalls visible in logs/profiler.

Debug/instrumented measurements must be labeled as such and are characterization, not release-FPS claims.

Do not change work-budget values, cache capacities, renderer policy, audio policy or gameplay semantics.

## Carry-forward host evidence

If no source/test/build-policy behavior changed since the PARTIAL run, the already-reported host matrix and immutable trace results may be cited and carried forward rather than rerun in full.

Still rerun at minimum after final evidence assembly:

- relevant bounded smoke/import/compile checks;
- `git diff --check`;
- `git status --short`;
- any focused owner tests directly exercised by a new device-observed issue.

If any source/test behavior changed, rerun all affected accepted regressions and immutable scenarios before claiming PASS.

## Change policy

Expected committed change:

- `recovery/p9_t02_android_regression_performance.md`

Production source: **UNAUTHORIZED**.
Tests: **UNAUTHORIZED** unless separately controller-approved after a proven defect.
Trace/golden/comparator/manifest: **UNAUTHORIZED**.
Project data/assets: **UNAUTHORIZED**.
Android tuning/build policy: **UNAUTHORIZED**.
Master: **UNAUTHORIZED**.

## PASS / PARTIAL / FAIL

PASS only if all original P9-T02 release requirements are satisfied, including:

- current-provenance Android artifact;
- real device/emulator install and launch;
- no unexplained logical parity divergence;
- accepted tilemap/load/restart/fast-forward/debugger/profiler contracts;
- representative audio/resource validation;
- representative device performance characterization;
- committed evidence report;
- no unauthorized production/project/Trace changes.

PARTIAL if the device/emulator, current artifact, required runtime observation, performance capture, or committed evidence remains unavailable.

FAIL on a reproducible Android semantic/invariant regression attributable to current recovery behavior.

Do not self-advance to P9-T03 even if PASS is reported.

## Escalation

Primary: GPT-5.6 Terra / medium.
Escalation target: GPT-5.6 Sol / high.
Pre-authorized: NO.

STOP/request controller authorization on ESC-02/03/04/05/06/07/08/09.

Do not self-escalate.

## Report

TASK RESULT: PASS | PARTIAL | FAIL
MODEL/EFFORT
BRANCH / START HEAD
FILES CHANGED
GIT INDEX/REPORT FINALIZATION
ANDROID ENVIRONMENT
DEVICE/EMULATOR
ADB STATUS
BUILD/APK PROVENANCE
INSTALL RESULT
REAL ANDROID LAUNCH RESULT
PROJECT STARTUP CHECKPOINT
PC/ANDROID SYNCHRONIZATION PARITY
IMMUTABLE TRACE MATRIX / CARRIED-FORWARD BASIS
HOST ANDROID/PLATFORM REGRESSION MATRIX / CARRIED-FORWARD BASIS
TILEMAP/WORK-BUDGET RESULT
SAVE/LOAD/RESTART RESULT
FAST-FORWARD/INPUT RESULT
DEBUGGER RESULT
PROFILER RESULT
AUDIO/RESOURCE RESULT
PERFORMANCE WORKLOADS
FRAME-TIME MEDIAN/P95/P99
MAJOR STALLS
MEMORY OBSERVATIONS
PERFORMANCE CLAIM LIMITATIONS
PRODUCTION CHANGES
TEST CHANGES
PROJECT/TRACE/GOLDEN CHANGES
COMMANDS RUN
KNOWN BASELINE ISSUES
NEW REGRESSIONS
ENVIRONMENT/TOOLING LIMITS
ESCALATION TRIGGERS
COMMIT SHA
WORKING TREE STATUS
NEXT ACTION: CONTROLLER REVIEW

STOP FOR CONTROLLER REVIEW.
