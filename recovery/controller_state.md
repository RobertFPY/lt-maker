# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 8 — Safe shared optimization reintroduction**
- Phases 1–7: **ACCEPTED**
- P8-T01 cache/memoization audit: **ACCEPTED** at `1d40f89cf33008e0592c35ef9ab094c4cc9d0b5d`
- P8-T02 render/cache/batching audit: **ACCEPTED** at `3d8624136ce58e8dfb7c576515d8e4585ca79ae0`
- P8-T03 allocation/redundant-work audit: **ACCEPTED** at `869e30d66f8005ef088f85083dce05cea661876a`
- Active task: **P8-T04 only — Android-only performance retuning**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- Phase 9+: **UNAUTHORIZED**
- Controller gate after P8-T04: **YES — STOP FOR CONTROLLER REVIEW**
- Android performance work must remain behind accepted platform-policy boundaries and preserve exact logical traces.
- FPS/frame-time improvement alone is never sufficient evidence.
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**

## P8-T03 acceptance record

The controller accepts `869e30d66f8005ef088f85083dce05cea661876a` (`test(android): certify title smoke seeding`).

Accepted evidence:

- it is exactly one descendant of P8-T03 authorization commit `88a4ac57d11502302b10160bdd3ddea654685c03`;
- scope is test/evidence only: `app/tests/test_title_smoke_seed.py` and `recovery/p8_t03_allocation_redundant_work_audit.md`;
- no production source, Trace V1 artifact, project data, asset, scheduler, gameplay cache, combat, load/restart, tilemap, fast-forward, debugger, or profiler behavior changed;
- title smoke seeding now has a stable presentation-only contract: same `Smoke` family, exact `system.abundance` population, valid lifetime envelope, ordinary later update/draw ownership, and no requirement for pixel-identical startup coordinates;
- deterministic tests prove the helper does not consume/change engine `static_random` seed/combat/growth/other RNG state;
- source inspection confirms `seed_title_smoke()` touches the supplied particle system and Python presentation RNG only; it does not call `Smoke.update()` or dispatch Event/gameplay/state/input/save/action work;
- deterministic work-count proof shows desktop-style `prefill()` performs exactly 300 particle-system updates while `seed_title_smoke()` performs zero such updates;
- the audit reports 31-run host measurements showing substantial startup-work reduction while both paths retain 11 title Smoke particles; timing remains supporting evidence rather than a logical oracle;
- title smoke is therefore certified **KEEP-PLATFORM — PRESENTATION/RESOURCE POLICY**;
- battle-animation source-frame caching is explicitly **REJECTED** because draw output depends on entrance scaling, flash/screen-dodge, opacity, grayscale, time-dependent skill tint, blend/partial blend, palette/effect state and child/effect ownership; no speculative frame cache was added;
- existing combat UI/highlight/menu caches expose no new proven allocation opportunity;
- styled-text allocation remains deferred because the isolated `FONT['convo']` baseline is not a valid optimization proof environment;
- `GC-REGION` remains untouched and **NOT CERTIFIED SAFE**;
- required immutable S5/S7/S8/S12/S13/S14/S15/S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 were reported exact;
- focused cache/render/combat/tilemap/load/fast-forward/debugger/profiler/recovery suites were reported green; known shared-registry/native Windows failures remain baseline constraints.

## Locked findings entering P8-T04

1. **One gameplay core.** Android retuning may alter platform presentation/resource policy only, never gameplay semantics/order.
2. **GC-REGION remains NOT CERTIFIED SAFE.** Do not touch, benchmark as a new target, extend, or add readers into its mutation gap.
3. **Title smoke seed is ACCEPTED.** Do not reopen its presentation contract or add work merely for pixel identity.
4. **Battle source-frame caching remains REJECTED.** Do not add a frame cache or reuse transformed mutable surfaces without a new controller decision.
5. **Styled-text allocation remains DEFERRED.** The existing font-registry fixture failure cannot be used as performance evidence.
6. **Settings/Sound Room `blocks_fast_forward` remains a narrow interactive-state semantic guard**, not a generic performance knob.
7. **Event command scheduling is shared and synchronous.** The removed Android wall-clock Event deadline must not return.
8. **P4 tilemap progressive work is off-world only.** `_android_tilemap_pending`/Event-local barrier and one synchronous live commit are protected.
9. **P5 canonical load/restart is protected.** Worker read/unpickle only; authoritative hydrate/install remains one logical main-thread transaction.
10. **P7 fast-forward/debugger/profiler contracts are protected.** No retune may alter input edges, outcomes, command execution, or observer state.

---

# P8-T04 — Android-only performance retuning

Execute **P8-T04 only** using **GPT-5.6 Terra / high**.

Escalation target: **GPT-5.6 Sol / max**, not pre-authorized.

Prerequisite satisfied: P8-T01 through P8-T03 are accepted.

This is the final Phase-8 gate. Use profiler/measurement evidence and optimize only behind the accepted P6 platform boundaries. A valid result may be audit/evidence-only if no additional Android retune is justified.

## Goal

Retune existing Android-only performance policy where measurable evidence shows a bounded opportunity and exact logical equivalence can be preserved.

Do not search for performance by changing gameplay lifecycle.

The permitted policy families are the already-accepted P6 seams:

- **CAP-AUDIO** — physical cached/streamed backend, preload/flush/release only;
- **CAP-RESOURCE** — immutable/background presentation-resource preparation only;
- **CAP-RENDER-CACHE** — owner-local presentation cache enablement/capacity only;
- **CAP-WORK-BUDGET** — numeric budget only for the already-approved off-world tilemap preparation;
- narrow Android UI/input presentation mechanics where they do not inject gameplay actions.

No new generic platform abstraction or service locator is authorized.

## Evidence-first inventory

Before changing production code, inventory current Android-only performance knobs and profiler evidence, including at minimum:

- `OffWorldWorkBudget` and the current Android tilemap preparation deadline;
- owner-local Android render-cache capacities/hit-miss behavior for highlight, title/menu/settings/Sound Room, info/unit menu and combat UI;
- title smoke seed as an accepted baseline, not a new target;
- audio/resource preload/flush/streamed fallback behavior;
- render/update profiler counters that identify real Android-specific cost;
- any existing Android-specific branch that suppresses, moves, or reduces presentation work.

For every candidate record:

- owner and accepted capability family;
- current knob/value;
- baseline profiler/call-count/memory evidence;
- expected benefit;
- semantic risk;
- presentation/resource risk;
- exact before/after measurement method;
- trace coverage;
- decision: `KEEP-AS-IS`, `RETUNE-LOCAL`, `DEFER-NO-DEVICE-EVIDENCE`, `REJECT-SEMANTIC-RISK`, or `ESCALATE`.

Create `recovery/p8_t04_android_performance_retuning.md`.

## Measurement requirements

A production retune is allowed only with before/after evidence.

Preferred evidence:

- Android-device profiler/frame-time distributions when available;
- deterministic operation/hit-miss/allocation counts;
- host-side microbenchmarks only for pure local code-path cost, clearly labeled as host evidence;
- memory/cache occupancy bounds where relevant.

If no Android device/JNI runtime is available, do not claim device FPS/frame-time gains. A host-proven reduction may justify a purely local presentation/resource retune only when the benefit is structural and semantics/output ownership are already proven; otherwise classify `DEFER-NO-DEVICE-EVIDENCE`.

Do not use a single timing sample. Report repeated samples/median or a stable aggregate.

## CAP-WORK-BUDGET lock

The current work budget applies only to pending/off-world tilemap construction.

A numeric budget change is allowed only if all of the following are proven:

1. pending build remains completely outside live gameplay state;
2. Event-local `_android_tilemap_pending` still blocks next command/input/movement as accepted;
3. final live tilemap/board/boundary/unit/region/aura/FOW publication remains one synchronous transaction;
4. rollback remains atomic;
5. no Event command wall-clock budget is introduced;
6. logical Trace V1 is identical;
7. before/after Android frame-time or equivalent platform evidence justifies the numeric change.

Without real Android evidence, keep the current budget unchanged.

## CAP-RENDER-CACHE lock

Capacity/enablement retuning is allowed only for owner-local presentation caches already certified in P8-T02.

For any capacity change prove:

- cache key/invalidation contract is unchanged and complete for presentation output;
- hit/miss cannot alter menu selection, command availability, state transitions, input, combat, FOW/aura, save/restart or observer semantics;
- memory remains bounded;
- before/after hit/miss or allocation evidence shows benefit;
- uncached fallback remains correct.

Do not centralize caches or extend gameplay-derived cache lifetime.

`GC-REGION` is forbidden.

## CAP-AUDIO / CAP-RESOURCE lock

Retuning may change preload/cache/flush/backend thresholds only if physical playback/resource behavior remains presentation policy.

Do not change:

- semantic music NID selection;
- battle/event/state ordering;
- whether combat or a transition completes;
- save/load resource authority;
- worker access to `game`, Event, solver, state machine or mutable registries.

Stream/backend failure must keep the accepted fallback path.

## Explicitly forbidden performance techniques

Do not:

- reintroduce Android Event command deadlines;
- yield between authoritative Actions/Event commands/combat cleanup steps;
- time-slice GameState hydration;
- move authoritative gameplay mutation to workers;
- defer live tilemap publication;
- add Android-only gameplay branches;
- change fast-forward substep count/edge semantics;
- change debugger/profiler observer semantics;
- use SAVE as pristine restart truth;
- add battle source-frame caching;
- modify `GC-REGION`;
- fix styled-text/font baseline in this task;
- add speculative caches or global cache architecture.

If a performance target requires any of these, classify `REJECT-SEMANTIC-RISK` or STOP under escalation rules.

## Production change policy

Production changes are optional, not required.

Each production retune must be:

- Android/platform-policy only;
- owner-local;
- supported by before/after measurement;
- protected by deterministic regression tests;
- exact under logical Trace V1;
- bounded in memory/resource lifetime;
- individually explainable/revertible.

Prefer one small retune over a bundle of unrelated tweaks.

Do not change shared gameplay code merely to improve Android profiling numbers.

## Required regressions

Always retain green:

- P8-T01 cache/memoization evidence;
- P8-T02 render/cache/batching evidence;
- P8-T03 title-smoke/allocation evidence;
- Phase-3 combat lifecycle;
- P4 tilemap atomicity/barrier/rollback;
- P5 canonical load/restart/compatibility;
- P6 platform-policy/audio/work-budget tests;
- P7 fast-forward equivalence;
- P7 debugger parity;
- P7 profiler observer-equivalence;
- P7 save/load/restart UX;
- recovery trace/lifecycle/golden integrity.

Run focused owner tests for every knob actually changed.

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

Run S2/S4 if any changed policy participates in title/load/restart resource or transition behavior.

No Trace V1 schema/comparator/normalizer/manifest/golden changes.

Any unexplained logical divergence => STOP under ESC-03.

## Performance result format

For each changed candidate report:

```text
CANDIDATE:
CAPABILITY:
BASELINE:
RETUNED:
MEASUREMENT ENVIRONMENT:
SAMPLE COUNT:
BENEFIT:
MEMORY IMPACT:
LOGICAL TRACE:
OWNER TESTS:
ROLLBACK/FALLBACK:
DECISION:
```

If no production retune is justified, explicitly say so and preserve all current values.

## Broad validation

Run broader unittest discovery and report existing component-registry/import-isolation/native Windows failures unchanged.

Then run:

- `python -m compileall -q app`
- `git diff --check`
- `git status --short`
- `git diff --name-only`

Commit only:

- `recovery/p8_t04_android_performance_retuning.md`;
- focused tests/measurement harnesses;
- explicitly justified bounded Android-policy retune(s), if any.

Then run:

- `git show --check`
- `git status --short`

## Escalation

Primary: **GPT-5.6 Terra / high**.
Escalation target: **GPT-5.6 Sol / max**.
Pre-authorized: **NO**.

STOP on ESC-02, ESC-03, ESC-04, ESC-05, ESC-07, ESC-08, ESC-09.

In particular:

- ESC-07 if Android performance requires gameplay semantic divergence;
- ESC-02/ESC-09 if a local retune requires cross-cutting lifecycle/cache/scheduler architecture;
- ESC-03 on any immutable trace divergence.

Do not self-escalate.

## Gate status

**P8-T01/P8-T02/P8-T03 are ACCEPTED. P8-T04 is the only authorized task. Phase 9+ remains blocked pending controller review.**
