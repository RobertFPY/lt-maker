# P4-T01 — Tilemap / board / event atomicity map

**Scope:** audit/decomposition only.  PC behavioral reference is
`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`; current audit HEAD is
`6ad10d13c201d33adcef5bfb4b1ed8558d0d9581`.  No production, test, trace,
fixture, manifest, or project-data file was changed.

## 1. Caller/function graph

```text
Event.process
  -> event_functions.change_tilemap
       -> capture old live placement / rollback snapshot
       -> TilemapChangeJob.update (Event.should_update)
            -> TileMapObject.from_prefab_iter [pending]
            -> GameBoard.build_iter [pending]
            -> BoundaryInterface [pending]
            -> validate [pending]
            -> event_functions.change_tilemap.commit [LIVE: generator]
                 -> LeaveMap / RemoveRegion
                 -> publish level.tilemap, board, boundary
                 -> optional cursor/movement/map_view replacement
                 -> ArriveOnMap / AddRegion
                 -> action_log.set_first_free_action / on_alter_game_state
  -> Event.should_remain_blocked keeps processor blocked until job finishes
  -> EventState.should_defer_render retains last surface while job runs

Event.process
  -> event_functions.add_group
       -> AddGroupJob.update (Event.should_update)
            -> _place_unit / action mutations, one live unit at a time
```

Affected live helpers are `GameState.leave/arrive`, `BoundaryInterface.leave/
arrive/register_unit_auras`, `aura_funcs.remove_all_auras/release_aura/
propagate_aura/pull_auras`, `UpdateFogOfWar`, and `AddRegion`/`RemoveRegion`.
They mutate unit position/occupancy, terrain and status registries, aura grids,
boundary ranges, fog/visited tiles, and regions.  They are not pending-world
operations.

## 2. PC-reference transaction maps

### 2.1 Normal `change_tilemap`

Reference executes one Event command synchronously:

1. Validate target prefab and normalize flags/offset.
2. Move cursor; for every live unit, save position and execute `LeaveMap`.
3. Save positions; for every positioned region, execute `RemoveRegion`.
4. Construct `TileMapObject.from_prefab`, publish `level.tilemap`, then call
   synchronous `GameState.set_up_game_board`.
5. If prior mode was overworld, replace cursor/movement/map view.
6. On `reload`, restore saved units with offset via `ArriveOnMap`; then restore
   regions via `AddRegion`.
7. Set the turnwheel's first-free boundary and return from the command.

There is no Event/job yield between the first `LeaveMap` mutation and final
action-log boundary.  Expensive board construction is live in the reference,
but it is not observable by normal Event/State lifecycle code because the
command does not return until the complete transaction is done.

### 2.2 Reload, regions, and overworld

Reload restores only positions inside the newly published tilemap and applies
`position_offset` before `ArriveOnMap`.  Region restoration runs after units;
`AddRegion` installs FOG/VISION effects through `AddFogRegion`/
`AddVisionRegion`, updates the board, and resets boundary fog.  The overworld
return path synchronously replaces LevelCursor, MovementSystem, and MapView,
then restores the saved board/boundary and positions before returning.

### 2.3 Reference failures and group placement

The reference has no pending-board failure branch and no rollback protocol:
an exception aborts the synchronous command rather than exposing a later
outer-frame continuation.  `add_group` iterates and places every group member
inside the same Event command; placement, initiative insertion, aura/FOW, and
board occupancy become one command transaction.

## 3. Current recovery transaction maps

### 3.1 Pending preparation — retainable shape

`TilemapChangeJob` (`cdd4be2a7`) keeps the following objects unreferenced by
live `game` until validation succeeds:

1. `TileMapObject.from_prefab_iter` creates `pending_tilemap`.
2. `GameBoard.build_iter(pending_tilemap, terrain_nid_resolver=...)` creates
   `pending_board` in terrain/movement/collection batches.
3. `BoundaryInterface` creates `pending_boundary`.
4. `_validate` verifies that all three exist and board dimensions equal the
   pending tilemap.

This is pending/off-world computation, provided the resolver and builders do
not consult or mutate live dynamic world state.  The supplied terrain resolver
uses the pending tilemap; DB terrain/movement data is static.  `FRAME_BUDGET_NS`
is therefore a platform scheduling policy only in these states.

### 3.2 Current authoritative commit — unsafe shape

After validation, `6b96e2f1` invokes a **generator** commit through
`TilemapChangeJob.COMMIT`.  It yields after live mutations:

1. `LeaveMap` every positioned unit; yield every 8 and once at completion.
2. Store old positions; `RemoveRegion` every positioned region; yield every
   16 and once at completion.
3. Publish `level.tilemap`, `board`, and `boundary`; yield `COMMIT`.
4. Replace cursor/movement/map_view when returning from overworld.
5. `ArriveOnMap` restored units; yield every 4 and once at completion.
6. `AddRegion` restored regions; yield every 16 and once at completion.
7. Set `action_log` first-free boundary and call `on_alter_game_state`.

The ordered terminal state matches the immutable S14 checkpoint, but states
1–6 are externally observable between outer Event updates.  This differs from
the PC reference's one command call and violates INV-03 even when the final
trace checkpoint matches.

### 3.3 Current Event/EventState scheduling

`change_tilemap` registers `job.update` in `Event.should_update`, adds a
`should_remain_blocked` callback, sets `Event.state='blocked'`, and sets
`_defer_render=True`.  On each Event update, queued job work runs **before**
the blocked-state check.  The event processor does not execute the next event
command until completion, but Event movement updates, state visual updates,
draw-independent map consumers, debugger observers, and any direct live-game
reader can run on later outer frames.  `StateMachine.update_visuals` still
runs while rendering is deferred.

`EventState.should_defer_render` prevents composing a new visual surface; it
does not restore the old board/tilemap/units or make direct readers see an
old snapshot.

### 3.4 Current `add_group`

`cd8607b6` makes `AddGroupJob` run `_place_unit` one member per operation
under the same Event blocking callbacks.  Each operation can call
`InsertInitiative` and placement actions, which mutate live units, board,
auras, fog, regions/statuses, and boundary.  Event blocking does not make the
partially placed group atomic.  There is no pending group representation or
rollback.

## 4. Yield/batch boundary table

| Boundary | Live tilemap / board / boundary | Units / regions / aura / FOW | Registries + action log | Normal code before next step | Classification / finding |
| --- | --- | --- | --- | --- | --- |
| `CREATE_TILEMAP`, `BUILD_BOARD` batches | Old / old / old | Old occupancy, regions, aura/FOW | Old | Event blocked; observers still see coherent old world | Pending/off-world computation; KEEP-PLATFORM candidate. |
| `VALIDATE` | Old / old / old | Old | Old | Same | Pending validation; KEEP-SHARED. |
| `DETACH_UNITS` | Old / old / old | Some/all units now `position=None`; `LeaveMap` has removed board occupancy, child auras, source auras, terrain/status effects, boundary data, and updated fog | Skill/terrain registries can already differ; action log is not yet fenced | Event movement update, StateMachine visuals, debugger/direct consumers can observe missing units on old map | Authoritative gameplay mutation; RESTORE-PC-SEMANTICS. |
| `DETACH_REGIONS` | Old / old / old | Positioned regions removed; FOG/VISION, terrain/status effects may be partially removed | Region lookup cache cleared; action boundary not final | Same | Authoritative gameplay mutation; RESTORE-PC-SEMANTICS. |
| `COMMIT` | New / new / new | No restored units/regions yet; new board has empty occupancy/aura/FOW except pending static grids | Old action-log boundary; live unit/region registries retain detached objects | Map consumers/debugger can see new map with no restored world | Atomic publication split from restore; RESTORE-PC-SEMANTICS. |
| `RESTORE_UNITS` | New / new / new | Prefix of units restored; each `ArriveOnMap` applies terrain/status/aura/boundary/FOW. Later units and their aura sources remain absent | Dynamic skill/terrain registrations and FOW are prefix-dependent | Same | Authoritative gameplay mutation; RESTORE-PC-SEMANTICS. |
| `RESTORE_REGIONS` | New / new / new | Prefix of regions restored; FOG/VISION and terrain/status effects are prefix-dependent | Region cache invalidated incrementally; action boundary still unset | Same | Authoritative gameplay mutation; RESTORE-PC-SEMANTICS. |
| Final return from commit | New / new / new | Fully restored | `set_first_free_action`, then cache-state token changes | Next Event command can execute | Atomic logical boundary should be here, but current implementation reaches it through observable intermediate states. |
| `AddGroupJob` member batches | Existing live world | Prefix of group appears; occupancy/auras/fog/initiative may differ per member | Action log progresses per placement | Same | Authoritative gameplay mutation; RESTORE-PC-SEMANTICS. |

## 5. Aura / FOW / region / action-log ordering matrix

| Operation | Required live effects | Why it cannot be split across outer frames |
| --- | --- | --- |
| `LeaveMap` | Remove aura children by stored source, release owned auras, unregister boundary auras, remove terrain/region status, boundary ranges, occupancy, position, then fog update | A partially detached set changes targeting, visibility, and skills on the still-old map. |
| Board publication | New tilemap, board, boundary must become a matched triple | Publishing any subset makes terrain, bounds, opacity, occupancy, or range queries disagree. |
| `ArriveOnMap` | Set position/occupancy, terrain and region statuses, pull/propagate auras, register boundary aura/ranges, update FOW and previous position | Each restored prefix changes unit legality, aura recipients, FOW, and attack ranges. |
| `AddRegion` / `RemoveRegion` | Mutate region registry/cache; for FOG/VISION mutate board grids and boundary fog; for terrain/status affect units and movement grids | A region prefix exposes different visibility/status/pathing from both old and completed new maps. |
| `set_first_free_action` | Fence the completed non-turnwheelable map transaction | Setting it before all live mutation misstates what turnwheel may reverse; setting it after yielding leaves an un-fenced partial transaction. |

S12, S13, S14, and S15 establish that complete aura/FOW/tilemap/phase states
still equal the PC fixtures.  They do not prove that current intermediate
generator frames are safe, because Trace V1 records only the scenario's
accepted synchronization checkpoints.

## 6. Rollback analysis

Current `rollback` captures tilemap, regions/positions, unit
position/previous-position/skill-list snapshots, level variables, skill and
terrain registries, action-log fields, bounds, visited tiles, and
cursor/movement/map-view.  It synchronously rebuilds an old board/boundary,
reapplies FOG/VISION regions, restores unit fields/occupancy, repopulates aura
sources, re-registers boundary auras/ranges, updates FOW, restores action-log
fields, and invalidates LTCache.

This is a useful **failure safeguard** and should be decomposed rather than
deleted wholesale.  It is not behavioral equivalence for an in-progress
commit:

- it runs only after a later `next(commit_iter)` raises; prior yielded frames
  already exposed detached/published-prefix state;
- it reconstructs derived board/boundary/aura/FOW state rather than undoing
  the exact action sequence at the original point in time;
- it restores action-log containers but cannot make external observers unsee
  partial logical state; and
- no analogous rollback exists for incremental `add_group`.

P4-T02 must retain a bounded abort/reset safeguard only after ensuring an
exception cannot expose a partially published world.  Rollback is never a
license to yield inside an authoritative commit.

## 7. Render-deferral analysis

`_defer_render` retains the previously presented surface.  It protects against
a visible half-map, and is valid presentation policy.  It does **not** prevent:

- Event's next outer update from calling job work then movement update;
- `StateMachine.update_visuals` from updating visible MapState consumers;
- runtime debugger/profiler or direct code from reading `game`;
- board/aura/FOW/region/action-log queries from observing a prefix mutation.

Therefore “not drawn” is not “not logically observable.”  Render deferral is
KEEP-PLATFORM only when it wraps an otherwise atomic world transaction; it
cannot satisfy INV-03 on its own.

## 8. Function-level classification and provenance

| File + symbol | PC reference / current behavior | Category | Recovery class / later treatment | Dependencies and proof |
| --- | --- | --- | --- | --- |
| `game_board.py: GameBoard.__init__` | PC builds synchronously; current wrapper consumes iterator synchronously | Shared construction | KEEP-SHARED | Reference semantics remain when used synchronously. |
| `game_board.py: build_iter`, `_initialize_iter`, `_filled_grid_iter` | Added by `cdd4be2a`; constructs only receiver object and DB-backed grids when supplied pending tilemap/resolver | Pending/off-world computation | KEEP-PLATFORM; P4-T03 candidate | Must prove no live-game resolver or publish; job tests pending build/failure. |
| `jobs/tilemap_change_job.py: CREATE_*`, `BUILD_BOARD`, `VALIDATE` | Added by `cdd4be2a` | Pending validation | KEEP-PLATFORM | `test_tilemap_change_job` and S14 terminal comparison. |
| `jobs/tilemap_change_job.py: COMMIT`, `_commit_iter` | `6b96e2f1` advances a callback generator across job updates | Authoritative mutation scheduler | RESTORE-PC-SEMANTICS; P4-T02 | Generator permits every listed live split. |
| `event_functions.py: change_tilemap.commit` | PC direct sequence; current yields after detach, publication, unit and region prefixes | Atomic publication + mutation | RESTORE-PC-SEMANTICS; P4-T02 | S14 terminal PASS does not cover intermediate state. |
| `event_functions.py: rollback` | Later exception recovery | Rollback/error recovery | KEEP-CORRECTNESS-FIX, narrow after proof | Preserve only synchronous failure safety, not current partial-yield justification. |
| `event.py: should_update`, `should_remain_blocked` | Job updates before blocked check | Scheduling | REWRITE-PLATFORM | Event remains logically live while job runs. |
| `event_state.py: should_defer_render`; `state_machine.py: update` | Suppresses draw but continues lifecycle/visual work | Presentation/render deferral | KEEP-PLATFORM, conditional | Safe only after P4-T02 makes live commit atomic. |
| `event_functions.py: add_group`; `jobs/add_group_job.py` | PC loops group synchronously; current places live members incrementally (`cd8607b6`) | Authoritative mutation | RESTORE-PC-SEMANTICS; P4-T02 | `test_add_group_job` proves one-at-a-time behavior. |
| `game_state.py: leave/arrive`; `action.py: LeaveMap/ArriveOnMap/UpdateFogOfWar` | Shared authoritative unit/aura/FOW semantics | Authoritative mutation | KEEP-CORRECTNESS-FIX | Preserve source-owned aura teardown and FOW ordering; move scheduling boundary, not bodies. |
| `action.py: AddRegion/RemoveRegion/AddFogRegion/AddVisionRegion` | Shared region/FOW/terrain semantics | Authoritative mutation | KEEP-SHARED | Must remain inside one commit transaction. |
| `boundary.py: leave/arrive/register_unit_auras` | Derived threat/aura/FOW data | Authoritative derived-state rebuild | KEEP-CORRECTNESS-FIX | Required adjacent to unit detach/restore; no separate publication. |

## 9. P4-T02 candidates — controller-blocked, not implemented

1. Change `TilemapChangeJob` so pending build/validate may remain sliced but
   its callback is not resumable after first live mutation.
2. Execute PC-reference detach → save old positions → remove regions → publish
   matched tilemap/board/boundary → cursor replacement → restore units →
   restore regions → action-log boundary synchronously in one main-thread
   Event update.
3. Keep failure handling transaction-local: before commit, discard pending;
   during commit, catch and reset/restore before returning control, never on a
   later outer frame.
4. Restore `add_group` as one Event command transaction; do not retain
   one-live-member batches without a separately approved pending representation.
5. Add boundary tests that instrument each attempted commit step and prove no
   normal `State`, Event, input, debugger, aura/FOW, region, or board consumer
   runs between first live mutation and final action-log boundary.

## 10. P4-T03 candidates — controller-blocked, not implemented

1. Retain Android frame budget only for TileMapObject/GameBoard/Boundary
   construction and validation against pending objects.
2. Keep `_defer_render` as presentation policy around the opaque pending-load
   state, after P4-T02 removes live intermediate state.
3. Do **not** retain the current generator commit or `AddGroupJob` member
   batching.  A future pending group plan would be a new architecture and is
   not proposed by this audit.

## 11. One proposed atomic commit boundary

```text
LIVE OLD
  -> pending tilemap + board + boundary build / validate (may yield; no live writes)
  -> synchronous main-thread transaction:
       detach units and regions
       publish tilemap + board + boundary together
       replace cursor/movement/map_view if required
       restore units, derived terrain/aura/boundary/FOW state, then regions
       set action-log first-free boundary and invalidate cache state
  -> LIVE NEW
```

No `yield`, budget boundary, Event processor continuation, input handler,
debugger observer, or normal State lifecycle call may occur inside the boxed
synchronous transaction.  Failure before it leaves LIVE OLD unchanged; failure
inside it must complete recovery/reset before the same outer update returns.

## 12. Unresolved controller decisions / escalation evidence

No escalation was required for this audit.  The required boundary is not
ambiguous: current generator yields demonstrably split authoritative mutation,
while reference executes the sequence synchronously.  Controller review is
still required before P4-T02 chooses the exact failure/reset API and before
any Android-only pending preparation is retained.

Known test constraints, not P4 regressions:

- combined unit-test execution leaks a test-only `_Uses` component and causes
  component-discovery failures; the relevant suites pass in fresh processes;
- existing event command tests have independent command-schema assertion
  failures; no test expectation was changed.
