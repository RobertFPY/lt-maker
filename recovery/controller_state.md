# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 3**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- P3-T01 combat lifecycle reference map: **ACCEPTED** at `ab16e7a149deaeb17d4398f298b3aebc234bc22e`
- P3-T02 Simple/Map transaction restore: **ACCEPTED** at `c20b9e02f853b0e527cf074e8168a442f353136f`
- P3-T03 Base/Animation/Arena ordering restore: **ACCEPTED** at `3ab40895ef7170e01e55dc4f1bf2b63889383832`
- Active task: **P3-T04 only — Combat feature/fix preservation sweep**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- Phase 4+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P3-T04: **YES — STOP FOR CONTROLLER REVIEW**

## P3-T03 acceptance record

The controller accepts `3ab40895ef7170e01e55dc4f1bf2b63889383832` (`fix(combat): restore base and animation order`).

Accepted evidence:

- the commit is a single direct descendant of P3-T03 authorization commit `1b79b08017908de15515f367d9011172f6366ccc`;
- changed production surfaces are limited to `app/engine/combat/base_combat.py` and `app/engine/combat/animation_combat.py`; remaining changes are bounded transaction/profiler tests;
- no SimpleCombat, MapCombat, solver, action system, skill/item system, Trace V1, comparator, manifest, golden JSONL, save schema, or project-data file changed;
- BaseCombat now matches the PC-reference transaction shape: constructor performs `start_combat()` and `start_event()` synchronously; first update drains all solver phases as `solver.do -> playback -> action application -> setup_next_state`; later cleanup remains `clean_up0 -> clean_up1 -> clean_up2`;
- BaseCombat keeps `finalizes_turn=False`, `handle_state_stack()` as a no-op, and its explicit attacker/distinct-defender skill+item `cleanup_combat()` override;
- AnimationCombat restores the reference same-update authoritative groups for normal init, arena init, CombatStart transition, battle-music/transform decision, solver-to-visual-destination setup, `combat_hit`, HP-ready dying setup, end-combat focus/camera, `clean_up1`, and normal/arena terminal finish;
- reference `start_hit`/`spell_hit` action semantics remain unchanged: generated actions are applied, solver advances, then playback is handled at the existing reference commit points;
- retained staged states are limited to resource/presentation work such as battle-animation loading, paint/UI preparation, entrance pairing, transform/revert resource rebuild/pairing, pre-proc/proc visual construction, delayed-death animation setup, fades, camera/HUD timing, and profiler instrumentation; focused tests assert these pre-init resource states do not run hooks, solver work, cleanup, gameplay state publication, or generated actions;
- arena remains `AnimationCombat(arena_combat=True)`; BACK/`stop_arena()` only sets solver `total_rounds = 0`, `finalizes_turn=True` remains, and arena-specific forced-death/terminal behavior is preserved;
- Android streamed battle-music and map-track restore behavior was not changed and remains platform implementation policy;
- reported immutable comparisons S5, S6, S7, S8, S9, S10, S11, S12, S16 and S17 PASS against unchanged Phase-1 oracle data;
- focused transaction/profiler tests report **54/54 PASS**, clean-process combat support modules **39/39 PASS**, recovery trace/lifecycle/golden **51/51 PASS**, and observer/Android suites **153 PASS**;
- documented `test_combat_calcs` MockUnit fixture error, shared-process `_Uses.tag` isolation pollution, and broader-suite `0xC0000409` editor-workspace termination remain baseline/test-isolation issues and were not modified;
- `python -m compileall -q app`, `git diff --check`, and `git show --check` PASS.

The accepted Phase-3 lifecycle contract now includes:

1. Simple, Map, Base, Animation, and Arena authoritative combat ordering is reference-shaped at the PC-reference logical boundaries;
2. presentation/resource work may remain progressive only when it does not advance hooks, RNG, actions, cleanup, state-stack semantics, or final logical state;
3. solver formulas/RNG primitives/action contents/playback contents remain shared and unchanged;
4. Android streamed battle music remains platform policy;
5. P3-T04 is a preservation/correctness sweep, not permission to redesign combat lifecycle architecture.

## P3-T04 — authorized preservation sweep

Execute **P3-T04 only** using **GPT-5.6 Terra / high**.

Escalation target is **GPT-5.6 Sol / high**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Use `recovery/p3_t01_combat_lifecycle_map.md`, the accepted P3-T02/P3-T03 implementations, root `AGENTS.md`, and immutable Phase-1 goldens as evidence.

### Goal

Verify and, only where a demonstrated regression exists, re-port bounded later correctness/features that must survive the combat ordering restoration.

P3-T04 is **not** a general combat refactor. Do not reopen accepted P3-T02/P3-T03 transaction architecture unless a concrete preservation failure proves a bounded correction is required. If the fix requires lifecycle architecture changes, STOP and escalate.

### Required preservation surfaces

Audit and verify at minimum:

1. **Cleanup ordering**
   - item/skill `cleanup_combat` hooks;
   - unusable/broken handling;
   - WEXP/mana/EXP;
   - `BeforeCombatEnd`;
   - `clean_up2` state-stack handling, `CombatEnd`, rewards/supports, end/post hooks, RNG record, death.

2. **Durability/use costs**
   - use count/durability deductions occur exactly once;
   - broken/unusable handling occurs after cleanup hooks;
   - alerts/removal behavior remains intact;
   - BaseCombat explicit item cleanup is preserved.

3. **Promotion cancel/finalization**
   - normal on-map combat finalizes the tactical turn correctly;
   - Base/prep item-use promotion does not consume/finalize a tactical map turn;
   - cancel/confirm paths preserve intended later feature behavior;
   - EXP/promotion state-stack ownership remains correct.

4. **Skill cache invalidation**
   - verify mutable component/skill state publication still invalidates the relevant LTCache/derived caches where required;
   - do not add broad cache clears unless a specific stale-cache bug is demonstrated;
   - preserve independent correctness fixes rather than reverting to reference bugs.

5. **Aura interactions**
   - aura child skills remain derived rather than serialized;
   - combat add/remove/death/cleanup interactions do not leave stale aura children or aliases;
   - authoritative teardown path remains intact.

6. **Fast-forward**
   - INV-06: timing/presentation may differ but hooks, RNG, actions, cleanup order, state stack and final logical result must remain identical OFF vs ON;
   - no replay of raw input across extra logical updates.

7. **Combat-related debugger/profiler behavior**
   - INV-07 idle observers do not mutate combat state/order/RNG/cache validity;
   - profiler scopes remain observer-only;
   - debugger mutating commands, if explicitly used, remain separate from idle-observer proof.

8. **Android combat presentation/platform policy**
   - streamed battle music remains platform-only;
   - Android render/UI caches/resource staging remain allowed only if they do not alter authoritative combat ordering;
   - do not trade gameplay semantics for frame pacing in P3-T04.

### Required method

For each preservation item:

- identify the current code path and provenance of any post-reference fix;
- compare against the accepted PC-reference lifecycle contract;
- classify as already-preserved, bounded regression needing re-port, or later-phase/out-of-scope;
- add or tighten focused tests where the invariant is not already proved;
- modify production only for a demonstrated bounded preservation regression.

Do not make speculative cleanup changes.

### Immutable semantic proof

Run at minimum:

- S5 MapCombat
- S6 SimpleCombat
- S7 AnimationCombat
- S8 BaseCombat
- S9 real skill proc/hooks
- S10 durability/broken
- S11 promotion/class change
- S12 aura lifecycle
- S16 fast-forward OFF/ON
- S17 debugger/profiler observer equivalence

All comparisons must use existing immutable oracle bytes. Do not regenerate or weaken a golden.

### Targeted tests

Run/add focused tests for:

- cleanup hook order and count;
- item uses/durability/broken/unusable behavior;
- BaseCombat cleanup override;
- promotion confirm/cancel/finalizes-turn behavior for map versus base/prep combat;
- skill/cache invalidation affected by combat state mutation;
- aura add/remove/death/load/teardown interactions;
- fast-forward combat equivalence;
- debugger/profiler idle equivalence;
- Android streamed battle music and combat UI/resource policy;
- P3-T02 and P3-T03 transaction tests as regression guards.

Run the broader unit suite required by `plan.md`; report documented baseline failures/native termination/test-isolation pollution rather than repairing unrelated code.

Also run:

- `python -m compileall -q app`
- `git diff --check`
- commit only bounded P3-T04 preservation changes/tests/evidence
- `git show --check`

### Deliverable

Create/update a bounded preservation record:

`recovery/p3_t04_combat_preservation.md`

It must record each required preservation item, evidence, classification, tests, any production change, and remaining risks.

Production changes are allowed only where the sweep demonstrates a real preservation regression. If no production changes are needed, the task may be evidence/tests/report only.

### Explicitly out of scope

Do not:

- begin Phase 4;
- redesign combat lifecycle/state architecture;
- alter solver formulas or RNG to force tests;
- modify Trace V1/comparator/manifest/golden JSONL;
- modify project data;
- change save/state-restore semantics;
- remove Android streamed battle music;
- perform broad cache invalidation/refactors without a demonstrated bug;
- repair unrelated baseline test fixtures or editor native termination;
- merge master.

## Escalation and stop rules

STOP and request controller authorization on:

- **ESC-02** preservation failure has a nonlocal root cause outside bounded combat feature/fix code;
- **ESC-03** deterministic immutable trace divergence after one bounded correction;
- **ESC-05** accepted cleanup/hook/RNG/state invariant fails;
- **ESC-07** Android platform optimization conflicts with shared gameplay semantics;
- **ESC-08** repeated local failure;
- **ESC-09** repair requires combat lifecycle architecture changes.

Do not self-escalate.

## Gate status

**P3-T03 is ACCEPTED. P3-T04 is the only authorized task. Phase 4+ remains blocked pending P3-T04 controller review.**
