# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **Scenario 13 — fog-of-war move preview/cancel/wait** after controller-authorized ESC-03 Sol/max diagnosis
- Controller disposition: **ESC-03 RESOLVED — HARNESS RESOLVED**
- Resume model: **GPT-5.6 Terra / high**
- Escalation target remains: **GPT-5.6 Sol / max**
- Escalation pre-authorized for any new issue: **NO**
- Scenarios 14–18 are **AUTHORIZED** under the existing P1-T03 contracts
- Controller gate after P1-T03: **YES — STOP FOR CONTROLLER REVIEW**
- Phase 2 remains **UNAUTHORIZED**
- Gameplay/state-machine/input repair remains **UNAUTHORIZED** during P1-T03
- Golden/reference behavior changes remain **UNAUTHORIZED**

## P1-T03 status accepted provisionally so far

Subject to final P1-T03 commit/diff/fixture review:

1. **S1 PASS** — new game to first playable map; authoritative deterministic seed; reference/recovery Trace V1 match.
2. **S2 PASS** — existing in-memory save/load; reference/recovery match.
3. **S3 N/A — REFERENCE-UNSUPPORTED** — no PC-reference mid-event save/load golden; no synthetic fixture.
4. **S4 PASS** — real PC restart-slot flow; reference/recovery match.
5. **S5 PASS** — real MapCombat through EXP and terminal cleanup under the approved deterministic virtual-frame driver; reference/recovery match.
6. **S6 PASS** — SimpleCombat; reference/recovery match.
7. **S7 PASS** — AnimationCombat using real default.ltproj animation assets; reference/recovery match.
8. **S8 PASS** — BaseCombat using real Vulnerary flow; reference/recovery match.
9. **S9 PASS** — approved DB-owned Luna / authoritative seed-0 fixture; real proc + ordered lifecycle hooks; reference/recovery match.
10. **S10 PASS** — item durability/uses and broken/unusable handling; reference/recovery match.
11. **S11 PASS** — promotion/class-change edge cases; reference/recovery match.
12. **S12 PASS** — aura propagation/teardown/load aliasing; reference/recovery match.
13. **S13 PASS** — fog move preview/cancel/wait through real InputManager after the approved test-owned deterministic host-time correction; terminal Trace V1 reference/recovery match.

Do not treat provisional PASS entries as final acceptance of uncommitted WIP.

## Scenario 13 — resolved harness clock contract

The controller accepts the Sol/max diagnosis classification: **HARNESS RESOLVED**.

### First divergence and cause

At `fog.move.cancel.complete`, reference and recovery were logically equivalent:

- state stack: committed `free` state;
- pending transitions: empty;
- Eirika position, previous position, and FOW vantage: `(4, 5)`;
- FOW visible/visited sets matched;
- unit was unfinished and had not moved;
- action-state flags matched;
- movement-left state matched.

The action menu then opened with the same options and initial index: `Item`, `Trade`, `Wait`, index `0`.

Raw KEYDOWN/KEYUP events and `InputManager.process_input()` logical outputs also matched. The first divergence occurred on the third DOWN keydown while navigating the real menu: the PC reference advanced `FluidScroll.move_counter`/menu index, while recovery did not.

Source comparison establishes the relevant implementation difference:

- PC reference `FluidScroll.reset_on_change_state()` and `FluidScroll.get_directions()` use `engine.get_time()`;
- recovery uses `engine.get_true_time()` so directional repeat/debounce follows host/UI time rather than virtual game time.

The prior headless test driver advanced only `engine.constants['current_time']`/`last_time`/`delta_t`; the host-side tick source observed by recovery therefore remained frozen. This made the recovery menu debounce fail even though the raw and logical InputManager event sequence was the same.

This is a **test-driver clock mismatch**, not evidence that InputManager, FOW, movement, or Wait gameplay semantics diverge.

### Approved RawInputFrameDriver correction

The P1-T03 test-owned raw-input frame driver may deterministically advance both timing domains required by the code under test:

1. continue to advance `engine.constants['current_time']`, `last_time`, and `delta_t` once per outer virtual frame using the already-approved virtual-frame contract;
2. provide a deterministic test-owned host-time value for the source observed by `engine.get_true_time()`, advancing once per outer frame on the same deterministic schedule;
3. construct real pygame KEYDOWN/KEYUP events;
4. pass them through the real `InputManager.process_input()`;
5. pass only the resulting real InputManager output to the state machine;
6. process repeat updates without advancing either clock within that outer frame;
7. restore all test-mutated engine timing and InputManager/raw-input state in `finally`/teardown.

The host-time shim/schedule is **test-owned provenance only**. It must not be emitted into Trace V1 logical equality or golden state.

Do not modify production `engine.get_true_time()`, `FluidScroll`, InputManager, menu code, FOW code, movement code, or Wait behavior for this harness issue.

### S13 result accepted provisionally

Under the bounded correction:

- both revisions navigate the real menu through `Item -> Trade -> Wait`;
- final SELECT exits the real menu back to `free`;
- the unit becomes finished through the normal Wait path;
- FOW position/vantage/visible/visited semantics remain matched;
- no direct Wait invocation, menu-index mutation, downstream SELECT injection, production change, or pending-transition exception is used;
- Trace V1 comparator passes for `fog.move.preview`, `fog.move.cancel.complete`, and `fog.wait.complete`.

Scenario 13 is therefore **provisionally accepted as PASS**, subject to final P1-T03 diff/harness review.

## Previously resolved P1-T03 contracts

### New-game seed authority

For any scenario crossing `GameState.build_new()`, deterministic seed input must use `cf.SETTINGS['random_seed']` before `GameState.build_new()` and restore mutated settings afterward.

### Reference generated component systems

For PC reference `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`, `app/engine/skill_system.py` and `app/engine/item_system.py` are generated via the reference-owned `generate_component_system_source()` path only.

### Scenario 3

Scenario 3 is `N/A — REFERENCE-UNSUPPORTED`; no synthetic mid-event save/load golden.

### Deterministic virtual-frame helper

The approved test-owned frame driver advances deterministic engine time once per outer frame and processes repeat chains at fixed time. It restores timing globals in `finally` and may not bypass semantic/player input.

### Scenario 9

Use the approved `default.ltproj` chapter-0 Eirika -> unit 102 Rapier + DB-owned Luna fixture with authoritative seed 0 and real SimpleCombat.

### Scenario 17

Scenario 17 remains hybrid:

- 17A: PC reference absent/disabled observer baseline;
- 17B: recovery disabled == reference baseline;
- 17C: recovery debugger enabled-idle == recovery disabled after leaving temporary observer UI state;
- 17D: recovery profiler enabled-idle == recovery disabled in logical state/order/RNG.

No simulated PC-reference enabled-idle debugger/profiler golden.

## P1-T03 resume contract

Resume P1-T03 using **GPT-5.6 Terra / high**.

1. Retain S13's bounded `RawInputFrameDriver` host-time correction only if it remains test-owned, deterministic, fully restored in teardown, and does not bypass real InputManager/menu behavior.
2. Continue S14 (`Tilemap change`) and S15 (`Phase transition`) as strict PC-reference comparisons.
3. Run S16 (`Fast-forward OFF vs ON`) under INV-06: timing/presentation may differ; logical actions/order/RNG/final state must not.
4. Run S17 under the approved hybrid observer contract above.
5. Run S18 (`Game-over/restart`) as the final required scenario.
6. Never copy recovery output into reference fixtures.
7. Never silently regenerate a golden after a recovery mismatch.
8. Do not repair gameplay or begin Phase 2.
9. Report scenarios 1–18 individually. S3 N/A is resolved and is not a skip; overall PASS remains forbidden if any other required scenario is skipped or unresolved.

If any new reference ambiguity, deterministic non-presentation trace divergence, required player-choice ambiguity, save-format decision, competing semantic interpretation, cross-system invariant failure, repeated bounded failure, or other global ESC condition appears, STOP and request **GPT-5.6 Sol / max**. Do not self-escalate.

## Final P1-T03 gate requirements

When S14–S18 are complete:

- run the required recovery trace/lifecycle tests and P1-T03 golden harness tests;
- run compileall;
- run `git diff --check` before commit and `git show --check` after commit;
- ensure reference/capture worktrees remain clean except explicitly ignored reference-generated component-system outputs;
- commit only bounded P1-T03 harness/fixture/evidence files; no production gameplay semantic changes;
- report each scenario 1–18 with fixture/checkpoint/reference comparison status and fixture/hash evidence;
- STOP FOR CONTROLLER REVIEW.

## Gate status

P1-T03 is authorized to resume from Scenario 14 using **GPT-5.6 Terra / high**. Phase 2 remains blocked until P1-T03 completes and receives controller review.
