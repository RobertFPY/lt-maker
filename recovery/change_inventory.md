# P0-T02 Post-reference Semantic Change Inventory

Date: 2026-08-08 (Asia/Ho_Chi_Minh)
Task: P0-T02 — Build post-reference semantic change inventory
Execution: GPT-5.6 Terra / medium
Escalation target: GPT-5.6 Sol / high (not authorized or used)

## Scope and method

Comparison range:

```text
PC reference:    9314f54b49f4552b5a3d023b4da0012ce7dfbc89
Recovery start:  0821182a717de2baaf52a699ee325241ffaddd03
Audit HEAD:      0521ba8d14b758adb23b30b8d5e4f2e21390131e
```

P0-T01 is accepted at `2f43d80ece1e3a3db9d9de18ac85c458a5b25012`.
This document is a source/history audit only. It makes no production,
test, project-content, or baseline-failure changes.

Classification labels are defined by `plan.md` Section 4. `NEEDS-CONTROLLER-
DECISION` means the file has an identified semantic boundary but this task
does not have enough approved evidence to choose its final treatment.

## Commit-level inventory

| Commit/range | Finding | Preliminary classification |
|---|---|---|
| `52bd0403` | Mixed Android/runtime import: 74 engine files, 10,008 additions, 1,429 deletions. It combines Android runtime, debugger, profiler, fast-forward, render/cache, save/load, and general gameplay changes. It cannot be reverted or retained as one unit. | `NEEDS-CONTROLLER-DECISION` per sub-change |
| `7735ca29`, `eda4f2d9`, `85299feb`, `7f437256`, `6abfdfc9` | Hierarchical and localized runtime profiling. | `KEEP-SHARED` |
| `6631e736`, `d2bbd026` | Android debugger panel caching/release disable and profiler worker-scope isolation. | `KEEP-PLATFORM` / `KEEP-CORRECTNESS-FIX` |
| `97c58a63` | Difficulty setup correctness fix, outside the changed-engine-file list but protected by INV-08. | `KEEP-CORRECTNESS-FIX` |
| `cdd4be2a`, `6b96e2f1`, `cd8607b6` | Yieldable board rebuild, queued tilemap change, and incremental add-group placement. | `REWRITE-PLATFORM` |
| `78acb08a..fff0145d` | Explicit staging of map, simple, base, animation, and arena combat phases. | `RESTORE-PC-SEMANTICS` |
| `390638ac`, `6bd9da4b`, `8306e1a9` | Camera/map guards and deferred saved-state installation introduced to contain staged restore visibility. | `REMOVE-WORKAROUND` |
| `9004c67b` | Android streamed battle music. | `KEEP-PLATFORM` |
| `04fc8877` | Project data/resource workflow refactor; protected project content, not a rollback target. | Out of engine recovery scope |
| `0821182a` | APK/build cleanup commit also touched ten engine files, so it is mixed and must be reviewed by file rather than reverted wholesale. | `NEEDS-CONTROLLER-DECISION` where semantic |

## Required audit surfaces

### Android gates

- `app/engine/android_runtime.py` owns `is_android_runtime()` and
  `is_android_render_optimization_enabled()`.
- The render gate is true only when both `LT_ANDROID_RUNTIME` and
  `LT_ANDROID_RENDER_OPT` are truthy.
- Direct gate consumers include render/menu/info/battle paths, Android
  debugger/input routing, sound/music, game-over, and load/general states.
- Any consumer in an authoritative transaction remains subject to INV-04;
  a platform gate alone does not prove a gameplay-ordering change is safe.

### Generators, staged work, and deferred commits

| Surface | Evidence | Risk |
|---|---|---|
| `GameState.start_level_iter`, `level_setup_iter`, `set_up_game_board_iter`, `load_iter` | Multiple `yield` boundaries construct registries, level, board, fog, unit arrival, auras, events, and saved state. | Partial authoritative state can become observable (INV-03). |
| `GameBoard.build_iter` and `TileMapObject.from_prefab_iter` | Board/tilemap construction is yieldable. | Must prepare pending structures outside live game, then commit atomically. |
| `TilemapChangeJob` and `AddGroupJob` | Event-facing queued jobs spread map/board mutation across updates. | Action/event ordering can change (INV-04). |
| `InChapterLoadState` and title load states | Android load advances `load_iter`/`start_level_iter`, then calls `commit_staged_state`. | Saved stack and map visibility are coupled to staged sequencing. |
| `StateMachine.update` and driver fast-forward | `defer_render`, presentation barriers, and multiple updates per host frame change scheduling. | Must prove time-only change under INV-06. |

### Worker threads

- `app/engine/general_states.py` starts Android music-loading threads and owns
  the staged in-chapter loader.
- Save/load work and Android profiler scope isolation cross thread boundaries.
- Worker-side file/resource work may remain platform policy; worker mutation
  of authoritative game state is not accepted without a later proof of one
  atomic main-thread commit.

## Correctness-critical file classification

| File(s) | Evidence | Classification | Status / reason |
|---|---|---|---|
| `app/engine/game_state.py` | `52bd0403`, `8306e1a9`; staged registries, `load_iter`, `start_level_iter`, deferred state stack | `RESTORE-PC-SEMANTICS` | Confirmed critical. The deferred saved-state portion is also a `REMOVE-WORKAROUND`; Phase 2 must separate it from save-format features. |
| `app/engine/general_states.py` | `52bd0403`, `8306e1a9`; Android staged in-chapter load, threads, post-load iterator | `RESTORE-PC-SEMANTICS` | Confirmed critical. Retain only resource preparation that stays outside live state. |
| `app/engine/state.py` | `390638ac`, `6bd9da4b`; map/camera safety guards for staged restore | `REMOVE-WORKAROUND` | Confirmed dependency on invalid staged visibility. Remove only after Phase 2 proves the state impossible. |
| `app/engine/state_machine.py` | `52bd0403`, `0821182a`; deferred render/presentation barriers and staged-state interaction | `NEEDS-CONTROLLER-DECISION` | Mixed with fast-forward and profiler work; Phase 2/7 needs trace evidence before final class. |
| `app/engine/game_board.py` | `52bd0403`, `cdd4be2a`; `build_iter` | `REWRITE-PLATFORM` | Confirmed staged board construction. Phase 4 decides whether pending-board preparation can be retained. |
| `app/engine/jobs/__init__.py`, `app/engine/jobs/tilemap_change_job.py` | `cdd4be2a`, `6b96e2f1`, `0821182a` | `REWRITE-PLATFORM` | Confirmed queued tilemap transition; event-facing ordering must be restored/isolated. |
| `app/engine/jobs/add_group_job.py` | `cd8607b6` | `REWRITE-PLATFORM` | Confirmed incremental live placement; must preserve one command's action/board/aura/fog semantics. |
| `app/engine/objects/tilemap.py` | `52bd0403`, `0821182a`; iterator construction | `REWRITE-PLATFORM` | Pending tilemap build is potentially retainable only behind one atomic logical commit. |
| `app/engine/action.py` | `52bd0403`; shared action mutations, including event/map surfaces | `NEEDS-CONTROLLER-DECISION` | Correctness-critical mixed change. Classify by action trace during Phases 2–4, not commit provenance. |
| `app/engine/combat/map_combat.py` | `78acb08a`, `9be65ca5`, `1e527510`, `97c8c375` | `RESTORE-PC-SEMANTICS` | Confirmed staging across solver, visual, action, and cleanup phases. |
| `app/engine/combat/simple_combat.py` | `88ebd6a5`, `e5addcde` | `RESTORE-PC-SEMANTICS` | Confirmed staged solver/start-hook changes. |
| `app/engine/combat/base_combat.py` | `0e2aa45a`, `d1fd6887` | `RESTORE-PC-SEMANTICS` | Confirmed staged solver/start-hook changes. |
| `app/engine/combat/animation_combat.py` | `29d1b65d..fff0145d`, `9004c67b` | `RESTORE-PC-SEMANTICS` | Staged gameplay/lifecycle portions restore; Android battle-music streaming is separately `KEEP-PLATFORM`. |
| `app/engine/battle_animation.py` | `52bd0403`; Android render gates and animation frame work | `NEEDS-CONTROLLER-DECISION` | Presentation/cache work is separable, but battle animation is coupled to combat lifecycle. |
| `app/engine/combat/interaction.py`, `app/engine/combat/mock_combat.py`, `app/engine/combat/solver.py`, `app/engine/combat_calcs.py` | `52bd0403` mixed commit | `NEEDS-CONTROLLER-DECISION` | Gameplay-critical; no final semantic classification from mixed provenance alone. Phase 3 must compare reference transaction traces. |
| `app/engine/driver.py` | `52bd0403`, `7735ca29`; fast-forward multi-update/deferred presentation plus profiling | `NEEDS-CONTROLLER-DECISION` | Profiler sub-change is `KEEP-SHARED`; fast-forward scheduling remains Phase 7 evidence work. |
| `app/engine/input_manager.py` | `52bd0403`; input processing consumed across extra updates | `NEEDS-CONTROLLER-DECISION` | Coupled to fast-forward input-edge semantics. |
| `app/engine/movement/unit_path_movement_component.py` | `52bd0403` mixed change | `NEEDS-CONTROLLER-DECISION` | Movement is authoritative; require reference trace before treatment. |
| `app/engine/objects/unit.py`, `app/engine/unit_funcs.py` | `52bd0403` mixed change | `NEEDS-CONTROLLER-DECISION` | Unit lifecycle/stat behavior is authoritative; do not infer from commit bulk. |
| `app/engine/save.py`, `app/engine/title_screen.py` | `52bd0403`, `8306e1a9` | `NEEDS-CONTROLLER-DECISION` | Save-format and restart features are protected; staged orchestration must be split during Phase 5. |
| `app/engine/runtime_reset.py` | `52bd0403` | `KEEP-SHARED` | Preserve restart/main-menu feature under INV-08; later audit must keep it independent of staged restore. |
| `app/engine/runtime_debugger.py`, `app/engine/runtime_debugger_controller.py`, `app/engine/runtime_debugger_service.py` | `52bd0403`, `0821182a` | `KEEP-SHARED` | Intended PC debugger feature; observer equivalence remains Phase 7 validation. |
| `app/engine/android_runtime.py`, `app/engine/android_debugger.py` | `52bd0403`, `6631e736` | `KEEP-PLATFORM` | Explicit Android adapter/UI; must not define gameplay ordering. |
| `app/engine/performance.py`, `app/engine/phase.py` | `52bd0403`, `7735ca29`, `eda4f2d9`, `d2bbd026` | `KEEP-SHARED` | Profiler is an observer. Worker-scope isolation is `KEEP-CORRECTNESS-FIX`. |
| `app/engine/base.py`, `app/engine/sound.py`, `app/engine/game_over.py` | `52bd0403`, `d2bbd026`, `9004c67b` | `KEEP-PLATFORM` | Android stream/cache policy is retained; staged-loading guards within `base.py` are `REMOVE-WORKAROUND`. |

## Other changed engine files

These files were reviewed as part of the `52bd0403` mixed import. They are
not currently identified as the primary authoritative transaction boundaries,
but are classified so later tasks do not treat the whole commit as safe.

| Classification | Files | Status |
|---|---|---|
| `KEEP-PLATFORM` | `app/engine/banner.py`, `app/engine/bmpfont.py`, `app/engine/dialog.py`, `app/engine/fluid_scroll.py`, `app/engine/fonts.py`, `app/engine/health_bar.py`, `app/engine/help_menu.py`, `app/engine/highlight.py`, `app/engine/icons.py`, `app/engine/info_menu/info_graph.py`, `app/engine/info_menu/info_menu_portrait.py`, `app/engine/info_menu/info_menu_state.py`, `app/engine/info_menu/multi_desc.py`, `app/engine/map_view.py`, `app/engine/menus.py`, `app/engine/particles.py`, `app/engine/settings.py`, `app/engine/settings_menu.py`, `app/engine/sprites.py`, `app/engine/text_entry.py`, `app/engine/ui_view.py`, `app/engine/unit_sprite.py`, `app/engine/game_menus/menu_components/unit_menu/unit_menu.py`, `app/engine/game_menus/menu_components/unit_menu/unit_table.py`, `app/engine/game_menus/menu_options.py`, `app/engine/game_menus/menu_states/unit_menu_state.py` | Render/UI/cache specialization only insofar as it remains output-equivalent and outside logical state ordering. |
| `NEEDS-CONTROLLER-DECISION` | `app/engine/achievements.py`, `app/engine/config.py`, `app/engine/convoy_funcs.py`, `app/engine/debug_mode.py`, `app/engine/engine.py`, `app/engine/feat_choice.py`, `app/engine/item_components/__init__.py`, `app/engine/item_components/utility_components.py`, `app/engine/item_funcs.py`, `app/engine/objects/overworld/overworld.py`, `app/engine/overworld/overworld_states.py`, `app/engine/persistent_records.py`, `app/engine/player_choice.py`, `app/engine/prep.py`, `app/engine/promotion.py`, `app/engine/skill_components/__init__.py`, `app/engine/status_upkeep.py`, `app/engine/trade.py` | Gameplay/data-facing changes landed only in `52bd0403`; retain or restore only after the relevant behavioral audit. |
| `KEEP-CORRECTNESS-FIX` | No additional file is accepted solely from provenance. Any later correctness fix embedded in the two mixed groups above must be isolated by its own test/evidence before retention. | Prevents accidental rollback of independent fixes. |

Together with the correctness-critical table, the file lists above cover all
81 `app/engine` paths changed in the reference-to-start range.

## Mixed-commit handling

1. Do not revert `52bd0403` wholesale. It contains desired debugger, profiler,
   restart, Android adapter, cache, and feature work alongside semantic-risk
   scheduling changes.
2. Do not revert `0821182a` wholesale. Despite its APK-cleanup subject, it
   modifies Android debugger, staged load, tilemap job, tilemap object, and
   state-machine files.
3. Treat `app/events/event.py`, `event_functions.py`, and `event_state.py` as
   adjacent transaction partners for later audits. They are not counted in the
   81-engine-file acceptance set, but their job/yield boundaries can affect
   event ordering.
4. Protected project data/resources in `04fc8877` are excluded from recovery
   rollback scope under INV-09.

## Controller decisions required before implementation

- Should `GameState`/board/tilemap progressive preparation be retained only
  as a pending-world build plus one atomic commit, or replaced entirely after
  Phase 4 evidence?
- Which `StateMachine` deferred-render/presentation-barrier behavior is
  required for fast-forward versus introduced solely for staged loading?
- Which `52bd0403` gameplay/data-facing edits are independent correctness
  fixes versus Android-driven semantic changes?
- For animation combat, how should retained Android streamed music be
  separated from staged authoritative combat advancement?

## P0-T02 disposition

- Every correctness-critical changed engine file is classified or explicitly
  marked `NEEDS-CONTROLLER-DECISION`.
- No baseline failures were fixed or reclassified as task work.
- No production behavior changed.
- No model escalation was used.
- **STOP FOR CONTROLLER REVIEW. P0-T03 and all later tasks remain
  unauthorized.**
