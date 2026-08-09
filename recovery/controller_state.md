# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 6**
- Phase 1 harness / immutable Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- Phase 5 save/load/restart consolidation: **ACCEPTED**
- P6-T01 runtime capability audit/design: **ACCEPTED** at `017e73c3164a56712a823016a7cfe642c75bbd17`
- Active task: **P6-T02 only — Migrate Android audio/resource policy**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P6-T03 and Phase 7+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller review required before P6-T03 despite the static plan's no-gate marker on P6-T02; executor must not self-advance.

## P6-T01 acceptance record

The controller accepts `017e73c3164a56712a823016a7cfe642c75bbd17` (`docs(recovery): map runtime capabilities`).

Accepted evidence:

- it is one direct descendant of Phase-6 authorization commit `12319eba16f7b6fb2f3a776cda81bdeef8d91cc4`;
- the commit adds only `recovery/p6_t01_runtime_capability_map.md`; no production, test behavior, project data, Trace V1, comparator, manifest, or golden fixture changed;
- the report inventories current Android/runtime branches and separates backend/presentation policy from authoritative gameplay semantics;
- combat solver/actions/RNG/hooks/cleanup, Event semantics, state/load publication, save/restart semantics, InputManager action edges, and live tilemap commit are explicitly non-forkable;
- Phase-4 pending tilemap preparation is the only currently approved progressive off-world work-budget seam; its Event-local barrier and synchronous live commit remain semantic proof machinery, not generic scheduling policy;
- P5 `SaveLoadJob` remains a protected canonical-load consumer, not a generic resource-preparation capability;
- filesystem/JNI/input/debugger/profiler branches are left direct where they are already narrow and platform-local;
- no giant `PlatformServices`/service-locator abstraction is proposed;
- immutable S5/S12/S13/S14/S16/S17/S18 and focused Android/audio/render/load/restart/tilemap/debugger/profiler tests were reported PASS with unchanged goldens.

## Controller refinement of the P6-T01 design

### Existing sound abstraction must be reused

`app/engine/sound.py` already defines the engine-facing `SoundController` abstraction and exposes legacy fade/battle playback, streamed playback/preview, preload, flush, and stop operations.

P6-T02 must **not** create a second full audio controller or duplicate those backend responsibilities in a parallel service object.

An approved audio capability may be one of the following bounded shapes:

- a very small policy object/function owned by the sound subsystem that decides whether to attempt the existing streamed path and preserves the existing legacy fallback; or
- a narrow addition to the existing sound subsystem/controller API that removes platform branching from gameplay callers without changing semantic music selection.

Do not move item/skill/level music selection, combat state transitions, title transitions, game-over semantics, or Sound Room state ordering into the policy.

### Resource/preload boundary

P6-T02 may isolate the existing platform difference in level-song preload/flush and other source-proven immutable/presentation preparation.

Workers may operate only on audio/resource/presentation data already proven thread-safe. They may not receive or mutate `GameState`, Event, solver, action state, save payload publication, runtime registries, units, board, or state machine.

Do not implement a speculative generic `PresentationRequest -> PreparedPresentation` framework merely because the audit sketched one. Add only APIs with concrete current callers and a direct platform branch that the migration actually removes.

### Render/cache boundary

P6-T02 may introduce a narrow feature-policy query for proven presentation-only cache owners when doing so actually eliminates repeated Android render-policy checks.

Safe initial candidates are owner-local caches whose keys/invalidation remain local: title/menu/settings/highlight/info/unit-menu presentation caches.

Do **not** migrate timing-sensitive battle-animation / animation-combat / mock-combat branches that suppress or advance visual counters/waits unless focused tests first prove visual lifecycle equivalence. Default P6-T02 scope is to leave those direct.

Do not centralize cache keys, cache contents, surfaces, or invalidation into a global cache service.

### Event.process Android 2 ms deadline — unresolved and excluded

Current `Event.process()` applies an Android render-optimization deadline and may return between EventProcessor commands; `_update_state()` observes `_android_process_yielded` and stops processing for that outer update.

This is potentially gameplay/event-order observable and is classified:

`GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK / NEEDS-CONTROLLER-DECISION`

P6-T02 must not touch, wrap, rename, or migrate this deadline.

It is **not** an approved CAP-WORK-BUDGET seam. P6-T03 remains blocked pending controller review after P6-T02 and will require explicit proof/decision before this behavior can be retained, removed, or migrated.

## P6-T02 — authorized implementation scope

Execute **P6-T02 only** using **GPT-5.6 Terra / medium**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Mandatory design input:

`recovery/p6_t01_runtime_capability_map.md`

### Goal

Implement the approved narrow audio/resource policy boundary and migrate only source-proven presentation/resource callers so platform choice no longer leaks through gameplay-critical callers where a bounded backend policy suffices.

Preserve exact gameplay ordering and all accepted Phase-2 through Phase-5 transaction contracts.

### Authorized migration cluster A — audio backend policy

Migrate physical playback/backend selection for current callers such as:

- `AnimationCombat.start_battle_music` / stream cleanup in finish paths;
- `TitleStartState._start_title_music`;
- `GameOverState.start`;
- `BaseSoundRoomState` preview physical playback;
- closely equivalent current physical playback callers proven by source.

Required contract:

- caller continues to select the semantic music NID and decide *when* music transition occurs;
- policy decides only whether the existing streamed Android backend is attempted;
- failed stream attempt preserves the caller's existing cached/legacy fallback;
- desktop continues the existing legacy/cached path;
- no policy call advances combat/Event/state lifecycle;
- no change to battle-music state timing or combat cleanup.

Prefer reuse/extension of the existing `SoundController` boundary over a parallel controller abstraction.

### Authorized migration cluster B — level audio/resource preload

Migrate only the existing platform policy around song cache flush/preload in `LoadingState` and closely related source-proven audio resource preparation.

Preserve:

- the current level-song set selection in the caller;
- loading-state completion semantics;
- current desktop behavior;
- Android ability to perform expensive proven audio cache release/preload off the gameplay thread where currently safe;
- no worker access to gameplay objects/registries/state machine.

Thread failure must remain presentation/resource failure; it must not publish partial gameplay state.

### Authorized migration cluster C — bounded render/cache query

Optional and bounded: migrate only presentation-only cache-policy checks where owner-local invalidation is already proven and the change is mechanical.

Initial permitted owners:

- title presentation caches/particles;
- menu/settings presentation caches;
- `HighlightController`;
- info-menu/unit-menu bounded presentation caches.

The policy may answer only enablement/capacity. Cache contents, keys, invalidation, surface ownership, and logical menu/state behavior remain in each owner.

Do not migrate animation/combat visual countdown branches in this task unless the executor first proves exact lifecycle equivalence with focused tests and the change remains local. If uncertain, leave them direct and report them.

### Direct branches that must remain direct in P6-T02

Do not migrate or redesign:

- `Event.process()` Android 2 ms deadline;
- Phase-4 `_android_tilemap_pending` Event barrier;
- `TilemapChangeJob` 4 ms pending-build budget;
- P5 `SaveLoadJob` / title/in-chapter load routing;
- raw touch/InputManager mapping;
- Android debugger JNI/touch ownership;
- profiler enablement/isolation;
- import-time sprite/bootstrap environment handling;
- filesystem/log path helpers;
- state-machine Android UI registrations.

### Dependency rules

Allowed:

`gameplay/presentation caller -> narrow policy -> android_runtime + existing sound/render/resource primitives`

Forbidden:

`gameplay -> capability -> game_state/combat/Event/save/state_machine/gameplay`

Capability modules must remain importable without PyQt5 and must not create circular ownership.

### Tests required

Prove at minimum:

1. desktop audio caller follows the same existing legacy/cached backend sequence;
2. Android stream success uses the existing streaming backend exactly once and does not also invoke legacy fallback;
3. Android stream failure invokes the same existing legacy fallback exactly once;
4. battle semantic music selection and `battle_music` state ordering are unchanged;
5. combat finish/stream cleanup does not change cleanup/state-stack ordering;
6. title and game-over state transitions are unchanged by backend choice;
7. Sound Room request/presentation ordering is unchanged;
8. level-song selection is unchanged;
9. desktop/Android preload policy performs no gameplay mutation from worker code;
10. loading-state completion still waits for the same required resource work;
11. any migrated render-cache owner renders equivalent logical output on cache hit/miss and retains owner-local invalidation;
12. capability modules do not import `game_state`, combat, Event, save, debugger controller, or state machine;
13. `Event.process()` deadline source remains untouched;
14. P4 tilemap barrier/budget source remains untouched;
15. P5 canonical load/restart tests remain green.

Run focused existing tests for:

- sound/streamed music/Sound Room;
- AnimationCombat music lifecycle;
- title/game-over music;
- loading-state audio preload;
- migrated UI/render caches, if any;
- Android runtime helpers;
- debugger/profiler observer behavior;
- canonical load/restart;
- tilemap pending barrier.

Immutable Trace V1 proof at minimum:

- S5
- S7
- S8
- S16
- S17 disabled/debugger-idle/profiler-idle
- S18

Run recovery trace/lifecycle/golden integrity.

Run broader unittest discovery and report known baseline failures/native Windows termination without repairing unrelated issues.

Then run:

- `python -m compileall -q app`
- `git diff --check`
- commit bounded P6-T02 production/tests
- `git show --check`
- `git status --short`

### Explicitly out of scope

Do not:

- begin P6-T03;
- alter Event command scheduling;
- migrate work-budget scheduling;
- create a giant platform service locator;
- create a second full audio controller;
- move semantic music selection into backend policy;
- alter combat/state/Event/save/restart semantics;
- weaken P4 atomic tilemap barrier;
- weaken P5 canonical load/restart contracts;
- modify Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / medium**.
Escalation target: **GPT-5.6 Sol / high**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** a bounded caller migration unexpectedly requires gameplay architecture changes;
- **ESC-04** two incompatible semantic fallback/order designs are both plausible;
- **ESC-05** an invariant or immutable trace cannot be preserved;
- **ESC-07** platform policy cannot be isolated without changing authoritative gameplay lifecycle;
- **ESC-08** repeated bounded migration/test failure;
- **ESC-09** implementation requires a new cross-cutting platform/service architecture.

Do not self-escalate.

## Gate status

**P6-T01 is ACCEPTED. P6-T02 is the only authorized task. P6-T03 and Phase 7+ remain blocked pending controller review.**
