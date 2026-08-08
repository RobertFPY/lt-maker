# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **Scenario 9 — skill proc and pre/post-combat hooks**
- Trigger: **ESC-08 — repeated local fixture failure**
- Controller disposition: **ESC-08 CONFIRMED**
- Authorized model/effort for the next bounded work: **GPT-5.6 Sol / max**
- Escalation is explicitly authorized **for Scenario 9 diagnosis / deterministic fixture determination only**
- No further self-escalation is authorized
- Scenarios 10–18 remain **BLOCKED** until Scenario 9 returns to controller review
- Phase 2 remains **UNAUTHORIZED**
- Gameplay/combat repair remains **UNAUTHORIZED** during this diagnosis
- Golden/reference behavior changes remain **UNAUTHORIZED**

## P1-T03 status accepted provisionally so far

Subject to final P1-T03 commit/diff/fixture review:

1. **S1 PASS** — new game to first playable map; deterministic seed supplied through `cf.SETTINGS['random_seed']`; real committed map-control state; reference/recovery Trace V1 match.
2. **S2 PASS** — existing in-memory save/load; reference/recovery match.
3. **S3 N/A — REFERENCE-UNSUPPORTED** — no PC-reference mid-event save/load golden; no synthetic fixture.
4. **S4 PASS** — real PC restart-slot flow via `save.save_io(kind='start')` -> `save.load_game`; reference/recovery match.
5. **S5 PASS** — real `MapCombat`, deterministic test-owned virtual frame driver, EXP and terminal `clean_up2()` complete naturally; reference/recovery match.
6. **S6 PASS** — `SimpleCombat`; reference/recovery Trace V1 match.
7. **S7 PASS** — `AnimationCombat` using real `default.ltproj` animation assets; reference/recovery match.
8. **S8 PASS** — `BaseCombat` using real Vulnerary flow; reference/recovery match.
9. **S9 BLOCKED / ESC-08** — PC reference fixture does not produce the required skill proc under the attempted deterministic inputs; no recovery golden has been created or altered.

Do not treat provisional PASS entries as final acceptance of uncommitted WIP.

## Scenario 9 — authorized Sol/max diagnosis

### Why ESC-08 applies

P1-T03 requires Scenario 9 to cover **skill proc and pre/post-combat hooks**. The primary Terra/high execution attempted a bounded deterministic fixture and a bounded correction, including at least seeds `1701` and `20`, but the PC behavioral reference still produced no `attack_proc` despite the intended Luna/Astra/Lethality setup and real lifecycle hook execution.

Repeatedly guessing seeds or weakening the requirement is no longer authorized mechanical work. The next step requires semantic diagnosis of the real proc eligibility + RNG-consumption path in the PC reference.

### Scope

Use **GPT-5.6 Sol / max** exactly.

Work on **Scenario 9 only**. This is diagnosis / deterministic fixture determination, not gameplay repair.

Allowed:

- inspect PC-reference skill definitions/components and generated skill-system behavior;
- inspect actual proc eligibility functions and hook dispatch order;
- inspect the combat solver's RNG-consumption sequence;
- add or use test-owned/read-only diagnostics that do not consume RNG or change hook invocation count/order;
- enumerate deterministic seeds mathematically or by an isolated observer-equivalent search harness, provided the search uses the exact authoritative scenario setup and does not mutate production behavior;
- determine whether Luna, Astra, Lethality, or another existing reference skill is the smallest stable proc fixture;
- determine whether the current S9 setup is ineligible for proc because of unit/item/target/skill conditions rather than RNG;
- identify a deterministic authoritative seed/input that produces a real proc in the PC reference, if one exists;
- compare the same finalized fixture on recovery only after the reference fixture is proven valid.

Forbidden:

- modifying production combat, skill, item, RNG, generated-system source, or event behavior;
- forcing a proc by monkeypatching the proc predicate/result;
- injecting an `attack_proc` playback record manually;
- changing proc chance/skill data/project content;
- consuming extra gameplay RNG while observing;
- accepting hook-only coverage with no real proc if the scenario can support a real proc;
- changing the PC golden to match recovery;
- continuing S10–S18 before controller review;
- beginning Phase 2.

### Required diagnosis evidence

Report, for the exact reference fixture:

1. attacker, defender, item, relevant skill NIDs, skill component types/values, and all proc eligibility conditions;
2. the exact pre-combat/start-combat hook path reached before the proc check;
3. the exact function/component that decides proc chance and the random primitive used;
4. the combat RNG state immediately before the proc roll, the random value/result, and state immediately after — captured observer-only;
5. every earlier combat-RNG mutation that shifts the proc roll, in order, if any;
6. why seeds `1701` and `20` do not proc under the current fixture;
7. whether the current fixture is logically eligible for Luna/Astra/Lethality at all;
8. the smallest deterministic reference-owned fixture that produces at least one real proc while also exercising pre/post-combat hooks;
9. a bounded deterministic seed-selection method based on the real reference path, not blind trial-and-error;
10. whether that finalized fixture produces an exact reference/recovery Trace V1 match or a new ESC-03 divergence.

### Decision outcomes

Return exactly one classification:

- **FIXTURE RESOLVED:** a stable, reference-owned deterministic S9 fixture exists and reference/recovery match;
- **TRACE DIVERGENCE:** valid reference fixture exists but recovery differs — report ESC-03 evidence and STOP;
- **REFERENCE CONTRACT AMBIGUITY:** no stable reference-owned proc fixture can be established without inventing semantics — report ESC-01/04 evidence and STOP;
- **HARNESS DEFECT:** the current runner/observer prevents or misidentifies a real proc — identify the bounded correction and STOP for controller approval before changing accepted harness semantics.

Do not proceed to S10 regardless of outcome. **STOP FOR CONTROLLER REVIEW.**

## Previously resolved P1-T03 contracts

### New-game seed authority

For any scenario crossing `GameState.build_new()`, deterministic seed input must use:

```python
cf.SETTINGS['random_seed'] = <scenario seed>
game.build_new()
```

Restore mutated settings after the scenario.

### Reference generated component systems

For PC reference `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`, `app/engine/skill_system.py` and `app/engine/item_system.py` are generated artifacts. The only authorized bootstrap is the reference-owned `generate_component_system_source()` path; never copy these outputs from recovery or hand-edit them.

### Scenario 3

Scenario 3 is `N/A — REFERENCE-UNSUPPORTED`; do not create a synthetic mid-event save/load golden.

### Deterministic virtual-frame helper

The approved test-owned frame driver may emulate the PC outer-frame loop by advancing `engine.constants` by `FRAMERATE` once per outer frame and processing repeat chains at fixed virtual time. It must restore timing globals in `finally`. It may not bypass semantic input/player decisions.

### Scenario 17

Scenario 17 remains hybrid:

- reference absent/disabled observer baseline;
- recovery disabled == reference baseline;
- recovery debugger enabled-idle == recovery disabled after leaving temporary observer UI state;
- recovery profiler enabled-idle == recovery disabled in logical state/order/RNG.

No simulated PC-reference enabled-idle debugger/profiler golden.

## Gate status

Only the bounded **P1-T03 Scenario 9 Sol/max diagnosis** above is authorized now. Scenarios 10–18 and Phase 2 remain blocked until controller review of the S9 diagnosis.
