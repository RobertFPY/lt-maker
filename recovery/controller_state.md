# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. Historical evidence remains in the committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 4**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- P4-T01 tilemap/board/event atomicity audit: **ACCEPTED** at `5c94701d936a5ebbb3ebc0147e9e16e5e1d0ef25`
- Active task: **P4-T02 only — Restore desktop atomic tilemap semantics**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- P4-T03 and Phase 5+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P4-T02: **YES — STOP FOR CONTROLLER REVIEW**

## P4-T01 acceptance record

The controller accepts `recovery/p4_t01_tilemap_atomicity_map.md` from `5c94701d936a5ebbb3ebc0147e9e16e5e1d0ef25` as the authoritative Phase-4 decomposition map.

Accepted findings:

- the commit is a single direct descendant of P4-T01 authorization commit `6ad10d13c201d33adcef5bfb4b1ed8558d0d9581` and changes only the audit report;
- the PC reference executes `change_tilemap` as one synchronous event-command transaction: unit detach -> region detach -> tilemap/board/boundary setup -> optional overworld controller replacement -> unit restore -> region restore -> turnwheel/action-log fence, with no normal lifecycle yield inside that sequence;
- current pending `TileMapObject`, `GameBoard`, and `BoundaryInterface` construction/validation can remain isolated from live gameplay when the pending builders use only the pending tilemap/static DB data;
- current `TilemapChangeJob` commit scheduling from `6b96e2f1` is unsafe: the callback is a generator and yields after authoritative `LeaveMap`, `RemoveRegion`, live tilemap/board/boundary publication, unit restore prefixes, and region restore prefixes;
- `_defer_render` is only a presentation policy. It can hide a visual half-map but cannot make a logically partial `game` state unobservable to movement/state updates, debugger/direct readers, aura/FOW/region queries, or board consumers;
- current rollback is useful exception recovery but cannot justify yielded partial publication. It must execute synchronously before control returns to normal lifecycle code if a live commit fails;
- `cd8607b6` `AddGroupJob` is also an authoritative scheduling regression: it places live units one at a time across Event updates, so board occupancy, initiative, aura/FOW, and other placement effects can be observed as a prefix group;
- complete-state immutable comparisons S12, S13, S14, S15, and S17 remain PASS, but terminal equality does not prove current intermediate generator frames are safe;
- the accepted transaction contract is:

```text
LIVE OLD STATE
    -> optional pending/off-world build and validation
    -> one synchronous main-thread authoritative commit
LIVE NEW STATE
```

No yield or normal lifecycle/observer execution is allowed between the first live mutation and the completed action-log fence.

## P4-T02 — authorized implementation contract

Execute **P4-T02 only** using **GPT-5.6 Terra / high**.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Use `recovery/p4_t01_tilemap_atomicity_map.md` as the accepted function/order map. Immutable Phase-1 goldens remain the oracle and may not be regenerated, replaced, or weakened.

### Goal

Restore reference-shaped atomic tilemap/event gameplay semantics on desktop and remove the shared live `add_group` batching regression, while keeping only behavior-preserving construction helpers and bounded exception safety.

P4-T02 is **not** authorization to design the final Android progressive-board policy. P4-T03 remains the gate that decides whether Android pending board preparation is worth retaining after profiling.

### Governing invariants

- **INV-03:** no observable partial gameplay state;
- **INV-04:** Android may specialize platform scheduling, not gameplay ordering;
- **INV-05:** shared optimizations are retained only when behavior/ordering are equivalent;
- **INV-09:** project content/data remains protected;
- **INV-10:** evidence precedes optimization retention.

### Desktop `change_tilemap` contract

On non-Android runtime, `change_tilemap` must complete as one synchronous logical event-command transaction before returning to normal Event/State lifecycle code.

Desktop must not enter a frame-spread `TilemapChangeJob`/blocked-state path merely to construct or publish the replacement world.

A behavior-preserving implementation may build the replacement tilemap/board/boundary into local pending objects **synchronously within the same command call** before the first live mutation, because P4-T01 established that this construction is off-world/static when using the pending tilemap resolver.

After pending objects are complete and validated, desktop must execute without yield:

1. reset cursor position as required by the reference path;
2. `LeaveMap` every positioned unit in reference order;
3. persist `_prev_pos_<tilemap>`;
4. `RemoveRegion` every positioned region in reference order;
5. persist `_prev_region_<tilemap>`;
6. publish `level.tilemap`, `board`, and `boundary` as one matched logical publication group;
7. perform the reference overworld cursor/movement/map_view replacement where applicable;
8. restore eligible units with position offset through `ArriveOnMap` in reference order;
9. restore eligible regions through `AddRegion` in reference order, including FOG/VISION effects;
10. call `action_log.set_first_free_action()` only after the complete live transaction;
11. call the existing cache/state invalidation hook (`on_alter_game_state`) where required by the accepted later correctness behavior;
12. return only after the world is coherent.

No normal Event update, movement update, State begin/update/update_visuals, input handling, debugger observer, or direct gameplay reader may run inside steps 1-11.

### Shared/Android commit safety

The existing generator **commit** is not allowed to survive P4-T02 as an authoritative mechanism.

`TilemapChangeJob` may continue to exist because P4-T03 may evaluate Android-only pending preparation, but its commit callback must be a synchronous/non-generator operation. The job may yield only while constructing/validating objects that are not referenced by live `game`.

Therefore:

- remove `_commit_iter` / commit-phase batching semantics;
- a `COMMIT` job operation calls the synchronous commit exactly once;
- after that call returns successfully, job state becomes COMPLETE in the same operation;
- there is no `DETACH_UNITS`, `DETACH_REGIONS`, `COMMIT`, `RESTORE_UNITS`, or `RESTORE_REGIONS` outer-frame yield boundary after live mutation begins.

Do not expand Android pending-build behavior or claim it as retained performance policy in P4-T02. Existing pending-build code may remain only as provisional infrastructure for the still-blocked P4-T03 decision.

### Failure / rollback contract

The controller resolves the P4-T01 failure/reset question as follows.

**Pending-build/validation failure before any live mutation:**

- live old world remains authoritative and unchanged;
- no rollback is needed;
- the job may become FAILED and the Event may unblock/log the error using the existing bounded failure path;
- `_defer_render` must be released when the job terminates.

**Failure after the synchronous live commit has begun:**

- the commit-local `try/except` must run rollback synchronously in the **same call**;
- rollback must finish before the exception is re-raised or before `TilemapChangeJob.step/update` returns control to EventState;
- after successful rollback, the old tilemap/board/boundary, unit/region placement, aura/FOW/boundary derived state, registries, action-log fields, and cursor/movement/map_view must be coherent enough to satisfy the accepted rollback tests/invariants;
- after rollback, re-raise the original commit failure so the caller/job records failure; do not silently convert a failed change into success;
- rollback is a failure safeguard only. It must never be used to permit an outer-frame partial world.

If rollback itself cannot restore the required old-world invariants in a demonstrated test case, STOP under ESC-05/ESC-09 rather than inventing a cross-cutting snapshot architecture.

### `add_group` contract

Restore `event_functions.add_group` to one synchronous reference-shaped event transaction.

For the selected `group.units`, preserve the existing/reference per-member order and checks:

- resolve/copy unit according to flags;
- skip already-positioned/dead/invalid units as before;
- resolve target position and placement policy;
- insert initiative when enabled;
- call `_place_unit` with the same entry behavior;
- continue to the next member inside the same command call.

Do not publish one member per outer Event update.

`AddGroupJob` must have no runtime caller after P4-T02. It may be deleted together with tests that assert the obsolete incremental behavior, or left unused only if a concrete bounded reason is documented. Do not create a new pending-group architecture.

A placement exception does not require inventing a new group rollback protocol in P4-T02; restore the PC-reference synchronous command semantics and allow the existing exception path to propagate. The critical requirement is that normal outer lifecycle code cannot observe deliberate per-frame prefix placement.

### Protected ordering and correctness

Preserve exactly:

- `LeaveMap` and `ArriveOnMap` action bodies/order;
- source-owned aura teardown/repopulation behavior accepted in Phase 3;
- terrain/status skill registration semantics;
- FOW and `previously_visited_tiles` behavior;
- region registry/cache behavior, including FOG/VISION actions;
- boundary aura/range registration;
- unit `position` / `previous_position` semantics;
- turnwheel/action-log fence semantics;
- overworld cursor/movement/map_view behavior;
- P2 atomic save/load/restart semantics;
- P3 combat semantics;
- debugger/profiler observer behavior;
- project data/assets;
- all immutable golden bytes.

Do not rewrite `LeaveMap`, `ArriveOnMap`, aura functions, FOW algorithms, region actions, or action-log semantics merely to make the transaction atomic.

### Authorized production surfaces

Primary:

- `app/events/event_functions.py`
- `app/engine/jobs/tilemap_change_job.py`
- `app/engine/jobs/add_group_job.py` only for removal/retirement required by the synchronous `add_group` restoration

Narrow adjacent changes are allowed only if strictly necessary for runtime platform gating or cleanup of now-dead job wiring. `app/engine/game_board.py` construction semantics should not change unless a minimal behavior-preserving synchronous helper adaptation is required.

Do not modify `event_state.py` / global StateMachine lifecycle merely to hide an intermediate state. Fix the transaction instead.

### Required tests

Add/update bounded tests proving at minimum:

1. desktop `change_tilemap` returns only after the complete coherent new world exists;
2. desktop `change_tilemap` does not register a frame-spread tilemap job/blocked lifecycle for normal map replacement;
3. live tilemap/board/boundary are published as a coherent matched set before restored-world consumers can run;
4. unit detach -> publication -> unit restore -> region restore -> action-log fence ordering remains reference-shaped;
5. FOG/VISION region restore remains after unit restore and produces the accepted final state;
6. pending tilemap/board/boundary build/validation failure leaves live old world untouched;
7. a commit failure rolls back synchronously before the job/update call returns and the job then reports FAILED;
8. no commit iterator/live mutation phase can be advanced one outer step at a time;
9. Android/provisional pending job, if exercised by tests, mutates no live gameplay state during CREATE_TILEMAP/BUILD_BOARD/VALIDATE phases;
10. synchronous `add_group` places all eligible members before the command returns and does not register `should_update`/blocked job callbacks;
11. initiative/placement order for `add_group` remains unchanged;
12. accepted aura/FOW/region/action-log behavior is unchanged at terminal checkpoints;
13. debugger/profiler idle observation does not change results.

### Immutable comparisons

Run at minimum:

- S12 aura lifecycle;
- S13 FOW move/cancel/wait;
- S14 tilemap change;
- S15 phase transition;
- S17 debugger/profiler observer equivalence.

Use existing fixture bytes exactly. Do not regenerate a golden after mismatch.

Also run focused:

- tilemap change/job tests;
- add_group/event processor tests;
- aura add/remove tests;
- FOW/region tests;
- action-log/turnwheel tests relevant to the touched transaction;
- runtime debugger/profiler tests if observer boundaries are touched by test harnesses.

Run the broader unit suite required by `plan.md`; report known baseline Windows native termination, command-schema failures, or test-isolation pollution instead of repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit only bounded P4-T02 implementation/tests
- `git show --check`

### Explicitly out of scope

Do not:

- begin P4-T03 or Phase 5;
- decide final Android progressive-board retention without the P4-T03 profiling gate;
- add a persistent pending-world architecture;
- add per-frame authoritative commit batching under another name;
- modify Trace V1/comparator/manifest/golden JSONL;
- modify project data;
- reopen Phase-2 restore or Phase-3 combat semantics;
- broadly rewrite GameBoard/aura/FOW/region/action systems;
- merge master.

## Escalation and stop rules

P4-T02 escalation target is **GPT-5.6 Sol / max**, but is **not pre-authorized**.

STOP and request controller authorization on:

- **ESC-02** atomic repair requires nonlocal changes outside the bounded event/tilemap-job surfaces;
- **ESC-03** deterministic immutable trace divergence after one bounded transaction correction;
- **ESC-04** source/tests expose competing plausible reference-shaped tilemap semantics;
- **ESC-05** aura/FOW/region/action-log or rollback invariant cannot be preserved;
- **ESC-07** Android platform scheduling requires gameplay-order divergence;
- **ESC-08** repeated local implementation failure;
- **ESC-09** repair requires a new cross-cutting snapshot/pending-world/lifecycle architecture.

Do not self-escalate.

## Gate status

**P4-T01 is ACCEPTED. P4-T02 is the only authorized task. P4-T03 and Phase 5+ remain blocked pending P4-T02 controller review.**
