# P3-T04 combat feature/fix preservation sweep

**Scope.** This is a preservation audit against PC reference
`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`, after accepted P3-T03
`3ab40895ef7170e01e55dc4f1bf2b63889383832`.  The immutable Trace V1 fixtures
are the behavioral oracle.  No fixture, comparator, project data, solver, RNG
formula, or production file was changed by this task.

## Result

Every required recovery capture matched its committed PC-reference Trace V1
golden: S5, S6, S7, S8, S9, S10, S11, S12, and S16.  S17 passed the approved
hybrid contract: recovery-disabled matched the PC disabled baseline, and both
recovery debugger-idle and profiler-idle matched recovery-disabled.  The
accepted P3-T02/P3-T03 transaction repairs therefore preserve the audited
later correctness/platform work.  There is no demonstrated bounded regression
to re-port in P3-T04.

## Classification matrix

| Area | Current file + symbol | Reference/current comparison and provenance | Classification | Invariant/evidence | Production treatment |
| --- | --- | --- | --- | --- | --- |
| Cleanup transaction | `combat/simple_combat.py: SimpleCombat.clean_up1`, `clean_up2`, `cleanup_combat`, `end_combat` | Current retains the PC cleanup groups; P3-T02 (`c20b9e02f`) restored Simple/Map transaction grouping. | ALREADY-PRESERVED | S5, S6, S9, S10; `test_combat_transaction_order` | None. |
| Map cleanup transaction | `combat/map_combat.py: MapCombat.update` (`begin_phase`, `anim`, `exp_wait`, `post_combat`) | Current terminal `clean_up0`, playback/action commit, `clean_up1`, and `clean_up2` grouping matches the accepted PC-shaped map lifecycle. | ALREADY-PRESERVED | S5; `test_combat_transaction_order` | None. |
| Base/animation cleanup | `combat/base_combat.py: BaseCombat.cleanup_combat`, `handle_state_stack`; `combat/animation_combat.py: AnimationCombat.update` | P3-T03 (`3ab40895e`) restored Base/Animation ordering without changing solver/action semantics. | ALREADY-PRESERVED | S7, S8; `test_animation_combat_transaction_order` | None. |
| Item use/broken handling | `item_components/usable_components.py: Uses.cleanup_combat`, `Uses.on_broken`, `ChapterUses.cleanup_combat` | `7006c2d43` is an independent correctness fix: one-loss-per-combat is committed in cleanup before broken/unusable checks; it must not be reverted to PC-era ordering. | KEEP-CORRECTNESS-FIX | S10 exact golden; Simple cleanup calls item hooks before unusable/broken handlers. | Retain. |
| Conditional combat cache | `skill_components/conditional_components.py: CombatCondition.pre_combat`; `utils/ltcache.py: ltcached`; `combat_calcs.py: compute_advantage` | `94fbeae8d` invalidates LTCache after publishing `_condition`, preventing a first-hit stale weapon-triangle/override result. | KEEP-CORRECTNESS-FIX | `test_item_skill_components.test_combat_condition_invalidates_cache_after_publishing`; S5/S9. | Retain targeted invalidation; no broad cache clear. |
| Promotion/class change | `combat/simple_combat.py: handle_exp`; `promotion.py: PromotionChoiceState._proceed`, `take_input`; `PromotionState.start`; `BaseCombat.finalizes_turn` | `98b1b24aa` preserves cancellable map choice: on-map confirm sets `_promo_finalize_turn`; base/prep remains no-turn (`BaseCombat.finalizes_turn = False`); cancel returns state and reverses use. | KEEP-CORRECTNESS-FIX | S11 exact golden; `test_animation_combat_transaction_order.test_base_combat_remains_no_turn`; direct source audit of confirm/cancel path. | Retain. |
| Aura serialization/rebuild/teardown | `objects/unit.py: UnitObject.save`, `restore`; `aura_funcs.py: repopulate_aura`, `remove_all_auras`, `release_aura` | `a961ee878` is a later correctness fix. AURA children are excluded from serialized skills, rebuilt from live board, and removed by stored source rather than fragile board lookup. | KEEP-CORRECTNESS-FIX | S12 exact golden at propagated/load/teardown checkpoints; `test_add_remove_skills` orphan and source-selective teardown tests. | Retain. |
| Fast-forward | `driver.py: update_game_state`, `update_game_state_for_frame`; `input_manager.py: consume_transient_input` | Later independent input/timing work retains first-substep edges, held state, repeat-chain suppression, and presentation fences. | KEEP-CORRECTNESS-FIX | S16 PC OFF == recovery OFF; recovery ON == OFF under INV-06; `test_fast_forward`. | Retain. |
| Debugger/profiler | `runtime_debugger.py: RuntimeDebugger`; `performance.py: RuntimeProfiler`; instrumentation in combat/driver | `7735ca29` profiler and debugger/service additions are observer-only on their idle paths. | KEEP-PLATFORM | S17 disabled/debugger-idle/profiler-idle equality; `test_runtime_debugger`, `test_performance_profiler`. | Retain. |
| Android music/resource/UI policy | `combat/animation_combat.py: _AndroidStreamedBattleMusic`, `start_battle_music`, `finish`, Android UI cache helpers; `sound.py: play_streamed_music` | `9004c67bd` / `0eef3a5d2` retain Android streaming and map-track restoration; UI caches are presentation-only. Worker/resource policy does not own authoritative combat mutation. | KEEP-PLATFORM | `test_performance_profiler.test_android_streamed_battle_music_restores_cached_map_track`; S7/S17; no Trace V1 difference. | Retain; later render/performance work only. |

No finding is classified `BOUNDED REGRESSION - RE-PORT REQUIRED`.

## Required cleanup order

The shared mechanical contract remains:

1. `cleanup_combat`: skill cleanup then item cleanup for every relevant actor/item.
2. `handle_unusable_items`, then `handle_broken_items`.
3. WEXP, mana, and EXP/promotion scheduling.
4. `BeforeCombatEnd`.
5. `clean_up2`: state-stack handling, `CombatEnd`, item/reward/support work,
   `end_combat`, then death handling.

`end_combat` owns end/post hooks and records the final combat RNG state after
those hooks.  Map combat reaches these groups through its normal EXP/promotion
states; Base retains the shared cleanup but deliberately has no tactical
state-stack finalization; Animation retains its visual waits and reaches the
same cleanup groups only at its natural terminal states.  The order is covered
by `test_combat_transaction_order`, `test_animation_combat_transaction_order`,
and S5/S6/S7/S8/S9/S10.

## Durability and item cleanup

`Uses` and `ChapterUses` mark one-loss-per-combat during hit/miss processing,
then commit exactly one `SetObjData` plus one item-use record in
`cleanup_combat`.  That commit happens before broken/unusable handling, so a
last use can fire cleanup hooks before removal/unequip/alert behavior.  The
one-loss helper also resets `_did_something`, preventing leakage to a later
combat.  S10 matches the immutable fixture
`10_item_durability_and_broken.jsonl` (SHA-256
`CF6CAF5FC6D1EC365BEE8982925F3EAB583840889BA768303C27B0A8B07EC3D1`).

## Promotion and class change

Normal map-origin choice marks `_promo_finalize_turn` only on confirmed
promotion/class-change; `PromotionState.start` consumes it once.  The choice
is intentionally cancellable: `BACK` pops to the prior state, emits
`HasNotAttacked`, and reverses the item use.  Base/prep remains outside a
tactical turn (`BaseCombat.finalizes_turn = False`) and therefore must not
inherit map finalization.  S11 matches
`11_promotion_class_change.jsonl` (SHA-256
`D6D02B66537E97A422C6BB86F5E97234E181532102D941446F3847572D3BA0B2`).

## Cache invalidation audit

The only audited mutable combat-condition cache state is
`CombatCondition._condition`.  `pre_combat` invalidates before evaluation and
again after publishing the new value; the latter is necessary because
evaluation can re-enter cached condition consumers before the new value is
visible.  `ltcache.ltcached` clears per-state cached values when the game state
token changes.  No broad cache clearing is present or required.

## Aura audit

Aura child skills (`SourceType.AURA`) are explicitly nonserialized in
`UnitObject.save` and excluded while restoring serialized skills.  Board aura
connections are rebuilt after authoritative unit arrival.  `remove_all_auras`
walks the unit's stored aura sources, so it removes stale/orphan children even
if the board no longer describes them, while leaving non-aura sources intact.
S12 matches all three immutable checkpoints and fixture SHA-256
`6A8EC39E493B984EC87D1A1EC03FC53C06A6A92D8DA8650E33AD0513229E3C43`.

## INV-06 and INV-07 observer/platform audit

Fast-forward advances normal simulation with a fixed bounded step, consumes
transient edges after the first update, preserves held input, and keeps
interactive states behind `blocks_fast_forward`.  S16 is PC-reference OFF and
recovery ON equals recovery OFF logically; its PC fixture SHA-256 is
`8B12BF2F43ADDC6777802451C20F34172A07C1BFDAE838ACEB0AE5C2B9E3EAEC`.

S17 confirms observer idleness: recovery-disabled matches the PC disabled
baseline and recovery debugger-idle/profiler-idle each match recovery-disabled.
Its PC fixture SHA-256 is
`20A582F6EEE02DC5A00DDEC4DF3D87ED80594DEE27ED444C8C7FF7A1926100F0`.
Profiler timing/log/buffer data and debugger presentation are diagnostic, not
logical Trace V1 inputs.

Android streamed battle music, resource preparation, and animation UI caches
remain outside authoritative combat ordering.  The streaming path records the
return map track and restores it in `AnimationCombat.finish`; it does not alter
solver, action, hook, RNG, or cleanup ownership.  This is retained platform
policy, not a desktop semantic substitute.

## Test/evidence matrix

| Evidence | Result | What it proves |
| --- | --- | --- |
| Recovery captures vs immutable goldens: S5-S12, S16 | PASS | Map/Simple/Animation/Base transactions, hook/RNG/action results, durability, promotion, aura, fast-forward logical behavior. |
| S17 disabled vs PC; debugger-idle/profiler-idle vs disabled | PASS | INV-07 observer paths do not alter logical trace/RNG/final state. |
| `app.tests.test_combat_transaction_order` | PASS | Simple/Map grouping, action commit before solver advance, visual waits retained. |
| `app.tests.test_animation_combat_transaction_order` | PASS | Base item+skill cleanup hooks, no-turn Base policy, Animation visual/cleanup groups. |
| `app.tests.test_item_skill_components` | PASS | Post-publication combat-condition cache invalidation. |
| `app.tests.test_add_remove_skills` | PASS | Aura orphan teardown and source isolation. |
| `app.tests.test_fast_forward` | PASS | Input-edge/repeat/held-input and fast-forward schedule invariants. |
| `app.tests.test_runtime_debugger`, `app.tests.test_performance_profiler` | PASS | Observer behavior and Android streamed-music restoration. |

## P3-T04 disposition

- Production changes: none; no bounded regression was demonstrated.
- Test changes: none; existing focused tests plus immutable scenario captures
  cover each preservation finding.  A proposed isolated promotion test was not
  retained because importing the UI-heavy promotion module directly triggers an
  unrelated pre-existing circular import in a fresh process; S11 and accepted
  lifecycle coverage remain the non-invasive proof.
- Out of scope/later phase: performance-only Android UI/resource scheduling
  and any non-idle debugger command semantics.  Neither is an authoritative
  combat transaction change in this task.
- Escalation: none.  No reference ambiguity, Trace V1 divergence, invariant
  failure, or need for cross-cutting architecture was encountered.
