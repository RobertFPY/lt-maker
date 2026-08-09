# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 7**
- Phases 1–6: **ACCEPTED**
- P7-T01 fast-forward equivalence: **ACCEPTED** at `874c7adcf83f14e6fcf961180a01f4ddfe1201fe`
- P7-T02 debugger parity PC/Android: **ACCEPTED** at `11f2a42cd055d089917834ef80d74d369aad5ed8`
- Active task: **P7-T03 only — Profiler observer-equivalence**
- Primary model: **GPT-5.6 Luna / low**
- Escalation target: **GPT-5.6 Terra / medium**
- Escalation pre-authorized: **NO**
- P7-T04 and Phase 8+: **UNAUTHORIZED**
- Production behavior changes: **test/evidence first; only a bounded profiler-specific observer-correctness fix is allowed if deterministic evidence proves one unambiguous defect**
- Gameplay-core semantic changes: **UNAUTHORIZED**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- P7-T03 static plan gate is `No`, but live recovery governance still forbids self-advancing to P7-T04; stop and report after the bounded P7-T03 commit so the controller can verify the evidence and authorize P7-T04 explicitly.

## P7-T02 acceptance record

The controller accepts `11f2a42cd055d089917834ef80d74d369aad5ed8` (`test(debugger): prove desktop android parity`).

Accepted evidence:

- it is exactly one descendant of P7-T02 authorization commit `6a28b268724dfd2a0f3ff1265cd352cbeea06576`;
- scope is test/evidence only: `app/tests/test_runtime_debugger_parity.py` and `recovery/p7_t02_debugger_parity.md`;
- no production source, Trace V1 implementation, comparator, manifest, golden fixture, save/restart code, project data, or assets changed;
- the desktop HTTP proof uses a real local request and proves the HTTP thread only queues/waits: `RuntimeDebuggerController.dispatch()` is not called until `RuntimeDebuggerService.update()` drains the command on the game thread;
- one queued command dispatches exactly once, including dispatch-error and HTTP-timeout cases; a timeout may leave one queued command for later execution but does not duplicate that mutation;
- Android representative Unit/World/Event actions and the desktop service queue converge on the same `RuntimeDebuggerController.dispatch(op, args)` call shape;
- shared-controller ownership means the two frontends do not contain separate gameplay mutation implementations requiring duplicated semantic algorithms;
- desktop Ctrl+1/2/3/4/5/0 hotkeys retain their intended shared operations;
- Android debugger remains `blocks_fast_forward`, owns/releases the raw-touch consumer through its lifecycle, and native editor result consumption is protected against duplicate submission;
- existing controller/runtime debugger, P5 canonical restart, P7 fast-forward, platform-policy and immutable S2/S4/S5/S16/S17/S18 contracts were reported green;
- no debugger parity defect required a production fix;
- lack of Android-device/JNI hardware validation remains an external validation limit, not a deterministic semantic blocker.

## Locked debugger contract

Later tasks must preserve:

1. `RuntimeDebuggerController.dispatch(op, args)` is the shared gameplay-semantic debugger boundary.
2. Desktop HTTP/server threads may queue/read presentation data but may not mutate gameplay directly.
3. Android UI may differ in presentation/input mechanics but may not fork debugger gameplay mutations.
4. Debugger restart remains bound to the accepted P5 pristine chapter restart contract and canonical load transaction.
5. Debugger enabled but idle remains observer-equivalent.

---

# P7-T03 — Profiler observer-equivalence

Execute **P7-T03 only** using **GPT-5.6 Luna / low**.

Escalation target: **GPT-5.6 Terra / medium**, not pre-authorized.

Plan objective: verify profiler ON/OFF logical state equivalence and worker-thread scope isolation.

## Semantic contract

`RUNTIME_PROFILER` is an observer only.

Profiler ON may change:

- timing samples;
- profiler-owned counters/deques/scope records;
- warning/log output;
- GC diagnostic counters;
- profiler memory overhead.

Profiler ON must NOT change:

- gameplay actions or action order;
- RNG state/consumption;
- combat solver/playback/cleanup outcomes;
- Event command ordering/lifecycle;
- state-machine transitions;
- phase/initiative;
- units/items/skills/statuses;
- board/aura/FOW/regions;
- save/load/restart semantics;
- fast-forward logical outcomes;
- debugger gameplay semantics;
- Android tilemap barrier/atomic commit behavior.

Profiler instrumentation must never become a semantic branch condition.

## Current profiler architecture to prove

`app/engine/performance.py` currently:

- enables runtime profiling only under the Android/profile environment policy;
- stores frame timing/scope/counter history inside `RuntimeProfiler`;
- registers `_on_gc` with `gc.callbacks` when enabled at construction;
- sets `_frame_thread_id` in `begin_frame()`;
- `section()` records scopes only when enabled **and** the current thread equals `_frame_thread_id`;
- worker-thread sections therefore yield without touching the shared main-thread scope stack;
- `finish_frame()` aggregates/logs profiler-owned data.

These are implementation details to verify, not authority to change gameplay behavior.

## Required proof

At minimum prove:

1. Profiler disabled: `begin_frame`, `section`, `count`, `finish_frame` do not alter gameplay state and do not emit profiler warnings.
2. Profiler enabled around a representative deterministic gameplay update produces the same logical state/result as profiler disabled.
3. Enabled profiler does not change RNG state before/after representative deterministic gameplay.
4. Enabled profiler does not change action/action-log order in representative combat/Event/state-machine paths.
5. S17 disabled == S17 profiler-idle exactly under immutable Trace V1.
6. S17 debugger-idle remains unchanged as a neighboring observer baseline.
7. A worker thread entering `RUNTIME_PROFILER.section()` during an active main-thread frame does not append/pop/corrupt the main-thread `_scope_stack` or `_frame_scopes`.
8. Main-thread nested scope parentage remains correct even when a worker attempts a scope concurrently.
9. Worker scope execution still executes the wrapped worker body exactly once; profiling cannot suppress worker work.
10. A worker thread cannot change `_frame_thread_id` merely by entering `section()`.
11. `count()`/logging/profiler metadata do not become gameplay inputs.
12. GC callback only mutates profiler-owned GC counters; registering/removing the test callback does not mutate gameplay state.
13. Profiler exceptions/log formatting are not used to alter gameplay lifecycle.
14. P7-T01 fast-forward equivalence remains green with existing profiler-idle observer proof.
15. P7-T02 debugger parity remains green.
16. P6 Event/tilemap platform-policy tests remain green.
17. P5 canonical load/restart and Phase-3 combat lifecycle focused tests remain green.

## Thread-isolation emphasis

The accepted Android preload/resource workers may execute code enclosed by profiler sections.

Worker-thread profiler calls must be observational no-ops with respect to the active main-thread frame scope tree.

Do not solve thread safety by:

- serializing gameplay on the profiler lock;
- moving gameplay to another thread;
- creating thread-local gameplay state;
- allowing worker scopes into the main frame tree.

If correct observer behavior would require such architecture, STOP under ESC-02/ESC-09.

## Test/evidence scope

Expected default changes:

- focused tests, preferably extending `app/tests/test_performance_profiler.py` or adding one bounded profiler-equivalence test file;
- optionally `recovery/p7_t03_profiler_observer_equivalence.md`.

Expected production changes: **NONE**.

A production change to `app/engine/performance.py` is allowed only if deterministic evidence proves a profiler-specific observer defect and the fix changes profiler-owned state only.

If a fix requires changing gameplay/state/combat/Event/save/load/tilemap code, STOP and escalate/review.

## Immutable proof

Run at minimum:

- S5 representative gameplay
- S16 fast-forward
- S17 disabled
- S17 debugger-idle
- S17 profiler-idle
- S18 game-over/restart

If any production profiler fix touches instrumentation in combat/Event/state-machine call sites, also run the relevant immutable scenarios exercised by those surfaces; do not regenerate goldens.

Run focused:

- `app.tests.test_performance_profiler`
- Android performance/profiler instrumentation tests
- recovery observer/S17 tests
- P7 fast-forward equivalence
- P7 debugger parity
- Phase-3 combat lifecycle
- P5 canonical load/restart
- P6 platform-policy/Event/tilemap tests
- recovery trace/lifecycle/golden integrity

Run broader unittest discovery and report known baseline/native/test-isolation failures without fixing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- bounded commit
- `git show --check`
- `git status --short`

## Explicitly out of scope

Do not:

- begin P7-T04 or Phase 8;
- modify gameplay to accommodate profiler instrumentation;
- change profiler into a scheduler;
- change fast-forward semantics;
- change debugger semantics;
- change combat/Event/tilemap/load/restart contracts;
- change Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Luna / low**.
Escalation target: **GPT-5.6 Terra / medium**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** observer defect root cause is nonlocal;
- **ESC-03** immutable trace divergence;
- **ESC-04** competing profiler semantics affect gameplay;
- **ESC-05** instrumentation changes logical state/lifecycle;
- **ESC-07** platform-specific instrumentation would require gameplay fork;
- **ESC-08** repeated bounded failure;
- **ESC-09** cross-cutting thread/scheduler architecture appears necessary.

Do not self-escalate.

## Gate status

**P7-T02 is ACCEPTED. P7-T03 is the only authorized task. P7-T04 and Phase 8+ remain blocked pending controller review.**
