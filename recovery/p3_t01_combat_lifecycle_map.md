# P3-T01 — Combat lifecycle reference map

## Scope, method, and fixed evidence

This is an audit only.  No production code, tests, Trace V1 normalisation,
fixtures, manifest, or project data was changed.

* **PC behavioural reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.
* **Current recovery audited:** `b6bec12ddef286fb82e67e55cd4b0edc5a720442`.
* **Primary evidence:** reference/current source and individual diffs for the
  staging cluster `78acb08a` through `fff0145d`; `29d1b65d`, `b323c01a`,
  `61d03cee`, `1b87bc85`; and Android music commit `9004c67b`.
* **Oracle:** immutable Trace V1 fixtures under
  `app/tests/fixtures/recovery_traces/v1/`.  In particular S5–S11, S12,
  S16, and S17 are semantic evidence.  They are not permission to alter the
  reference contract.

The relevant history is not treated as one feature.  Every row below maps the
individual operation, because the cluster mixes authoritative combat staging,
presentation staging, profiler-only scopes, and Android audio policy.

## Inheritance and caller graph

```text
event `combat` command / player targeting / AI / prep item use
    -> app.engine.combat.interaction.start_combat()
       -> game.state.change('combat')
       -> engage()
          position is None                  -> BaseCombat
          skip                              -> SimpleCombat
          multi-target/splash/no animation  -> MapCombat
          eligible battle animation          -> AnimationCombat
             arena flag -> same AnimationCombat(arena_combat=True)
       -> game.combat_instance.append(combat)
    -> general_states.CombatState.start()
       -> pop combat instance; current state is authoritative CombatState
       -> CombatState.update() -> combat.update()
       -> StateMachine repeat processing when update returns True

SimpleCombat
  ^
  |-- MapCombat                         (on-map visual combat)
  `-- BaseCombat                        (base/prep item use; no turn finalise)
        ^
        `-- AnimationCombat + MockCombat (animated on-map/arena combat)
```

There is no separate `ArenaCombat` class.  Arena is an `AnimationCombat`
instance constructed with `arena_combat=True`, uses `arena_*` states and the
arena panorama, and `CombatState.take_input('BACK')` calls the inherited
`SimpleCombat.stop_arena()` to set `CombatPhaseSolver.total_rounds = 0` for
the next solver boundary.  Events enter the same route through
`event_functions.start_combat(..., arena='arena' in flags)`.

`CombatPhaseSolver` owns phase selection and RNG consumption.  Its phase
states call `skill_system.start_sub_combat`, resolver processing, then
`skill_system.end_sub_combat`; controllers own when that work is invoked and
when its generated actions are committed.

## Common semantic vocabulary

* **Authoritative gameplay:** hooks, solver execution, combat RNG, queued
  actions once applied, uses/durability, death, EXP/WEXP/mana, events, state
  changes, and random-state recording.
* **Playback:** the `PlaybackBrush` lists record semantic results and also
  drive HUD, proc icons, battle animation, sounds, hit effects, and records.
  Producing a brush is often semantic evidence; consuming it for animation is
  presentation-only unless the consumer calls `_apply_actions`,
  `clean_up0`, or a hook.
* **Publication boundary:** `game.state.change('combat')` queues CombatState;
  it becomes live through normal StateMachine lifecycle.  While CombatState
  is current, `combat.update()` is observable each frame.  Therefore a new
  controller state is not automatically private merely because it is called
  a “staging” state.
* **RNG:** `SimpleCombat.start_combat` stores an initial combat RNG state;
  `CombatPhaseSolver.generate_roll` and `generate_crit_roll` consume
  `static_random.get_combat`; proc components consume the same primitive in
  `start_combat` and `start_sub_combat`; `end_combat` records the final state.
  Frame boundaries do not consume RNG by themselves, but expose the post-roll
  pre-action/pre-cleanup state to normal lifecycle work and can permit other
  code to consume RNG before the next controller phase.

## Ordered transaction maps

### SimpleCombat — skip/immediate mechanical path

| Boundary | PC reference | Current recovery | Observable risk |
|---|---|---|---|
| Construction | `_full_setup`; make solver/playback/actions; synchronously call `start_combat`, `start_event`, then loop every solver state: `do -> full_playback += -> _apply_actions -> setup_next_state`; controller returns only after solver is terminal. | `_full_setup`; make solver/playback/actions; set `state='init'`; no hook, event, solver, action, or RNG mutation yet. | The reference's full combat resolution is complete before the new controller can be observed. Current exposes an unresolved combat object. |
| Per solver phase | Already completed during construction. | one normal `update`: `solver.do -> append playback -> action.execute each action -> setup_next_state`; one phase per update. | Between updates a normal State/update/debugger can observe an intermediate resolved phase. |
| Cleanup | next updates: `clean_up0 -> clean_up1 -> clean_up2`. | additional `cleanup0 -> post_combat(clean_up1) -> exp_pause(clean_up2)` updates. | Same local cleanup order, but wider transaction publication. |

**Reference ordering:** action generation and `action.execute` are
synchronous with every solver transition.  `clean_up1` remains after all
solver actions.  This is an authoritative ordering contract, not a visual
optimisation.

**Current source/history:** `88ebd6a5` moved the solver loop from constructor
to `update`; `e5addcde` moved start hooks/event to `init`/`start_event`.
`RUNTIME_PROFILER.section` itself is observer-only; the frame boundaries are
not.

### MapCombat — standard on-map path

| Stage | PC reference order | Current recovery order | Category / result |
|---|---|---|---|
| Initial hook/event | `init`: remove highlights -> `start_combat` -> `start_event` -> init pause. | Same call order, wrapped in profiler scopes. | Authoritative hook/event; order matches. |
| Terminal check and cleanup0 | `begin_phase`: terminal check; if terminal immediately `clean_up0 -> exp_wait`. | `begin_phase` only selects `cleanup0`; next update calls `clean_up0 -> exp_wait`. | Authoritative lifecycle staging (`97c8c375`). |
| Solver and semantic playback | `begin_phase`: `solver.do -> full_playback +=`; empty phase advances immediately. | `begin_phase -> solve_phase`; next update does identical solver call. | Authoritative computation/RNG staging (`78acb08a`). |
| Visual preparation | In the same `begin_phase` call after solver: health bars, pre-proc icon setup, cursor/move-camera request, sprites and cast pose. | later `setup_phase_visuals`; profiler wraps health/proc construction. | Mixed: HUD/icons/sprites are presentation, but cursor state and queued move-camera lifecycle must not be treated as a safe semantic boundary without proof. |
| Playback/action commit | `anim`: `_handle_playback()` then `_apply_actions()` and derive HP-bar time in one update. | `anim`: `_handle_playback()`; later `apply_actions`: `_apply_actions()` then HP-bar time. | Gameplay action application is staged by `1e5275103`; not presentation-only. |
| End and cleanup | `end_phase` sets solver next state; then terminal path has `clean_up0`, `exp_wait(clean_up1)`, `post_combat(clean_up2)`. | Same local ordering, with explicit `cleanup0`; cleanup1/2 profiler scopes only. | cleanup0 boundary was added by `97c8c375`; later cleanup order remains source-identical. |

The map path is the clear P3-T02 surface: a solver result and its playback can
be exposed for an outer frame before action application.  Any later restore
must retain existing waits/animations and S5's natural EXP progression, but
must make the authoritative portions reference-shaped or otherwise prove no
unrelated lifecycle code observes the intermediate transaction.

### BaseCombat — base/prep item use

| Boundary | PC reference | Current recovery | Risk |
|---|---|---|---|
| Construction | initialise fields/solver; synchronously `start_combat`; synchronously `start_event`; `_counter=0`. | initialise fields/solver only; `state='init'`. | Hook-triggered actions/procs/RNG occur later. |
| First update(s) | first update loops all solver phases/actions synchronously, then returns false; later three cleanup updates. | `init -> start_event -> combat`; each combat phase runs on a separate update; then `cleanup0 -> cleanup1 -> cleanup2`. | Every solver phase is published between updates. |
| State-stack | `BaseCombat.handle_state_stack` is no-op and `finalizes_turn=False`. | Same override. | Preserve prep/base no-turn rule and promotion finalisation distinction. |

`0e2aa45a` staged the solver; `d1fd6887` staged start hooks/event.  This is a
P3-T03 surface because it is an inherited Base path, even though its solver
semantics match Simple's issue.  The local override of `cleanup_combat` is
critical: it calls both skill and item cleanup for attacker and distinct
defender, so an inheritance rewrite may not silently fall back to an
incomplete hook sequence.

### AnimationCombat — animated on-map path

The reference already has timed visual states.  Its important guarantee is
that each listed *same-update group* happens atomically relative to the next
normal lifecycle call.  Current recovery keeps the same individual calls but
inserts state boundaries from the staging cluster.

| Reference same-update group | Current split states | Classification |
|---|---|---|
| Constructor creates battle animations/partners, runs `initial_paint_setup`, `_set_stats`. | constructor sets `animation_setup` or `arena_animation_setup`; later `setup_battle_animations`; later `initial_paint_setup` and stats. | animation/resource preparation; may only remain progressive after proof it cannot affect gameplay ordering. (`6b1d5017`, `69e26e93`) |
| `init`: `start_combat`, sprites/cursor/camera request, `_set_stats`. | `init(start_combat) -> init_visuals -> init_stats`. | start hooks are authoritative; visual/stat split is P3-T03 review. (`0e162555`, `371c6cee`) |
| `arena_init`: start hooks, stats, pair animations, offsets. | `arena_init -> arena_visuals -> arena_pair_animations`. | Same issue on arena path. (`c9f598de`) |
| `init_pause`: `start_event(True)` then battle music state. | `init_pause -> start_event -> battle_music`. | event is authoritative; music is policy/presentation. (`fff0145d`, `3c61650d`) |
| battle music state selects music, checks transforms and initiates transforms. | `battle_music -> check_transform -> initiate_transform -> transform`. | music audio policy; transform rebuild must preserve order. (`fff0145d`, `b323c01a`) |
| transform completion rebuilds all relevant battle anims, re-pairs, then pre-proc. | `rebuild_transform_animations -> repair_transform_animations -> pre_proc`. | resource/presentation, but transform compatibility must be retained. |
| pre-proc readiness consumes full playback to select proc effects/icons. | `pre_proc -> setup_pre_proc`. | presentation consumes semantic proc playback; preserve ordered brushes. (`61d03cee`) |
| `begin_phase`: terminal check or `solver.do`, append playback, then effect/proc/animation setup. | `begin_phase -> solve_phase -> setup_phase_visuals -> setup_phase_followup`. | solver/RNG and generated actions are authoritative; effect/proc visual setup is presentation. (`1b87bc85`, `29d1b65d`, `fff0145d`) |
| Hit: `clean_up0`, set up hit effect; HP-ready branch resumes animation and dying animation. | `combat_hit -> setup_hit_effect`; `hp_change -> resume_hit_animation`. | cleanup/death boundary is authoritative; animation resume is presentation but must stay after committed hit actions. |
| End: focus EXP, move camera, `clean_up1`, then later transform revert; fade finish calls `finish -> clean_up2 -> end_skip` in one terminal update. | `end_combat_focus -> end_combat_camera`; `cleanup1`; rebuild/repair/initiate revert; `finish_combat -> cleanup2`. | `clean_up1/2` are authoritative; focus/camera/revert/fade are presentation/lifecycle adjacent. (`fff0145d`) |

Animation's `_apply_actions()` calls `action.do` then
`state_machine.setup_next_state`; it is reached by hit/start spell pathways,
not merely by the generic map controller.  It must therefore be audited as a
gameplay commit point even though its playback consumers also produce audio
and visuals.

### Arena wrapper/state path

Reference and current share the same object type and solver.  The differences
are staging of animation setup, start hooks, stats, pairing and finish steps,
not a separate arena rules engine.

1. `interaction.start_combat(..., arena=True)` queues `combat`, creates
   `AnimationCombat(..., arena_combat=True)`, and marks `combat.arena_combat`.
2. Reference starts at `arena_init`; current starts at
   `arena_animation_setup -> arena_paint_setup -> arena_init`.
3. Arena start then runs the same hook/solver/action contract as animation
   combat, but uses arena panorama/fade states and solver `total_rounds`.
4. BACK never injects a result: it only makes the next solver boundary
   terminal via `stop_arena`.
5. `clean_up2` sees `arena_combat`; dying units use the arena death path
   (`force_death`) rather than the ordinary `dying` state publication.

P3-T03 must keep those arena-specific termination/death semantics while
removing only unsafe intra-transaction staging.

## Function-level classification table

| File + symbol | Path(s) | Reference vs current order | Commit(s) | Category / invariant risk | Classification; later treatment | Dependencies and proof |
|---|---|---|---|---|---|---|
| `combat/interaction.py: engage, start_combat` | all | chooses controller, queues `combat`, then appends instance in both. | pre-reference; current target validation follow-up is independent. | state-machine publication; selection must stay stable. | KEEP-SHARED; retain. | `test_combat_interaction`; S5–S9 selection scenarios. |
| `combat/solver.py: CombatPhaseSolver.do, setup_next_state, process` | all | same solver logic; reference invokes it synchronously by path, current controller schedules calls. | staging consumers `78acb08a`, `88ebd6a5`, `0e2aa45a`, `1b87bc85`. | authoritative computation/RNG/actions. | RESTORE-PC-SEMANTICS at callers; retain solver. | S5–S9; S16; `test_combat_solver_missing_item`. |
| `combat/simple_combat.py: __init__, update` | Simple | reference executes hooks/event/all solver/action phases during construction; current `init/start_event/combat/cleanup0` spans updates. | `88ebd6a5`, `e5addcde`. | authoritative transaction publication. | RESTORE-PC-SEMANTICS; P3-T02 restore. | S6; S9; S10; S16. |
| `combat/simple_combat.py: start_combat` | Simple/Map inherited | same ordered initial RNG snapshot, pre/start skill/item dispatch; current merely delays it on Simple. | `e5addcde` for Simple scheduling. | authoritative hooks/RNG/proc playback. | RESTORE-PC-SEMANTICS scheduling; preserve body. | S6/S9 hook order, `test_recovery_trace`. |
| `combat/simple_combat.py: _apply_actions` | Simple/Map | same per-action `action.execute`; reference Simple reaches it before controller construction ends. | `88ebd6a5`. | gameplay action application. | RESTORE-PC-SEMANTICS; P3-T02. | S5–S10; final state/RNG traces. |
| `combat/simple_combat.py: clean_up1, cleanup_combat` | Simple/Map | same local order: skill/item cleanup -> unusable -> broken -> WEXP/mana/EXP -> BeforeCombatEnd. | inherited baseline. | authoritative cleanup; item cleanup must precede broken/unusable checks. | KEEP-CORRECTNESS-FIX; retain exact order. | S10 durability/broken; S11 promotion/EXP. |
| `combat/simple_combat.py: clean_up2, handle_state_stack, end_combat` | Simple/Map | same local order: back/HasAttacked/records/messages/state stack -> CombatEnd -> rewards/supports -> end hooks/post hooks/RNG record -> death. | scheduling altered by Simple staging only. | state publication, rewards, final RNG. | RESTORE-PC-SEMANTICS scheduling; retain bodies. | S5/S6/S10/S11/S18; S16. |
| `combat/map_combat.py: update` | Map | reference combines terminal cleanup0, solver, and generic playback/action pieces as listed above; current adds `cleanup0`, `solve_phase`, `setup_phase_visuals`, `apply_actions`. | `78acb08a`, `9be65ca5`, `1e527510`, `97c8c375`; profiler `85299feb`. | mixed authoritative/presentation; action split is unsafe until proved. | RESTORE-PC-SEMANTICS for solver/action/cleanup boundaries; P3-T02. | S5, S9, S10, S12, S13/S14 map state; S16. |
| `combat/base_combat.py: __init__, update` | Base | reference constructor starts hooks/event and first update solves all; current six staged authoritative states. | `0e2aa45a`, `d1fd6887`. | authoritative base/prep lifecycle. | RESTORE-PC-SEMANTICS; P3-T03. | S8, S10/S11; base/prep tests. |
| `combat/base_combat.py: cleanup_combat` | Base/Animation | explicit skill **and item** cleanup for attacker and distinct defender in both reference/current. | inherited necessary override. | durability/item-cleanup invariant. | KEEP-CORRECTNESS-FIX; retain. | S8/S10; direct source proof. |
| `combat/animation_combat.py: __init__, setup_battle_animations, initial_paint_setup` | Animation/Arena | reference performs construction setup synchronously; current postpones to two states. | `6b1d5017`, `69e26e93`. | animation/resource preparation. | REWRITE-PLATFORM; P3-T03 controller decision after non-semantic proof. | S7; `test_performance_profiler`; resource availability. |
| `combat/animation_combat.py: update` | Animation/Arena | reference groups multiple calls per visual frame; current splits hooks, event, solver, proc/effect, hit/death, end/cleanup/revert/final finish. | `29d1b65d`, `0e162555`, `371c6cee`, `c9f598de`, `b323c01a`, `61d03cee`, `1b87bc85`, `fff0145d`. | mixed; solver/actions/cleanup are authoritative. | RESTORE-PC-SEMANTICS for authoritative groups; presentation only may REWRITE-PLATFORM. P3-T03. | S7/S9/S10/S11/S16; performance tests. |
| `combat/animation_combat.py: _apply_actions, clean_up1, clean_up2` | Animation/Arena | same action/hook/cleanup bodies; current finish defers terminal cleanup by a state. | `fff0145d` terminal split. | gameplay action/state-stack/end hooks. | RESTORE-PC-SEMANTICS scheduling; P3-T03. | S7/S10/S11; lifecycle tests. |
| `combat/animation_combat.py: transform/revert states` | Animation/Arena | reference rebuilds/re-pairs in one readiness handling block; current has explicit rebuild/repair/initiate states. | `b323c01a`, `fff0145d`. | animation/resource preparation coupled to transform correctness. | REWRITE-PLATFORM; re-port only after transform order proof. | S7; `test_performance_profiler`. |
| `combat/animation_combat.py: start_battle_music, finish` | Animation/Arena | desktop reference uses battle fade in/back. Current Android branch streams battle track and restores current/stream preview selection; desktop fallback stays fade behavior. | `9004c67b`; setup `3c61650d`. | audio/platform policy, no solver/hook/action/RNG calls. | KEEP-PLATFORM; retain. | `test_performance_profiler` streamed-music tests; S17 observer equivalence. |
| `combat/interaction.py` + `general_states.py: CombatState` | all | controller instance is popped and updated under CombatState; BACK only affects arena round cap. | shared. | lifecycle publication/arena contract. | KEEP-SHARED; retain. | S5–S10; event tests; arena source path. |
| `driver.py: update_game_state_for_frame` | all | current fast-forward gives first update input, extra updates `[]`, consumes transient input and keeps StateMachine lifecycle ordering. | later independent fast-forward work. | state scheduling; must not replay input edge. | KEEP-CORRECTNESS-FIX; P3-T04 preserve. | S16 INV-06; `test_fast_forward`. |
| `performance.py: RuntimeProfiler.section` / debugger observer paths | all | disabled by default; sections record timing only when enabled/main-thread; no combat mutation in scope wrapper. | `7735ca29`, `d2bbd026` and combat scope commits. | profiling/observer only. | KEEP-SHARED; retain. | S17 INV-07; `test_performance_profiler`, runtime debugger tests. |

## Hook-order matrix

This is the actual body order, common to reference/current except when the
current controller delays the entire named phase.  “Skill” and “item” mean the
generated dispatchers iterate components in stored order; skill dispatch also
evaluates conditional and unconditional hooks as implemented.

| Hook / point | Ordered participants and dispatch | RNG/action/playback consequence |
|---|---|---|
| `pre_combat` | attacker skill; attacker partner skill; each unique defender skill then defender partner skill; all splash skill. `BaseCombat` has attacker, distinct defender, then partners. No item pre hook. | Components may add pre-proc playback; no generic action application here. |
| `start_combat` | attacker skill -> attacker item; attacker partner skill only in Simple/Map, skill+item in Base; each unique defender skill -> item if defender item -> defender partner skill; splash skill. | Pre-proc components can call `static_random.get_combat`, directly `action.do(AddSkill)`, and append pre-proc playback. |
| `start_event` | `game.events.trigger(CombatStart(..., full_animation))` after start hooks; `True` for Animation, false/default elsewhere. | State/event publication; may queue event state. |
| `start_sub_combat` | every solver attacker/defender/partner phase calls attacker attack-mode skill dispatch then defender defense-mode skill dispatch before `solver.process`. | Attack/defense procs roll combat RNG, directly add/remove temporary skills, append `attack_proc`/`defense_proc`; action list also collects strike effects. |
| strike resolution | solver rolls hit (one/two/three `get_combat` per RNG mode) and crit (`get_combat`), then item hit/miss/crit and skill after-strike/take-strike dispatch. | Generates action list and semantic playback marks/damage. |
| `end_sub_combat` | defending-side temporary proc cleanup then attacking-side cleanup after each phase. | Trigger charge/remove temporary proc skills; must remain after that phase's strike. |
| `cleanup_combat` | attacker skill -> item; each unique defender skill -> item when it has one; splash skill. `BaseCombat` explicitly has attacker skill+item and distinct defender skill+item. | Must precede unusable/broken checks. |
| `end_combat` | attacker skill+item; partners (path-specific); defenders skill+item; splash skill; deactivate combat arts. | Ends long-lived combat effects. |
| `post_combat` | attacker skill; partners/defenders/splash skills as path-specific; then clear strike partners and record initial/final combat RNG with `RecordRandomState`. | Final semantic cleanup and RNG transaction record. |

`item_system` owns `start_combat`, `cleanup_combat`, and `end_combat` only;
the required reference contract does not contain a generic item
`pre_combat`, `start_sub_combat`, or `post_combat` hook.  This distinction
must be preserved when re-porting inherited paths.

## Action, playback, and RNG ordering matrix

| Operation | Reference ordering | Current difference | Required treatment |
|---|---|---|---|
| Initial RNG snapshot | first operation in `start_combat` before pre/start hook dispatch. | same call body; delayed on Simple/Base/Animation states. | Preserve exact placement. |
| Pre-combat proc roll | component `start_combat`, before CombatStart event. | same component/order; can occur frames later. | No direct seed/RNG workaround; S9 is the proof fixture. |
| Sub-combat proc roll | `start_sub_combat` immediately before phase resolver. | same solver call; current may put a frame before/after solver depending path. | Keep relative hook/roll/solver order. |
| Hit/crit roll | `CombatPhaseSolver.process`: hit roll, then crit roll only on a hit when eligible. | same primitive and mode logic. | Retain solver; change caller scheduling only with trace proof. |
| Action generation | solver/item/skill append actions while producing phase playback. | same generation. | Authoritative but not yet committed. |
| Action application | Simple/reference: immediately after each solver result; Map/reference: in `anim` with playback; Animation: `_apply_actions` before next solver state. | Simple/Base phase frames; Map separates `_handle_playback` from `apply_actions`; Animation inherited/direct action points remain stateful. | P3-T02 for Simple/Map; P3-T03 for Base/Animation. |
| Playback consumption | full playback retains ordered semantic brushes; per-phase playback drives effects/HUD/audio. | current can expose full/per-phase brush sequence at added state boundaries. | Preserve brush order/count; visual consumption can be progressive only after action/RNG isolation proof. |
| Final RNG snapshot | after end/post hooks and partner clearing in `end_combat`; record action follows. | same body; later frame in staged paths. | Preserve final position and S5–S10/S16 trace equality. |

## Cleanup, state-stack, and end-combat matrix

| Ordered step | Exact behaviour | Invariant / proof |
|---|---|---|
| 1. `clean_up0` | mark `should_die` for HP <= 0, then emit `CombatDeath` trigger with killer inferred from ordered marks. Animation may delay visual death but still uses this semantic decision. | Must be after all relevant hit actions. S5/S7/S18 lifecycle evidence. |
| 2. `clean_up1` | restore non-dying sprites; `cleanup_combat`; `handle_unusable_items`; `handle_broken_items`; WEXP; mana; EXP queue/state; `BeforeCombatEnd`. | Accepted root invariant: item cleanup precedes unusable/broken. S10 and S11 are immutable evidence. |
| 3. EXP / promotion | player EXP or mana queues `game.exp_instance` and `game.state.change('exp')`; normal state machine then owns EXP/growth/promotion choice. | Do not skip, mutate EXP, or bypass promotion inputs. S5/S11. |
| 4. `clean_up2` | `game.state.back`; HasAttacked; records/messages; `handle_state_stack`; `CombatEnd`; item gains; supports; `end_combat`; `handle_death`; built guard. Animation also resets battle anim unit state after this. | State-stack action remains before CombatEnd/end hooks. |
| 5. state-stack policy | event: no-op; AI: wait unless Canto; dying: clear/free/wait; player: menu, Canto move, or clear/free/wait. Base: no-op. Animation delegates to MapCombat. | Preserve finalizes-turn distinction, Canto, alerts, and promotion cancellation. |
| 6. terminal death policy | ordinary combat queues `dying`; arena force-deaths after hooks. | Arena must not be flattened into ordinary map death. |

## P3-T02 candidates — Simple/Map only

1. Restore Simple's reference synchronous construction transaction:
   start hooks -> CombatStart -> every solver phase -> append playback ->
   apply actions -> solver advance, before its resolved controller is normally
   observable.  Retain profiler scopes only as observers around the restored
   work.
2. Restore Map's authoritative groupings: terminal check with `clean_up0`,
   solver invocation with its immediate required semantic follow-up, and
   playback/action application as one logical transaction.  Do not equate
   existing visual waits with permission to publish a solver result whose
   actions are not yet applied.
3. Preserve `clean_up1` and `clean_up2` bodies/order exactly, including item
   cleanup, item use/durability, EXP queue, state stack, `CombatEnd`, rewards,
   end/post hooks, and final RNG recording.
4. Prove S5, S6, S9, S10, S12 and S16 against immutable fixtures before
   accepting any re-port.  S11 is additionally required when EXP/promotion
   state timing changes.

## P3-T03 candidates — Base/Animation/Arena and presentation/resource/audio

1. Re-port Base's synchronous reference hook/event and all-solver first
   update ordering while retaining its no-turn `handle_state_stack` and
   explicit item cleanup override.
2. Reconcile Animation/Arena authoritative states: start hooks, CombatStart,
   solver/action application, clean_up0/1/2, state stack, and terminal finish
   must not be separated in a way that changes logical ordering.
3. Evaluate animation load, initial paint, UI stats, transform rebuild/revert,
   proc icon/effect setup, focus/camera, and fade steps individually as
   progressive presentation/resource work.  Keep a step progressive only if
   it does not change hooks, RNG, actions, state publication, cleanup order,
   or logical trace.
4. Retain Android battle-music streaming from `9004c67b` as
   `KEEP-PLATFORM`: its source touches sound-thread selection/start/restore,
   not solver/hook/action/RNG/state-stack code.  Verify S17 idle observer
   equivalence and its direct music tests after any animation work.
5. Preserve arena wrapper semantics: one AnimationCombat class, round cap,
   real BACK behaviour, arena visual path, and arena-specific forced death.

## P3-T04 preservation list

* `cleanup_combat` item hooks, especially `BaseCombat.cleanup_combat`.
* Item use costs, unusable/broken checks, alerts, WEXP/mana/EXP/rewards and
  their cleanup ordering (S10/S11).
* Promotion/class-change queue and cancellation/finalises-turn distinction
  (S11; Base must not consume a tactical map turn).
* Initial/final combat RNG snapshots, real pre/sub-combat procs, ordered
  playback and action commits (S5–S10, particularly S9).
* Aura/FOW-adjacent side effects and terminal control state after combat
  (S12 and S13/S14).
* Fast-forward input-edge/StateMachine lifecycle policy, including no replay
  of raw input over extra updates (S16 and `test_fast_forward`).
* Debugger/profiler observer-only behaviour (S17); profiler worker-scope
  isolation from `d2bbd026` must not be undone.
* Transform/revert pairing and resource availability; Android UI render cache
  and streamed battle music must remain platform policies, not gameplay
  scheduling mechanisms.
* `CombatPhaseSolver.process` no-item scripted-phase no-op correctness from
  its independent fix; do not revert it while restoring scheduling.

## Unresolved controller decisions and escalation evidence

No escalation condition was reached during this audit.

* **No reference ambiguity:** source establishes reference order for all four
  controllers and arena is a flag path, not a missing class.
* **No inheritance invariant conflict found:** Base explicitly preserves item
  cleanup; Animation delegates map state-stack/support behaviour while setting
  `finalizes_turn=True`.
* **Controller decision needed before P3-T02/P3-T03:** choose the bounded
  implementation boundary for re-porting authoritative groups while retaining
  genuinely presentation-only progressive work.  The report intentionally
  does not choose or implement that architecture.
* **Risks to test, not assumptions:** whether a particular visual setup queues
  a lifecycle state (for example move-camera) that can observe a solver result;
  transform resource work; and the interaction between terminal animation
  fade and `clean_up2`.  These are P3-T03 proof obligations, not grounds to
  weaken Trace V1 or alter immutable goldens.
