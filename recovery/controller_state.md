# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 4**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- P4-T01 tilemap/board/event atomicity audit: **ACCEPTED** at `5c94701d936a5ebbb3ebc0147e9e16e5e1d0ef25`
- P4-T02 desktop atomic tilemap semantics: **ACCEPTED** at `02f959b98d3f20f254acbc2f6a2842d0f53dd7c4`
- Active task: **P4-T03 only — Android-only progressive board preparation**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- Phase 5+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P4-T03: **YES — STOP FOR CONTROLLER REVIEW**

## P4-T02 acceptance record

The controller accepts `02f959b98d3f20f254acbc2f6a2842d0f53dd7c4` (`fix(tilemap): restore atomic event commits`).

Accepted evidence:

- the commit is a single direct descendant of P4-T02 authorization commit `953595c4de288b3f33170cf8877447282bb4ce50`;
- production changes are limited to `app/events/event_functions.py`, `app/engine/jobs/tilemap_change_job.py`, and removal of obsolete `app/engine/jobs/add_group_job.py`; remaining changes are bounded tests;
- desktop `change_tilemap` now constructs pending tilemap/board/boundary synchronously and completes the entire authoritative detach/publish/restore/action-log transaction inside the same event-command call, without registering a job or blocked-state callback;
- `TilemapChangeJob` no longer owns `_commit_iter` or any frame-spread live commit phases; its commit callback is required to be synchronous and return `None`, and generator commits fail before their generator body can execute;
- live commit ordering is reference-shaped: cursor reset -> unit detach -> region detach -> matched tilemap/board/boundary publication -> optional overworld controller replacement -> unit restore -> region restore -> action-log fence -> cache/state invalidation;
- pending-build failure before live mutation leaves the old world untouched;
- a failure after live mutation begins runs the existing bounded rollback synchronously inside `commit()` before the original error leaves the call; Android job failure is recorded only after that rollback has completed;
- rollback may reconstruct `GameBoard`/`BoundaryInterface` from the old tilemap rather than preserve object identity; this remains bounded exceptional-path recovery accepted by the P4-T01 classification, not normal transaction semantics or permission for outer-frame partial publication;
- `event_functions.add_group` is synchronous again and `AddGroupJob` has been removed, eliminating deliberate per-frame prefix publication of group members;
- reported focused tilemap/add-group/aura/FOW/turnwheel/event/debugger/profiler tests PASS, recovery trace/lifecycle/golden tests PASS, and immutable S12/S13/S14/S15/S17 comparisons PASS against unchanged oracle data;
- broader-suite Windows native termination remains baseline and unrelated;
- `python -m compileall -q app`, `git diff --check`, and `git show --check` PASS.

P4-T02 establishes this accepted shared authoritative contract:

```text
LIVE OLD STATE
    -> optional pending/off-world preparation
    -> complete validation
    -> one synchronous authoritative commit
LIVE NEW STATE
```

There is no yield after the first live mutation begins. Desktop uses the whole transaction synchronously. `add_group` is synchronous on all platforms.

## P4-T03 — authorized Android policy task

Execute **P4-T03 only** using **GPT-5.6 Terra / high**.

Escalation target is **GPT-5.6 Sol / max**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Use `recovery/p4_t01_tilemap_atomicity_map.md` and accepted P4-T02 as the semantic baseline. Immutable Phase-1 goldens remain fixed.

### Goal

Decide, from measured evidence, whether Android should retain progressive pending tilemap/board preparation. If retained, make it semantically opaque and reference-equivalent: only off-world pending construction may span host frames; authoritative gameplay must not advance while the event command is suspended; the final live commit remains one synchronous operation.

P4-T03 is **not** permission to reintroduce generator commits, live partial maps, incremental `add_group`, or a second persistent GameState/world architecture.

### Profiling gate comes first

Before changing Android production policy, measure the cost of synchronous tilemap/board preparation on representative project maps using existing runtime/profiler infrastructure or a bounded benchmark harness.

At minimum:

- identify representative small/medium/large tilemaps from existing project/resources without modifying project data;
- record dimensions/tile counts;
- measure tilemap object preparation and GameBoard build separately where feasible;
- run repeated measurements and report median/high-percentile or otherwise stable repeated timing, not one sample;
- compare observed work to the existing frame-budget motivation (`FRAME_BUDGET_NS = 4_000_000`) and normal frame cadence;
- distinguish host measurement from actual Android-device measurement. Do not claim device latency if no device run exists.

Decision rule:

1. **If profiling does not demonstrate meaningful frame-stall risk/benefit**, remove the Android progressive `TilemapChangeJob` path and use the accepted synchronous P4-T02 transaction on Android too. Deleting now-unneeded pending-job infrastructure is allowed if bounded.
2. **If profiling does justify progressive preparation**, retain only the pending/off-world phases and satisfy every semantic barrier below.

Do not retain complexity merely because it already exists.

### Required semantic barrier if progressive preparation is retained

Current Event scheduling still calls `game.movement.update()` on every outer Event update even while `Event.state == 'blocked'`. Therefore coherent-old-world visibility alone is insufficient: the PC reference completes the command before another movement/gameplay update can occur.

If Android progressive preparation spans frames, the command suspension must be **authoritatively opaque**:

- no movement advancement while the tilemap job is pending;
- no gameplay input edge may invoke listeners or mutate the old world during the suspended command;
- no next event command may execute;
- no aura/FOW/region/action-log gameplay mutation may occur during pending build;
- debugger/profiler idle observation may read the coherent old world but must not mutate it;
- presentation-only updates may continue only when they cannot change gameplay state;
- `previous_unit_pos`, `previous_region_pos`, reload offsets, and other commit inputs must not become stale because gameplay advanced while preparation was pending;
- after pending validation, the P4-T02 synchronous commit executes once and returns a coherent new world in the same job operation.

A narrow event-local Android tilemap-pending barrier is allowed if sufficient. Do not introduce a generic new lifecycle scheduler. If safety requires a cross-cutting pause/snapshot architecture, STOP under ESC-09.

### Retained pending work, if justified

Only these categories may span frames:

- `TileMapObject.from_prefab_iter` work that mutates only the pending object;
- `GameBoard.build_iter` against the pending tilemap/static DB resolver;
- pending `BoundaryInterface` construction/validation if it does not reference live dynamic gameplay;
- profiler counters and presentation/render deferral.

The following may never span frames:

- `LeaveMap` / `ArriveOnMap`;
- `RemoveRegion` / `AddRegion`;
- live tilemap/board/boundary publication;
- aura/terrain/status/FOW/boundary rebuild on live units;
- action-log fencing;
- `add_group` placement;
- rollback after a live commit failure.

### Failure contract

Preserve accepted P4-T02 failure semantics:

- pending preparation failure: old world remains coherent and unchanged, job fails, render deferral/barrier releases cleanly;
- live synchronous commit failure: rollback completes synchronously before control returns, then job records failure;
- no barrier/blocked flag may remain stuck after success or failure.

### Required proof

If progressive path is retained, add focused tests proving at minimum:

1. multiple pending-build updates can occur while live tilemap/board/boundary/unit/region/aura/FOW/action-log state remains unchanged;
2. `game.movement.update()` does not advance during Android tilemap pending suspension;
3. gameplay input/listeners cannot mutate state during that suspension, while any allowed skip/presentation control remains explicitly bounded;
4. event processor cannot run the next command before job completion;
5. commit inputs such as saved unit/region positions cannot become stale due to suspended-frame gameplay advancement;
6. final commit remains synchronous with no live yield;
7. success releases render deferral/barrier and resumes normal lifecycle exactly once;
8. pending-build failure releases barrier with old world intact;
9. commit failure rolls back before barrier release;
10. S12/S13/S14/S15/S17 remain unchanged.

If progressive path is removed, add/update tests proving Android now uses the same synchronous reference-shaped transaction and no dead job/barrier wiring remains.

### Deliverable

Create:

`recovery/p4_t03_android_board_policy.md`

Record:

- profiling setup and measurements;
- maps/workloads measured;
- limitations of host-vs-device evidence;
- RETAIN or REMOVE decision for progressive pending preparation;
- exact semantic-barrier design if retained;
- production changes;
- tests/evidence;
- performance tradeoff;
- remaining risks.

### Validation

Run immutable comparisons at minimum:

- S12 aura lifecycle;
- S13 FOW movement/cancel/wait;
- S14 tilemap change;
- S15 phase transition;
- S17 debugger/profiler observer equivalence.

Also run focused tilemap/job/Event/EventState/movement/input/aura/FOW/region/action-log tests and Android performance/profiler tests relevant to the policy decision.

Run the broader unit suite required by `plan.md`; report known baseline failures/native termination without repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit only bounded P4-T03 policy/implementation/tests/report
- `git show --check`

### Explicitly out of scope

Do not:

- begin Phase 5;
- reintroduce live commit batching;
- reintroduce incremental `add_group`;
- create a second/persistent pending GameState or world graph;
- change GameBoard/aura/FOW/region gameplay algorithms merely for performance;
- modify Trace V1/comparator/manifest/goldens;
- modify project data;
- reopen Phase 2 or Phase 3;
- merge master.

## Escalation and stop rules

STOP and request controller authorization on:

- **ESC-02** performance/safety root cause crosses into unrelated correctness-critical systems;
- **ESC-03** immutable trace divergence after one bounded Android scheduling correction;
- **ESC-05** aura/FOW/region/action-log/input ordering invariant cannot be preserved;
- **ESC-07** measured Android performance requirement conflicts with shared gameplay semantics;
- **ESC-08** repeated local failure;
- **ESC-09** safe progressive preparation requires a new generic lifecycle/snapshot/pending-world architecture.

Do not self-escalate.

## Gate status

**P4-T02 is ACCEPTED. P4-T03 is the only authorized task. Phase 5+ remains blocked pending P4-T03 controller review.**
