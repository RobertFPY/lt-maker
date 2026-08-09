# P6-T01 Runtime capability map

## Scope and decision

This is an architecture audit and migration design for P6 only.  It makes no
production change and does not move a caller.  The behavioral comparison point
is PC revision `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.

The proposed direction is deliberately small:

```
gameplay caller -> narrow policy capability -> desktop or Android backend
```

The capability selects *how* a presentation/resource operation happens.  It
does not own game objects, the state machine, Event processing, a solver, RNG,
or save/restart data.  A capability implementation must remain importable
without PyQt5.

The following remain shared gameplay semantics and must never platform-fork:

| Area | Required shared behavior | Classification |
| --- | --- | --- |
| Combat | Solver phases, RNG consumption, hook/event order, generated actions, playback meaning, and cleanup order | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK; KEEP-SHARED |
| State/load | One complete authoritative `GameState` transaction; S/Q publication and destination installation once | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK; KEEP-CORRECTNESS-FIX |
| Tilemap | Live unit/region/board/aura/FOW commit is synchronous and atomic | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK; KEEP-CORRECTNESS-FIX |
| Save/restart | Canonical load, `SAVE_SLOTS != RESTART_SLOTS`, pristine chapter-start restart | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK; KEEP-CORRECTNESS-FIX |
| Input actions | `InputManager` owns raw-input interpretation and game actions; fast-forward edge behavior remains INV-06 | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK; KEEP-SHARED |
| Observers | Debugger/profiler are idle observers under INV-07 and cannot advance or mutate a transaction | OBSERVER-ONLY; KEEP-CORRECTNESS-FIX |

## 1. Whole-repository platform-branch inventory

The table records source branches rather than treating the name “Android” as
proof of a semantic difference.  “Lifecycle advances” means that the branch
can directly decide whether normal gameplay/Event/state-machine work advances.

| File and symbol | Caller / condition | Data read or written | Authoritative mutation / lifecycle advance | Provenance and classification | Proposed treatment |
| --- | --- | --- | --- | --- | --- |
| `app/engine/android_runtime.py::{is_android_runtime,is_android_render_optimization_enabled}` | All listed platform callers; `LT_ANDROID_RUNTIME`, `LT_ANDROID_RENDER_OPT` | Environment only | None | CAP-FILESYSTEM; KEEP-PLATFORM | Keep low-level helpers local; no wrapper merely for aesthetics |
| `android_runtime.py::{AndroidVirtualControls,get/set_android_virtual_controls}` | `settings.py` controls editor | Registered UI bridge | No game mutation | CAP-INPUT-TOUCH; KEEP-PLATFORM | Keep existing narrow protocol direct |
| `android_runtime.py::{set_android_touch_consumer,dispatch_android_touch}` | Android debugger; platform bootstrap | Current UI touch consumer and raw finger coordinates | Delivers UI-owned raw touch only; no action injection | CAP-INPUT-TOUCH; KEEP-CORRECTNESS-FIX | Keep direct; `InputManager` remains the gameplay boundary |
| `android_runtime.py::{show,poll,dismiss}_android_debug_input`, visible-height helpers | `android_debugger.py` | JNI/UI request identifiers, text, viewport size | No direct game mutation | CAP-INPUT-TOUCH / OBSERVER-ONLY; KEEP-PLATFORM | Keep Android-local; lazy JNI imports preserve desktop importability |
| `engine.py::on_end` and `driver.py::run` | Runtime shutdown/debug setting; desktop-only debugger window | Runtime debugger service/window state | Starts/stops desktop observer service, not gameplay | OBSERVER-ONLY; KEEP-PLATFORM | Keep direct; not a capability client |
| `performance.py::RuntimeProfiler` and profiler sections in driver/state machine | Android plus `LT_ANDROID_PROFILE` | Timing, GC, thread-local frame scopes, counters | No game mutation; worker scopes deliberately ignored | OBSERVER-ONLY; `d2bbd026e` isolation work | Keep direct and observer-only |
| `debug_mode.py::DebugState.start`, `android_debugger.py`, `runtime_debugger.py::restart` touch release | Debug menu router, raw touch ownership during restart | UI router, touch consumer | Router changes only debug UI state; controller executes existing explicit debug commands | CAP-INPUT-TOUCH / OBSERVER-ONLY; KEEP-CORRECTNESS-FIX | Keep direct; P6 must not make debugger a platform gameplay policy |
| `title_screen.py::{TitleStartState.start,_start_title_music}` | Android render optimisation; Android stream result | Title particles/cache and audio backend result | Particle/cache only; title state transitions remain caller-owned | CAP-RESOURCE, CAP-RENDER-CACHE, CAP-AUDIO | P6-T02 may migrate backend/cache policy only |
| `title_screen.py::{TitleLoadJobState,TitleLoadState}` | Android title Load/Restart route | `SaveLoadJob`, loader presentation, next action | Invokes P5 canonical transaction; loader owns input/presentation | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK; KEEP-CORRECTNESS-FIX | Leave direct and protected by P5 |
| `general_states.py::{LoadingState,InChapterLoadJobState,LoadState}` | Android preload / Android in-chapter save load | Song set/thread, `SaveLoadJob`, opaque loader state | Music worker touches audio cache only; load job calls canonical main-thread hydration | CAP-RESOURCE for song preload; canonical-load portion is GAMEPLAY-SEMANTIC | P6-T02 may migrate only preload policy; leave loader routing intact |
| `save.py::SaveLoadJob` | Android worker read then main-thread `load_game_data` | Immutable save bytes/data, job state | Worker only reads/unpickles; authoritative transaction remains synchronous main thread | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK; Phase-5 KEEP-CORRECTNESS-FIX | Leave direct; it is not generic resource preparation |
| `sound.py::{SoundThread.play_streamed_music,play_streamed_preview,stop_streamed_*,load_songs,flush}` | Combat/title/game-over/sound room/loading state | Mixer stream, sound cache, selected NIDs | No `game`, solver, Event, or state-machine mutation | CAP-AUDIO and CAP-RESOURCE; `9004c67b` Android streamed-music provenance | P6-T02 capability implementation candidates |
| `combat/animation_combat.py::{start_battle_music,finish}` | Animation-combat lifecycle | Semantic music candidates, current song, backend handle | Semantic music selection reads item/skill/level data; backend only affects playback | Selection is GAMEPLAY-SEMANTIC; physical playback is CAP-AUDIO | P6-T02 may migrate only backend calls; leave selection and `battle_music` lifecycle local |
| `game_over.py::GameOverState.start` | Android title-music stream fallback | Music NID and mixer result | No game-over transaction change | CAP-AUDIO | P6-T02 backend migration candidate |
| `base.py::BaseSoundRoomState` | Android stream preview/cache | UI choice, `request_present`, mixer stream, title surface cache | UI action remains local; request-present ordering is state-machine behavior | CAP-AUDIO and CAP-RENDER-CACHE; action ordering is GAMEPLAY-SEMANTIC | P6-T02 may migrate backend/cache work only |
| `battle_animation.py::{update,_advance_android_render_state,draw}` | Android render optimisation | Sprite/effect surfaces, display offsets, visual counters | Presentation animation/render state only; profiler metadata observer-only | CAP-RENDER-CACHE; KEEP-PLATFORM | P6-T02 may consolidate policy query, not change combat timing or visual lifecycle |
| `combat/animation_combat.py` visual cache/draw branches and `combat/mock_combat.py::draw_anims/draw` | Android render optimisation | Animation/damage-number rendering state | Branches suppress display-side progression/draw work; no solver/action hook logic | CAP-RENDER-CACHE, but timing-sensitive presentation | Candidate only after explicit visual-equivalence tests in P6-T02 |
| `highlight.py::HighlightController.draw` | Android render optimisation | Highlight revision/key/surface | Cache derived solely from current authoritative state; does not modify it | CAP-RENDER-CACHE | P6-T02 candidate; retain local invalidation ownership |
| `menus.py::Table`, `settings_menu.py::SettingsMenu`, `settings.py::SettingsState`, `game_menus/menu_options.py::TitleOption` | Android render optimisation | Static menu/text/header/info surfaces and keys | Presentation cache only; settings also controls UI availability | CAP-RENDER-CACHE; input portion CAP-INPUT-TOUCH | P6-T02 can standardize opt-in cache policy; keep each invalidation local |
| `info_menu/info_menu_state.py`, `info_menu/info_graph.py`, `game_menus/menu_components/unit_menu/unit_menu.py` | Android render optimisation | Portrait/content/table surfaces, bounded LRU cache | Derived presentation only; unit data is read, never changed | CAP-RENDER-CACHE | P6-T02 candidates subject to cache invalidation tests |
| `game_menus/menu_states/unit_menu_state.py::take_input` | Android hardware label direction swap | Logical navigation mapping | Delivers the same menu navigation contract; no direct action injection | CAP-INPUT-TOUCH; KEEP-PLATFORM | Leave direct: a small UI-local mapping is clearer than a capability |
| `sprites.py::load_images` import-time `ANDROID_ARGUMENT` | Resource bootstrap before driver initializes Android display | Sprite image surfaces and display format | Resource decode only; no game world | CAP-RESOURCE / CAP-FILESYSTEM | Keep direct bootstrap branch; avoid an import-time capability singleton |
| `data/resources/resources.py`, `utilities/file_utils.py`, `lt_log.py` Android environment paths | Runtime resource/path/log handling | Paths/files/diagnostic output | No gameplay semantic mutation by platform policy | CAP-FILESYSTEM; KEEP-PLATFORM | Leave direct until two source-proven callers need the same narrow API |
| `events/event.py::_draw_overlay_if_present` | Android render optimisation | Event overlay surface | Draw omission only when overlay has no renderable content | CAP-RENDER-CACHE | P6-T02 candidate only with presentation regression test |
| `events/event.py::process` | Android render optimisation, 2 ms deadline | Event processor position and `_android_process_yielded` | Yes: returns between event commands; `EventState` observes the yield | GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK / NEEDS-CONTROLLER-DECISION | Do not migrate in P6-T02. P6-T03 needs proof or controller decision before touching it |
| `events/event.py::{update,take_input}` and `event_functions.py::change_tilemap` | `_android_tilemap_pending` | Pending callback/block predicate/render deferral | Explicitly blocks movement, gameplay input/listeners, and next event command while pending | CAP-WORK-BUDGET plus Phase-4 KEEP-CORRECTNESS-FIX | Preserve Event-local barrier; P6-T03 may move only numeric pending-work policy |
| `jobs/tilemap_change_job.py::TilemapChangeJob.update` | 4 ms `FRAME_BUDGET_NS` Android pending build | Pending tilemap/board/boundary and status | Builds off-world only; final commit is one synchronous live transaction | CAP-WORK-BUDGET; Phase-4 KEEP-CORRECTNESS-FIX | P6-T03 sole approved work-budget migration candidate |
| `state_machine.py` Android state registrations | Static import/routing of Android UI states | State class registry | No runtime platform conditional or gameplay fork | LEAVE-DIRECT — PLATFORM-LOCAL | Keep direct registry entries |
| `map_view.py`, `phase.py`, `combat/base_combat.py`, `combat/map_combat.py`, `combat/simple_combat.py` profiler/render references | Profiling or presentation calculation | Counters/surfaces only | No Android policy selects mechanics | OBSERVER-ONLY or GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK | No P6 capability migration |

### Inventory conclusion

There are many Android-named caches, but they are not one subsystem.  The
common, proven seams are mixer/backend selection, resource/cache policy, and
the already-approved *off-world* tilemap build budget.  Load/restart, combat,
raw action input, Event processing, and live tilemap commit are not seams for a
platform policy API.

## 2. Authoritative gameplay versus platform-policy boundary

| Capability family | It may decide | It must not decide |
| --- | --- | --- |
| CAP-AUDIO | Cached versus streamed backend, preload/flush/release, backend fade/play result | Which battle music is semantically selected; combat/event/state order; whether an action completes |
| CAP-RESOURCE | Immutable/background preparation and release of resource data/surfaces | Mutation of `game`, DB registries, Event, solver, state machine, or worker-side world hydration |
| CAP-RENDER-CACHE | Cache enablement, bounded capacity, presentation-surface prefill and invalidation checks | Logical menu selection, timer/action completion, RNG, model data, or observer effects |
| CAP-WORK-BUDGET | A numeric deadline and enablement of explicitly approved off-world work | A yield between live authoritative mutations, solver/action/cleanup staging, live load hydration, or incremental group placement |
| CAP-FILESYSTEM | A demonstrated runtime path/availability difference | Save schema, slot routing, compatibility, or generic wrapping of `os.path` |
| CAP-INPUT-TOUCH | Android raw-touch/UI-overlay ownership before input interpretation | Direct gameplay action injection, `InputManager` edge behavior, menu mutation, or fast-forward semantics |

The Phase-2 loader, Phase-4 Event-local tilemap barrier, and Phase-5 restart
source are therefore protected consumers, not capability implementations.

## 3. CAP-AUDIO proposal

**Proposed module/name (P6-T02, not created now):**
`app.engine.runtime_capabilities.audio_policy` with a small backend-facing
`MusicPlaybackPolicy` protocol.  This is not a service locator: callers receive
the policy through the existing sound subsystem or a narrow explicit accessor.

```python
class MusicPlaybackPolicy(Protocol):
    def play(self, nid: str, *, battle: bool = False, fade_in: int = 0,
             play_intro: bool = True) -> bool: ...
    def stop_stream(self) -> None: ...
    def preload(self, nids: set[str]) -> None: ...
    def flush_cached(self, *, keep_nids: set[str] = frozenset()) -> None: ...
```

* Desktop/default: use the existing cached `SoundThread` fade/battle-fade path;
  `play()` returns `False` when it does not select a stream.
* Android: attempt the existing streamed mixer path, retain the existing
  fallback to cached/legacy fade, and keep stream stop/release in the mixer
  owner.
* Threading: pygame mixer mutation stays on its current established owner.
  Resource preload may run only with the existing thread-safe sound loader; it
  may never use `game`, Event, solver, registries, or the state machine.
* Failure: backend failure returns a result and the caller performs its existing
  fallback.  It cannot change an active combat, title transition, or game-over
  decision.
* Current caller migration: `animation_combat.start_battle_music/finish`,
  `TitleStartState`, `GameOverState`, `BaseSoundRoomState`, and
  `LoadingState` song preload.  The item/skill/level selection before these
  calls remains in the current gameplay caller.

## 4. CAP-RESOURCE proposal

**Proposed module/name (P6-T02, not created now):**
`app.engine.runtime_capabilities.resource_policy`.

```python
class ResourcePreparationPolicy(Protocol):
    def prepare_audio(self, nids: set[str]) -> None: ...
    def prepare_presentation(self, request: PresentationRequest) -> PreparedPresentation: ...
    def release(self, resource_keys: set[str]) -> None: ...
```

The initial approved callers are level-song preload/flush, title-particle
prefill/seed selection, and any already-existing display-surface preparation.
`PresentationRequest` is immutable data (keys, dimensions, format), never a
live `GameState`, unit, Event, or board object.

* Desktop/default: perform current synchronous/cache behavior.
* Android: may select the proven worker/preload policy for audio and the
  Android display-format preparation policy for surfaces.  Pygame object
  publication remains on the appropriate existing owner.
* Failure: discard prepared result or use the current uncached path; never
  publish a partial authoritative world.
* Direct checks intentionally retained: `sprites.load_images` import-time
  `ANDROID_ARGUMENT` and P5 `SaveLoadJob`; each has a bootstrap/load contract
  unsuitable for generic resource policy.

## 5. CAP-RENDER-CACHE proposal

**Proposed module/name (P6-T02, not created now):**
`app.engine.runtime_capabilities.render_cache_policy`.

```python
class RenderCachePolicy(Protocol):
    def enabled(self, feature: str) -> bool: ...
    def max_entries(self, feature: str, default: int) -> int: ...
```

This policy only selects whether an individual owner may use its own cache and
its bounded capacity.  It never receives a cache key or surface; cache keys,
invalidations, and ownership remain local in `HighlightController`, menu,
settings, info-menu, unit-menu, title, sound-room, and combat-render classes.
That avoids a global surface cache with hidden invalidation/lifetime behavior.

* Desktop/default: `enabled()` is false for the Android-specific fast paths.
* Android: enables only feature keys already proven equivalent, such as static
  menu backgrounds/options, highlights, and bounded unit-menu content.
* Failure: cache miss falls back to the existing uncached draw; it is never a
  logical state failure.
* P6-T02 must not migrate animation branches that suppress visual countdown
  work until focused visual-state tests demonstrate retained waits/effects.

## 6. CAP-WORK-BUDGET proposal

**Proposed module/name (P6-T03, not created now):**
`app.engine.runtime_capabilities.work_budget`.

```python
@dataclass(frozen=True)
class OffWorldWorkBudget:
    enabled: bool
    deadline_ns: int

class OffWorldWorkPolicy(Protocol):
    def tilemap_prepare_budget(self) -> OffWorldWorkBudget: ...
```

* Desktop/default: `enabled=False`; existing synchronous P4-T02 transaction.
* Android: the current 4 ms budget may be returned only for
  `TileMapObject.from_prefab_iter`, `GameBoard.build_iter`, pending boundary
  construction, and validation.  Phase-4 host profiling documented median
  tilemap-plus-board cost of 2.643 ms (small), 7.076 ms (medium), and 14.662 ms
  (large); these are host measurements, not device claims.
* Authoritative contract: the Event-local `_android_tilemap_pending` barrier
  remains.  It blocks movement, gameplay input/listeners, and later event
  commands.  There is no yield after the first live mutation: final P4-T02
  commit either succeeds once or rolls back synchronously before barrier
  release.
* Explicit prohibitions: no policy API for combat staging, `GameState.load_iter`
  host-frame yields, a live `AddGroup` batch, or partial board/units/regions/
  aura/FOW publication.

`Event.process()` is deliberately outside this API.  Its present Android 2 ms
deadline can defer an EventProcessor command to a later outer update.  It has
not been proven equivalent to desktop command scheduling.  P6-T03 may not
migrate it without a controller decision and tests proving that it cannot alter
observable gameplay/event ordering.

## 7. Filesystem/runtime-environment findings

No evidence supports a new generic `CAP-FILESYSTEM` module.  The proven
runtime-specific operations are already narrow: environment detection and lazy
JNI imports in `android_runtime.py`, deferred Android sprite loading in
`sprites.py`, and Android-specific paths/logging in resource/file utilities.
They do not share a stable higher-level contract, and wrapping `os.path` would
only add indirection.  Editor/build paths remain outside the runtime scope.

`SaveLoadJob` file reading is also intentionally not absorbed: Phase 5 defines
it as worker-only immutable read/unpickle followed by the shared canonical
main-thread load transaction.  It is a load semantic boundary, not a resource
cache policy.

## 8. Input/touch findings

The existing `android_runtime` virtual-control and touch-consumer protocol is
already the required narrow interface.  The Android debugger owns its drawer
touches and releases them during restart; the normal engine then routes raw
input through `InputManager`.  `UnitMenuState`'s small Android hardware-label
direction swap is presentation-local and preserves a logical navigation action.

No P6 module is proposed for input in this phase.  A new input facade would
risk bypassing `InputManager` and INV-06 without eliminating meaningful
leakage.  P6-T02/P6-T03 should leave all raw action mapping direct.

## 9. Observer/debugger/profiler findings

`RuntimeProfiler` has no game dependency and explicitly rejects worker-thread
scope mutation.  Its Android enablement is a diagnostic environment decision.
Desktop runtime-debugger service ownership and Android debug drawer routing are
frontends around the existing controller.  They must remain observer-only when
idle; only an explicit user command may invoke the already shared command path.

No observer capability is proposed.  A shared observer service would be too
broad and would risk making debugger/profiler state a lifecycle scheduler.

## 10. Direct checks intentionally left local

| Direct check | Reason to retain |
| --- | --- |
| `android_runtime` environment/JNI/touch functions | Platform bridge is already narrow and lazy-import safe |
| `sprites.py` `ANDROID_ARGUMENT` bootstrap | Import-time display-loader constraint, not a runtime policy client |
| P5 title/in-chapter `SaveLoadJob` routes | Canonical authoritative load contract, not platform resource work |
| P4 Event-local pending barrier and `change_tilemap` | Barrier is semantic proof machinery; only its pending build budget is a policy seam |
| `Event.process()` Android deadline | Potential Event ordering difference; controller proof required before any migration |
| Unit-menu hardware label swap / Android debugger drawer | UI-local mapping and raw-touch ownership; no shared abstraction benefit |
| profiler enablement and desktop debugger window service | Observer plumbing with no gameplay policy role |
| animation render countdown branches | Must remain local until visual lifecycle equivalence is proved |

## 11. P6-T02 migration plan: audio/resource/render

P6-T02 should implement only the approved narrow backends and migrate these
callers in incremental clusters:

1. `sound.py` backend selection/stream lifecycle plus `LoadingState` song
   preload.  Test stream success/fallback, preload thread isolation, flush, and
   no `game` access from worker code.
2. `animation_combat`, title, game-over, and sound room physical music calls.
   Preserve semantic music selection, `request_present`, combat finish order,
   and legacy fallback at the caller boundary.
3. Opt-in cache-policy query for title/menu/settings/highlight/info/unit-menu
   owners.  Preserve owner-local keys/invalidation and bounded LRU eviction.
4. Only after focused tests, consider battle/mock-combat draw cache policy;
   do not alter presentation counters merely because a policy is available.

Each cluster must prove desktop uses its existing default path, Android uses
the current policy/fallback, and no capability imports gameplay-critical
modules.  P6-T02 must not migrate load jobs, raw input, debugger commands,
Event process budgets, or the P4 barrier.

## 12. P6-T03 migration plan: accepted scheduling/work budget

P6-T03 may migrate only the numeric enablement/deadline used by
`TilemapChangeJob.update`.  The job remains pending/off-world; Event retains
the block predicate, movement/input/listener suspension, next-command block,
and one-shot barrier release.  Desktop remains synchronous.

Before that migration, test multiple pending updates, no movement/input/event
advance, no stale position/region inputs, single atomic commit, pending-build
failure, and rollback-before-release.  `Event.process()`'s command deadline is
explicitly excluded pending a controller decision.

## 13. Dependency and circular-import analysis

The allowed dependency direction is:

```
gameplay callers -> runtime_capabilities.<family> ->
    android_runtime / sound backend / engine render-resource helpers
```

Capability modules may import configuration/runtime detection and low-level
audio/render/resource helpers.  They must not import `game_state`, combat,
action, solver, Event, save, title, debugger controller, or state machine.
Those imports would create `gameplay -> capability -> gameplay` cycles and
hide semantic policy in a backend.  Requests are immutable primitives or
dataclasses; no `GameState`, EventProcessor, unit, surface cache owner, or
live save payload crosses the boundary.

## 14. Deterministic migration tests required

| Family | Focused proof |
| --- | --- |
| Audio | Stream success/fallback calls exactly one existing backend path; preload worker cannot mutate gameplay; battle/title/game-over/sound-room order retained |
| Resource | Desktop synchronous and Android preparation results are equivalent; failure uses existing fallback and publishes no partial state |
| Render cache | Cache hit/miss/invalidation renders same logical view; cache-only objects do not affect game data; fast-forward and observer idle remain equal |
| Work budget | Existing `test_tilemap_change_job` barrier matrix plus no live mutation during every pending update and commit/rollback before release |
| Input/touch | Existing Android debugger touch release, virtual-control, and real `InputManager` edge tests; S13 protects move/cancel/Wait contract |
| Load/restart protected paths | Canonical-load/atomic-restore/restart tests prove capabilities never replace the P2/P5 transaction |
| End-to-end | Immutable Trace V1 S5, S12, S13, S14, S16, S17 disabled/debugger-idle/profiler-idle, and S18 |

## 15. Unresolved controller decisions and escalation evidence

1. **P6-T03 controller decision required:** whether `Event.process()`'s Android
   2 ms command deadline is an allowed presentation responsiveness policy.  It
   can postpone an EventProcessor command to a later outer update, so it is not
   safe to treat as generic off-world work without a proof of unchanged event
   ordering.  No implementation is proposed here.
2. **Device evidence gap:** P4-T03 profiling supporting tilemap pending work is
   host-only.  It justifies the accepted retained path but must not be reported
   as Android-device timing.
3. No ESC-02/04/05/07/09 condition was reached in this audit: the current
   source supplies a bounded capability design and the only unsafe candidate is
   explicitly left unmigrated for later controller review.
