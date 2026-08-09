# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 7**
- Phases 1–6: **ACCEPTED**
- P7-T01 fast-forward equivalence suite: **ACCEPTED** at `874c7adcf83f14e6fcf961180a01f4ddfe1201fe`
- Active task: **P7-T02 only — Debugger parity PC/Android**
- Primary model: **GPT-5.6 Luna / medium**
- Escalation target: **GPT-5.6 Terra / high**
- Escalation pre-authorized: **NO**
- P7-T03/P7-T04 and Phase 8+: **UNAUTHORIZED**
- Production behavior changes: **test/evidence first; only a bounded debugger-specific correctness fix is allowed when parity evidence proves one unambiguous defect**
- Gameplay-core semantic changes: **UNAUTHORIZED**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P7-T02: **YES — STOP FOR CONTROLLER REVIEW**

## P7-T01 acceptance record

The controller accepts `874c7adcf83f14e6fcf961180a01f4ddfe1201fe` (`test(recovery): prove fast-forward equivalence`).

Accepted evidence:

- it is exactly one descendant of P7-T01 authorization commit `fc3f1812fc4548702f9ab549ce7ce203b169e5c4`;
- scope is test/evidence only: `app/tests/recovery_trace_runner.py`, `app/tests/test_fast_forward_equivalence.py`, and `recovery/p7_t01_fast_forward_equivalence.md`;
- no production source, Trace V1 implementation, comparator, manifest, golden fixture, schema, project data, or asset changed;
- the new `FastForwardScenarioFrameDriver` is test-owned and routes fast-forward ON runs through production `driver.update_game_state_for_frame()` rather than reimplementing fast-forward semantics;
- existing scenario scripts retain their state/readiness-driven input conditions; ON/OFF input is not aligned by host-frame number;
- ON/OFF pairs compare complete existing Trace V1 records with `trace.compare_records()` for S5/S6/S7/S8/S13/S15/S18;
- speed invariance OFF vs 200%/300%/800% is covered using the same simple-combat trace;
- transient SELECT/BACK/START/directional/TEXTINPUT/mouse-click evidence proves only the first fast-forward substep sees the host transient input while later substeps see an empty transient snapshot;
- existing repeat-chain, blocking-state and explicit presentation-barrier tests remain part of the proof;
- immutable S5/S7/S8/S13/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 were reported exact PASS;
- S17 does not run an outer-frame driver at all: it starts a level, exercises an idle observer, and captures checkpoints. Therefore the existing S17 harness has no fast-forward frame seam to combine without inventing additional infrastructure; its disabled/debugger-idle/profiler-idle equality remains the appropriate observer proof for P7-T01;
- no fast-forward divergence or production fix was required;
- broad-suite `_Uses.tag` registry pollution/native Windows termination remains unrelated baseline evidence.

## Locked fast-forward contract

Later phases must preserve:

1. Fast-forward OFF is the accepted recovery gameplay semantic baseline.
2. Fast-forward ON may change host-frame/presentation timing only, never logical outcomes/order.
3. Input equivalence is aligned to logical readiness/user intent, not host-frame number.
4. Only the first fast-forward substep may consume a host transient input edge; later substeps/repeat chains do not replay it.
5. `blocks_fast_forward` and explicit presentation fences may stop additional substeps without changing gameplay outcomes.
6. Fast-forward may not reintroduce generic Android Event command scheduling or alter accepted combat/load/restart/tilemap semantics.

---

# P7-T02 — Debugger parity PC/Android

Execute **P7-T02 only** using **GPT-5.6 Luna / medium**.

Escalation target: **GPT-5.6 Terra / high**, not pre-authorized.

PC behavioral reference remains `9314f54b49f4552b5a3d023b4da0012ce7dfbc89` for core gameplay semantics, but the runtime debugger itself is a later intended feature. The parity oracle is the shared accepted recovery debugger semantics, not absence from the PC reference.

## Semantic authority

`app/engine/runtime_debugger_controller.py` is the shared semantic command boundary.

Current architecture:

```text
desktop web UI / HTTP thread
    -> RuntimeDebuggerService command queue
    -> RuntimeDebuggerService.update() on game thread
    -> RuntimeDebuggerController.dispatch(op, args)
    -> RuntimeDebugger gameplay operation

Android in-game debugger UI
    -> RuntimeDebuggerController.dispatch(op, args) directly on game thread
    -> RuntimeDebugger gameplay operation
```

The two frontends do **not** need identical visual widgets or input mechanics. They must expose equivalent intended operations and produce the same logical mutation/result for the same controller operation and valid arguments.

Do not create separate Android cheat semantics or duplicate controller operations in either frontend.

## Goal

Verify intended debugger operations and frontend integration on desktop and Android, including:

- selected-unit inspection/focus;
- editable unit fields: level, EXP, HP, mana, fatigue, guard, movement, position, stats, growths, cap modifiers and WEXP where available;
- max selected unit;
- auto-level +1;
- give item including bounded uses/charges;
- teleport and tile-pick flow;
- max all player units;
- max all enemy units;
- set enemy HP to 1;
- disable enemy AI;
- complete current chapter;
- go to chapter with explicit difficulty;
- restart current chapter with explicit difficulty and accepted P5 pristine restart semantics;
- set money;
- set turn count;
- set turnwheel uses/enabled state;
- set/clear weather;
- event command execution and command suggestions/catalog where frontend-supported;
- desktop hotkeys Ctrl+1..5 / Ctrl+0;
- Android native text editor fallback/Save/Cancel/error routing where testable without JNI device code;
- Android touch-consumer registration/release, especially around debugger exit and restart.

## Required parity model

Prefer controller-level paired tests for semantic operations:

```text
same initial logical game state
same op + args
route A: desktop service queue -> game-thread update -> controller
route B: Android frontend/direct controller route
compare:
    result/validation class
    logical game mutation
    state/temp-state transitions
    action-log relevant state
    save/restart destination where applicable
```

Do not compare browser HTML, pixel layout, touch coordinates, native Android typography, or HTTP timing as gameplay parity fields.

Where directly invoking the Android UI action handler is practical, prove it maps to the same controller op/args. Do not reimplement every full UI gesture just to reach the controller.

## Desktop service / thread contract

Prove:

- HTTP/server thread only enqueues commands and waits for completion;
- `RuntimeDebuggerService.update()` drains commands on the game thread and calls the shared controller;
- snapshot publication remains observer-only;
- timeouts/errors do not execute the same command twice;
- stopping/starting the debugger service does not mutate gameplay state by itself;
- debugger disabled/idle remains observer-equivalent to disabled gameplay.

Do not move game mutation onto the HTTP thread.

## Android frontend contract

Prove:

- Android debugger remains a transparent `blocks_fast_forward` state;
- actions call the shared controller rather than duplicating RuntimeDebugger mutations;
- commands that need to close the drawer insert/pop the debugger state in the correct order before queued Event/state transitions;
- raw-touch consumer is registered while the debugger owns touch and released on end;
- native text editor success/cancel/error handling cannot submit a command twice;
- pygame text-input fallback remains available when native editor is unavailable;
- debugger restart releases Android touch ownership before canonical restart can replace the state stack.

Platform UI integration may differ; gameplay mutation semantics may not.

## Restart / chapter navigation

Preserve accepted Phase-5 contracts.

`restart_chapter` must:

- use a matching current-session `chapter_start_snapshot` first;
- otherwise use only a source-proven matching RESTART_SLOT;
- preserve explicit requested difficulty through P5 canonical load context;
- never fall back to current mid-chapter SAVE_SLOT as pristine restart truth;
- rebuild chapter-start initiative semantics;
- release Android raw-touch capture before state replacement.

`go_chapter` / `complete_chapter` must continue to queue the shared Event path rather than directly mutating chapter state in a frontend-specific way.

If parity failure points into P5 canonical load/restart architecture, STOP rather than reopening it in P7-T02.

## Observer equivalence

Run S17 disabled/debugger-idle/profiler-idle and preserve exact equality.

Additionally prove debugger snapshot/catalog polling while idle does not mutate gameplay state, action log, RNG, phase, units, board/FOW/aura, save state, or state-stack transitions except UI-only debugger state when the Android drawer itself is intentionally opened.

Do not instrument gameplay hooks merely to observe them.

## Production-change boundary

Expected default scope is tests/evidence only.

A bounded production fix is allowed only when:

- parity test demonstrates a debugger-specific defect;
- the shared controller semantics or other frontend give one unambiguous correct behavior;
- fix remains inside debugger frontend/controller/service integration;
- no accepted gameplay-core contract changes.

Allowed bounded surfaces if evidence requires a fix:

- `app/engine/runtime_debugger.py`
- `app/engine/runtime_debugger_controller.py`
- `app/engine/runtime_debugger_service.py`
- `app/engine/android_debugger.py`
- narrow `app/engine/android_runtime.py` debugger/touch bridge only if the defect is proven there
- focused tests/report

If another gameplay-critical module is required, STOP under ESC-02/ESC-05/ESC-09.

## Required tests

At minimum prove:

1. Shared controller command catalog/snapshot is available to both frontends without gameplay mutation.
2. Desktop queued command executes exactly once on service update/game thread.
3. Android frontend action maps to the same controller operation and arguments for representative Unit, World and Event operations.
4. Unit field edit parity.
5. Max/auto-level parity.
6. Give-item parity including explicit uses where supported.
7. Teleport parity and occupied/out-of-bounds rejection.
8. Batch player/enemy max parity.
9. Enemy HP/AI parity.
10. Complete-chapter shared Event routing.
11. Go-chapter + difficulty shared Event routing.
12. Restart + difficulty uses accepted P5 snapshot/restart source and canonical load path.
13. Money/turn-count/turnwheel/weather parity.
14. Event-command validation/execution parity and no duplicate dispatch.
15. Desktop hotkey mapping calls the same controller ops.
16. Android drawer close-before-event transition ordering remains correct.
17. Android raw-touch consumer is installed/released correctly.
18. Native text editor Save/Cancel/error/fallback logic does not double-submit.
19. Debugger enabled but idle is observer-equivalent.
20. Existing fast-forward equivalence remains green; Android debugger remains `blocks_fast_forward`.
21. P5 canonical load/restart tests remain green.
22. P6 platform-policy tests remain green.

Use deterministic state assertions; prefer mutation/result equality over checking only that calls did not crash.

## Immutable proof

Run at minimum:

- S2 load
- S4 restart
- S5 representative gameplay
- S16 fast-forward
- S17 disabled
- S17 debugger-idle
- S17 profiler-idle
- S18 game-over/restart

Add S12/S13/S14 if a production debugger fix touches board/aura/FOW/tilemap integration.

No golden regeneration.

Run focused:

- existing `test_runtime_debugger*` suites;
- Android debugger/frontend tests;
- runtime debugger service/controller tests;
- canonical load/restart;
- fast-forward/input state tests;
- observer/profiler tests;
- recovery trace/lifecycle/golden integrity.

Run broader unittest discovery and report known baseline/native/test-isolation failures without repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- bounded commit
- `git show --check`
- `git status --short`

## Explicitly out of scope

Do not:

- begin P7-T03/P7-T04 or Phase 8;
- redesign the debugger UI;
- require desktop and Android visual/UI identity;
- fork debugger gameplay semantics by platform;
- move desktop mutations onto the HTTP thread;
- change P5 load/restart contracts;
- change fast-forward semantics;
- change Phase-3 combat or Phase-4 tilemap semantics;
- change P6 platform capability contracts;
- change Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Luna / medium**.
Escalation target: **GPT-5.6 Terra / high**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** parity defect root cause is nonlocal;
- **ESC-03** immutable trace divergence;
- **ESC-04** desktop/Android expose genuinely competing intended debugger semantics with no shared-controller answer;
- **ESC-05** debugger operation exposes partial/invalid gameplay state;
- **ESC-06** restart/save compatibility conflict appears;
- **ESC-07** fix would require a platform gameplay fork;
- **ESC-08** repeated bounded fix failure;
- **ESC-09** new cross-cutting debugger/gameplay architecture appears necessary.

Do not self-escalate.

## Gate status

**P7-T01 is ACCEPTED. P7-T02 is the only authorized task. P7-T03/P7-T04 and Phase 8+ remain blocked pending controller review.**
