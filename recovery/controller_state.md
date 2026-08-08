# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 3**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- P3-T01 combat lifecycle reference map: **ACCEPTED** at `ab16e7a149deaeb17d4398f298b3aebc234bc22e`
- Active task: **P3-T02 only — Restore Simple/Map combat transaction ordering**
- Primary model: **GPT-5.6 Sol / max**
- Escalation target: **GPT-5.6 Sol / ultra**
- Escalation pre-authorized: **NO**
- P3-T03/P3-T04 and Phase 4+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P3-T02: **YES — STOP FOR CONTROLLER REVIEW**

## P3-T01 acceptance record

The controller accepts `recovery/p3_t01_combat_lifecycle_map.md` from `ab16e7a149deaeb17d4398f298b3aebc234bc22e` as the authoritative Phase-3 combat lifecycle map.

Accepted findings:

- `CombatPhaseSolver` core logic/RNG/action generation remains the shared semantic engine; the primary regressions are caller/controller scheduling boundaries, not solver math.
- `SimpleCombat` PC reference resolves start hooks, CombatStart, all solver phases, playback accumulation and per-phase action application synchronously before the constructed combat object can be observed by normal controller updates. Current recovery spreads those authoritative phases across outer updates.
- `MapCombat` reference keeps its visual timing states, but does not publish a solver result across an outer-frame boundary before its required semantic follow-up; current recovery adds authoritative staging around terminal `clean_up0`, solver execution, and especially playback/action application.
- `BaseCombat` has the same solver-staging problem but remains assigned to P3-T03 because its no-turn semantics and explicit cleanup override must be preserved independently.
- `AnimationCombat`/arena mix authoritative hook/solver/cleanup work with legitimately progressive animation/resource/presentation work and remain P3-T03 scope.
- arena is an `AnimationCombat(arena_combat=True)` path, not a separate rules engine; its round-stop and forced-death semantics are protected.
- skill/item hook ordering, combat RNG snapshots/rolls, action generation/application, cleanup, EXP/promotion, state-stack handling, `CombatEnd`, end/post hooks and final RNG recording are mapped and protected.
- `clean_up1` ordering is protected: combat cleanup hooks precede unusable/broken handling, then WEXP/mana/EXP and `BeforeCombatEnd`.
- `clean_up2` ordering is protected: state-stack handling precedes `CombatEnd`/end hooks/final death handling.
- Android streamed battle music remains `KEEP-PLATFORM`; profiler scopes remain observer-only.
- immutable S5-S12, S16 and S17 evidence remains the semantic oracle and may not be rewritten.

## P3-T02 — authorized implementation contract

Execute **P3-T02 only** using **GPT-5.6 Sol / max**.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

### Goal

Restore reference-shaped authoritative transaction ordering for **SimpleCombat and MapCombat only** while retaining behavior-preserving profiling/presentation work.

### SimpleCombat required contract

Restore the mechanical transaction so that before a resolved `SimpleCombat` can be observed by a normal outer controller update, the following authoritative sequence has completed in reference order:

1. setup/initial combat RNG snapshot;
2. pre/start skill and item combat hooks;
3. CombatStart event trigger;
4. every solver phase;
5. ordered playback accumulation;
6. immediate application of that phase's generated actions;
7. solver `setup_next_state`/advancement until terminal.

Do not alter solver formulas, proc/hit/crit RNG, generated action contents, playback ordering, or hook bodies merely to restore scheduling.

The later cleanup transaction may retain normal state-machine/EXP presentation progression only if local semantic order remains exactly:

`clean_up0 -> clean_up1 -> EXP/promotion state handling as applicable -> clean_up2`

with the protected internals from P3-T01.

### MapCombat required contract

MapCombat may retain visual waits, map sprites, HUD timing, proc icons/effects, camera movement and animation timing, but an authoritative result may not be left externally observable in a reference-impossible partial state.

At minimum restore these logical groupings:

1. terminal detection and required `clean_up0` must not be separated by a normal outer-frame publication boundary;
2. a solver phase's authoritative computation/RNG result must receive its required immediate semantic follow-up before an unrelated lifecycle observer can act on an intermediate transaction;
3. `_handle_playback()` presentation work may remain separated only where safe, but the gameplay actions represented by that phase must not remain unapplied across an outer frame if the PC reference commits them in the same logical update;
4. solver next-state advancement must remain ordered after the action commit;
5. preserve existing natural EXP/promotion and terminal `clean_up1`/`clean_up2` ordering.

Prefer collapsing only authoritative staging states. Do **not** remove visual waits merely because they are adjacent to combat logic.

### Protected semantics

Preserve exactly:

- `CombatPhaseSolver` behavior and RNG primitives;
- initial/final combat RNG snapshots;
- skill/item hook order and count;
- action generation contents and application order;
- ordered playback brushes;
- durability/use costs;
- item cleanup hooks;
- unusable/broken handling;
- WEXP/mana/EXP/reward ordering;
- promotion/class-change behavior and player decision points;
- Canto/state-stack/finalizes-turn behavior;
- `CombatEnd`, end/post hooks and death handling;
- aura/FOW-adjacent effects;
- fast-forward INV-06;
- debugger/profiler INV-07;
- Android audio/resource policy;
- project data/assets;
- all immutable golden bytes.

### Authorized production surfaces

Primary:

- `app/engine/combat/simple_combat.py`
- `app/engine/combat/map_combat.py`

Narrow adjacent test-only/helper changes are allowed when directly necessary to prove the transaction.

`combat/solver.py`, shared skill/item systems, action semantics, BaseCombat, AnimationCombat and arena are **not** authorized for behavior changes in P3-T02 unless a minimal compile/interface adaptation is unavoidable. If a semantic change there appears necessary, STOP under the applicable ESC rule.

### Required tests and semantic proof

Add/update bounded tests proving at minimum:

1. SimpleCombat start hooks/event/solver/actions complete in reference order before normal outer-frame observation;
2. SimpleCombat each generated phase action is applied before solver advancement and before the transaction becomes externally observable;
3. MapCombat terminal `clean_up0` grouping is reference-shaped;
4. MapCombat solver/playback/action application no longer publishes a reference-impossible solver-result/action-not-applied state;
5. MapCombat visual waits remain functional and do not change semantic ordering;
6. cleanup1/cleanup2 bodies/order remain unchanged;
7. durability/broken/EXP/promotion paths remain intact;
8. fast-forward produces the same logical outcome/order/RNG;
9. debugger/profiler remain observer-only.

Run immutable semantic comparisons at minimum:

- S5 MapCombat
- S6 SimpleCombat
- S9 skill proc/hooks
- S10 durability/broken
- S11 promotion/class change if cleanup/EXP timing is touched
- S12 aura interaction
- S16 fast-forward
- S17 observer equivalence

Do not modify expected goldens after a mismatch.

Also run the focused combat/solver/action/lifecycle tests relevant to touched code and the recovery trace/lifecycle/golden suites.

Then run the broader unit suite required by `plan.md`; report known baseline termination/failures rather than repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit bounded P3-T02 implementation/tests
- `git show --check`

### Explicitly out of scope

Do not:

- begin P3-T03 or P3-T04;
- change BaseCombat ordering;
- change AnimationCombat/arena ordering;
- redesign battle-animation/resource preparation;
- remove Android streamed battle music;
- alter combat formulas/RNG to make traces pass;
- modify Trace V1/comparator/manifest/goldens;
- modify project content;
- revert staged combat commits wholesale;
- merge master.

## Escalation and stop rules

P3-T02 escalation target is **GPT-5.6 Sol / ultra**, but is **not pre-authorized**.

STOP and request controller authorization on:

- **ESC-02** nonlocal correctness root cause crossing Base/Animation/solver/shared action systems;
- **ESC-03** deterministic Trace V1 divergence after one bounded scheduling correction;
- **ESC-04** competing plausible combat semantics;
- **ESC-05** hook/RNG/action/cleanup invariant conflict;
- **ESC-08** repeated local failure;
- **ESC-09** need for new cross-cutting combat transaction architecture.

Do not self-escalate.

## Gate status

**P3-T01 is ACCEPTED. P3-T02 is the only authorized task. P3-T03/P3-T04 and later phases remain blocked pending P3-T02 controller review.**
