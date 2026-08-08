# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **Scenario 13 — fog-of-war move preview/cancel/wait**
- Trigger: **ESC-03 — deterministic state/input-path divergence before terminal recovery capture**
- Controller disposition: **ESC-03 CONFIRMED**
- Authorized model/effort for the next bounded work: **GPT-5.6 Sol / max**
- Escalation is explicitly authorized **for Scenario 13 diagnosis only**
- No further self-escalation is authorized
- Scenarios 14–18 remain **BLOCKED** until Scenario 13 returns to controller review
- Phase 2 remains **UNAUTHORIZED**
- Gameplay/state-machine/input repair remains **UNAUTHORIZED** during this diagnosis
- Golden/reference behavior changes remain **UNAUTHORIZED**

## P1-T03 status accepted provisionally so far

Subject to final P1-T03 commit/diff/fixture review:

1. **S1 PASS** — new game to first playable map; deterministic seed supplied through `cf.SETTINGS['random_seed']`; reference/recovery Trace V1 match.
2. **S2 PASS** — existing in-memory save/load; reference/recovery match.
3. **S3 N/A — REFERENCE-UNSUPPORTED** — no PC-reference mid-event save/load golden; no synthetic fixture.
4. **S4 PASS** — real PC restart-slot flow via `save.save_io(kind='start')` -> `save.load_game`; reference/recovery match.
5. **S5 PASS** — real `MapCombat`, deterministic test-owned virtual-frame driver, EXP and terminal cleanup complete naturally; reference/recovery match.
6. **S6 PASS** — `SimpleCombat`; reference/recovery Trace V1 match.
7. **S7 PASS** — `AnimationCombat` using real `default.ltproj` animation assets; reference/recovery match.
8. **S8 PASS** — `BaseCombat` using real Vulnerary flow; reference/recovery match.
9. **S9 PASS** — approved DB-owned Luna / authoritative seed-0 fixture integrated; real proc + ordered lifecycle hooks; reference/recovery match.
10. **S10 PASS** — item durability/uses and broken/unusable handling; reference/recovery match.
11. **S11 PASS** — promotion/class-change edge cases; reference/recovery match.
12. **S12 PASS** — aura propagation/teardown/load aliasing; reference/recovery match.
13. **S13 BLOCKED / ESC-03** — reference completes the approved fog move preview/cancel/wait input path, but recovery cannot select Wait through the same InputManager/virtual-frame schedule after `fog.move.cancel.complete`; terminal recovery trace is therefore unavailable.

Do not treat provisional PASS entries as final acceptance of uncommitted WIP.

## Scenario 13 — authorized Sol/max diagnosis

### Why ESC-03 applies

Scenario 13 requires deterministic proof of fog-of-war movement semantics, including preview/cancel behavior and the authoritative Wait commit behavior.

The same scenario and deterministic runner reach `fog.move.cancel.complete` successfully on both sides. The PC reference then reaches/selects the Wait menu action through the real InputManager/frame path and completes the scenario. Recovery does not: after menu navigation reaches the intended Wait position, the same input schedule fails to select Wait, so no terminal recovery capture/comparator result exists.

This is not yet classified as a gameplay regression. It may be:

- a test-owned input timing/menu-cursor assumption that is no longer equivalent;
- a state-stack/menu-state ordering divergence;
- InputManager edge/held/repeat semantics interacting differently with the current state path;
- a presentation-only menu difference with an equivalent logical Wait action still reachable under the same logical input contract; or
- an actual recovery regression that changes the authoritative move/wait transaction.

The diagnosis must locate the **first divergence after `fog.move.cancel.complete`** before any repair or fixture relaxation is authorized.

### Scope

Use **GPT-5.6 Sol / max** exactly.

Work on **Scenario 13 only**. This is diagnosis, not repair.

Allowed:

- inspect and compare PC-reference vs recovery state stack, current state object/type, menu model/options/current index, cursor/unit movement state, movement-left/action state, FOW vantage/position, pending transitions, and InputManager state after `fog.move.cancel.complete`;
- inspect exact InputManager processing and menu navigation/selection code on both revisions;
- add/use test-owned observer-only diagnostics around the already-authorized input/frame runner;
- record each logical/raw test input step, resulting processed input event, state stack before/after, menu selection/index before/after, pending transitions, and unit/FOW logical state;
- compare source/history to identify the smallest responsible file/function/commit cluster;
- determine whether the same **logical** user action sequence can be expressed with a bounded correction to test timing while still going through real InputManager and real menu selection;
- rerun reference and recovery after a diagnosis-only bounded test-driver correction **only if the correction does not change the semantic input sequence and merely restores the normal InputManager edge/frame contract**; if that point is ambiguous, STOP for controller review instead of applying it.

Forbidden:

- directly invoking the Wait command/handler to bypass InputManager or the action menu;
- mutating menu index/current option directly;
- injecting a processed `SELECT`/`Wait` result downstream of InputManager;
- bypassing movement/menu states;
- changing FOW vantage/unit position to make the test pass;
- changing production InputManager, menu, movement, FOW, state-machine, or action behavior;
- accepting a different gameplay outcome because the menu is presentation;
- adding a Trace pending-state exception;
- weakening the required preview/cancel/wait semantics;
- generating or altering golden expected output after a recovery mismatch;
- continuing S14–S18;
- beginning Phase 2.

### Required diagnosis evidence

Report, from the exact S13 fixture and schedule:

1. the complete state stack and pending transitions at `fog.move.cancel.complete` on reference and recovery;
2. unit logical position, movement start/vantage, FOW-visible/visited state, finished/action state, and movement-left state at that boundary;
3. action-menu option list/order and selected index when the menu first becomes input-ready;
4. every subsequent scheduled raw/logical input used to navigate to/select Wait;
5. for each input step, the InputManager output event and held/pressed/repeat state relevant to that event;
6. state stack/menu index before and after each step on both revisions;
7. the **first exact step** where reference and recovery differ;
8. source-level cause of that difference and smallest responsible file/function/commit cluster;
9. classification of the divergence as one of:
   - **HARNESS INPUT-SCHEDULE MISMATCH** — same logical Wait action is reachable through real InputManager with a bounded frame/edge correction and logical gameplay before/after remains reference-equivalent;
   - **PRESENTATION/MENU-PATH DIFFERENCE WITH EQUIVALENT LOGICAL INPUT CONTRACT** — menu presentation/path differs but a controller-reviewable equivalent real user-input sequence reaches the same authoritative Wait semantics;
   - **TRACE/GAMEPLAY DIVERGENCE** — recovery state/input ordering or resulting movement/FOW/wait semantics differ from reference;
   - **REFERENCE/CONTRACT AMBIGUITY** — no single valid user-input contract can be established without inventing semantics;
10. if and only if a bounded observer/test-driver correction is clearly non-semantic and within the existing virtual-frame/InputManager contract, show reference/recovery terminal Trace V1 result after that correction; otherwise STOP without applying it.

### Scenario 13 invariant reminder

The authoritative FOW invariant remains:

- during move preview, FOW vantage remains the movement start tile;
- cancel restores the pre-move logical state;
- FOW must not commit to the destination merely because preview position changes;
- Wait is the commit point for the completed movement/action semantics;
- `recalc_unit` or equivalent must not make preview movement authoritative before Wait.

Do not relax this invariant to solve an input/menu problem.

### Decision outcomes

Return exactly one classification:

- **HARNESS RESOLVED:** bounded real-InputManager schedule correction established; reference/recovery terminal Trace V1 match;
- **EQUIVALENT INPUT CONTRACT FOUND:** real user-input path differs but semantics appear equivalent; STOP for controller approval before changing the S13 fixture contract;
- **TRACE DIVERGENCE:** recovery differs logically/state-order-wise; provide first divergence and smallest responsible cluster, then STOP;
- **REFERENCE CONTRACT AMBIGUITY:** deterministic user-input semantics cannot be fixed without inventing a contract; STOP.

Regardless of outcome, do not proceed to S14. **STOP FOR CONTROLLER REVIEW.**

## Previously resolved P1-T03 contracts

### New-game seed authority

For any scenario crossing `GameState.build_new()`, deterministic seed input must use `cf.SETTINGS['random_seed']` before `GameState.build_new()` and restore mutated settings afterward.

### Reference generated component systems

For PC reference `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`, `app/engine/skill_system.py` and `app/engine/item_system.py` are generated via the reference-owned `generate_component_system_source()` path only.

### Scenario 3

Scenario 3 is `N/A — REFERENCE-UNSUPPORTED`; no synthetic mid-event save/load golden.

### Deterministic virtual-frame helper

The approved test-owned frame driver emulates the PC outer-frame loop by advancing `engine.constants` by `FRAMERATE` once per outer frame and processing repeat chains at fixed virtual time. It restores timing globals in `finally` and may not bypass semantic/player input.

### Scenario 9

Use the approved `default.ltproj` chapter-0 Eirika -> unit 102 Rapier + DB-owned Luna fixture with authoritative seed 0 and real SimpleCombat.

### Scenario 17

Scenario 17 remains hybrid: reference disabled baseline; recovery disabled == reference; recovery debugger enabled-idle == recovery disabled; recovery profiler enabled-idle == recovery disabled. No simulated PC-reference enabled-idle observer golden.

## Gate status

Only the bounded **P1-T03 Scenario 13 Sol/max diagnosis** above is authorized now. Scenarios 14–18 and Phase 2 remain blocked until controller review of the S13 diagnosis.
