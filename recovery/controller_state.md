# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 7**
- Phases 1–6: **ACCEPTED**
- P7-T01 fast-forward equivalence: **ACCEPTED** at `874c7adcf83f14e6fcf961180a01f4ddfe1201fe`
- P7-T02 debugger parity PC/Android: **ACCEPTED** at `11f2a42cd055d089917834ef80d74d369aad5ed8`
- P7-T03 profiler observer-equivalence: **ACCEPTED** at `9fcefdf8f2d6d03724d86523ae46b320bcd8802b`
- Active task: **P7-T04 only — Save/load/restart UX regression sweep**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- Phase 8+: **UNAUTHORIZED**
- Production behavior changes: **test/evidence first; only a bounded UX-routing correctness fix is allowed when one unambiguous frontend integration defect is proven**
- Canonical save/load/restart architecture changes: **UNAUTHORIZED in P7-T04**
- Gameplay-core semantic changes: **UNAUTHORIZED**
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P7-T04: **YES — STOP FOR CONTROLLER REVIEW**

## P7-T03 acceptance record

The controller accepts `9fcefdf8f2d6d03724d86523ae46b320bcd8802b` (`test(profiler): prove observer equivalence`).

Accepted evidence:

- it is exactly one descendant of P7-T03 authorization commit `487af528aec5dcf967f6cface487f70ae5488e51`;
- scope is test/evidence only: `app/tests/test_performance_profiler.py` and `recovery/p7_t03_profiler_observer_equivalence.md`;
- no production, Trace V1, comparator, manifest, golden, save/load/restart, gameplay, project-data, or asset file changed;
- deterministic profiler OFF/ON evidence uses the same RNG seed and proves identical ordered gameplay effects, HP result, and post-run combat RNG state;
- disabled profiling executes wrapped work once and emits no profiler warning merely because instrumentation exists;
- a real secondary Python thread enters a profiler section while a main-thread scope is active; the worker body executes exactly once but does not enter `_frame_scopes`, alter `_scope_stack`, change parentage, or replace `_frame_thread_id`;
- main-thread `outer -> inner` scope nesting remains coherent through `finish_frame()`;
- GC callback evidence changes only profiler-owned counters and restores callback membership after the test;
- representative StateMachine/Event/driver source checks confirm profiling wraps the same gameplay operations rather than selecting different operations;
- P7-T01 fast-forward, P7-T02 debugger, P5 load/restart, combat lifecycle, P6 platform policy and immutable S17 observer contracts were reported green;
- no profiler observer defect required a production fix;
- device/JNI timing and visual behavior remain external validation limits and are not part of logical observer equality.

## Locked observer contract

Later tasks must preserve:

1. Profiler/debugger idle modes are observers and may not alter logical gameplay outcomes/order.
2. Worker-thread profiler sections may execute wrapped work but may not enter/corrupt the active main-thread frame scope tree.
3. Profiler timing/counters/log output are diagnostic state only and may not become gameplay inputs or scheduling policy.
4. Historical profiler labels must not be used to reintroduce rejected Android Event command scheduling.

---

# P7-T04 — Save/load/restart UX regression sweep

Execute **P7-T04 only** using **GPT-5.6 Terra / medium**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

This is the final Phase-7 user-facing feature-preservation gate.

The authoritative core save/load/restart contracts were already accepted in Phase 5. P7-T04 verifies that user-facing desktop and Android entry paths route into those contracts correctly. It does **not** redesign or reopen canonical load/restart architecture.

## Core semantic authority

Preserve accepted Phase-5 contracts exactly.

### SAVE

- SAVE means current progress.
- Mid-chapter SAVE is not pristine restart truth.
- Existing save compatibility rules remain unchanged.

### RESTART

- RESTART means source-proven pristine chapter-start state for the same chapter.
- Prefer the current-session `chapter_start_snapshot` when valid/matching.
- Persistent fallback must be a matching RESTART slot, not the current mid-chapter SAVE slot.
- Stale/wrong-chapter restart sources are rejected/removed according to accepted P5 behavior.
- Test Chapter must not accidentally seed pristine restart from an already-progressed first save.
- Overworld special cases retain their accepted SAVE behavior.

### LOAD

All user-facing loads/restarts must converge on the accepted canonical transaction:

1. validate source/context before authoritative build;
2. worker/background portion may read/unpickle only;
3. authoritative hydrate/build executes synchronously as one logical transaction on the main thread;
4. START/RESTART context applies the accepted chapter-start path;
5. compatibility restoration happens inside the transaction;
6. validate complete world before publication;
7. publish/install once at the transaction boundary;
8. exception/failure leaves no partially installed gameplay state.

Do not introduce a second load path for Android or any frontend.

## UX paths to verify

Inventory and exercise the actual current frontend routes for at least:

### Title / save menu

- load an existing current-progress SAVE;
- new game / chapter-start source setup where applicable;
- restart-current-chapter option if exposed through title/save UI;
- slot availability/selection routes to the intended SAVE vs RESTART source;
- desktop and Android presentation differences do not change selected logical source/context.

### Game over

- restart current chapter uses pristine restart semantics;
- any return/title/load option routes correctly;
- no mid-chapter SAVE is silently used as pristine restart;
- state-stack/input transition ordering remains valid.

### Runtime debugger

- restart current chapter retains P7-T02 shared controller semantics;
- matching in-memory snapshot is preferred;
- persistent matching RESTART fallback only;
- explicit difficulty is preserved;
- Android touch ownership is released before canonical state replacement.

### Direct load/restart integration

- canonical `load_game_data` behavior remains the only authoritative install transaction;
- Android `SaveLoadJob` worker remains read/unpickle only;
- desktop may load synchronously where accepted but must produce the same logical transaction result;
- failure/corrupt/invalid source does not publish partial state.

## PC / Android parity model

The two platforms do not need identical widgets, animations, file-dialog presentation, or host timing.

Required equivalence is:

```text
same logical user intent
+ same save/restart source
+ same requested difficulty/context
=> same canonical transaction/context
=> same logical restored/restarted world
```

Platform-specific filesystem location, touch mechanics, loading screen presentation, and resource-preload timing are excluded from gameplay equality when they preserve the same canonical source and transaction.

Do not compare host-frame counts.

## Required scenario matrix

At minimum cover deterministic feature-level evidence for:

1. **Title load — current SAVE**
   - desktop route;
   - Android route or Android-routing policy seam;
   - same source/context and logical result.

2. **Restart — current-session pristine snapshot**
   - mutate current chapter after chapter-start snapshot;
   - restart;
   - prove mutations disappear and pristine source wins.

3. **Restart — persistent RESTART fallback**
   - no valid in-memory snapshot;
   - matching RESTART source exists;
   - restart uses it.

4. **Wrong/stale restart source rejection**
   - wrong chapter or stale source is not accepted as pristine restart.

5. **Mid-chapter SAVE separation**
   - current SAVE exists and differs from pristine state;
   - restart must not use it.

6. **Difficulty propagation**
   - explicit restart/debugger difficulty reaches accepted canonical load context and chapter-start semantics.

7. **Game-over restart**
   - same pristine-source contract;
   - no alternate Android gameplay semantics.

8. **Debugger restart**
   - shared controller route remains consistent with Game Over/Title restart source rules.

9. **Load failure atomicity**
   - invalid/corrupt/incompatible source fails without partial authoritative install.

10. **Initiative/phase compatibility regression**
   - accepted P5 exact-state/new-save behavior remains green;
   - legacy ambiguous initiative current-progress failure remains atomic rather than guessed;
   - START/RESTART deterministic rebuild remains accepted where applicable.

11. **Aura/FOW reconstruction regression**
   - aura children remain re-derived rather than serialized as independent truth;
   - FOW logical state remains consistent after load/restart where existing fixtures cover it.

12. **Fast-forward / observers around UX**
   - P7-T01/P7-T02/P7-T03 regressions remain green;
   - loading/restart routing is not altered by debugger/profiler idle modes.

## Source/source-context proof

For each user-facing route, prove the selected source type and context explicitly.

Distinguish:

- SAVE current progress;
- RESTART pristine chapter source;
- `chapter_start_snapshot` current-session pristine source;
- START/new-game chapter setup;
- overworld special SAVE behavior.

A test that only checks the final state changed is insufficient if it cannot prove the route chose the correct source/context.

## Atomicity proof

P7-T04 must keep Phase-2/5 atomicity evidence green.

No UX route may observe/install:

- partially hydrated GameState;
- incomplete tilemap/board/world;
- staged state stack as authoritative truth;
- partially restored initiative/phase state;
- worker-thread authoritative gameplay mutation.

If a frontend route bypasses canonical `load_game_data`, STOP and report it before attempting a fix.

## Test/evidence policy

Expected default production changes: **NONE**.

Expected default changes:

- focused UX regression tests;
- optionally `recovery/p7_t04_save_load_restart_ux.md`.

A bounded production fix is allowed only when tests prove a local frontend/routing defect with one unambiguous correct answer, such as:

- wrong slot/source selected before canonical API call;
- wrong requested difficulty/context forwarded;
- Android touch/UI ownership not released before an already-correct canonical transition;
- duplicate frontend submission of one load/restart request.

Allowed frontend/integration surfaces if evidence proves such a defect:

- `app/engine/title_screen.py`
- `app/engine/game_over.py`
- `app/engine/runtime_debugger.py`
- `app/engine/runtime_debugger_controller.py`
- `app/engine/android_debugger.py`
- narrow Android frontend/runtime bridge code directly owning the UX request
- focused tests/report

Phase-5 core is protected.

If the defect requires changing:

- canonical `load_game_data` transaction;
- `GameState.load_iter` semantics;
- SaveLoadJob worker authority;
- save schema/compatibility;
- pristine restart definition/source precedence;
- initiative/phase compatibility policy;
- aura/FOW serialization semantics;

STOP under ESC-02/ESC-06/ESC-09 and request controller review/escalation.

## Regression requirements

Keep green:

- P7-T01 fast-forward equivalence;
- P7-T02 debugger parity;
- P7-T03 profiler observer-equivalence;
- P5 canonical load/restart/compatibility tests;
- Phase-4 tilemap atomicity/barrier tests;
- Phase-3 combat lifecycle;
- P6 platform policy.

## Immutable proof

Run at minimum:

- S2 load
- S4 restart
- S5 representative gameplay
- S12 aura
- S13 FOW
- S16 fast-forward
- S17 disabled
- S17 debugger-idle
- S17 profiler-idle
- S18 game-over/restart

Run S14 tilemap as well because load/restart world publication must not regress the accepted tilemap/board contract.

No golden regeneration.

Run focused:

- canonical load tests;
- restart contract tests;
- atomic restore tests;
- Android restart/load/persistence tests;
- title/save-menu routing tests;
- game-over tests;
- runtime debugger restart tests;
- initiative/phase compatibility tests;
- aura/FOW/tilemap regression tests;
- P7 fast-forward/debugger/profiler tests;
- recovery trace/lifecycle/golden integrity.

Run broader unittest discovery and report known baseline/native/test-isolation failures without repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- bounded commit
- `git show --check`
- `git status --short`

## Explicitly out of scope

Do not:

- begin Phase 8;
- redesign title/save/game-over/debugger UI;
- create Android-only gameplay load/restart semantics;
- create another load API;
- change P5 canonical transaction or restart-source precedence;
- add a generic save migration framework;
- guess ambiguous legacy initiative progress;
- serialize aura children as new save truth;
- alter fast-forward/debugger/profiler semantics;
- alter combat/tilemap/platform-policy contracts;
- change Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / medium**.
Escalation target: **GPT-5.6 Sol / high**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** failure root cause is inside/nonlocal to canonical load/restart rather than local UX routing;
- **ESC-03** immutable trace divergence;
- **ESC-04** desktop/Android UX routes imply competing gameplay semantics;
- **ESC-05** partial/invalid gameplay state becomes observable;
- **ESC-06** save-format/compatibility/restart-source conflict;
- **ESC-07** fix would require a platform gameplay fork;
- **ESC-08** repeated bounded frontend fix failure;
- **ESC-09** new cross-cutting save/load/restart architecture appears necessary.

Do not self-escalate.

## Gate status

**P7-T01/P7-T02/P7-T03 are ACCEPTED. P7-T04 is the only authorized task. Phase 8+ remains blocked pending controller review.**
