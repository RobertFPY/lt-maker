# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 3**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- P2-T01 restore audit/map: **ACCEPTED**
- P2-T02 authoritative restore implementation: **ACCEPTED** at `0a6b854e0943905dc472986d4a2d9e5f95962ab4`
- P2-T03 staged-workaround cleanup: **ACCEPTED** at `9efad11a914502a10047789ec8cb44ba3e78494a`
- Active task: **P3-T01 only — Build combat lifecycle reference map**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- P3-T02 implementation: **UNAUTHORIZED**
- P3-T03/P3-T04 and Phase 4+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P3-T01: **YES — STOP FOR CONTROLLER REVIEW**

## Phase 2 acceptance record

The controller accepts commit `9efad11a914502a10047789ec8cb44ba3e78494a` (`refactor(restore): remove staged workarounds`) as closing Phase 2.

Accepted evidence:

- the commit is a single direct descendant of the P2-T03 controller authorization commit `c2d52c605d3883eb3481b5906721100d2c6758da`;
- changed production surfaces are limited to `app/engine/game_state.py` and `app/engine/state.py`; remaining changed files are bounded recovery/lifecycle tests;
- no save schema, slot kind, Trace V1 schema/comparator, manifest, golden JSONL, or project-data file changed;
- the pre-existing S2/S4 runner drift was corrected test-only by allowing `_prepare_playable_game(..., initial_states=[])` for S2/S4 while all other scenarios retain the existing `free` default;
- PC-reference S2/S4 reruns were reported byte-identical across two runs and recovery exact-compared against the immutable goldens;
- `_staged_state_data` and `commit_staged_state()` were removed after P2-T02 eliminated all new-runtime writers/consumers;
- `prepare_for_load()` was retained because failed-restore cleanup still requires clearing board/overworld/controller fields not fully covered by `GameState.clear()`;
- `MapState.update_visuals()` camera/tilemap and map-view/tilemap guards were removed only after P2-T02 made the staged partial-world condition impossible;
- provenance confirms those two guards were introduced specifically by `390638ac` and `6bd9da4b` to tolerate staged loading before tilemap readiness;
- settings transparent-map guards and debugger cursor/board/tilemap guards were retained because they remain valid for independent title/no-map/observer paths;
- `Camera.update()` and `MapView.update_visuals()` dereference `game.tilemap`, so their now-unconditional execution under a live `MapState` relies on the restored INV-03 lifecycle invariant: a map state cannot become normally observable without a complete tilemap/world;
- relevant immutable semantic comparisons S1/S2/S4/S12/S13/S14/S18 PASS after cleanup;
- reported targeted suites pass: recovery/atomic/lifecycle/golden **65/65**, title/load/restart/debugger/settings/Android **118/118**;
- `python -m compileall -q app`, `git diff --check`, and `git show --check` PASS;
- broader-suite `0xC0000409` termination/baseline failures remain pre-existing and were not modified.

Phase 2 therefore establishes the following accepted contract for all later work:

1. save read/unpickle may remain Android worker-side;
2. authoritative `GameState` hydration is one synchronous main-thread logical transaction;
3. no saved/gameplay state stack is published against a partial world;
4. destination installation occurs exactly once;
5. no `_staged_state_data` compatibility path remains;
6. map lifecycle now assumes complete tilemap/world validity when a live `MapState` runs;
7. later phases must not reintroduce frame-sliced authoritative world mutation.

## P3-T01 — authorized audit scope

Execute **P3-T01 only** using **GPT-5.6 Terra / high**.

This is an **audit/reference-map task only**. It does not authorize combat implementation or gameplay repair.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

The immutable Phase-1 combat-related goldens remain the behavioral oracle, especially S5-S10, S11 where promotion/EXP is relevant, S12 where combat-adjacent aura effects matter, S16 fast-forward, and S17 observer equivalence. Do not regenerate or weaken them.

### Required combat surfaces

Audit reference versus current recovery for all combat transaction paths and every inheritance/caller relationship that can alter gameplay ordering, including at minimum:

- `SimpleCombat`;
- `MapCombat`;
- `BaseCombat`;
- `AnimationCombat`;
- arena combat paths and arena wrappers/states;
- solver creation, initialization, advancement, action generation, and RNG consumption;
- pre-combat proc setup and skill/item hook dispatch;
- playback production/consumption;
- action application timing;
- `clean_up1`, `cleanup_combat`, broken/unusable handling, EXP/mana/wexp/rewards, `clean_up2`, state-stack handling, and `end_combat`;
- item durability/use costs and item/skill cleanup hooks;
- promotion/class-change transitions reached from combat EXP;
- transform animation preparation;
- battle animation/resource preparation;
- battle music selection/start/stop/streaming;
- fast-forward interaction with combat advancement;
- debugger/profiler observer paths touching combat.

Inspect the relevant post-reference commits individually, especially the staged combat cluster `78acb08a` through `fff0145d`, plus related battle-music/transform/proc changes such as `29d1b65d`, `9004c67b`, `b323c01a`, `61d03cee`, `1b87bc85`, and any follow-up commits discovered in history. Never classify a mixed commit wholesale.

### Required semantic questions

For every combat path answer explicitly:

1. what is the complete synchronous PC-reference transaction order;
2. which objects/state stacks are authoritative before, during, and after combat;
3. where RNG is consumed and whether staging changes RNG timing/order;
4. exact hook ordering and count for skill/item pre/start/sub/cleanup/end/post combat hooks;
5. when actions are generated versus applied;
6. when playback is produced and whether playback is gameplay-authoritative or presentation-only;
7. when durability/use costs, broken/unusable removal, EXP/wexp/mana/rewards, promotion, state transitions, and `end_combat` occur;
8. whether current recovery yields or stages across frames at any point where unrelated state/lifecycle code can observe an intermediate gameplay transaction;
9. which optimizations are pure computation/resource preparation and can remain shared/platform-specific;
10. which later intended fixes/features must be preserved even if current staging is removed.

The accepted cleanup invariant from root `AGENTS.md` remains authoritative. In particular, verify the actual reference/current order around:

- `SimpleCombat` actions;
- `clean_up1`;
- `cleanup_combat` including item cleanup hooks;
- broken/unusable handling and EXP;
- `clean_up2`;
- state-stack handling;
- `end_combat`.

Do not assume class inheritance preserves this order. Trace exact overrides and `super()` calls.

### Gameplay versus presentation separation

The report must classify each staged/progressive operation as one of:

- authoritative gameplay computation/order;
- gameplay action application;
- state-machine/lifecycle publication;
- presentation playback only;
- animation/resource preparation only;
- audio/platform policy only;
- profiling/observer only.

Android battle-music streaming from `9004c67b` is a KEEP-PLATFORM candidate unless evidence shows gameplay ordering contamination.

Animation/resource preparation may remain progressive only if it cannot alter gameplay actions, hooks, RNG, state publication, cleanup ordering, or final logical outcome.

### Required deliverable

Create only:

`recovery/p3_t01_combat_lifecycle_map.md`

The report must contain:

1. an inheritance/caller graph for Simple/Map/Base/Animation/Arena combat;
2. ordered PC-reference and current-recovery transaction maps for each combat path;
3. a function-level classification table with:
   - file + symbol;
   - owning combat path(s);
   - PC-reference behavior/order;
   - current recovery behavior/order;
   - introducing/follow-up commit(s), where identifiable;
   - gameplay/presentation category;
   - invariant/risk;
   - classification: KEEP-SHARED / KEEP-PLATFORM / REWRITE-PLATFORM / RESTORE-PC-SEMANTICS / REMOVE-WORKAROUND / KEEP-CORRECTNESS-FIX;
   - later treatment: retain / restore / re-port / remove-after-proof / controller decision;
   - dependencies;
   - exact immutable Phase-1 golden/tests proving the treatment;
4. a hook-order matrix for skill/item combat hooks;
5. an action/playback/RNG ordering matrix;
6. a cleanup/state-stack/end-combat ordering matrix;
7. a list of P3-T02 candidates limited to Simple/Map ordering;
8. a separate list of P3-T03 candidates for Base/Animation/Arena and presentation/resource/audio work;
9. independent correctness/features that P3-T04 must preserve;
10. unresolved controller decisions or escalation evidence.

Do not modify production code or tests during P3-T01.

### Validation

Because this is audit-only:

- run the existing immutable golden integrity/recovery tests without modification;
- run the combat-focused existing tests necessary to validate claims, but do not change expected behavior;
- run `git diff --check`;
- commit only `recovery/p3_t01_combat_lifecycle_map.md`;
- run `git show --check`;
- report the exact reference/current source/history evidence used.

## Escalation and stop rules

P3-T01 escalation target is **GPT-5.6 Sol / max**, not pre-authorized.

STOP and request controller authorization on:

- ESC-01 reference ambiguity;
- ESC-02 nonlocal root cause crossing another correctness-critical subsystem;
- ESC-04 competing plausible combat semantics;
- ESC-05 an invariant conflict between inheritance paths;
- ESC-09 an unplanned cross-cutting architecture decision.

Also stop if the PC reference ordering conflicts with a demonstrated later correctness fix that cannot be cleanly re-ported without choosing semantics.

Do not self-escalate. Do not begin P3-T02.

## Gate status

**Phase 2 is ACCEPTED. P3-T01 is the only authorized task. P3-T02 and later work remain blocked until P3-T01 receives controller review.**
