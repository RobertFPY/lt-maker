# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 9 — Full validation and release candidate**
- Phases 1–8: **ACCEPTED**
- P9-T01 full PC regression matrix: **ACCEPTED** at `50e7339986d3eff2998d49000c3b61437949e358`
- P9-T02 full Android regression/performance matrix: **PARTIAL / NOT ACCEPTED**
  - initial committed PARTIAL evidence: `392a8f5fb260a8b84ff86fc767c1b2e3136f1968`
  - device-gate recheck PARTIAL evidence: `81670bb6ca194217e78a652ac7e57e6e42387063`
  - host Android/platform regression matrix passed;
  - required immutable Android-relevant Trace V1 scenarios passed exactly;
  - no production/test/project/Trace/build-policy changes occurred;
  - no authorized Android device/emulator was connected;
  - no current-provenance Android artifact was installed/launched;
  - no real-device audio/resource/runtime or performance evidence exists yet.
- Active task: **P9-T02 remains open — WAITING ON REAL ANDROID TARGET**
- Next executor continuation when a target exists: **P9-T02-R2 only — Android device completion**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P9-T03/P9-T04: **UNAUTHORIZED**
- Expected production/test changes: **NONE**
- Allowed evidence change: `recovery/p9_t02_android_regression_performance.md`
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Android tuning/build-policy changes merely to manufacture validation: **UNAUTHORIZED**
- Merge to `master`: **UNAUTHORIZED**

## P9-T02 partial acceptance record

The controller accepts `81670bb6ca194217e78a652ac7e57e6e42387063` as **valid PARTIAL evidence only**. It does not close P9-T02.

Accepted evidence:

- ancestry from controller gate `a890539c52fddbfa3e5c07602fb356a9ec00c798` is clean;
- the two executor commits after that controller gate change only `recovery/p9_t02_android_regression_performance.md`;
- `392a8f5fb260a8b84ff86fc767c1b2e3136f1968` committed the original Android matrix PARTIAL report;
- `81670bb6ca194217e78a652ac7e57e6e42387063` only rechecked the Android device gate and appended evidence;
- execution used the authorized primary `GPT-5.6 Terra / medium`;
- ADB 37.0.0 was available but `adb devices -l` returned no connected/authorized target;
- the historical 2026-08-07 APK is explicitly rejected as current-provenance release evidence;
- required host Android/platform policy suites and immutable S2/S4/S5/S7/S8/S12/S13/S14/S15/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 were reported green/exact;
- compileall and diff checks passed;
- no Android knob, including the accepted `4_000_000 ns` off-world work budget, changed;
- no production source, tests, project data/assets, Trace V1 schema/comparator/manifest/goldens, Android build policy or master changed.

These host/Trace results may be carried forward while source/test/build-policy behavior remains unchanged. Do not mechanically rerun them on every no-device retry.

P9-T02 remains blocked solely on real Android release evidence. Do not invoke another executor retry until `adb devices -l` shows an authorized usable device/emulator, unless the controller explicitly asks for another environment diagnosis.

## Locked contracts while waiting

1. One shared gameplay core; no Android gameplay fork.
2. No observable partial authoritative gameplay state.
3. Combat action/RNG/hook/cleanup/state-stack ordering remains locked.
4. Canonical save/load/restart remains one authoritative transaction; SAVE != pristine RESTART.
5. Fast-forward changes time/presentation only, not logical outcomes/input-edge semantics.
6. Debugger/profiler remain observers absent explicit debugger commands.
7. No Event wall-clock command scheduler may return.
8. Android work budgeting remains limited to accepted off-world tilemap preparation; `4_000_000 ns` is not a validation tuning target.
9. `_android_tilemap_pending` remains an Event-local correctness barrier with one synchronous live commit/rollback.
10. P8 cache decisions remain locked: `GC-REGION` NOT CERTIFIED SAFE; battle source-frame cache REJECTED; title smoke KEEP-PLATFORM; styled-text optimization deferred.
11. No Android FPS/device-performance claim may be inferred from host simulation.
12. Trace/goldens and project content/assets remain protected.

---

# P9-T02-R2 — Android device completion

Run **only when `adb devices -l` shows an authorized usable Android device/emulator**.

Use **GPT-5.6 Terra / medium** exactly.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

Do not begin P9-T03.

## Required completion evidence

Using only the repository-supported Android build/install/launch route:

1. record device/emulator model, API level, ABI and ADB state;
2. build or obtain an artifact provenance-valid for the current recovery source;
3. record exact artifact/build provenance and hash;
4. install/update it on the authorized target;
5. launch the real application/project;
6. capture bounded startup/runtime logs proving project/resource/DB load and normal title/game startup;
7. verify no recovery-specific startup exception;
8. gather real-runtime evidence where supported for movement/touch intent, combat completion, tilemap pending+atomic commit, SAVE load, pristine RESTART, fast-forward, debugger idle/shared-controller behavior, profiler disabled/observer behavior, and representative Android streamed audio/resource transitions;
9. compare synchronization-point logical semantics against the accepted PC behavior; any unexplained deterministic divergence => STOP/report `ESC-03`;
10. characterize current-build performance without changing knobs for representative startup/title, map/movement, combat, tilemap transition, save/load/restart and fast-forward workloads;
11. where measurable record sample duration/frame count, median frame time, p95, p99/worst meaningful stall, major stalls and process memory/heap/RSS indication;
12. label debug/instrumented measurements as characterization, not release-FPS claims;
13. update only `recovery/p9_t02_android_regression_performance.md` unless the controller separately authorizes something else;
14. run relevant compile/import checks, `git diff --check`, `git show --check` and finish clean.

Do not change production source, tests, Trace/goldens, project data/assets, Android work-budget/cache/render/audio policy, or master.

Host/Trace evidence from `392a8f5f`/`81670bb6` may be carried forward if source/test/build-policy behavior is unchanged. If any such behavior changes, rerun all affected accepted regressions and immutable scenarios.

## PASS / PARTIAL / FAIL

PASS only if current-provenance real Android install/launch, runtime parity evidence, representative audio/resource validation and device performance characterization are complete with no unexplained semantic divergence.

PARTIAL if any required real-device gate remains unavailable.

FAIL on a reproducible Android semantic/invariant regression attributable to current recovery behavior.

STOP FOR CONTROLLER REVIEW. Do not self-advance to P9-T03.
