# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 8 — Safe shared optimization reintroduction**
- Phases 1–7: **ACCEPTED**
- P8-T01 cache/memoization audit: **ACCEPTED** at `1d40f89cf33008e0592c35ef9ab094c4cc9d0b5d`
- Active task: **P8-T02 only — Render/cache/batching optimization audit**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P8-T03/P8-T04 and Phase 9+: **UNAUTHORIZED**
- Expected default production changes: **NONE — audit/test/evidence first**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P8-T02: **YES — STOP FOR CONTROLLER REVIEW**

## P8-T01 acceptance record

The controller accepts `1d40f89cf33008e0592c35ef9ab094c4cc9d0b5d` (`docs(recovery): audit runtime caches`).

Accepted evidence:

- it is exactly one descendant of P8-T01 authorization commit `da7c3895002ddd1cdae192690fa182c8de62282a`;
- scope is test/evidence only: `app/tests/test_cache_memoization.py` and `recovery/p8_t01_cache_memoization_audit.md`;
- no production cache owner, key, lifetime, capacity, invalidation behavior, gameplay code, Trace V1 artifact, project data, or asset changed;
- gameplay-derived LTCache owners `compute_advantage` and skill `condition` are retained only with the global generation/invalidation contract; object identity alone is not treated as a complete key;
- the existing `CombatCondition` re-entrant path keeps the required post-publication invalidation and remains covered by deterministic regression evidence;
- `UnitObject` visible-skill caching is cleared after supported skill-list publication and is covered by add/remove-after-hit evidence;
- immutable Manhattan-range and eval-range memoization have value-complete keys and hit/forced-miss equivalence tests;
- presentation/render/resource/observer caches were inventoried but not tuned or centralized; their optimization decisions remain deferred to P8-T02 or their accepted platform/observer owner;
- required isolated immutable comparisons S2/S4/S5/S7/S8/S12/S13/S14/S15/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 were reported exact;
- focused cache/component/target/combat/load/restart/fast-forward/debugger/profiler/recovery suites were reported green; broad shared-registry/native Windows failures remain known baseline isolation issues.

### Locked GC-REGION finding — NOT CERTIFIED SAFE

`GameState.get_region_under_pos` is a gameplay-derived bounded LRU whose current `AddRegion`/`RemoveRegion` mutation paths clear the cache immediately **before** mutating `level.regions` membership.

The audit did not reproduce a stale observation because the current synchronous action-body gap contains no callback, yield, or known re-entrant reader. Therefore P8-T01 does not invent a production change merely to cosmetically satisfy the general publish-first/invalidate-after rule.

However this cache is explicitly **NOT CERTIFIED SAFE** for expansion or optimization:

1. P8-T02/P8-T03/P8-T04 may not increase its lifetime, reuse it as a new optimization primitive, add readers in the mutation gap, or cite P8-T01 as proof that its ordering is safe.
2. Any task that touches region-query caching must first create deterministic re-entrant/ordering proof.
3. If a supported stale reader is reproduced and the fix is local, controller review may authorize a bounded correction.
4. If correctness requires changing region-publication/action/tilemap transaction architecture, STOP under ESC-02/ESC-09.
5. P4 tilemap atomicity and Event-local barrier remain protected.

## Locked contracts entering P8-T02

Every render/cache/batching optimization must preserve:

1. one shared gameplay core and accepted PC logical semantics;
2. no new host-time/command-count scheduling of gameplay work;
3. no partial live gameplay state or yielded authoritative transaction;
4. combat solver/action/RNG/hook/cleanup order;
5. Event/state-machine semantic boundaries, including presentation fences;
6. P4 tilemap atomic commit/barrier;
7. P5 canonical load/restart and pristine-source precedence;
8. P7 fast-forward logical equivalence;
9. debugger/profiler observer semantics;
10. P6 platform capabilities: platform policy may select presentation/resource backend behavior, not gameplay ordering;
11. cache keys/invalidation remain owner-local unless an already-accepted architecture explicitly says otherwise;
12. `GC-REGION` remains out of optimization scope as described above.

---

# P8-T02 — Render/cache/batching optimization audit

Execute **P8-T02 only** using **GPT-5.6 Terra / medium**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

Plan objective: keep output-equivalent shared render/cache/batching optimizations, reject or bound any optimization that changes logical update scheduling or state visibility.

## Scope

This task is an audit of existing presentation/render/cache/batching optimizations. It is not authorization to broadly add new optimizations.

Start from the P8-T01 presentation inventory and perform a fresh local repository search for current implementations and post-reference optimization remnants.

At minimum inventory/search:

- `is_android_render_optimization_enabled` and related Android render policy checks;
- render/surface/text/menu/highlight/info/unit-menu/title caches;
- combat animation/mock-combat render caches and draw suppression/staging;
- dialog/tagged-text/font/layout culling caches;
- explicit batch/batching/batched draw/update helpers;
- surface composition/prefill/precompute paths;
- render revision/key/generation fields;
- countdown/defer-render/request-present interactions;
- any optimization that skips, combines, delays, or reorders update/draw work.

Classify each relevant optimization as exactly one of:

- **KEEP-SHARED — OUTPUT EQUIVALENT**
- **KEEP-PLATFORM — PRESENTATION POLICY ONLY**
- **FIX-LOCAL — PRESENTATION CORRECTNESS**
- **REJECT — CHANGES LOGICAL SCHEDULING/STATE VISIBILITY**
- **DEFER-P8-T03 — ALLOCATION/REDUNDANT-WORK ONLY**
- **DEAD/UNUSED**
- **ESCALATE**

## Required proof dimensions

For every retained optimization prove, as applicable:

- same gameplay logical state before/after rendering;
- same state-stack transition semantics;
- same input consumption semantics;
- same Event command/order and presentation-fence semantics;
- same combat solver/actions/hooks/cleanup/RNG;
- same menu logical selection/command availability;
- same FOW/aura/highlight logical ownership (pixels may differ only where presentation policy intentionally allows it);
- cache hit/miss cannot decide a gameplay action;
- missed/invalidated cache falls back to a correct uncached render path;
- render deferral cannot expose a partially committed gameplay world;
- batching cannot combine authoritative gameplay mutations across semantic boundaries.

Host frame count, draw-call count, surface allocation count and profiler timing are not logical equality criteria.

## P8-T01 carry-forward presentation owners

Audit current implementations for at least:

- `bmpfont.py::{Glyph,BmpFont}`;
- `health_bar.py` HP-bar surface caches;
- `dialog.py::Dialog.tagged_text_cache`;
- `graphics/text/tagged_text.py`;
- `graphics/ui_framework/ui_framework_layout.py::should_cull`;
- `highlight.py::HighlightController` Android surface cache/revision;
- `menus.py::Table`;
- title/menu/settings/sound-room cached surfaces;
- info-menu/help/multi-description render caches;
- unit-menu bounded render cache;
- `combat/animation_combat.py` render/UI/tint/surface caches;
- `combat/mock_combat.py` render caches;
- resource/presentation caches controlled by accepted P6 boundaries;
- Android debugger panel cache only as observer/presentation regression evidence, not as gameplay optimization work.

Do not change `GC-REGION` in this task.

## Batching / scheduling boundary

Any optimization that batches or defers work must be classified by what is being batched.

Allowed candidates:

- pure surface blits/composition;
- text/glyph/layout work;
- immutable resource preparation;
- owner-local presentation cache rebuilds;
- rendering-only list construction/culling;
- already-accepted off-world preparation behind an existing protected transaction boundary.

Not allowed:

- batching Actions across semantic fences;
- batching Event commands based on wall-clock/frame budget;
- splitting or combining combat solver/action/cleanup lifecycle;
- delaying authoritative state publication until a later render frame;
- exposing pending tilemap/load/combat state;
- replaying/skipping input due to render optimization;
- using `request_present`/`waiting_for_present` as a generic performance scheduler.

If an existing optimization does any of the above, mark **REJECT** and STOP before architectural remediation unless a bounded local presentation-only fix is unambiguous.

## Shared versus Android policy

Shared optimization is acceptable only when output/behavior is equivalent on both platforms.

Android may specialize presentation/resource policy only at accepted seams:

- whether a local presentation cache is enabled;
- bounded cache capacity where it affects only presentation memory/performance;
- physical resource preparation/backend behavior;
- draw/culling behavior proven not to affect logical state.

Android must not specialize gameplay ordering, Event command scheduling, input/action semantics, combat mechanics, save/load/restart, or live transaction boundaries.

Do not introduce a global render-cache service locator.

## Production change policy

Expected production changes: **NONE**.

A production fix is allowed only when deterministic evidence proves a local presentation/output defect or an existing render optimization is crossing a logical boundary, and the correct fix is bounded to the presentation owner.

Do not add a new speculative optimization simply because an uncached path is measurable.

Do not tune performance without evidence.

Do not touch gameplay-derived cache families from P8-T01, especially `GC-REGION`.

If a correction requires changes to gameplay scheduling/lifecycle or accepted transactions, STOP under ESC-02/ESC-05/ESC-07/ESC-09.

## Tests / evidence

Create `recovery/p8_t02_render_cache_batching_audit.md`.

Add focused tests only where current evidence is missing.

Use current owner-specific suites, including where applicable:

- Android performance/render-cache tests;
- title-option cache tests;
- info-menu render optimization tests;
- styled-text/parser/dialog tests;
- menu/settings/unit-menu rendering cache tests;
- highlight invalidation/camera/region-signature tests;
- health-bar/render surface tests;
- animation-combat/mock-combat render tests;
- runtime debugger Android panel observer tests;
- state-machine presentation barrier tests;
- P7 fast-forward equivalence;
- Phase-3 combat lifecycle;
- P4 tilemap barrier/atomicity;
- P6 platform policy;
- P7 debugger/profiler observer suites;
- recovery trace/lifecycle/golden integrity.

For any cache/optimization enabled only under Android policy, test both enabled and disabled paths where practical and prove identical logical state/selection results.

For render caches, visual pixel equality may be proven with deterministic surface signatures/checksums or equivalent owner-specific assertions where stable; do not add volatile host-dependent image goldens.

## Immutable trace gate

Run at minimum:

- S5
- S7
- S8
- S12
- S13
- S14
- S15
- S16
- S17 disabled
- S17 debugger-idle
- S17 profiler-idle
- S18

Also run S2/S4 if any touched render/load surface participates in a load/restart transition.

All invoked Trace V1 fixtures must match exactly.

No golden regeneration or normalizer/comparator/schema changes.

## Performance evidence

This task may measure render/cache hit/miss or composition cost where practical, but performance is secondary to correctness.

Do not accept an optimization solely because FPS/timing improves.

If no production optimization is changed, measurement is optional and the task may remain an audit/evidence-only commit.

## Broad validation

Run broader unittest discovery and report known baseline shared-registry/import-order/native Windows failures unchanged.

Then run:

- `python -m compileall -q app`
- `git diff --check`
- bounded commit
- `git show --check`
- `git status --short`

Expected default commit scope:

- `recovery/p8_t02_render_cache_batching_audit.md`
- focused render/cache/batching tests if evidence is missing

Production files only if a deterministic bounded presentation correctness defect was proven.

## Explicitly out of scope

Do not:

- begin P8-T03/P8-T04 or Phase 9;
- change `GC-REGION` or other gameplay-derived cache semantics;
- add speculative caches;
- centralize render caches;
- reintroduce Android Event command budgeting;
- change fast-forward semantics;
- change combat lifecycle;
- change tilemap/load/restart transaction architecture;
- change debugger/profiler semantic behavior;
- change Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / medium**.
Escalation target: **GPT-5.6 Sol / high**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** render/cache issue root cause is nonlocal to presentation ownership;
- **ESC-03** immutable trace divergence;
- **ESC-04** competing PC/Android semantics appear;
- **ESC-05** optimization changes logical state visibility/lifecycle;
- **ESC-07** platform performance requires gameplay fork;
- **ESC-08** repeated bounded correction failure;
- **ESC-09** new global cache/batching/scheduler architecture appears necessary.

Do not self-escalate.

## Gate status

**P8-T01 is ACCEPTED. P8-T02 is the only authorized task. P8-T03/P8-T04 and Phase 9+ remain blocked pending controller review.**
