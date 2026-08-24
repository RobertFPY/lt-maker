# P8-T02 render/cache/batching audit

**Task:** P8-T02 — render/cache/batching optimization audit
**Revision audited:** `ec0c98cbb0441194522a751c27f3295b669ce2cd`
**PC reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
**Scope:** existing owner-local presentation/resource work only. No production,
Trace V1, project-data, asset, or gameplay-derived cache change was made.

## 1. Method and hard boundary

Fresh local searches covered Android render gates, cache/revision/generation
names, deferred rendering, `request_present`, `waiting_for_present`, batching,
prefill/precompute/composition, draw suppression, render countdown state, and
all mandatory owners. This report classifies active runtime owners, not every
comment or profiler label containing the word `cache`.

The acceptance boundary is strict:

* a cache can retain or compose pixels only;
* cache hit/miss cannot select an action, menu command, Event command, combat
  result, or state transition;
* `request_present` remains a one-cue presentation fence, not a work budget;
* fast-forward may defer intermediate composition but not input/lifecycle
  updates; and
* the P4 pending tilemap build remains the sole approved progressive work,
  off-world behind its Event-local barrier and one synchronous live commit.

`GameState.get_region_under_pos` (`GC-REGION`) is deliberately absent from
this audit. P8-T01 marked it not certified safe; this task neither changes it
nor adds a reader to its pre-publication invalidation gap.

## 2. Render/cache optimization inventory

| Owner | Platform gate | Key/revision, value, invalidation and uncached fallback | Work skipped/batched; gameplay read/write; lifecycle/input/fence effect | Evidence, classification and decision |
| --- | --- | --- | --- | --- |
| `bmpfont.py::{Glyph,BmpFont}` | None | Character/color/font identity -> glyph width/subsurface/render result; cache lifetime is font/surface lifetime. Uncached path resolves the same glyph. | Batches repeated glyph lookup/surface slicing only. Reads font resources; writes no gameplay state. | `test_styled_text_parser` owner coverage. **KEEP-SHARED — OUTPUT EQUIVALENT.** |
| `health_bar.py::{_create_hp_bar_surf,_create_double_hp_bar_surf}` | None | HP/overflow args -> bar surface; one-entry LRU per bar owner. New argument replaces cached result. | Avoids rebuilding pixels; HP remains read-only input. No action/combat lifecycle mutation. | Android render tests exercise bounded rebuild. **KEEP-SHARED — OUTPUT EQUIVALENT.** |
| `dialog.py::Dialog.tagged_text_cache` and `graphics/text/tagged_text.py::_cache` | None | Text span/cycle index -> tagged text or surface. Dialog/text lifetime and caching eligibility own invalidation; uncached branch draws the same span. | Text/layout composition only. Dialogue state advances in `Event.update`, not cache draw. | `test_styled_text_parser`; P7 fast-forward and S17 protect updates/observer behavior. **KEEP-SHARED — OUTPUT EQUIVALENT.** |
| `graphics/ui_framework/ui_framework.py::_cached_surf` and `ui_framework_layout.py::should_cull` | None | Component redraw state/geometry tuples -> rendered component or cull boolean. Property recalculation invalidates dimensions/surface; miss redraws. | Surface reuse and render-only culling; reads UI props, no game write. | UI-framework tests. **KEEP-SHARED — OUTPUT EQUIVALENT.** |
| `highlight.py::HighlightController._android_cache_surf` | Android render optimization | `(revision, cull_rect, region signature)` -> static highlight surface. Mutator calls bump revision; region geometry is independently included. Uncached desktop path redraws same settled highlights. | Batches static highlight blits; dynamic animation still draws separately. Reads highlights/regions; does not mutate FOW, regions, selection or input. | `test_android_performance_round3` covers revision and cull-key invalidation; S13/S14 protect FOW/tilemap. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `menus.py::Table` static backgrounds/options; `menu_options.py::TitleOption` text/outline | Android render optimization | Table key includes scroll/layout/choice display text/font/color; TitleOption invalidates on text/color mutation and bounds outline frames. Miss invokes ordinary draw. | Static composition; cursor/highlight and dynamic choice layer remain outside cache. Does not change `current_index`, availability, or `takes_input`. | `test_android_title_option_cache`, `test_android_soundroom_round2`. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `settings.py::SettingsMenuState` and `settings_menu.py` static header/info/background surfaces | Android render optimization | Header key uses width/active tab; info key includes text; controls prompt is immutable for state lifetime. Miss draws desktop-equivalent primitives. | Avoids menu pixels. The Android `blocks_fast_forward` flag is an interactive-state guard, not cache batching; it prevents extra user-input opportunities while editing settings. | Existing fast-forward/input tests protect edge consumption. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** Do not generalize this guard into platform scheduling. |
| `base.py::BaseSoundRoomState` title/table cache | Android render optimization | Music NID -> cropped title surface; Table key as above. Miss uses regular title/text draw. | Pixel composition only. | `test_android_soundroom_round2`. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `base.py::_queue_stream_preview` | Android streamed-preview policy | Pending `(music,battle)` tuple, consumed once by `update`; no cached gameplay value. | Defers only physical mixer preview until a requested present makes selection feedback visible. It does not batch actions or Event commands. Stream failure clears UI playing state and uses existing error path. | P6 sound policy tests, `test_android_soundroom_round2`, P7 fence/fast-forward tests. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** Explicit fence retained; not a generic scheduler. |
| `title_screen.py` title smoke seed | Android render optimization | Android initializes a title-only `MapParticleSystem` with `seed_title_smoke`; desktop runs 300 visual prefill updates. Both retain particle count/bounds/lifetime direction; neither writes `GameState`, RNG service, input, or Event state. | Replaces title-particle startup churn, not gameplay work. Its distribution is intentionally not pixel-identical to desktop prefill. | `test_android_performance_round3` source/owner evidence only; no deterministic visual-equivalence proof. **DEFER-P8-T03 — ALLOCATION/REDUNDANT-WORK ONLY.** Do not tune, extend, or claim output equivalence without a stable title-presentation contract. |
| `info_menu/*`, `help_menu.py`, `multi_desc.py` | Android render optimization where applicable | Portrait blink/frame or help/page inputs -> surfaces/dialog objects; owner invalidation on dialog/page/text/portrait change. LTCache generation invalidates multi-description values after supported game mutation. Miss uses normal composition. | Portrait/help/text composition only; item/skill values are displayed, not selected or mutated. | `test_info_menu_render_optimization`, P8-T01 LTCache evidence. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `game_menus/menu_components/unit_menu/unit_menu.py` | Android render optimization | `(page, scroll, sort, visible unit NIDs)` -> top/table surfaces; `OrderedDict` capped at four and LRU-evicted. | Batches static table text/icons; cursor, selection and input remain dynamic. Reads unit values for display only. | `test_android_performance_round3` verifies four-view bound/hit reuse. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `combat/animation_combat.py` Android UI/bar/gauge/name/tint/arrow layers | Android render optimization | Immutable display-layer identity/stats/HP/gauge/tint/arrow-frame keys -> prepared surfaces; local bounded ordered dictionaries. Miss uses source composition. `prepare_cached_surface` retains alpha/colorkey semantics. | Batches UI surface composition/blits only. Combat calculation reads feed display values; no solver/action/hook/RNG/cleanup mutation. | `test_android_performance_round3` covers health-key invalidation, bounds, alpha semantics and arrow animation keys; S7/S8/S16 protect combat/FF logic. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `combat/mock_combat.py` Android transient visual progression | Android render optimization | No retained action cache: animations/damage numbers advance in `update_android_transient_visuals` when draw may be deferred; desktop advances them in draw. | Moves draw-owned particle/number updates to simulation-time so fast-forward does not freeze display effects. It does not alter MockCombat combat state transition or gameplay actions. | P7 fast-forward suite and Phase-3 lifecycle tests. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** Do not use this as precedent for solver/action scheduling. |
| `battle_animation.py::_advance_android_render_state` | Android render optimization | Draw countdown fields advance in update on Android. No image cache is involved. | Prevents deferred-draw visual countdown stalls. No hit/action/RNG/state-machine write. | Android battle-animation render tests and S7. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `battle_animation.py` source-frame reuse proposal | None (not implemented) | Frames are copied each draw because later flash/opacity/palette/blend transforms mutate the result. | A retained frame cache would skip copies but has no proven safe key/invalidation contract. | Source evidence only. **DEFER-P8-T03 — ALLOCATION/REDUNDANT-WORK ONLY.** Do not add it. |
| `events/event.py::_draw_overlay_if_present` | Android render optimization | No cache; empty overlay bypasses `to_surf`/blit. Non-empty branch retains normal composition. | Skips an empty surface composition only. Reads overlay children/manual surfaces/background; writes no Event state. | `test_android_performance_round3` overlay tests; S5/S16/S17. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `android_debugger.py::_panel_cache` | Android debugger UI | Snapshot revision/page/view/selection/filter -> panel surface; confirmation/number/text views intentionally bypass cache. | Observer UI composition only; never dispatches a command on cache hit. | P7 debugger parity/observer tests and S17 debugger-idle. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |
| `sound.py::{MusicDict,SoundDict}` and P6 preload/flush policy | P6 audio/resource policy | Resource NID -> sound object; explicit preload/flush/clear lifetime. | Resource/backend reuse only. Semantic music selection remains caller-owned. | P6 policy tests, S17 observer and S18. **KEEP-PLATFORM — PRESENTATION POLICY ONLY.** |

The commented `@lru_cache` in `ui_framework_styling.py` and code-generator
template strings that merely emit already-listed decorators are **DEAD/UNUSED**
for runtime batching analysis.

## 3. Batching and deferred-render inventory

| Mechanism | What is batched/deferred | Classification and proof |
| --- | --- | --- |
| `driver.update_game_state_for_frame` | Only intermediate **composition** during accepted fast-forward; every logical substep still runs state input/update and repeat chains consume transient input. | **KEEP-SHARED — OUTPUT EQUIVALENT.** P7 tests prove first-substep input only, blocks-fast-forward, and no logical ON/OFF divergence. |
| `StateMachine.request_present` + `Event.waiting_for_present` | Exactly one visual cue; the fence forces one compose/present and stops remaining fast-forward substeps. | **KEEP-SHARED — OUTPUT EQUIVALENT.** It is an explicit semantic/presentation boundary, not a deadline or command batch. State-machine/Event lifecycle tests and P6-T03 evidence cover it. |
| `State.should_defer_render` | Retains the previously presented surface for a visual-atomic event update while state/lifecycle commits still execute. | **KEEP-SHARED — OUTPUT EQUIVALENT.** It cannot delay publication or next command; tests cover pending/waiting-for-present cases. |
| P4 `TilemapChangeJob` + Event-local `_android_tilemap_pending` | Pending TileMap/GameBoard/Boundary construction off-world only; no live unit/region/aura/FOW/board mutation until one synchronous commit or rollback. | **KEEP-PLATFORM — PRESENTATION POLICY ONLY** for the progress policy, with an existing correctness barrier. P4 tests and S14 protect no partial visibility. |
| `Event.process` | No render budget remains. Consecutive processor commands run synchronously until a command-created semantic boundary. | **KEEP-SHARED — OUTPUT EQUIVALENT.** P6-T03 removed the rejected Android 2 ms command deadline. No Event command batching remains to approve. |
| Combat solver/actions/cleanup, GameState load, live AddGroup | Not a render batch and not eligible for one. | **REJECT — CHANGES LOGICAL SCHEDULING/STATE VISIBILITY** if reintroduced. Protected by Phases 2–5 and immutable traces. |

## 4. Equivalence conclusions

* Cache hit/miss paths are owner-local draw/resource paths. They do not write
  game state, action logs, unit state, FOW/aura, phase/initiative, saves, or
  state stacks.
* The uncached fallback for every retained cache remains the pre-existing
  direct draw/composition path.
* Highlight, menu, settings, unit-menu, combat UI, debugger panel and Event
  overlay caches preserve logical selection/availability and input ownership.
* Presentation fences preserve Event order and fast-forward input semantics;
  they do not delay an authoritative transaction to a later render frame.
* No production defect was deterministically demonstrated. No capacity,
  lifetime, invalidation ownership, or platform policy was changed.

## 5. Required validation record

Focused suites passed in fresh processes: Android render optimization,
performance round 3, title-option cache, Sound Room round 2, info-menu render
optimization, animation-combat transaction order, state-machine lifecycle,
tilemap-change job, fast-forward equivalence, runtime-debugger parity,
performance profiler, recovery trace/golden integrity, canonical load,
restart contract, and atomic restore.

The locked Trace V1 recovery comparator passed S5, S7, S8, S12, S13, S14,
S15, S16, S17 disabled/debugger-idle/profiler-idle, and S18. The comparator
intentionally ignores only the trace-header provenance fields
`runner_revision` and `platform_profile`; every compared logical record
matched the immutable PC fixture. S2/S4 were not rerun because no audited
owner participates in a changed load/restart transition and this task made no
production change.

`test_styled_text_parser` reproduces the pre-existing isolated-run failure:
three tagged-text caching tests raise `KeyError: 'convo'` from the font
registry. Full `unittest discover -s app/tests` reproduces existing
component-registry/import-isolation failures and terminates natively with
`-1073740791`. Neither failure is modified by this audit. `compileall -q app`
and `git diff --check` pass. No visual image golden was added: host-dependent
pixel snapshots are not a stable correctness oracle for these paths.

## 6. Risks and controller boundaries

1. Title smoke seed is intentionally distribution-equivalent rather than
pixel-identical and lacks stable visual proof; it remains deferred, not an
accepted general render optimization.
2. Android Settings/Sound Room fast-forward guards must stay narrow to their
interactive UI states. Moving them into driver/platform policy would change
logical update scheduling and requires controller review.
3. Combat frame source caching remains rejected: later transforms make frame
surface reuse unsafe.
4. `GC-REGION` remains out of scope and not certified safe.
5. Any future render optimization that changes Event command timing, action
publication, combat lifecycle, input replay, or partial-world visibility is
**REJECT** and triggers the task escalation rules.
