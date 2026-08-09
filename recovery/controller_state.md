# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 8 — Safe shared optimization reintroduction**
- Phases 1–7: **ACCEPTED**
- P8-T01 cache/memoization audit: **ACCEPTED** at `1d40f89cf33008e0592c35ef9ab094c4cc9d0b5d`
- P8-T02 render/cache/batching optimization audit: **ACCEPTED** at `3d8624136ce58e8dfb7c576515d8e4585ca79ae0`
- Active task: **P8-T03 only — Allocation/redundant-work audit**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P8-T04 and Phase 9+: **UNAUTHORIZED**
- Expected default production changes: **NONE — measure/audit/test first**
- New optimization is allowed only when a bounded owner-local redundant-work defect/opportunity has deterministic equivalence evidence and measurable benefit; speculative lifecycle/scheduler/cache changes are unauthorized.
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P8-T03: **YES — STOP FOR CONTROLLER REVIEW**

## P8-T02 acceptance record

The controller accepts `3d8624136ce58e8dfb7c576515d8e4585ca79ae0` (`docs(recovery): audit render batching`).

Accepted evidence:

- it is exactly one descendant of P8-T02 authorization commit `ec0c98cbb0441194522a751c27f3295b669ce2cd`;
- scope is audit-only: `recovery/p8_t02_render_cache_batching_audit.md`;
- no production source, tests, Trace V1 artifact, project data, assets, cache lifetime/capacity, scheduler, Event, combat, load/restart, fast-forward, debugger, or profiler behavior changed;
- retained caches are owner-local presentation/resource caches with uncached fallbacks and no gameplay selection ownership;
- fast-forward composition deferral remains shared presentation work only; logical substeps/input semantics remain protected by P7-T01;
- `request_present` / `waiting_for_present` remain explicit one-cue presentation fences, not generic work budgets;
- P4 Android tilemap preparation remains the sole approved progressive off-world preparation and still commits live state synchronously behind the Event-local barrier;
- no Android Event command deadline/budget or combat/action/load batching exists or is authorized;
- `GC-REGION` was not touched and remains explicitly NOT CERTIFIED SAFE;
- title smoke seeding was correctly deferred to P8-T03 because it removes startup allocation/redundant work but lacks a stable pixel-equivalence proof;
- battle-animation source-frame caching remains only a proposal and was not implemented because post-fetch transforms can mutate/derive draw-specific surfaces;
- required immutable S5/S7/S8/S12/S13/S14/S15/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 were reported exact;
- focused render/lifecycle/fast-forward/debugger/profiler/load/restart/recovery suites were reported green except the unchanged isolated `test_styled_text_parser` font-registry `KeyError: 'convo'` baseline; because P8-T02 changed only documentation, this failure is not a task regression and cannot be used as performance proof until its fixture/environment dependency is isolated;
- broad component-registry/import-isolation/native Windows failures remain known baseline issues;
- no new performance claim was made because no optimization changed.

## Locked findings entering P8-T03

1. **GC-REGION remains NOT CERTIFIED SAFE.** P8-T03 may not modify, reuse, extend, or benchmark it as an optimization primitive.
2. **Title smoke seed is CURRENT but NOT YET CERTIFIED as an accepted optimization.** P8-T03 must define a stable presentation-only contract and measure the redundant-work benefit before classifying it KEEP-PLATFORM. Exact pixel identity is not required if the contract intentionally permits presentation distribution differences, but gameplay RNG/state/input/Event semantics must remain untouched.
3. **Battle source-frame caching is NOT IMPLEMENTED and NOT AUTHORIZED by default.** `BattleAnimation.draw()` applies entrance scaling, flash, screen dodge, opacity, grayscale, skill tint, background/partial blend and other draw-specific transforms after retrieving the frame. Any reuse must prove mutable-surface independence and exact deterministic output for all covered transform combinations. If that proof is not cheap and complete, classify REJECT/DEFER rather than implement.
4. Settings/Sound Room `blocks_fast_forward` guards remain narrow interactive-state semantics, not a generic platform performance policy.
5. Styled-text/font isolated failure remains a fixture/baseline limitation; do not treat failing font setup as evidence for or against an allocation optimization.
6. All Phase-3 through Phase-7 correctness contracts remain protected.

---

# P8-T03 — Allocation/redundant-work audit

Execute **P8-T03 only** using **GPT-5.6 Terra / medium**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

Plan objective: measure before/after where practical, remove or retain only redundant/allocation work whose semantic and presentation contract remains equivalent, and require logical trace equality.

## Core rule

This task is not a license to micro-optimize arbitrary code. First identify repeated work and prove ownership. Then measure where practical. Only after correctness proof may one bounded owner-local optimization be implemented.

Optimization must not change:

- gameplay action/RNG/hook/Event order;
- state-machine lifecycle or input opportunities;
- fast-forward logical semantics;
- canonical load/restart or tilemap publication;
- combat solver/cleanup;
- debugger/profiler observer behavior;
- P6 platform capability boundaries;
- project data or immutable recovery oracles.

## Mandatory inventory

Fresh-search current runtime for repeated allocation/redundant work, including:

- repeated `copy`, `copy_surface`, `convert`, `convert_alpha`, scale, color/tint/translucency operations;
- per-frame list/set/dict construction in hot draw/update paths;
- repeated sorting/filtering/layout calculations;
- repeated surface/text construction where ownership/lifetime is clear;
- repeated resource lookup/preparation already covered by P6 policy;
- title-screen particle prefill/seed paths;
- battle-animation draw transforms;
- combat UI/damage-number/highlight/menu/info/unit-menu composition;
- existing profiler scopes/counters that identify repeated work;
- post-reference optimizations that replaced repeated work with staged/cached work.

Do not count small allocations as optimization targets merely because they exist. Record frequency/hot-path evidence.

Classify candidates as:

- KEEP — MEASURED SAFE REDUCTION
- KEEP-PLATFORM — PRESENTATION/RESOURCE POLICY
- NO-OPPORTUNITY — COST/TRIVIALITY DOES NOT JUSTIFY CHANGE
- DEFER — INSUFFICIENT STABLE OUTPUT CONTRACT
- REJECT — MUTABLE/ORDERING/LIFECYCLE RISK
- DEAD/UNUSED
- ESCALATE

Create `recovery/p8_t03_allocation_redundant_work_audit.md`.

## Measurement rule

For each candidate that may be changed or newly certified:

- establish a baseline operation/allocation/count/timing metric using a deterministic owner-level benchmark or profiler counter where practical;
- run enough repeated iterations to avoid one-off startup noise;
- report both baseline and candidate/optimized result;
- do not use FPS alone;
- do not make wall-clock timing part of logical correctness;
- if timing is too noisy, use deterministic operation/call/allocation counts plus a bounded timing sanity check.

A claimed optimization without before/after evidence is not accepted.

## Title smoke seed decision

Audit the existing Android title-start path:

Desktop currently creates `MapParticleSystem(... Smoke ...)` then performs `prefill()`.
Android render optimization calls `seed_title_smoke(...)` instead.

P8-T03 must:

1. inspect `particles.MapParticleSystem.prefill` and `seed_title_smoke`;
2. define the stable title-presentation contract before comparison;
3. prove both paths preserve at minimum:
   - particles enabled/disabled semantics;
   - same particle type/family;
   - valid bounds;
   - stable count/density envelope appropriate to title startup;
   - ongoing update/draw lifecycle;
   - no gameplay RNG consumption/change;
   - no game-state/Event/input/state-stack mutation;
4. measure the startup work reduced by seed vs 300-style prefill updates;
5. classify KEEP-PLATFORM only if the presentation difference is intentional, bounded, and independent of gameplay semantics;
6. otherwise DEFER or REJECT; do not force pixel identity by adding expensive work.

Do not alter title gameplay routing/music/Event semantics.

## Battle-animation source-frame candidate

Do NOT implement a frame cache merely because repeated copying is measurable.

First prove the complete transform chain around `BattleAnimation.get_image/draw`, including:

- entrance scale;
- flash/flash-image state;
- screen dodge;
- blend/partial blend;
- opacity/alpha conversion;
- pair-up grayscale;
- skill flicker tint/time dependence;
- palette/effect ownership;
- background blend;
- child/effect drawing;
- any Android render-state advancement.

A retained source surface must never be mutated by a draw-specific transform or reused with transformed pixels from a prior draw.

If complete deterministic independence cannot be proven with a narrow test matrix, classify **REJECT/DEFER** and make no production change.

No new global frame cache.

## Other candidates

For any other candidate:

- owner-local only;
- no new service locator;
- no global mutable cache;
- no extending `GC-REGION` or gameplay-derived cache lifetime;
- no Event/combat/load/state-machine scheduling changes;
- no worker-thread gameplay mutation;
- no change from authoritative update to draw or draw to authoritative update unless the state is proven presentation-only and P8-T02 already classified that ownership safe.

## Production change policy

Expected default: **audit/tests/report only**.

At most bounded production optimization(s) are allowed when all are true:

1. deterministic before/after measurement shows meaningful redundant work/allocation reduction;
2. owner and lifetime are local and explicit;
3. identical logical state/Trace V1 is proven;
4. deterministic output/presentation contract is satisfied;
5. uncached/fallback behavior remains correct where relevant;
6. no accepted lifecycle/platform boundary is reopened.

If correctness requires a new cross-cutting cache, scheduler, lifecycle phase, worker authority, or gameplay publication boundary, STOP under ESC-02/ESC-09.

## Tests and regressions

Use focused suites selected from actual candidates. At minimum retain green:

- P8 cache/memoization tests;
- P8 render/cache owner tests;
- Phase-3 combat lifecycle;
- P4 tilemap atomicity/barrier;
- P5 canonical load/restart;
- P6 platform policy;
- P7 fast-forward equivalence;
- P7 debugger parity;
- P7 profiler observer equivalence;
- P7 save/load/restart UX;
- recovery trace/lifecycle/golden integrity.

If touching title smoke, add deterministic owner-level tests for the stable presentation contract and RNG/game-state non-interference.

If touching battle-animation draw/allocation, add deterministic surface/state tests for every transform class affected; do not add host-dependent screenshot goldens.

`test_styled_text_parser` may be reported with its unchanged `FONT['convo']` fixture failure, but do not use that failing suite as an optimization proof until the test setup dependency is isolated without changing product semantics.

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

Run S2/S4 if any changed candidate participates in title/load/restart transition surfaces or restored world presentation.

No Trace V1 schema/comparator/normalizer/manifest/golden changes.

Any unexplained logical divergence => STOP under ESC-03.

## Broad validation

Run broader unittest discovery and report existing component-registry/import-isolation/native Windows failures unchanged.

Then run:

- `python -m compileall -q app`
- `git diff --check`
- `git status --short`
- `git diff --name-only`

Commit only bounded P8-T03 audit/tests and explicitly justified production optimization(s), if any.

Then:

- `git show --check`
- `git status --short`

## Explicitly forbidden

Do not:

- begin P8-T04 or Phase 9;
- modify or extend GC-REGION;
- add speculative gameplay memoization;
- create global render/frame cache architecture;
- reintroduce Event command budgeting;
- change action/combat/load/tilemap/state-machine scheduling;
- alter fast-forward/debugger/profiler semantics;
- change Trace V1/goldens;
- modify project data/assets;
- merge master.

## Escalation

Primary: **GPT-5.6 Terra / medium**.
Escalation target: **GPT-5.6 Sol / high**.
Pre-authorized: **NO**.

STOP on ESC-02, ESC-03, ESC-04, ESC-05, ESC-07, ESC-08, ESC-09.
Do not self-escalate.

## Report

TASK RESULT
FILES CHANGED
ALLOCATION/REDUNDANT-WORK INVENTORY
MEASUREMENT RESULT
TITLE SMOKE RESULT
BATTLE FRAME RESULT
OTHER CANDIDATES RESULT
LOGICAL EQUIVALENCE RESULT
PRESENTATION CONTRACT RESULT
TRACE RESULT
COMBAT RESULT
TILEMAP RESULT
LOAD/RESTART RESULT
FAST-FORWARD RESULT
DEBUGGER/PROFILER RESULT
PRODUCTION CHANGES
TESTS ADDED/UPDATED
COMMANDS RUN
TEST RESULTS
REFERENCE/GOLDEN COMPARISON
KNOWN RISKS
UNRESOLVED QUESTIONS
ESCALATION TRIGGERS
COMMIT SHA
WORKING TREE STATUS
NEXT ACTION: CONTROLLER REVIEW

STOP FOR CONTROLLER REVIEW.
