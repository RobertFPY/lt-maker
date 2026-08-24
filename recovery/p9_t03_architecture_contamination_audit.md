# P9-T03 — Architecture contamination audit

## Scope and result

Starting point: `dfa5f9ef672b22af15fc648e1bf4fd4dd20e5569` on
`recovery/pc-core-semantics`.  This audit covers the controller-authorized
post-P9-T02 recovery architecture only.  It found no Android gameplay fork,
staged authoritative restore, partial-world publication, or worker-thread
gameplay mutation.  The one local correction removes stale wording from a
failure-reset helper; it does not change executable behavior.

Classification terms below are those required by the controller:

- **CLEAN**: no suspicious behavior remains.
- **ACCEPTED-PLATFORM**: platform policy is isolated from authoritative game
  semantics.
- **ACCEPTED-SHARED**: one shared authoritative implementation, with an
  allowed presentation/off-world seam.
- **DEFENSIVE-VALID**: null/availability guard is independently required in a
  valid non-map, title, overworld, debugger, or error state.
- **PERMANENT-DOCUMENTATION**: marker describes a retained, accepted contract.

## Method

The audit searched all non-test engine/event Python sources for Android runtime
checks, deferred/staged/pending wording, generators and explicit thread
creation.  Each suspicious result was traced to its writer, consumer and
publication point.  Targeted recovery tests were run in fresh baseline Python
processes; no source behavior was modified while testing.

## Android conditional findings

| ID | File / symbol | Category | Mechanism and affected state | Classification / disposition |
| --- | --- | --- | --- | --- |
| A-01 | `app/events/event.py:Event.draw` | render overlay | Android skips composing an empty transparent overlay.  It neither consumes input nor advances an Event command. | **ACCEPTED-PLATFORM** — retain. |
| A-02 | `app/events/event.py:Event.update`, `Event.take_input`, `EventState.should_defer_render` | tilemap barrier | While `_android_tilemap_pending` is true, Event updates only the pending job, rejects gameplay input, and reports deferred rendering. | **ACCEPTED-SHARED** — retain the Event-local P4 barrier. |
| A-03 | `app/events/event_functions.py:change_tilemap` and `app/engine/jobs/tilemap_change_job.py:TilemapChangeJob` | off-world work | The capability selects pending TileMap/GameBoard/Boundary construction only.  The common commit closure publishes all live structures synchronously, rolls back synchronously on error, and releases the barrier once. | **ACCEPTED-PLATFORM** — retain.  No job state is save truth or a pending GameState. |
| A-04 | `app/engine/general_states.py:LoadingState`, `InChapterLoadState`; `app/engine/title_screen.py` | load presentation | Android selects opaque loading presentation and `SaveLoadJob`; its worker reads/unpickles immutable data only, then the shared canonical transaction runs on the game thread. | **ACCEPTED-SHARED** — retain. |
| A-05 | `app/engine/sound.py` | audio/resource backend | Stream/cache/preload/release decisions are physical backend policy.  Callers still select music NIDs and lifecycle timing. | **ACCEPTED-PLATFORM** — retain P6 policy. |
| A-06 | `app/engine/combat/animation_combat.py`, `mock_combat.py`, `battle_animation.py` | combat rendering | Android branches select draw caches/transient visual progression.  Solver, actions, RNG, hooks and cleanup have no Android conditional. | **ACCEPTED-PLATFORM** — retain. |
| A-07 | `app/engine/title_screen.py`, `menus.py`, `settings*.py`, `info_menu`, `unit_menu`, `highlight.py`, `menu_options.py` | UI/render caches | Branches control surface, particle, highlight or bounded UI caches.  Keys/content/invalidation remain owner-local and do not change menu selection or state transitions. | **ACCEPTED-PLATFORM** — retain. |
| A-08 | `app/engine/base.py`, `game_menus/menu_states/unit_menu_state.py`, `engine.py`, `android_runtime.py`, `android_debugger.py`, `debug_mode.py`, `driver.py` | input/debugger/platform bridge | These own raw touch/JNI ownership, hardware labels, Android debugger UI, or desktop HTTP-debugger presentation.  Both frontends dispatch through `RuntimeDebuggerController`; driver HTTP servicing is desktop-only. | **ACCEPTED-PLATFORM** — retain. |
| A-09 | `app/engine/performance.py` | observer | Android enables profiling presentation/instrumentation, not gameplay branching. | **CLEAN** — observer-only. |
| A-10 | `app/engine/runtime_capabilities/work_budget.py` | capability | The only Android numeric scheduling policy is immutable `OffWorldWorkBudget(enabled=True, deadline_ns=4_000_000)`. | **ACCEPTED-PLATFORM** — retain; no Event command budget exists. |

There are no direct Android conditions in `game_state.py`, `action.py`,
`phase.py`, the movement core, Simple/Map combat authoritative transaction
code, or canonical `save.py` hydration.  The state-machine registry imports
Android state classes statically; it does not choose an Android gameplay state
machine.

## GameState staged/deferred findings

| ID | File / symbol | Mechanism | Authoritative publication / consumer | Result |
| --- | --- | --- | --- | --- |
| G-01 | `app/engine/game_state.py:prepare_for_load` | Clears transient state after a failed load. | Its only production caller is `save.reset_failed_load`; normal restores never call it. | **CLEAN** after the documentation correction below. |
| G-02 | `GameState.load_iter`, `save._record_restore_iter`, `save.load_game_data` | `load_iter` yields profiling/dependency labels while constructing the world. | `_record_restore_iter` exhausts it in the same canonical main-thread transaction; saved S/Q remains transaction-local until validation, UID finalization and one `install_state_machine`. | **ACCEPTED-SHARED** — no host-frame hydration. |
| G-03 | `GameState.set_up_game_board_iter`, `GameBoard.build_iter`, `TileMapObject.from_prefab_iter` | Builders may yield while creating local/pending structures. | Board assignment happens only after build return; public synchronous wrappers drain them.  P4 is the sole multi-frame consumer and keeps the built structures off-world. | **ACCEPTED-SHARED** — retain. |
| G-04 | `GameState.chapter_start_snapshot` | Deep-copied pristine chapter-start payload used for restart source selection. | Captured after chapter setup and before LevelStart; it is data, not a staged live GameState. | **ACCEPTED-SHARED** — retain P5 restart contract. |
| G-05 | `_staged_state_data`, `commit_staged_state` | Historical staged-restore fields/method. | No production occurrence remains; only historical tests assert their absence. | **CLEAN** — already removed. |

The yielded GameState helpers are potentially unsafe only if an unsupported
external caller manually advances them across host frames.  Repository callers
either drain synchronously or use the P4 pending/off-world transaction.  No
such production caller was found.

## Partial-state guard findings

| ID | File / symbol | Guard | Why it remains valid | Result |
| --- | --- | --- | --- | --- |
| H-01 | `app/engine/state.py:MapState` | camera, highlight and `map_view` availability | Title, overworld, transitions and no-map contexts legitimately lack map rendering objects.  The guard avoids a visual crash; it does not publish or conceal a partial restore. | **DEFENSIVE-VALID** — retain. |
| H-02 | `app/engine/settings.py:AndroidControlsEditor` | `map_view`/camera before `MapState.draw` | Transparent controls editing can run over non-map presentation. | **DEFENSIVE-VALID** — retain. |
| H-03 | `app/engine/highlight.py:HighlightController._region_cache_signature` | missing level returns empty signature | Highlight is presentation-only and title/overworld need no level. | **DEFENSIVE-VALID** — retain. |
| H-04 | `runtime_debugger*` controller/service | cursor/board/tilemap/level/position checks | Inspector, focus, tile pick, teleport and weather must reject unavailable map context rather than mutate it. | **DEFENSIVE-VALID** — retain. |
| H-05 | `app/events/event_functions.py` | board/tilemap availability checks | Commands report/reject invalid no-board contexts before mutation. | **DEFENSIVE-VALID** — retain. |
| H-06 | `app/engine/driver.py:_performance_counters` | `getattr` observer reads | Counters must tolerate startup/title objects without writing game state. | **DEFENSIVE-VALID** — retain. |

The Phase-2 restoration map noted historical staged-restore motivation for
some map guards, but each listed guard also has the independently valid
runtime purpose above.  None is removed merely because it originated during
Android work.

## Worker and background ownership

| ID | Owner | Worker work | Gameplay mutation / result |
| --- | --- | --- | --- |
| W-01 | `save.SaveLoadJob._read_worker` | File read and unpickle into job-local `_save_data`. | **CLEAN** — `advance()` calls shared `load_game_data` on the game thread. |
| W-02 | `save.suspend_game` / `SAVE_THREAD` | Serialize frozen save/restart payload arguments. | **CLEAN** — no live `GameState` reference is handed to worker persistence. |
| W-03 | `sound.prepare_level_songs` | Audio cache flush/load/preload. | **ACCEPTED-PLATFORM** — resource cache only; no game/Event/solver/registry mutation. |
| W-04 | `RuntimeDebuggerService` HTTP handler | Enqueue `PendingCommand`, wait for result. | **CLEAN** — `update()` dispatches exactly once on the game thread. |
| W-05 | `RuntimeProfiler.section` | Worker timing body executes but bypasses frame scope tree when thread ID differs. | **CLEAN** — observer-only; P7 worker-isolation test passes. |

No worker moves actions, solver state, Event commands, S/Q, units, boards,
regions, aura, FOW or save publication.

## Duplicate PC/Android gameplay implementation findings

No duplicate authoritative PC/Android implementation was found.  The Android
classes are presentation/bridge owners (`AndroidDebuggerState`, touch runtime,
controls editor and combat UI layer).  Shared semantic owners are:

- canonical `save.load_game_data` for desktop and Android load;
- common `change_tilemap` commit/rollback closure for desktop and Android;
- `RuntimeDebuggerController.dispatch(op, args)` for desktop service and
  Android frontend;
- shared Event, action, combat, movement, phase and GameState code.

Classification: **CLEAN**.

## Yield/generator and deferred-boundary findings

| ID | Location | Boundary | Result |
| --- | --- | --- | --- |
| Y-01 | TileMap/GameBoard builder iterators | local/off-world construction only; live assignment after return | **ACCEPTED-PLATFORM**. |
| Y-02 | canonical GameState iterators | internal profiling/dependency phases drained in one load transaction | **ACCEPTED-SHARED**. |
| Y-03 | `TilemapChangeJob` | only permitted multi-frame pending build; Event-local barrier blocks movement/input/later commands | **ACCEPTED-PLATFORM**. |
| Y-04 | `Event.process` | waits, dialog, pause, block, completion and `waiting_for_present` are semantic boundaries | **CLEAN**.  No wall-clock deadline, command-count batching, or `_android_process_yielded` remains. |
| Y-05 | `StateMachine`/driver fast-forward | additional updates receive empty transient input; presentation fence stops remaining substeps | **ACCEPTED-SHARED**. |

No combat solver/action/cleanup, live board placement, save/restart, phase or
Event-command transaction is generator-sliced for Android performance.

## Recovery/TODO marker findings

| ID | Location | Marker | Interpretation / decision |
| --- | --- | --- | --- |
| R-01 | `event_functions.py:change_tilemap` | synchronous recovery/rollback wording | **PERMANENT-DOCUMENTATION**: documents rollback-before-barrier-release and is required by P4. |
| R-02 | `event.py`, `event_state.py`, `state_machine.py` | deferred render / historical `event_budget_deferred_draw` counter | **PERMANENT-DOCUMENTATION**: presentation fence and observer label, not a generic Event scheduler. |
| R-03 | `game_state.py:prepare_for_load` | obsolete staged-load compatibility wording | **REMOVED-STALE-MARKER**: corrected docstring only; behavior already failure-reset-only. |
| R-04 | `objects/tilemap.py:TileMapObject.restore` | old tint-load stopgap TODO | **PERMANENT-DOCUMENTATION / out of scope**: legacy malformed/missing tint compatibility guard; it does not stage or publish world state. |
| R-05 | `event_functions.py:interact_unit` | temporary duplicate wording | **PERMANENT-DOCUMENTATION**: selects a live acquired item when available to preserve item state; not an Android or recovery workaround. |
| R-06 | general component/UI/AI TODOs and event-converter output marker | historical feature debt | **DEAD/UNRELATED-DOCUMENTATION** for this audit; none describes recovery staging, platform gameplay forks or partial publication. |

## P9-T02 ABI boundary

The x86_64/arm64-v8a policy lives in the editor Android build configuration
and `utilities/build_tools/android_runtime` build/preflight/APK-verifier
tooling.  The verifier remains strict by requiring the requested ABI directory
and matching ELF machine.  No ABI string, build selector or verifier is used by
engine gameplay, Event, combat, save, restart, GameState, action, movement or
phase code.

Classification: **ACCEPTED-PLATFORM**.  P9-T02's ABI repair is build/package
policy, not architecture contamination of runtime semantics.

## Local correction

`GameState.prepare_for_load` now accurately states that it is retained only
for failed-transaction cleanup.  Search confirmed one production caller:
`save.reset_failed_load`; normal load paths do not call it.  This is a
documentation-only cleanup of a stale recovery marker, not a lifecycle or
save-schema change.

## Validation

Fresh-process baseline-interpreter results:

| Command group | Result |
| --- | --- |
| atomic restore, canonical load, restart contract, TilemapChangeJob, state-machine lifecycle | 74 tests, OK |
| fast-forward equivalence/input, debugger controller/parity, profiler | 78 tests, OK |
| Android runtime/build-config/render/performance instrumentation | 25 tests, OK |
| recovery trace and golden integrity | 40 tests, OK |

The P9-T02 accepted full immutable trace and Android evidence is carried
forward: no executable code or build policy changed in this audit.  The tests
above additionally confirm the affected recovery contracts remain intact.

## Retained accepted cases and rationale

- Off-world tilemap preparation is retained because the P4 Event barrier
  prevents movement, input and later command execution until one atomic commit
  or rollback.
- Canonical load iterators are retained because their yields are drained
  internally before S/Q publication; Android differs only in read/presentation
  orchestration.
- Map/debugger/observer null guards are retained for valid no-map states.
- Streamed audio/resource policy, render caches, title smoke and debugger
  frontends remain owner-local platform/presentation mechanisms.

## Risks and unresolved questions

- `load_iter` and builder iterators must continue to be consumed only by their
  synchronous wrappers/canonical transaction or the explicitly protected P4
  pending-job path.  A future external frame-by-frame consumer would require
  controller review.
- The legacy tile-animation tint restore guard intentionally accepts malformed
  old tint data; it is unrelated compatibility debt and was not expanded.
- No unresolved contamination requires escalation.  No new architecture,
  semantic divergence, or partial-state failure was observed.

## Exact audit commands

```powershell
rg -n "is_android_runtime\(|is_android_render_optimization_enabled\(" app --glob '*.py' --glob '!app/tests/**' --glob '!app/editor/**'
rg -n -i "is_android_runtime|is_android_render_optimization_enabled|ANDROID_ARGUMENT|android_" app/engine/game_state.py app/engine/state_machine.py app/events/event.py app/events/event_functions.py app/engine/action.py app/engine/phase.py app/engine/driver.py app/engine/save.py app/engine/general_states.py app/engine/title_screen.py app/engine/game_over.py app/engine/runtime_debugger.py app/engine/runtime_debugger_controller.py app/engine/combat app/engine/jobs/tilemap_change_job.py app/engine/runtime_capabilities
rg -n "prepare_for_load\(|_staged_state_data|commit_staged_state" app --glob '*.py'
rg -n -C 3 "\byield\b" app/engine/game_board.py app/engine/objects/tilemap.py app/engine/action.py app/engine/state_machine.py app/engine/combat/animation_combat.py app/events/event_functions.py app/engine/save.py app/engine/general_states.py app/engine/driver.py
rg -n -C 4 "^import threading|^from threading|threading\.Thread|\bThread\(" app --glob '*.py'
```

The final compile and Git whitespace checks are recorded with the commit.
