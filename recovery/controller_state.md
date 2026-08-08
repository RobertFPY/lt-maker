# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: **Phase 1**
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **Scenario 18 — Game-over/restart** under requested ESC-01/04
- Controller disposition: **ESC-01/04 RESOLVED — reference contract found**
- Resume model: **GPT-5.6 Terra / high**
- Escalation target remains: **GPT-5.6 Sol / max**
- Sol/max is **not authorized for the resolved S18 ambiguity**; a new ESC requires a new stop/request
- Scenario 18 is the only remaining execution scenario
- Controller gate after S18 + final validation/commit: **YES — STOP FOR CONTROLLER REVIEW**
- Phase 2 remains **UNAUTHORIZED**
- Gameplay/state-machine/input/save repair remains **UNAUTHORIZED** during P1-T03
- Golden/reference behavior changes remain **UNAUTHORIZED**

## P1-T03 provisional scenario status

Subject to final P1-T03 commit/diff/fixture review:

1. **S1 PASS** — new game to first playable map; authoritative deterministic seed; reference/recovery Trace V1 match.
2. **S2 PASS** — existing in-memory save/load; reference/recovery match.
3. **S3 N/A — REFERENCE-UNSUPPORTED** — no PC-reference mid-event save/load golden; no synthetic fixture.
4. **S4 PASS** — real PC restart-slot flow; reference/recovery match.
5. **S5 PASS** — real MapCombat through EXP and terminal cleanup; reference/recovery match.
6. **S6 PASS** — SimpleCombat; reference/recovery match.
7. **S7 PASS** — AnimationCombat with real reference assets; reference/recovery match.
8. **S8 PASS** — BaseCombat; reference/recovery match.
9. **S9 PASS** — DB-owned Luna, authoritative seed 0, real proc and ordered lifecycle hooks; reference/recovery match.
10. **S10 PASS** — item durability/uses and broken/unusable handling; reference/recovery match.
11. **S11 PASS** — promotion/class-change edge cases; reference/recovery match.
12. **S12 PASS** — aura propagation/teardown/load aliasing; reference/recovery match.
13. **S13 PASS** — FOW preview/cancel/wait through real InputManager with approved test-owned deterministic host-time correction; reference/recovery match.
14. **S14 PASS** — tilemap change; strict PC-reference Trace V1 match.
15. **S15 PASS** — phase transition; strict PC-reference Trace V1 match.
16. **S16 PASS** — reference OFF == recovery OFF and recovery fast-forward ON == recovery OFF under INV-06.
17. **S17 PASS** — hybrid observer contract: 17A PC disabled baseline == 17B recovery disabled; 17C debugger enabled-idle == recovery disabled; 17D profiler enabled-idle == recovery disabled. Each comparator matched 3 Trace V1 records.
18. **S18 AUTHORIZED** — use the reference-owned game-over and title restart chain defined below.

Do not treat provisional PASS entries as final acceptance of uncommitted WIP.

## Scenario 18 — resolved reference contract

The previous claim that the PC behavioral reference has no engine-owned game-over trigger is incorrect/incomplete. The reference owns the entire trigger chain:

1. event command `lose_game` is a public reference event command;
2. reference `event_functions.lose_game()` sets `game.level_vars['_lose_game'] = True`;
3. `EventState.end_event()` consumes `_lose_game`, sets `game.memory['next_state'] = 'game_over'`, and enters the normal `transition_to` path;
4. `GameOverState` is the reference `game_over` state; once it reaches `stasis`, any real input sets `next_state = 'title_start'` and transitions normally;
5. `default.ltproj` contains the DB-owned global event `Global DeathEirika`, whose real event script ends with `lose_game`;
6. the reference title main menu exposes `Restart Level` when saves exist, routes it to `title_restart`, and `TitleRestartState` uses `save.RESTART_SLOTS`;
7. the reference restart load path handles a start/restart slot through the normal `save.load_game()` + level-start flow.

Therefore S18 must not use the runtime-debugger restart command and must not directly push `game_over`.

### Authorized S18 fixture contract

Use the same deterministic project/new-game/restart-slot setup style already accepted for S1/S4. Any scenario crossing `GameState.build_new()` must seed through `cf.SETTINGS['random_seed']` and restore mutated config afterward.

Before the game-over trigger, establish a valid real restart slot through the already accepted PC start/restart save machinery. Do not fabricate a `SaveSlot` payload or write a test-only restart format.

Trigger game over through the **DB-owned `Global DeathEirika` event** and the real event system:

- use the real Eirika runtime object;
- issue the event's real `combat_death` trigger through `game.events.trigger(...)` / normal EventManager dispatch so that `Global DeathEirika` is selected by the reference DB;
- allow its real event commands to run, including its final `lose_game` command;
- do **not** call `event_functions.lose_game()` directly;
- do **not** set `_lose_game` directly;
- do **not** call `game.state.change('game_over')` directly;
- do **not** use the runtime debugger or a synthetic anonymous loss event.

This S18 fixture is testing the reference-owned game-over transaction, not re-testing lethal combat damage. S5–S10 already cover combat lifecycle semantics; therefore direct dispatch of the real `combat_death` trigger through the real EventManager is an acceptable scenario input and is preferred over inventing a brittle lethal-combat setup.

### Required game-over path

Drive the real state machine with the approved deterministic frame/input helpers until:

1. `Global DeathEirika` completes its real event transaction;
2. `EventState.end_event()` consumes `_lose_game` and transitions to `game_over`;
3. `GameOverState` reaches its normal input-ready `stasis` state;
4. send real raw input through the approved `RawInputFrameDriver`/real `InputManager`;
5. allow the real transition to committed `title_start`.

Do not bypass transition states or mutate `GameOverState.state` to `stasis` manually. Presentation time may be driven by the already-approved deterministic frame clock.

### Required restart path

From committed `title_start`:

1. use real raw input -> real `InputManager` to enter `title_main`;
2. let the reference title code run `save.check_save_slots()` and construct its real menu;
3. navigate the real menu to **Restart Level** without direct menu-index mutation;
4. select it through real input and let title code enter `title_restart`;
5. select the intended real `RESTART_SLOTS` entry through the normal title restart UI/state path;
6. let the reference restart/load path call normal `save.load_game()` and level start logic;
7. drive until the restarted chapter reaches committed playable map control with pending transitions empty.

The test may isolate save files to a temporary test-owned filesystem location if the existing harness already does so, but it must use the real save/restart APIs and formats and restore global save-path/slot state afterward.

### Trace/equality contract

Use existing Trace V1 synchronization semantics; do not add a new schema meaning solely for S18.

At minimum establish/compare:

- the committed transition into the reference `game_over` path (existing `state.transition.commit` semantics or equivalent already-approved runner observation);
- committed return to `title_start` through the real GameOver input path;
- terminal **`restart.complete`** only after restarted chapter/map/control state is fully committed and `state_stack.pending == []`.

Host time, fade progress, exact frame counts, title animation state, audio, and menu render state remain presentation/provenance and are not logical golden equality fields.

Reference and recovery must use the same save-slot setup, event trigger, raw-input intent, and deterministic frame schedule. If their logical traces/final restarted state differ, STOP under a new **ESC-03**; do not repair or regenerate golden output.

### S18 forbidden shortcuts

Do not:

- use runtime-debugger restart/game-over commands;
- directly set `_lose_game`;
- directly invoke `lose_game()`;
- directly push `game_over`, `title_start`, or `title_restart` to skip the normal chain;
- create a synthetic loss event when `Global DeathEirika` exists in the reference project;
- directly mutate title/restart menu indices;
- bypass real InputManager for title/restart selections;
- fabricate restart save payloads;
- weaken pending-transition requirements;
- modify production/project data;
- begin Phase 2.

## Previously resolved harness contracts

- New-game seed authority: set `cf.SETTINGS['random_seed']` before `GameState.build_new()` and restore it afterward.
- Reference generated `skill_system.py` / `item_system.py`: bootstrap only with the reference-owned `generate_component_system_source()` path.
- Virtual-frame helper: advance deterministic engine time once per outer frame; process repeat chains at fixed time; restore globals.
- RawInputFrameDriver: may also advance deterministic test-owned host time for `engine.get_true_time()`, must use real pygame KEYDOWN/KEYUP -> real `InputManager.process_input()`, and must restore clock/input state.
- S9: `default.ltproj`, chapter 0, Eirika -> unit 102, Rapier, DB-owned Luna, authoritative seed 0, real SimpleCombat.
- S17 hybrid observer contract remains as provisionally passed above.

## Resume contract

Resume **P1-T03 only** with **GPT-5.6 Terra / high**.

1. Run only S18 under the exact resolved contract above.
2. If S18 PASSes reference vs recovery, run the final P1-T03 validation suite.
3. Run required recovery trace/lifecycle tests and complete P1-T03 golden harness tests.
4. Run `compileall`.
5. Run `git diff --check` before commit.
6. Ensure isolated reference/capture worktrees are clean except explicitly ignored reference-generated outputs.
7. Remove redundant diagnosis-only WIP that is not required by the final bounded harness/evidence.
8. Commit only bounded P1-T03 test-owned harness/fixture/evidence files; no production/project-data changes.
9. Run `git show --check` after commit.
10. Report scenarios 1–18 individually, including S3 N/A, fixture/checkpoint/hash evidence, test commands/results, files changed, and commit SHA.
11. **STOP FOR CONTROLLER REVIEW.**

If any new reference ambiguity, deterministic non-presentation divergence, save-format conflict, required player-input ambiguity, invariant failure, or repeated bounded failure occurs, STOP and request **GPT-5.6 Sol / max**. Do not self-escalate.

## Gate status

Only S18 + final P1-T03 validation/commit remain authorized. Phase 2 is blocked until controller acceptance of the completed P1-T03 evidence commit.
