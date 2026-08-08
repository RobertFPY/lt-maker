# P2-T01 GameState / state-restore delta map

Date: 2026-08-08 (Asia/Bangkok)
Task: P2-T01-R1 — destination-stack audit correction only; no production,
test, golden, save-format, or project-data change.
Reference: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
Audit HEAD: `cf9188f013af74e4c58b1f566a6ef5951edff626`

## Scope, sources, and conclusion

Read/reference-compared the complete restore surface in `game_state.py`,
`state_machine.py`, `state.py`, `general_states.py`, `title_screen.py`,
`save.py`, `overworld/overworld_states.py`, `runtime_debugger.py`,
`runtime_reset.py`, `game_board.py`, and `objects/tilemap.py`. Call sites were
found with repository-wide symbol searches and compared through the reference
revision, current source, and introducing/follow-up commits.

The PC reference performs normal load, restart, and level setup synchronously:
the saved stack is installed early inside `GameState.load`, but no state lifecycle
method can run until that Python call returns with registries, level, board,
fog/vision, units, auras, controllers, events, and combat RNG restored. Its
logical transaction boundary is the return from `GameState.load` (or
`GameState.start_level` for restart/start flows).

Current desktop wrappers still exhaust `load_iter`, `start_level_iter`,
`level_setup_iter`, and `set_up_game_board_iter` in one call, so their externally
observable behavior remains the reference-shaped synchronous transaction. This
is covered by S1, S2, S4, S12, and S18.

Current Android title and in-chapter paths instead retain an opaque loader as
the top state while `SaveLoadJob` advances `GameState.load_iter` and sometimes
`start_level_iter` over multiple frames. The loader refuses input and does not
draw the map, so a normal saved `MapState.begin`/`update` does not run during
the shown yield phases. However, the live singleton's registries, level,
board, controllers, RNG, and events are nevertheless mutated incrementally.
That is containment by loader/guards, not the PC-reference atomic world
transaction required by INV-03. The P2-T02 target is therefore to retain only
off-world/pending preparation and publish a complete world in one main-thread
commit.

No reference ambiguity, competing semantic result, or new architecture choice
was required to produce this map. The exact pending-world representation is an
implementation question for plan-defined P2-T02 (`GPT-5.6 Sol / max`), which
remains controller-blocked; it is not an implementation decision made here.

## Restore-call and field/consumer index

| Surface | Current callers/consumers | Reference behavior and audit finding |
| --- | --- | --- |
| `GameState.load` | `save.load_game`; `RuntimeDebugger.restart_chapter` for `chapter_start_snapshot`; module `load_level`; S2/S12 Trace V1 harness calls | Synchronous public API in both revisions. Current drains `load_iter`, so no yield is externally visible to desktop callers. |
| `GameState.load_iter` | `GameState.load` drains it; `SaveLoadJob.advance` drives it with `replace_state_machine=True` | New post-reference yieldable live-world restore. Its only asynchronous consumer is `SaveLoadJob`. |
| `GameState.start_level` | title desktop Load/Restart/New Game; in-chapter desktop load; debugger restart; module `start_level`/`load_level`; overworld transition | Synchronous wrapper around current iterator; reference implementation itself was synchronous. |
| `GameState.start_level_iter` | `GameState.start_level` drains it; `TitleLoadJobState`; `InChapterLoadJobState` | New yieldable tilemap/level/setup sequence. The latter two are Android-only staged consumers. |
| `GameState.level_setup` / `_iter` | `start_level[_iter]`; `build_level_from_scratch`; module entry points | Current wrapper remains synchronous; iterator exposes board/region/fog/unit-arrival/aura phases. |
| `GameState.set_up_game_board` / `_iter` | `level_setup_iter`; `load_iter`; `OverworldFreeState.set_up_overworld_game_state` | Current wrapper remains synchronous. Iterator assigns live `board` after `GameBoard.build_iter`; board construction is a Phase 4 dependency. |
| `_staged_state_data` | initialized/cleared by `GameState.__init__`, `clear`, `prepare_for_load`; written by `load_iter(replace_state_machine=True)`; consumed by `commit_staged_state` | Added by `8306e1a9`; prevents saved map stack exposure but leaves a live world incrementally rebuilt. Android start/restart/overworld branches do not consume it, so it remains stale until the next preparation. The title-overworld branch also appends destination state twice. |
| `chapter_start_snapshot` | written after `level_setup_iter`; cleared by `clear`; consumed by `RuntimeDebugger.restart_chapter` | Added in `0821182a`; protected restart feature. Captures state before `LevelStart` events mutate chapter data. |
| `commit_staged_state` | title job normal-save completion; in-chapter job normal-save completion | Replaces `game.state` only after `load_iter` reaches events/aura completion. It is the current state-stack commit, not a complete-world commit. |
| `load_iter(..., replace_state_machine=True)` | only `SaveLoadJob.advance` | Defer saved state stack; the false/default path preserves desktop stack-install timing. |
| `StateMachine.load_states` | `GameState.load_states`; direct desktop title/load/restart calls; `GameState.load` default; `commit_staged_state`; title/in-chapter job destinations | Appends state instances; it does not clear/replace existing runtime stack. State installation is authoritative as soon as called. |
| `StateMachine.process_temp_state` | engine driver; direct title/general callers after queueing clear/push/wait; state machine update | Commits queued stack changes and invokes `end`/`finish`. It is not a world-validity barrier. |
| `save.load_game` | desktop title Load/Restart; `general_states.load_save_slot`; debugger fallback restart | Reads synchronously, `build_new`, `GameState.load`, assigns slot, updates UIDs. Preserve API and save format. |
| Android title/load jobs | `TitleLoadState._start_android_load` → `TitleLoadJobState`; `InChapterLoadState._start_android_load` → `InChapterLoadJobState` | Added by `52bd0403`/`0821182a`; the only normal asynchronous restore orchestration. |

## Ordered transaction maps

### 1. Desktop normal save load

Reference and current desktop execution have the same no-frame-visible shape:

```text
authoritative old title/map state
  -> title/general caller queues and commits clear where applicable
  -> save.load_game reads pickle
  -> build_new initializes default registries/controllers
  -> GameState.load (current drains load_iter synchronously)
       game vars + seed + mode + counters
       saved state instances installed
       item/skill/unit/region/party/team registries and links
       overworld registry, action/support/record/dialog/RNG data
       level restore -> board -> generic controllers/cursor
       fog/vision regions -> unit arrival/FOW -> aura re-derivation
       EventManager restore
  -> current save slot/next UIDs
  -> optional start-level or overworld destination setup
  -> title_wait / loading state
  -> next engine frame sees a complete restored world
```

The reference saved stack is instantiated before registry rebuilding, but it
cannot call `start`, `begin`, or `update` until `load_game` returns. Current
desktop has the same property because `GameState.load` exhausts the iterator.
`load_game` and direct title/restart callers are `KEEP-SHARED`; the optional
restart/overworld destination is a protected later feature.

### 2. Android title save load

```text
title Load/Restart menu (old authoritative title state)
  -> TitleLoadState._start_android_load stores job/context, starts read thread,
     queues title_load_job
  -> title_load_job is top/opaque; input is ignored and draw is title/black
  -> worker reads/unpickles bytes only (no game singleton mutation)
  -> main thread SaveLoadJob.prepare_for_load clears live runtime fields
  -> main thread advances GameState.load_iter over many frames
       registries/links/world data/RNG/controllers/level/board/fog/arrivals/
       auras/events mutate the live singleton incrementally
       saved stack held in _staged_state_data
  -> normal save: commit_staged_state installs saved stack, then title_wait
  -> start/restart save: advance start_level_iter, then append loading state
  -> overworld save: _begin_post_load appends overworld once; _complete_load
     appends overworld a second time; then title_wait is queued and committed
  -> destination state begins on a later engine update
```

The loader blocks normal state lifecycle access during the yielded steps, but
the live world is still partial. The `start` and `overworld` branches do not
consume `_staged_state_data`; the payload is discarded only by a later
`prepare_for_load`/`clear`. The two title-overworld appends are source-proven:
`_begin_post_load()` at `title_screen.py:974-976` appends the first, then
`_complete_load()` at `:994-995` appends the second before it queues and
commits `title_wait`. This is not an idempotent API: `StateMachine.load_states`
appends directly to `self.state`. P2-T02 must make destination selection
explicit and install it once at the atomic transaction boundary.

### 3. In-chapter load

```text
Map option menu -> in_chapter_load (real input/menu)
  desktop: load_save_slot -> save.load_game synchronously -> destination setup
  Android: InChapterLoadState._start_android_load
       -> queue clear + opaque in_chapter_load_job
       -> SaveLoadJob read thread / main-thread load_iter slices
       -> normal save: commit_staged_state
       -> start save: start_level_iter, then start_level_asset_loading
       -> overworld save: load_states(['overworld'])
       -> remove suspend; loader ends
```

`in_chapter_load_job` has `show_map=False`, ignores input, and draws black, so
the previous map state cannot observe the incomplete world after the queued
clear commits. This is stronger containment than the old staged saved-stack
swap, but still not an atomic world restore because `prepare_for_load` and each
iterator phase mutate `game` live.

### 4. Chapter restart

```text
Title Restart Level (desktop)
  -> select RESTART_SLOTS[slot] (or SAVE_SLOTS[slot] for overworld)
  -> build_new -> save.load_game(restart slot) synchronously
  -> start_level(_next_level_nid) synchronously -> title_wait/loading

Runtime debugger restart
  -> use in-memory chapter_start_snapshot if available
     else RESTART_SLOTS[current_save_slot] if it is a start save
  -> release Android debugger touch consumer
  -> build_new + GameState.load(snapshot), or save.load_game(slot)
  -> preserve selected difficulty -> start_level(level_nid)
```

`chapter_start_snapshot` is captured after board/unit/aura setup and before
`LevelStart` can mutate persistent chapter objects. Preserve it as
`KEEP-CORRECTNESS-FIX`/feature behavior; do not conflate it with the staged
loader. Restart slots remain slot-keyed and the normal `kind == 'start'`
new-game save remains their pristine source. Test Chapter fallback behavior is
also preserved (it may seed a restart from the first save when no start slot
exists).

### 5. Overworld restore

```text
load save with no level
  -> restore registries, overworld objects, game vars/RNG/events
  -> generic controllers (current load_iter does this before its controllers yield)
  -> caller/job installs overworld state
  -> OverworldFreeState.start:
       generic -> overworld cursor/controller/movement/map view
       set_up_game_board(overworld tilemap)
       next-level marker, entity cleanup, cursor/camera, OverworldStart event
```

Desktop completes the first half synchronously before `OverworldFreeState` can
begin. Android must defer `OverworldFreeState` installation until the complete
restore commit; its state start itself synchronously builds overworld map
controllers and board.

## Destination-stack matrix — exact current and reference shapes

Notation: `S` is the ordered saved-state payload `s_dict['state'][0]`; `Q`
is its ordered pending-transition payload `s_dict['state'][1]`; `W` is
`title_wait`; `L` is `start_level_asset_loading`; `O` is `overworld`; and `J`
is the opaque load-job state. `T_L`, `T_R`, and `T_M` mean the pre-existing
Title Load, Title Restart, and in-map stacks respectively. `P(X; Q + D)`
means the exact `StateMachine.process_temp_state()` result after appending
`X`, then processing the saved transitions `Q` followed by destination queue
`D`; it is the only exact source-level representation possible when a save
itself serializes arbitrary pending transitions.

| Entry path / revision | Saved payload and installation | Explicit operations in exact order | `_staged_state_data` | Final stack immediately before the next normal lifecycle update |
| --- | --- | --- | --- | --- |
| PC reference desktop, normal save (`TitleLoadState`) | `S`, `Q`; `GameState.load` calls `load_states(S, Q)` synchronously after title stack clear | `clear; process; build_new; load_states(S,Q); change(W); process` | absent | `P(S; Q + [W])` |
| Current desktop, normal save (`TitleLoadState`) | `S`, `Q`; `GameState.load` drains `load_iter` and calls `load_states(S, Q)` synchronously | `clear; process; build_new; load_iter` (drained) `→ load_states(S,Q); change(W); process` | not used | `P(S; Q + [W])` — reference-shaped |
| PC reference desktop, `kind == 'start'`, Load Game | `S`, `Q`; installed synchronously | `clear; process; build_new; load_states(S,Q); load_states([L]); start_level; change(W); process` | absent | `P(S + [L]; Q + [W])` |
| Current desktop, `kind == 'start'`, Load Game | `S`, `Q`; installed synchronously while `load_iter` is drained | `clear; process; build_new; load_iter → load_states(S,Q); load_states([L]); start_level; change(W); process` | not used | `P(S + [L]; Q + [W])` — reference-shaped |
| PC reference desktop, `kind == 'start'`, Restart Level | `S`, `Q`; appended to existing Title Restart machine because this path has no pre-load `clear` | `build_new; load_states(S,Q); start_level; change(W); process` | absent | `P(T_R + S; Q + [W])` |
| Current desktop, `kind == 'start'`, Restart Level | same `S`, `Q`; current wrapper is synchronous and also has no pre-load `clear` | `build_new; load_iter → load_states(S,Q); start_level; change(W); process` | not used | `P(T_R + S; Q + [W])` — reference-shaped |
| PC reference desktop, `kind == 'overworld'`, Load Game | `S`, `Q`; installed synchronously after clear | `clear; process; build_new; load_states(S,Q); load_states([O]); change(W); process` | absent | `P(S + [O]; Q + [W])` |
| Current desktop, `kind == 'overworld'`, Load Game | `S`, `Q`; installed synchronously after current iterator drains | `clear; process; build_new; load_iter → load_states(S,Q); load_states([O]); change(W); process` | not used | `P(S + [O]; Q + [W])` — reference-shaped |
| PC reference desktop, `kind == 'overworld'`, Restart Level | `S`, `Q`; appended to existing Title Restart machine | `build_new; load_states(S,Q); load_states([O]); change(W); process` | absent | `P(T_R + S + [O]; Q + [W])` |
| Current desktop, `kind == 'overworld'`, Restart Level | same `S`, `Q`; no pre-load clear | `build_new; load_iter → load_states(S,Q); load_states([O]); change(W); process` | not used | `P(T_R + S + [O]; Q + [W])` — reference-shaped |
| Current Android title, normal save | `S`, `Q` held by `load_iter(..., replace_state_machine=True)` until `commit_staged_state()` creates a new machine with `load_states(S,Q)` | `T_L; change(J); process → T_L+[J]; prepare/load slices; commit_staged_state; change(W); process` | consumed by `commit_staged_state` | `P(S; Q + [W])`; old title/job machine is replaced |
| Current Android title, `kind == 'start'` Load Game | `S`, `Q` never installed; level is rebuilt after restore | `T_L; change(J); process; stage(S,Q); start_level_iter; load_states([L]); change(W); process` | remains stale | `T_L + [J,L,W]` |
| Current Android title, `restart_level` | `S`, `Q` never installed; same post-load level rebuild | `T_R; change(J); process; stage(S,Q); start_level_iter; load_states([L]); change(W); process` | remains stale | `T_R + [J,L,W]` |
| Current Android title, `overworld` (Load Game or Restart Level's overworld slot) | `S`, `Q` never installed | `T; change(J); process; stage(S,Q); _begin_post_load: load_states([O]); _complete_load: load_states([O]); change(W); process`, where `T` is `T_L` or `T_R` | remains stale | `T + [J,O,O,W]` — two distinct `OverworldFreeState` instances |
| Current Android in-chapter, normal save | `S`, `Q` held until replacement | `T_M; clear; change(J); process → [J]; stage(S,Q); commit_staged_state` | consumed by `commit_staged_state` | `S` with pending `Q`; no post-commit `process_temp_state` occurs before the next lifecycle update |
| Current Android in-chapter, `kind == 'start'` | `S`, `Q` never installed; level rebuilt | `T_M; clear; change(J); process → [J]; stage(S,Q); start_level_iter; load_states([L])` | remains stale | `[J,L]` |
| Current Android in-chapter, `kind == 'overworld'` | `S`, `Q` never installed | `T_M; clear; change(J); process → [J]; stage(S,Q); _begin_post_load: load_states([O])` | remains stale | `[J,O]` — exactly one `OverworldFreeState` |

Reference-shaped destination target, established by the desktop source, is
therefore exact rather than a generic retain/discard policy: normal saves
publish `S` and its pending `Q`, then `W`; Load Game start saves publish `S`,
`Q`, `L`, then `W`; restart-level start saves preserve their documented title
stack behavior and add no duplicate destination; overworld saves append one
and only one `O` before `W`. Android must not retain the saved stack as a
long-lived singleton payload, and it must not append either destination twice.

## R1 title-overworld reference comparison

The double append is a demonstrated current Android divergence/workaround
defect, not an established later feature requirement.

- PC reference `9314f54b` has no `TitleLoadJobState`. Its synchronous desktop
  Load Game and Restart Level overworld paths each call
  `game.load_states(['overworld'])` once, then queue/process `title_wait`.
- Current `52bd0403` introduced `TitleLoadJobState._begin_post_load()` and its
  first `overworld` append. `git blame` assigns that call to `52bd0403`.
- Current `8306e1a9` added the second append in `_complete_load()` while
  changing the start-save sequencing to defer saved state until level rebuild.
  Its title-job test additions cover normal-save commit and start-level
  installation; they contain no title-overworld assertion and the diff does
  not remove the pre-existing first append.
- `StateMachine.load_states()` is append-only in both reference and current
  code. No source, history, or existing test establishes a requirement for two
  `OverworldFreeState` instances. Current `InChapterLoadJobState` independently
  demonstrates the intended single-append shape for its overworld path.

Accordingly, P2-T02's reference-shaped requirement is one explicit final
overworld installation, after authoritative world restore, followed by the
same title handoff where that handoff applies. This R1 records the defect only;
it does not alter production behavior.

## Function and field classification map

`S#` references the immutable Phase 1 fixtures under
`app/tests/fixtures/recovery_traces/v1/`; test names identify targeted
lifecycle coverage. “Commit” is provenance, not a request to revert the whole
commit.

| File + symbol | PC reference | Current recovery | Commit(s) | Invariant/risk | Class | Later treatment | Dependencies and proof |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `game_state.py::clear` | resets live session/state | also clears staged payload and chapter snapshot | `8306e1a9`, `0821182a` | stale pending state/snapshot | `KEEP-SHARED` | retain; define transaction abort reset | S1/S2/S4/S18; lifecycle tests |
| `GameState::build_new` | synchronous default-world construction | same public behavior; desktop load calls it before synchronous restore | baseline / `52bd0403` context | seed/save compatibility | `KEEP-SHARED` | retain | S1 seed, S2/S4/S18 |
| `GameState::prepare_for_load` | absent | clears live registries/controllers before async iterator | `52bd0403` | live old world becomes half-new world | `REWRITE-PLATFORM` | re-port as pending-context creation | S2/S4/S18; Android loader tests |
| `GameState::_staged_state_data` | absent | stores saved `(states,temp)` until job finalization | `8306e1a9` | protects state stack but not live world; stale in start/overworld branches | `REMOVE-WORKAROUND` | remove-after-proof or replace with transaction-local payload | lifecycle + S2/S4/S18 |
| `GameState::commit_staged_state` | absent | creates/replaces state machine after `load_iter` | `8306e1a9` | only stack is atomic; old loader executes after replacement | `RESTORE-PC-SEMANTICS` | replace with final full-world commit | S2/S4/S18; lifecycle tests |
| `GameState::generic` | synchronous controller creation | invoked early by iterators and on overworld no-level restore | `52bd0403` | controllers can point at incomplete level/board | `KEEP-SHARED` | retain, invoke inside final commit or pending context | S1/S2/S4/S12/S18 |
| `GameState::level_setup` / `level_setup_iter` | one synchronous level transaction | yieldable board/regions/fog/register/arrival/aura/snapshot phases | `52bd0403`, `0821182a` | partial board/aura/FOW/units | `RESTORE-PC-SEMANTICS` | desktop restore; Android re-port pending preparation | S1/S4/S12/S13/S18 |
| `GameState::start_level` / `start_level_iter` | build tilemaps, level, setup synchronously | iterator exposes live controllers then level/setup phases | `52bd0403`, `0821182a` | destination could see partial chapter | `RESTORE-PC-SEMANTICS` | restore wrapper; re-port iterator off-world | S1/S4/S18; loading lifecycle tests |
| `GameState::set_up_game_board` / `_iter` | synchronously assigns `GameBoard` then boundary | `GameBoard.build_iter` then assigns live board | `cdd4be2a`, `0821182a` | board without regions/FOW/aura; Phase 4 ownership | `REWRITE-PLATFORM` | keep synchronous in P2; pending board only after P4 proof | S12/S13/S14; board/tilemap tests |
| `GameState::load` / `load_iter` | synchronous restore; saved stack cannot run mid-call | default drains iterator; job advances live singleton over frames | `52bd0403`, `8306e1a9` | INV-03 core delta | `RESTORE-PC-SEMANTICS` | one canonical atomic restore transaction | S2/S4/S12/S18; trace/lifecycle |
| `GameState::chapter_start_snapshot` | absent | deep save after level setup, used by debugger restart | `0821182a` | preserve restart intent/pristine boundary | `KEEP-CORRECTNESS-FIX` | retain; capture in atomic post-setup point | S4/S18; `test_runtime_debugger` |
| `state_machine.py::load_states` | appends restored instances | same append API; adds Android loader registrations | `52bd0403`, `0821182a` | installation instantly authoritative; not replacement | `KEEP-SHARED` | retain append semantics; P2 commit uses explicit replacement only | lifecycle tests; S2/S4/S18 |
| `StateMachine::process_temp_state` / `update` | commits queued changes at update end | same authoritative queue plus profiler/render behavior | `52bd0403`, `7735ca29` | no world-validity guarantee | `KEEP-SHARED` | retain; do not use as restore barrier | lifecycle tests, S15-S17 |
| `state.py::MapState.update_visuals` guards | unconditional camera/map draw path | skips camera/map-view work when tilemap absent | `390638ac`, `6bd9da4b` | workaround proves staged partial state existed | `REMOVE-WORKAROUND` | P2-T03 candidate after proof; do not remove now | lifecycle tests; S1/S2/S4/S18 |
| `save.py::SaveLoadJob` | absent | worker reads bytes; main thread mutates live state in timed slices | `52bd0403`, `7f717b6b9` | safe I/O, unsafe live restore granularity | `REWRITE-PLATFORM` | retain worker read; re-port hydrate/build to pending world | S2/S4/S18; Android round-3 tests |
| `save.py::load_game` | read → build_new → load → slot/UIDs synchronously | same API with profiled byte read | `52bd0403` | save API/format compatibility | `KEEP-SHARED` | retain synchronous semantic API | S2/S4/S18 |
| `save.py::save_io` / restart slots | reference slots; restart flow exists | serial I/O, user-data paths, restart carry-forward and Test Chapter fallback | `52bd0403`/later save fixes | protected save/restart feature | `KEEP-CORRECTNESS-FIX` | retain independently of scheduling | S4/S18; title save tests |
| `title_screen.py::TitleLoadState` / `TitleRestartState` desktop branches | direct synchronous load/restart | retains direct branches; Android dispatch added | `52bd0403` | title stack/destination order | `KEEP-SHARED` | retain exact desktop destination behavior | S2/S4/S18 |
| `TitleLoadState::_start_android_load` | absent | queues opaque title job and starts reader | `52bd0403` | title remains live under loader | `REWRITE-PLATFORM` | retain UI handoff only; pending transaction beneath | S2/S4/S18; title job tests |
| `TitleLoadJobState` | absent | drives restore/start iterators; commits state only for ordinary save. For title-overworld, `_begin_post_load` appends `overworld`, then `_complete_load` appends it again before `title_wait`. | first append `52bd0403`; second append `8306e1a9` | live partial world; stale staged payload for start/overworld; demonstrated double destination stack | `RESTORE-PC-SEMANTICS` | replace with one final destination installation; do not repair in R1 | S2/S4/S18; current tests cover normal/start only, not title-overworld |
| `title_screen.py::TitleSaveState` | synchronous next level/overworld after save | same logical save/restart flow | `52bd0403` mixed | preserve save kind/destination | `KEEP-SHARED` | retain | S4/S18 |
| `general_states.py::load_save_slot` | absent in reference | desktop in-map load wrapper, synchronous | `52bd0403` | in-chapter saved-state replacement | `KEEP-SHARED` | retain through transaction API | S2/S4/S18 |
| `InChapterLoadState` / `InChapterLoadJobState` | absent | Android loader clears map stack, drives SaveLoadJob | `0821182a` | opaque state contains but does not eliminate partial live world | `RESTORE-PC-SEMANTICS` | re-port UI only; final atomic commit | S2/S4/S18; Android round-3 |
| `general_states.py::LoadingState` | music loading after level is ready | Android music flush/load worker policy | `52bd0403`, `9004c67b` | resource thread must not mutate gameplay | `KEEP-PLATFORM` | retain resource policy outside commit | S1/S4/S18 |
| `overworld_states.py::OverworldFreeState.set_up_overworld_game_state` | synchronous controllers/board during state start | same construction plus later entity correctness fix | `52bd0403`/later | must not start before restore committed | `KEEP-SHARED` | retain start; gate installation on atomic commit | S2/S4/S18 |
| `runtime_debugger.py::restart_chapter` | absent | snapshot/restart-slot recovery, touch release | `0821182a`/later | debugger/restart preservation; direct state replacement | `KEEP-CORRECTNESS-FIX` | retain; route through future transaction API | S4/S17/S18; debugger tests |
| `runtime_reset.py::queue_return_to_title` | absent | queued reset avoids ending an active child mid-input | later feature | state lifecycle correctness | `KEEP-CORRECTNESS-FIX` | retain | lifecycle tests; S17/S18 |
| `game_board.py::GameBoard.build_iter`, `objects/tilemap.py::from_prefab_iter` | synchronous construction | yieldable construction consumed by restore/start iterators | `cdd4be2a`, `0821182a` | live board/tilemap visibility | `REWRITE-PLATFORM` | Phase 4 pending-board decision; P2 must not expose it | S12-S14 |

## Proposed authoritative atomic restore boundary for P2-T02

This is a design recommendation only.

```text
old authoritative GameState + current StateMachine
  -> (optional worker) read immutable save bytes
  -> main-thread pending restore preparation/hydration
       no writes to live registries, level, board, controllers, events,
       combat RNG, current party, or active state machine
  -> build and cross-link pending items/skills/units/parties/teams/overworlds
  -> build pending level/tilemaps/board/boundary/regions/FOW/unit placement/
       aura children/controllers/cursor/events; validate all required links
  -> choose explicit destination policy:
       saved stack OR rebuilt start/restart level OR overworld
  -> ONE main-thread commit:
       publish complete world fields + RNG + current slot + destination stack
       clear temporary restore data as part of the same commit
  -> normal State.start/begin/update and input are permitted
```

The commit must be all-or-nothing: a failed read/hydration/build leaves the old
authoritative session intact or moves to a clean title session, never a
partially-mutated live map. The design preserves serialized save payloads,
restart slots, `chapter_start_snapshot`, aura re-derivation, existing RNG,
fast-forward timing, debugger/profiler observer contracts, and Android
resource/audio work. It does **not** require changing any Phase 1 fixture.

## P2-T03 workaround candidates — do not remove in P2-T01

| Candidate | Why it exists now | Required proof before removal |
| --- | --- | --- |
| `MapState.update_visuals`: `game.camera and game.tilemap` | `390638ac` camera safety during staged restore | no MapState can become visible/start/update before one complete world commit |
| `MapState.update_visuals`: `game.map_view and game.tilemap` | `6bd9da4b` map-view safety during staged restore | same, including overworld and restart destinations |
| `settings.py` transparent-map null guard | prevents an options overlay drawing a missing map/camera | lifecycle trace proves no transparent map UI survives restore commit |
| debugger `cursor`/`board`/`tilemap` checks | defensive observer behavior; some protect normal no-map title/overworld modes too | classify individually; do not remove merely because staged restore is fixed |
| `prepare_for_load` clearing live camera/board/cursor | makes staged job drawable after tearing down map | replace with pending preparation, then remove only after failure/abort proof |
| `_staged_state_data` and delayed `commit_staged_state` | suppresses saved map stack while live world is rebuilt | replace only after full transaction commit owns both world and stack |

## Safe P2-T02 implementation slices (not implemented)

1. Define the restore transaction input/output and destination policy without
   changing save bytes or `save.load_game` callers. Include normal, start,
   restart, and overworld destination cases.
2. Separate non-authoritative construction from `GameState` publication; keep
   every object cross-link, aura, FOW, board, cursor, controller, event, and
   RNG step in the pending side until it validates.
3. Add one main-thread publication point that installs world and state stack
   together, consumes/discards pending state deterministically, and provides
   an all-or-nothing error path.
4. Rewire desktop direct callers and Android title/in-chapter loaders to the
   same transaction semantics while retaining Android worker I/O/resource
   scheduling outside the commit.
5. Run S1/S2/S4/S12/S18 first, then all immutable golden comparisons and
   lifecycle/title/debugger tests. Only after those prove the invalid state
   impossible may P2-T03 evaluate the listed guards.

## Required proof matrix and risks

| Concern | Required existing evidence | Residual risk to address in P2-T02 |
| --- | --- | --- |
| normal save restore | S2 `save.restore.complete` | state stack/world commit must remain one transaction |
| restart slot and game-over restart | S4 `restart.complete`, S18 restart chain | preserve slot format, start-save distinction, and title transitions |
| new-game/chapter setup | S1 `player.control.ready` | retain config-authoritative seed and post-setup control state |
| aura load/teardown | S12 propagated/load/teardown checkpoints | pending re-derivation must use live parent skill identities only after commit |
| FOW/board state | S13 preview/cancel/wait; S14 tilemap commit | no board/fog/region state may publish separately |
| fast-forward and observers | S16 INV-06, S17 INV-07 | loaders/commit must not change logical order/RNG/state transitions |
| title/in-chapter lifecycle | `test_state_machine_lifecycle`, title-load/save, Android round-3 tests | do not depend on append-only `load_states` as a hidden replacement operation |

## Unresolved controller decisions

- The P2-T02 implementation must choose the concrete pending-world container
  only if it can stay bounded; controller direction expressly does not
  authorize inventing a cross-cutting pending `GameState` abstraction.
- There is no open retain/discard semantic question for the destination stack:
  the matrix records the established desktop/reference shapes for normal,
  start, restart, and overworld saves. The remaining implementation question
  is mechanical: how to hold `S`/`Q` transaction-locally until the single
  restore commit, rather than in `_staged_state_data`.
- Keep every save-format/restart compatibility field until a later save-format
  audit proves it independent. In particular, do not solve atomicity by
  recreating saves, changing slot kinds, or dropping restart metadata.

## Audit disposition

- No production behavior was modified.
- Immutable Trace V1 fixtures/manifest were not opened for write or changed.
- No escalation trigger was reached during the source/reference comparison.
- P2-T02 is plan-defined as `GPT-5.6 Sol / max` and remains controller-blocked
  pending acceptance of this R1 map.
