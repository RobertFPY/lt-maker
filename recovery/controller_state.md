# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 3**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- P3-T01 combat lifecycle reference map: **ACCEPTED** at `ab16e7a149deaeb17d4398f298b3aebc234bc22e`
- P3-T02 Simple/Map transaction restore: **ACCEPTED** at `c20b9e02f853b0e527cf074e8168a442f353136f`
- Active task: **P3-T03 only — Restore Base/Animation/Arena combat ordering**
- Primary model: **GPT-5.6 Sol / max**
- Escalation target: **GPT-5.6 Sol / ultra**
- Escalation pre-authorized: **NO**
- P3-T04 and Phase 4+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P3-T03: **YES — STOP FOR CONTROLLER REVIEW**

## P3-T02 acceptance record

The controller accepts `c20b9e02f853b0e527cf074e8168a442f353136f` (`fix(combat): restore transaction ordering`).

Accepted evidence:

- the commit is a single direct descendant of P3-T02 authorization commit `08b3389ea62dcd0f3fa8ffff763ba05424f9e421`;
- changed production surfaces are limited to `app/engine/combat/simple_combat.py` and `app/engine/combat/map_combat.py`; remaining changes are bounded combat/profiler tests;
- no BaseCombat, AnimationCombat, arena, solver, action-system, Trace V1, comparator, manifest, golden JSONL, or project-data file changed;
- current `SimpleCombat.__init__` and `update` now reproduce the PC-reference transaction shape: start hooks -> CombatStart -> all solver phases -> ordered playback -> per-phase action application -> solver advancement before normal outer observation, followed by `clean_up0 -> clean_up1 -> clean_up2` lifecycle progression; retained differences are observer-only profiler scopes;
- current `MapCombat.update` now reproduces the PC-reference authoritative grouping: terminal detection and `clean_up0` share `begin_phase`; solver and reference visual setup share `begin_phase`; `_handle_playback()` and `_apply_actions()` share `anim`; the staged states `solve_phase`, `setup_phase_visuals`, `apply_actions`, and `cleanup0` are removed while legitimate visual waits remain;
- `BaseCombat` and `AnimationCombat` both own their own constructors/update scheduling, so P3-T02 does not implicitly restore or alter their P3-T03 semantics;
- profiler contract tests continue to assert AnimationCombat's still-staged behavior, so P3-T03 was not bypassed by weakening tests;
- reported immutable comparisons S5, S6, S9, S10, S11, S12, S16, and S17 PASS against unchanged Phase-1 oracle data;
- reported targeted suites pass except the documented pre-existing `test_counter_logic` fixture issue (`MockUnit.skills` missing); broader-suite native termination remains the pre-existing `0xC0000409` baseline and no P3-T02-specific regression was demonstrated;
- `python -m compileall -q app`, `git diff --check`, and `git show --check` PASS.

The accepted Phase-3 contract now includes:

1. Simple combat's complete mechanical solver transaction is synchronous/reference-shaped before outer observation;
2. Map combat retains presentation timing but does not publish the P3-T01-added solver/action/cleanup staging boundaries;
3. solver formulas/RNG/action contents remain unchanged;
4. Base/Animation/Arena remain the only combat-ordering implementation scope for P3-T03.

## P3-T03 — authorized implementation contract

Execute **P3-T03 only** using **GPT-5.6 Sol / max**.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Use `recovery/p3_t01_combat_lifecycle_map.md` as the accepted function/order map. Immutable Phase-1 goldens remain the oracle and may not be regenerated or weakened.

### Goal

Restore reference-shaped **authoritative** ordering for BaseCombat, AnimationCombat, and arena while retaining genuinely presentation/resource-only progressive work and Android audio policy.

Do not textual-revert the staging cluster. Separate authoritative gameplay work from presentation/resource work and change only the scheduling that violates the reference lifecycle contract.

### BaseCombat required contract

Restore the PC-reference Base transaction exactly at the logical boundaries that matter:

1. constructor/setup creates solver and combat fields;
2. constructor synchronously runs `start_combat()` and `start_event()` before the BaseCombat object can be normally observed;
3. first BaseCombat update drains **all** remaining solver phases synchronously in reference order:
   `solver.do -> playback accumulation -> _apply_actions -> setup_next_state`, repeated until terminal;
4. subsequent cleanup progression remains:
   `clean_up0 -> clean_up1 -> clean_up2`;
5. preserve `BaseCombat.handle_state_stack()` as no-op and `finalizes_turn=False`;
6. preserve BaseCombat's explicit `cleanup_combat()` override, including attacker and distinct-defender **skill and item** cleanup hooks.

Do not inherit SimpleCombat's on-map turn-finalization policy into BaseCombat.

### AnimationCombat / Arena governing boundary

AnimationCombat is not SimpleCombat with all visual waits removed. The PC reference already contains legitimate multi-frame animation states.

The rule is:

> Progressive work may remain only when it is presentation/resource/audio work and does not introduce an extra outer-frame boundary *inside a PC-reference same-update authoritative group* or expose newly advanced gameplay/RNG/actions/cleanup before the reference's required same-update follow-up.

#### Progressive work that may be retained after proof

Current Android-oriented staging may remain when its operations are demonstrably limited to:

- battle-animation/resource loading;
- paint/UI surface construction;
- health/stat display preparation that does not mutate gameplay;
- transform/revert resource lookup and pairing where no hook/RNG/action/state-stack ordering changes;
- proc icon/effect construction after the reference-authoritative inputs are already fixed;
- camera/focus/fade/pan presentation;
- streamed battle-music implementation and audio restore policy;
- profiler scopes.

A comment naming a state “visual” is not proof. Inspect calls and tests.

#### Authoritative same-update groups to restore/preserve

At minimum restore reference-equivalent grouping for these operations:

1. **Normal animation init:** when authoritative combat init begins, `start_combat()` must remain ordered with the reference init-side sprite/cursor/camera setup and `_set_stats(self.playback)` before the next normal lifecycle boundary. Resource preparation may occur before this only if it has not advanced gameplay.
2. **Arena init:** `start_combat()`, stats, battle-animation pairing, and arena offsets must retain the reference order before entering the arena fade progression.
3. **CombatStart:** once `init_pause` completes, `start_event(True)` and transition into battle-music handling must not gain an extra authoritative staging frame.
4. **Battle music / transform decision:** keep battle music selection/start plus transform decision/initiation in reference order. Android streamed music is implementation policy only and must not affect solver/hook/RNG/state ordering.
5. **Phase begin:** terminal check or `solver.do`, ordered `full_playback` accumulation, and the reference's immediate combat-effect/proc/combat-animation setup must not be split by extra outer-frame authoritative staging such as `solve_phase` before the reference visual destination is established. The later battle-animation progression before hit/action commit may remain because the reference itself is multi-frame there.
6. **Action commit points:** preserve reference `start_hit` / `spell_hit` ordering. Generated actions must be applied exactly where the reference applies them relative to playback, hit effects, and solver `setup_next_state`. Do not move action application earlier merely to make the path look atomic.
7. **Combat hit:** `clean_up0()` and the reference on-hit-effect setup belong to the same logical update when `combat_hit` is reached.
8. **HP-ready branch:** animation resume and dying-animation/wait setup must retain the reference same-update grouping once the readiness predicate becomes true.
9. **End combat before EXP:** reference `focus_exp()` and `move_camera()` happen together before entering `exp_pause`; retain that grouping.
10. **Cleanup1:** when the EXP pause condition completes, `clean_up1()` and transition to `exp_wait` keep reference order. Preserve item cleanup -> unusable/broken -> WEXP/mana/EXP -> BeforeCombatEnd internals.
11. **Terminal finish:** normal `fade_out` and arena `arena_out` complete with `finish() -> clean_up2() -> end_skip() -> return True` in one reference terminal update. Do not leave `finish()` and `clean_up2()` separated across an outer frame.

If a currently split transform/revert/resource state can remain progressive without altering any authoritative operation, it may stay. If keeping it progressive would change hook/RNG/action/cleanup/state publication relative to the reference, collapse/re-port only that unsafe boundary.

### Arena-specific protected behavior

Arena remains `AnimationCombat(arena_combat=True)`, not a new rules class.

Preserve:

- arena-specific init/fade/background path;
- real BACK behavior: `stop_arena()` only sets solver `total_rounds = 0` so termination occurs at the next solver boundary;
- arena round cap and solver behavior;
- arena-specific terminal forced-death semantics;
- `finalizes_turn=True` for AnimationCombat while BaseCombat remains `False`;
- no synthetic arena result injection.

### Protected behavior across P3-T03

Preserve exactly:

- CombatPhaseSolver formulas and RNG primitives;
- initial/final combat RNG snapshots;
- skill/item pre/start/sub/cleanup/end/post hook order/count;
- action generation and application order;
- ordered playback brushes;
- durability/use costs;
- item cleanup hooks;
- unusable/broken handling;
- WEXP/mana/EXP/rewards;
- promotion/class-change decision behavior;
- state-stack/Canto/finalizes-turn behavior;
- CombatEnd/end hooks/post hooks/death ordering;
- transform/revert compatibility;
- aura/FOW side effects;
- P3-T02 Simple/Map semantics;
- fast-forward INV-06;
- debugger/profiler INV-07;
- Android streamed battle music (`9004c67b`) and unrelated Android resource/render policy;
- project data/assets;
- immutable golden bytes.

### Authorized production surfaces

Primary:

- `app/engine/combat/base_combat.py`
- `app/engine/combat/animation_combat.py`

Narrow test-only changes are authorized.

Do not semantically change `simple_combat.py`, `map_combat.py`, `solver.py`, action/skill/item systems, or shared state-machine architecture. If a semantic production change outside Base/Animation becomes necessary, STOP under ESC-02/ESC-09 and request controller review.

### Required proof

Add/update focused tests proving at minimum:

1. Base constructor completes start hooks and CombatStart before normal outer observation;
2. Base first update drains all solver phases/actions synchronously and applies each action before solver advancement;
3. Base cleanup override still invokes required item cleanup hooks and remains no-turn;
4. Animation resource-only pre-init staging, if retained, performs no hook/RNG/action/state-stack advancement;
5. normal Animation init authoritative same-update grouping matches reference;
6. arena init authoritative grouping matches reference;
7. CombatStart/battle-music/transform decision ordering matches reference while Android streamed music stays behaviorally isolated;
8. Animation `begin_phase` no longer adds an unsafe authoritative solver-staging boundary before reference visual setup;
9. `start_hit`/`spell_hit` action/playback/solver advancement ordering remains reference-shaped;
10. `combat_hit` keeps `clean_up0` with on-hit-effect setup;
11. end-combat focus/camera and `clean_up1` ordering match reference;
12. normal fade and arena-out terminal paths execute `finish -> clean_up2 -> end_skip` without a new outer-frame split;
13. arena BACK/round-stop/forced-death behavior remains intact;
14. P3-T02 Simple/Map transaction tests remain green;
15. fast-forward and debugger/profiler observer contracts remain green;
16. Android streamed battle-music tests remain green.

### Immutable semantic comparisons

Run at minimum:

- S5 MapCombat regression guard
- S6 SimpleCombat regression guard
- S7 AnimationCombat
- S8 BaseCombat
- S9 skill proc/hooks
- S10 durability/broken
- S11 promotion/class change
- S12 aura lifecycle
- S16 fast-forward
- S17 observer equivalence

Use the existing fixtures exactly. Do not regenerate a golden after mismatch.

Arena has no dedicated persisted Phase-1 golden, so add/use bounded source/behavioral arena tests for init, BACK/round stop, cleanup, forced-death, and terminal ordering rather than inventing a new golden during P3-T03.

### Validation

Run focused Base/Animation/Arena transaction tests first, then combat/solver/action/lifecycle tests and the recovery trace/lifecycle/golden suites.

Run Android battle-music/audio tests and profiler/debugger/fast-forward tests relevant to touched code.

Run the broader unit suite required by `plan.md`; report the known baseline native termination/failures instead of repairing unrelated baseline issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit only bounded P3-T03 implementation/tests
- `git show --check`

### Explicitly out of scope

Do not:

- begin P3-T04 or Phase 4;
- change Simple/Map semantics accepted in P3-T02;
- change solver formulas/RNG to force traces;
- introduce a new combat transaction architecture;
- rewrite battle-animation/resource systems broadly;
- remove Android streamed battle music;
- change save/state-restore semantics;
- modify Trace V1/comparator/manifest/goldens;
- modify project content;
- revert the staging cluster wholesale;
- merge master.

## Escalation and stop rules

P3-T03 escalation target is **GPT-5.6 Sol / ultra**, but is **not pre-authorized**.

STOP and request controller authorization on:

- **ESC-02** nonlocal correctness root cause crossing solver/action/skill/item/shared lifecycle systems;
- **ESC-03** deterministic Trace V1 divergence after one bounded scheduling correction;
- **ESC-04** competing plausible Animation/Arena semantics;
- **ESC-05** hook/RNG/action/cleanup/inheritance invariant conflict;
- **ESC-07** Android boundary conflict where preserving platform performance requires gameplay-order divergence;
- **ESC-08** repeated local failure;
- **ESC-09** need for new cross-cutting combat/resource architecture.

Do not self-escalate.

## Gate status

**P3-T02 is ACCEPTED. P3-T03 is the only authorized task. P3-T04 and Phase 4+ remain blocked pending P3-T03 controller review.**
