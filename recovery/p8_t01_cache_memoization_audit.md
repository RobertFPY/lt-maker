# P8-T01 cache and memoization audit

**Task:** P8-T01 — cache/memoization audit
**Revision audited:** `da7c3895002ddd1cdae192690fa182c8de62282a`
**PC reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
**Scope:** inventory and correctness proof only.  No production cache owner,
key, lifetime, capacity, or invalidation order was changed.

## 1. Method and inventory boundary

The inventory was produced from local source searches for `LTCache`,
`ltcached`, `lru_cache`, `functools.cache`, `cached_property`, `_cache`,
`cache_`, `cache_clear`, and cache-key/invalidation sites.  It was then
reduced to active runtime memoization/cache owners.  Searches for `cache` in
comments, code generation templates, profiler labels, or cache-management
methods without stored/reused values are recorded as non-owners rather than
being treated as caches.

The component-system generator emits the `ltcached` decorators into generated
`item_system.py` and `skill_system.py`; the audited owners are the source
templates `item_system_base.py` and `skill_system_base.py`.  Generated files
are reference-owned artifacts and were not changed.

`LTCache` is one process-global generation token.  `GameState.__init__` calls
`ltcache.init()`, `GameState.on_alter_game_state()` replaces the token, and a
wrapped function clears its own underlying `lru_cache` immediately before its
next call when it observes a new generation.  Before initialization each
`get_state()` call returns a new UUID, which disables useful reuse rather than
allowing a stale hit.

## 2. Authoritative/gameplay-derived cache inventory

| Cache ID / owner | Key and value | Mutable dependencies and publication/invalidation | Lifetime / miss / evidence | Classification and decision |
| --- | --- | --- | --- | --- |
| `GC-ADV` `app/engine/combat_calcs.py::compute_advantage` | Object identities for `(unit1, unit2, item1, item2, advantage)` under the LTCache generation; `CombatBonus` or `None`. | Weapon type/override, ignore flag, triangle modifier, component condition, wexp, item state and `DB.weapons`/ranks. Normal action/hook publication calls `game.on_alter_game_state()` after the mutation. `CombatCondition.pre_combat()` deliberately invalidates once before evaluation and again **after** publishing `_condition`, because evaluation can re-enter this cache through `item_override`. | Unbounded per generation; miss recomputes triangle choice. `test_golden_knight_weapon_triangle` covers the result matrix; `test_item_skill_components.test_combat_condition_invalidates_cache_after_publishing` covers the former stale re-entry defect. S5/S7/S8/S9/S10 cover combat consumers. | **GAMEPLAY-DERIVED CACHE — KEEP.** A supported mutation cannot retain an old result after its authoritative publish path completes: the post-publication generation changes. Direct out-of-band mutation of item/skill/unit fields is unsupported and not safe. |
| `GC-COND` `component_system/skill_system_base.py::condition` (generated `skill_system.py`) | `(skill, unit, item)` identities plus LTCache generation; boolean aggregate of `condition` components. | Components, equipped item when `item is None`, position/evaluated variables, component-local combat condition state and any values consulted by `evaluate`. Action wrapper publishes then invokes `game.on_alter_game_state`; conditional combat hooks have explicit post-publication invalidation. | Unbounded per generation; miss iterates components. Same focused `CombatCondition` regression proves nested read, publish, and second invalidation; S5/S9 exercise hooks. | **GAMEPLAY-DERIVED CACHE — KEEP.** Safe only through the supported mutation API; no object-identity-only claim is made. |
| `GC-REGION` `app/engine/game_state.py::get_region_under_pos` | `(GameState identity, pos, region_type)`; first matching live `RegionObject` or `None`. | `level.regions` membership, type and geometry. `GameState.generic()` clears it. `AddRegion`/`RemoveRegion` do/reverse and tilemap rollback clear it; `change_tilemap` restores regions through those actions. | Bounded 128-entry LRU; miss scans regions. New `test_cache_memoization.test_region_query_cache_is_invalidated_by_region_action` exercises cached miss -> public AddRegion -> hit -> public RemoveRegion -> miss. S13/S14 cover FOW/move/tilemap consumers. | **GAMEPLAY-DERIVED CACHE — FIX-LOCAL CANDIDATE, NOT MARKED SAFE.** Current Add/Remove actions clear immediately *before* collection mutation. There is no callback/yield/re-entrant reader in that gap, so no stale result was reproduced, but this is not the accepted publish-first/invalidate-after ordering. Keep behavior unchanged in P8-T01; a future local change requires a deterministic re-entrancy proof and controller review of the ordering. |
| `GC-VISIBLE-SKILLS` `app/engine/objects/unit.py::UnitObject._visible_skills_cache` | Implicit key: unit `_skills`; filtered visible `SkillObject` list. | `_skills` membership/order, duplicate shadowing, stack value. `add_skill`, `remove_skill`, construction/setup and restore all clear the cache after their list publication. Tilemap rollback restores both `_skills` and the cached list atomically before the old world is republished. | Until explicit clear; miss filters reversed skill list. New `test_cache_memoization.test_visible_skill_cache_is_invalidated_by_public_skill_mutation` proves add/remove after a hit. | **GAMEPLAY-DERIVED CACHE — KEEP.** Supported skill membership mutation clears after publish. A direct mutation of `_skills` is unsupported and can stale the cache. |

### LTCache mutation-path conclusion

The normal `Action` subclass wrapper calls the action method, publishes its
authoritative mutation, then calls `game.on_alter_game_state()`.  This is the
required order for `GC-ADV` and `GC-COND`.  `CombatCondition.pre_combat()` is
the important re-entrant exception: it changes the generation before an
evaluation that can recursively populate `condition`, publishes `_condition`,
then changes the generation again.  That final invalidation is required and
is covered by the focused regression test.

`GC-REGION` is not LTCache-backed.  Its pre-mutation clears are isolated from
the next mutation by no callback or yield in current action code, but they are
not a proof of the general LTCache invariant.  It is deliberately left as a
local audit finding rather than papered over by a test or changed without a
reproducible stale observation.

## 3. Immutable-data memoization inventory

| Cache ID / owner | Key / value / lifetime | Dependency and invalidation proof | Evidence / decision |
| --- | --- | --- | --- |
| `IM-MANHATTAN` `app/engine/target_system.py::TargetSystem._cached_base_manhattan_spheres` | TargetSystem identity plus immutable `frozenset[int]`; set of origin-centered Manhattan offsets; 1024-entry LRU. Callers construct translated new sets and do not mutate the cached set. | Depends only on the frozen numeric radii. No game, board, unit, RNG, DB or global input. | New hit/forced-clear equivalence test; existing `test_target_system` exercises normal targeting. **IMMUTABLE-DATA MEMOIZATION — KEEP.** |
| `IM-EVAL-RANGE` `item_components/target_components.py::EvalSpecialRange.calculate_range_restrict` | `(condition: str, max_rng: int)`; set of offsets; unbounded static LRU. | `eval` receives only the condition string and local `x,y`; it does not read game globals. The caller obtains mutable item range only to derive the keyed integer. | New hit/forced-clear equivalence test; existing range-restrict targeting test. **IMMUTABLE-DATA MEMOIZATION — KEEP.** Unbounded project-authored expression/range cardinality is a memory-risk only, not a stale-result proof. |
| `IM-COMPONENT-CLASSES` `item_component_access.get_cached_item_components` and `skill_component_access.get_cached_skill_components` | `proj_dir` string; sorted `Data` of discovered component classes; one-entry LRU. | Runtime project/component definitions are fixed after project load. The key changes when the project directory changes. Same-path live custom-Python/editor reload has no explicit `cache_clear` and is therefore not safe to treat as a runtime-edit cache. | Engine load uses it as immutable component-class discovery. **IMMUTABLE-DATA MEMOIZATION — KEEP for runtime; DEFER-P8-T02 for editor/live-custom-component reload policy.** No gameplay cache correctness claim depends on it. |
| `IM-EVENT-SOURCE` `events/python_eventing/python_event_processor.py::get_source_line` | Processor identity plus line number; source-line text; default LRU. | Event source for a constructed processor is immutable. Used for diagnostics/errors, not command selection or execution. | Existing event tests cover processor execution. **IMMUTABLE-DATA MEMOIZATION — KEEP.** |
| `IM-LAYOUT-CULL` `graphics/ui_framework/ui_framework_layout.py::should_cull` | Geometry/scroll/overflow tuples; boolean; default LRU. | All inputs are value tuples. The result only decides pixel culling. | UI-framework layout ownership. **PRESENTATION/RENDER CACHE — DEFER-P8-T02**, despite an immutable key, because the value affects drawing only. |

No cached function in aura, FOW, GameBoard, Boundary, phase, initiative, or
pathfinding was found by the mandatory search.  Those systems therefore have
no hidden memoization owner to validate in this task.  Their derived state is
protected by the existing Phase 2–5 transactions, not by a cache.

## 4. Presentation/render cache inventory

These caches retain pixels/layout/dialog data only.  They must not decide an
action, target availability, menu command, or state transition.  No capacity
or invalidation policy was tuned in P8-T01.

| Owner(s) | Key / value / invalidation / eviction | Classification and decision |
| --- | --- | --- |
| `bmpfont.py::{Glyph, BmpFont}` | Character, color, font/surface identity -> glyph widths/subsurfaces/rendered text; cache lifetime follows the font object. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** Font/resource replacement is the owner lifetime boundary. |
| `health_bar.py::{_create_hp_bar_surf,_create_double_hp_bar_surf}` | HP/overflow arguments -> surface; one-entry LRU per bar object. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** Does not alter HP or combat result. Existing Android render tests cover bounded rebuilds. |
| `dialog.py::Dialog.tagged_text_cache` and `graphics/text/tagged_text.py::_cache` | Text span / animation-cycle index -> renderable tagged text or surface; each owner discards with dialog/text lifetime and disables caching for unsuitable cycles. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** `test_styled_text_parser` covers enabled/disabled/large-cycle behavior. |
| `highlight.py::HighlightController._android_cache_surf` | Revision, cull rectangle and region signature -> static highlight surface; revision bumps on owner mutations. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** Key includes region geometry; existing Android performance test covers mutation/camera invalidation. It does not own FOW or selection truth. |
| `menus.py::Table`, `game_menus/menu_options.py::TitleOption`, `settings_menu.py`, `base.py::BaseSoundRoomState` | Local text/background/static-option/title surfaces keyed by display data; owner-local invalidation methods. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** Cached pixels do not choose commands. |
| `info_menu/info_menu_state.py`, `help_menu.py`, `info_menu/multi_desc.py`, generated `item_system/skill_system::get_multi_desc*` | Portrait/help/dialog pages and item/skill multi-description values; LTCache generation for descriptions, local draw-state invalidation for surfaces. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** Live item/skill description reads can use mutable unit context, so global LTCache generation invalidates them after supported game mutation; no action availability is cached. |
| `game_menus/menu_components/unit_menu/unit_menu.py` | Page, scroll, sort and visible unit NIDs -> top/table surfaces; `OrderedDict` bounded to four views, LRU eviction. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** Existing test proves four-view bound and hit reuse. Any future key expansion must remain a rendering concern. |
| `combat/animation_combat.py` and `combat/mock_combat.py` Android UI/tint/surface caches | Combat render values/animation phase -> UI/text/tint surfaces; owner-local fields hold cache key. | **PRESENTATION/RENDER CACHE — DEFER-P8-T02.** Phase-3 solver/action/cleanup are not keyed or scheduled by these caches. |

## 5. Platform/resource and observer caches

| Owner | Key/value/lifetime | Classification and decision |
| --- | --- | --- |
| `sound.py::{MusicDict,SoundDict}` | Music/SFX NID -> backend `SongObject`/sound; explicit `preload` and `clear(song_to_keep)` own lifetime. | **PLATFORM/RESOURCE CACHE — KEEP.** P6-T02 owns streamed success/fallback and preload policy. Cache never selects semantic music NID or mutates GameState. |
| Resource/presentation caches behind P6 capability boundaries | Title/menu/highlight/unit-menu caches and Android backend resource preparation. | **PLATFORM/RESOURCE CACHE — DEFER-P8-T02.** P6 map requires owner-local invalidation; no global cache architecture is authorized. |
| `performance.py::RuntimeProfiler` scopes, counters, deques, frame history | Enabled-frame/main-thread diagnostic samples and bounded deques. | **OBSERVER CACHE — KEEP.** P7-T03 proves worker isolation and ON/OFF observer equivalence; it must not branch gameplay. |
| `android_debugger.py::AndroidDebuggerState._panel_cache` | Snapshot revision, page/view/selection/filter/editor state -> panel surface; confirmation/number/text screens intentionally bypass cache. | **OBSERVER CACHE — KEEP.** P7-T02/P7-T03 require observer-only snapshots and no double command submission. |

`graphics/ui_framework/ui_framework_styling.py` contains a commented-out
`@lru_cache`; it is **DEAD/UNUSED/TEST-ONLY — REMOVE-DEAD only if a later task
owns that source cleanup**.  The code generator's `cache_handling` string is
not a runtime cache; it is **DEAD/UNUSED/TEST-ONLY for this audit** because it
merely emits the already inventoried component-system decorators.

## 6. Key completeness and stale-result answers

* `GC-ADV`: complete only with the LTCache generation.  Object identity alone
  is explicitly insufficient because component/unit/item fields are mutable.
  Supported mutations publish and then invalidate.  **Answer: no supported
  post-publication mutation can return a result valid only for old state.**
* `GC-COND`: same requirement.  The nested `CombatCondition` path has an
  explicit second invalidation after `_condition` publication.  **Answer: no
  supported post-publication mutation can return a stale condition.**
* `GC-VISIBLE-SKILLS`: the key is implicit and therefore valid only because
  every supported `_skills` membership/order publication clears afterwards.
  **Answer: no supported mutation can return an old visible list.**
* `GC-REGION`: membership/geometry are absent from its key.  **Answer:
  UNKNOWN for a future re-entrant mutation path; current synchronous actions
  do not expose an observed stale result, but clear before publication is not
  the accepted ordering.** It is not marked safe.

All immutable memoization entries encode every value input in their key and
have no hidden gameplay/global dependency.  Cache-hit and forced-miss paths
for the two numerical range families are directly compared by the new tests;
they do not consume RNG, execute actions, or schedule Event/state-machine
work.

## 7. Trace and regression coverage

The required immutable harness comparisons for this task are S5, S7, S8,
S12–S18 (including S17 disabled/debugger-idle/profiler-idle), plus S2/S4
because `GC-REGION` and LTCache state can be observed after restore/restart.
Their recorded execution result is added in the validation section below.

Focused evidence selected from actual owners:

* `test_cache_memoization` — new public hit/miss and invalidation tests;
* `test_item_skill_components` — LTCache post-publication regression;
* `test_target_system` — targeting/range consumer behavior;
* `test_golden_knight_weapon_triangle` — combat triangle result matrix;
* existing Android render-cache tests (`test_android_performance_round3`,
  `test_android_title_option_cache`, `test_info_menu_render_optimization`,
  `test_styled_text_parser`) — local presentation keys/invalidation/bounds;
* Phase 3–7 suites — combat, tilemap/FOW, canonical load/restart,
  fast-forward, debugger, profiler and trace/golden integrity.

## 8. Decisions and follow-up boundary

No deterministic production cache defect was demonstrated.  Therefore P8-T01
does not change cache behavior.  The only non-safe finding is `GC-REGION`'s
pre-publication clear; it is a bounded local candidate, not a license to
reorder cache invalidation across lifecycle owners.  If a supported re-entrant
or asynchronous reader is found, it needs a dedicated deterministic test and
may be a local fix only if no transaction/region-publication architecture is
affected.  Otherwise it triggers ESC-02/ESC-09.

P8-T02 may evaluate presentation-cache optimization/tuning only after keeping
local owner invalidation and proving no logical selection dependency.  P8-T01
does not authorize increasing capacities, extending lifetimes, centralizing
caches, or adding memoization.

## 9. Validation record

Focused cache evidence passed in isolated Python processes:

```text
python -m unittest app.tests.test_cache_memoization                         # 4 passed
python -m unittest app.tests.test_item_skill_components \
  app.tests.test_target_system app.tests.test_golden_knight_weapon_triangle # 41 passed
python -m unittest app.tests.test_combat_transaction_order                  # passed
python -m unittest app.tests.test_tilemap_change_job                         # passed
python -m unittest app.tests.test_canonical_load                             # passed
python -m unittest app.tests.test_restart_contract                           # passed
python -m unittest app.tests.test_atomic_restore                             # passed
python -m unittest app.tests.test_fast_forward_equivalence                  # passed
python -m unittest app.tests.test_runtime_debugger_parity                    # passed
python -m unittest app.tests.test_performance_profiler                       # passed
python -m unittest app.tests.test_recovery_trace \
  app.tests.test_state_machine_lifecycle app.tests.test_recovery_golden      # 97 passed
```

The mandatory immutable captures were each run in a fresh process and checked
with `Trace V1 compare_records` against the committed PC fixture: S2, S4, S5,
S7, S8, S12, S13, S14, S15, S16, S17 disabled, S17 debugger-idle, S17
profiler-idle, and S18 all passed.  No fixture, manifest, normalizer, or
comparator was changed.

A deliberately aggregated 305-test cache/regression invocation failed with
the known shared component-registry pollution: a dynamically introduced
`_Uses` subclass lacks `tag`, causing later `DB.load()` component discovery to
raise `AttributeError`; one registry-uniqueness test also then fails.  The
same focused suites pass in fresh processes as shown above.  A separate
aggregated render command also exposed an existing font setup/order failure
(`KeyError: 'convo'` in `test_styled_text_parser`).  These are test-isolation
baseline failures; P8-T01 does not modify component discovery, registry
ownership, font bootstrap, or tests outside this bounded cache evidence.

Broader `python -m unittest discover -s app/tests` was also attempted.  It
reproduced existing scattered isolation failures and then terminated natively
with Windows exit `-1073740791`; no P8 source file had been loaded as a
production change.  `python -m compileall -q app` and `git diff --check`
passed after the audit changes.
