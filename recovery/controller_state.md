# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 8 — Safe shared optimization reintroduction**
- Phases 1–7: **ACCEPTED**
- P7-T01 fast-forward equivalence: **ACCEPTED** at `874c7adcf83f14e6fcf961180a01f4ddfe1201fe`
- P7-T02 debugger parity PC/Android: **ACCEPTED** at `11f2a42cd055d089917834ef80d74d369aad5ed8`
- P7-T03 profiler observer-equivalence: **ACCEPTED** at `9fcefdf8f2d6d03724d86523ae46b320bcd8802b`
- P7-T04 save/load/restart UX regression sweep: **ACCEPTED** at `6613d2b07c480f2c5e73349f9b29ca7e9f144340`
- Active task: **P8-T01 only — Cache/memoization audit**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P8-T02/P8-T03/P8-T04 and Phase 9+: **UNAUTHORIZED**
- Expected default production changes: **NONE — inventory/test/evidence first**
- New optimization insertion or broader cache redesign: **UNAUTHORIZED in P8-T01**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P8-T01: **YES — STOP FOR CONTROLLER REVIEW**

## P7-T04 acceptance record / Phase-7 closure

The controller accepts `6613d2b07c480f2c5e73349f9b29ca7e9f144340` (`test(save): verify UX routing parity`).

Accepted evidence:

- it is exactly one descendant of P7-T04 authorization commit `802023ce277bd0d43fda162c8c37022df6db8c54`;
- scope is test/evidence only: `app/tests/test_restart_contract.py` and `recovery/p7_t04_save_load_restart_ux.md`;
- no production, canonical load/restart, Trace V1, comparator, manifest, golden, save schema, project-data, or asset file changed;
- Title Load input-boundary evidence proves desktop and Android select the same current-progress SAVE slot; desktop forwards `LoadDestination.SAVED`, while Android forwards that exact slot into the already-accepted SaveLoadJob/context seam;
- tactical restart remains distinct from current SAVE and uses the accepted RESTART source contract; matching `chapter_start_snapshot` precedence, matching persistent RESTART fallback, stale/wrong-chapter rejection and explicit difficulty remain covered by accepted P5/P7 tests;
- the accepted overworld exception intentionally resolves to the matching main SAVE slot with `LoadDestination.OVERWORLD` rather than a tactical RESTART slot;
- Game Over only hands off to `title_start` and therefore cannot directly reinterpret a mid-chapter SAVE as pristine restart truth;
- canonical/atomic restore, initiative/phase, aura/FOW/tilemap, fast-forward, debugger and profiler regressions were reported green;
- isolated immutable S2/S4/S5/S12/S13/S14/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 all matched exactly;
- shared aura singleton contamination when multiple captures share one process remains a known test-isolation constraint, not a logical divergence;
- no UX routing defect required a production fix.

Phase 7 is therefore closed: fast-forward, debugger, profiler and save/load/restart UX are accepted user-facing features and become protected regression contracts for later optimization work.

## Locked contracts entering Phase 8

Every Phase-8 optimization must preserve all accepted invariants, especially:

1. One shared gameplay core; Android specialization remains platform policy only.
2. No partial live gameplay state or new yielded authoritative transaction.
3. Fast-forward changes host/presentation timing only, never logical outcomes/order.
4. Debugger/profiler remain observers when idle; debugger commands retain one shared semantic controller.
5. Canonical load/restart, pristine source precedence and atomic publication remain unchanged.
6. Combat action/RNG/hook/cleanup ordering and tilemap atomic commit remain unchanged.
7. Cache/memoization may only be retained or changed when dependency/invalidation correctness and logical equivalence are proven.
8. Project content and immutable recovery oracles remain protected.

---

# P8-T01 — Cache/memoization audit

Execute **P8-T01 only** using **GPT-5.6 Terra / high**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

Plan criteria:

- correct invalidation;
- no hidden mutable-state dependency absent from cache keys;
- identical logical traces;
- preserve the LTCache invariant: **publish mutable component state first, invalidate dependent caches after publication**.

This task is correctness-first. It does not authorize speculative cache additions, capacity tuning, batching, or render-cache redesign.

## Goal

Produce a repository-level audit of existing runtime cache/memoization mechanisms that can influence shared semantics or derive from mutable gameplay state.

For every relevant cache/memoized value, identify:

- owner/module/symbol;
- purpose and value type;
- cache key / memoization key;
- all mutable or versioned inputs that influence the result;
- publication/mutation points for those inputs;
- invalidation/clear/eviction points;
- whether invalidation happens before or after authoritative state publication;
- fallback behavior on miss;
- whether stale data could affect gameplay logic, ordering, targeting, stats, availability, hooks, UI decisions, or save-relevant state;
- existing tests/evidence;
- classification and decision.

## Required classification

Classify each discovered mechanism as one of:

1. **GAMEPLAY-DERIVED CACHE** — mutable gameplay/data dependency; requires complete key/invalidation proof and logical-equivalence tests.
2. **IMMUTABLE-DATA MEMOIZATION** — only immutable/value inputs; prove key completeness and no hidden mutable/global dependency.
3. **PRESENTATION/RENDER CACHE** — surfaces/text/layout/highlight/menu presentation only; inventory it but defer optimization/tuning decision to P8-T02 unless it affects a gameplay decision.
4. **PLATFORM/RESOURCE CACHE** — audio/resource/backend policy; preserve accepted P6 boundaries and defer performance tuning unless semantic cache correctness is implicated.
5. **OBSERVER CACHE** — debugger/profiler diagnostic data only; must remain observer-only.
6. **DEAD/UNUSED/TEST-ONLY** — record evidence; do not revive it.

Do not collapse all Android-named caches into one subsystem.

## Mandatory inventory methods

Use local repository search, not memory alone. At minimum search for and inspect relevant uses of:

- `LTCache`;
- `lru_cache`, `cache`, `cached_property` or equivalent decorators;
- explicit `*_cache`, `cache_*`, memo dictionaries/sets and bounded LRU structures;
- `clear`, `invalidate`, revision/version fields used for cache validity;
- component/item/skill/stat/target/range/path/query caches whose results may depend on mutable state;
- Android-specific caches only to classify whether they are P8-T01 semantic caches or P8-T02 presentation caches.

Create `recovery/p8_t01_cache_memoization_audit.md` unless a better bounded report name is clearly justified.

## LTCache invariant

The authoritative ordering is:

```text
mutate/publish authoritative component or owner state
-> dependent readers can now observe the new state
-> invalidate LTCache/dependent memoized results
-> future query recomputes from the published new state
```

Do not move invalidation before publication merely to make a test deterministic.

Audit every discovered LTCache mutation/invalidation call site for this order.

If current code violates the invariant and a fix requires reasoning across multiple gameplay lifecycle owners, STOP under ESC-02/ESC-09 rather than editing broadly.

## Hidden dependency proof

For gameplay-derived caches, a key is correct only if every input capable of changing the result is either:

- explicitly represented in the key/version; or
- guaranteed immutable for the cache lifetime; or
- paired with an authoritative invalidation event that covers every mutation path.

Examples of dangerous omitted dependencies include, where relevant:

- unit position/team/finished state;
- HP/mana/status/skill/item/component state;
- item uses/durability;
- game/level variables;
- phase/initiative;
- aura/FOW/regions/tilemap identity;
- DB/resource mutation in editor/runtime contexts;
- difficulty/mode/constants;
- component ordering or hook availability.

Do not assume an object identity key is sufficient when fields inside that object are mutable.

## Equivalence tests

For each retained gameplay-derived cache family, create or identify deterministic tests proving at least:

1. first query computes the expected result;
2. repeated query may hit cache without changing logical result;
3. every representative authoritative mutation that should affect the result causes recomputation or a new complete key;
4. unrelated mutation does not incorrectly alter the result;
5. cache enabled/hit path and forced-miss/cleared path produce the same logical result;
6. ordering-sensitive actions/RNG/events/hooks are not changed by cache hits.

Prefer existing public behavior/API tests over asserting private dictionary internals only.

If the cache is purely presentation/render, do not expand this task into pixel/performance work; record it for P8-T02.

## Trace proof

Run representative immutable Trace V1 scenarios covering any gameplay-derived cache surfaces found by the audit.

Minimum immutable gate even when no production code changes:

- S5 representative gameplay
- S7/S8 combat paths
- S12 aura
- S13 FOW/movement
- S14 tilemap
- S15 phase transition
- S16 fast-forward
- S17 disabled/debugger-idle/profiler-idle
- S18 game-over/restart

Add S2/S4 if any audited cache touches load/restart-derived state.

No golden regeneration.

## Existing optimization boundaries

The P6 runtime-capability audit already established that render caches remain locally owned and platform policy may decide only enablement/capacity; keys and invalidation remain with the owning highlight/menu/info/title/combat-render class.

P8-T01 may inventory those caches but must not centralize them into a global cache or move local invalidation ownership.

Render/cache/batching optimization decisions belong to P8-T02.

Audio/resource cache/backend behavior remains under accepted P6 policy and must not be reopened unless this audit proves a cache-correctness defect.

## Production-change policy

Expected production changes: **NONE**.

A bounded production fix is allowed only if all are true:

- audit/test proves one concrete cache-specific correctness defect;
- correct behavior is unambiguous from accepted semantics;
- fix is local to the cache owner/invalidation call site;
- no gameplay lifecycle/order/API redesign is required;
- immutable traces remain identical after the fix.

Do not add a new cache or broaden cache lifetime in P8-T01.

Do not change cache capacity/performance policy merely because profiling suggests it might be faster; that belongs to later Phase-8 tasks.

STOP rather than fix if correctness requires changing:

- combat solver/action/hook lifecycle;
- Event/state-machine scheduling;
- canonical load/restart;
- tilemap atomicity;
- fast-forward semantics;
- debugger/profiler semantics;
- Android platform capability boundaries;
- cross-cutting component publication architecture.

## Required regression gates

Keep green:

- Phase-3 combat transaction/lifecycle tests;
- Phase-4 tilemap atomic/barrier tests;
- Phase-5 canonical load/restart tests;
- Phase-6 platform-policy tests;
- P7 fast-forward equivalence;
- P7 debugger parity;
- P7 profiler observer equivalence;
- P7 save/load/restart UX tests;
- recovery trace/lifecycle/golden integrity.

Run focused cache/component/item/skill/stat/target/path/query tests selected from the actual inventory.

Run broader unittest discovery and report known baseline/native/test-isolation failures without repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- bounded commit
- `git show --check`
- `git status --short`

## Explicitly out of scope

Do not:

- begin P8-T02/P8-T03/P8-T04 or Phase 9;
- add speculative caches or memoization;
- tune cache sizes/capacities for FPS;
- centralize owner-local render caches;
- alter authoritative gameplay semantics to accommodate a cache;
- change Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / high**.
Escalation target: **GPT-5.6 Sol / high**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** cache correctness depends on nonlocal lifecycle semantics;
- **ESC-03** immutable trace divergence;
- **ESC-04** competing intended cache semantics affect gameplay result;
- **ESC-05** cache exposes/depends on partial authoritative state;
- **ESC-07** correctness would require platform gameplay fork;
- **ESC-08** repeated bounded fix failure;
- **ESC-09** new cross-cutting cache/publication architecture appears necessary.

Do not self-escalate.

## Gate status

**Phases 1–7 are ACCEPTED. P8-T01 is the only authorized task. P8-T02/P8-T03/P8-T04 and Phase 9+ remain blocked pending controller review.**
