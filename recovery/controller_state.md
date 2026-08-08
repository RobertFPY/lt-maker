# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **Scenario 9 — skill proc and pre/post-combat hooks** after controller-authorized ESC-08 Sol/max diagnosis
- Controller disposition: **ESC-08 RESOLVED — FIXTURE RESOLVED**
- Resume model: **GPT-5.6 Terra / high**
- Escalation target remains: **GPT-5.6 Sol / max**
- Escalation pre-authorized for any new issue: **NO**
- Scenario 9 deterministic fixture contract is approved; test-owned runner integration is authorized
- Scenarios 10–18 are authorized after the approved S9 fixture is integrated and revalidated
- Phase 2 remains **UNAUTHORIZED**
- Gameplay/combat repair remains **UNAUTHORIZED** during P1-T03
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
9. **S9 FIXTURE RESOLVED / PROVISIONAL PASS PENDING RUNNER INTEGRATION** — Sol/max diagnosis established a stable reference-owned deterministic Luna proc fixture and the identical diagnostic reference/recovery Trace V1 comparison passes. The main P1-T03 S9 runner must now use exactly the approved fixture and rerun before S9 is treated as fully integrated evidence.

Do not treat provisional PASS entries as final acceptance of uncommitted WIP.

## Scenario 9 — approved deterministic proc fixture

The controller accepts the Sol/max diagnosis classification: **FIXTURE RESOLVED**.

### Approved fixture

Use exactly this reference-owned setup for the P1-T03 Scenario-9 runner:

- project: `default.ltproj`;
- chapter: `0`;
- attacker: `Eirika`;
- defender: unit `102`;
- attacking item: `Rapier`;
- add only the DB-owned skill `Luna` to Eirika using the normal `action.AddSkill` path;
- deterministic new-game seed: `0`, supplied through the engine-authoritative `cf.SETTINGS['random_seed']` before `GameState.build_new()`;
- combat path: real `SimpleCombat` / normal solver and lifecycle;
- no forced/injected playback or proc result.

Restore any mutated configuration after the scenario.

### Why this fixture is valid

Reference code establishes:

- `AttackProc.start_sub_combat()` checks attack mode, a real target, enemy relation, weapon filter, then computes proc rate;
- proc success uses the strict comparison `static_random.get_combat() < proc_rate`;
- `static_random.get_combat()` is the combat LCG `randint(0, 99)`;
- the LCG transition is `(state * 1103515245 + 12345) & 0x7fffffff`, using the shifted result for the roll;
- in the diagnosed fixture, there is no earlier combat-RNG draw before the Luna proc check;
- with authoritative seed `0`, the first combat transition is `0 -> 12345`, producing roll `0`;
- Eirika's Luna proc rate in this fixture is `SKL // 4 = 2`, therefore `0 < 2` and a real `attack_proc` is generated.

The prior seeds were valid deterministic inputs but did not satisfy the strict proc inequality. In particular, equality to the proc rate is a failure because the implementation uses `<`, not `<=`.

### Required S9 coverage

The integrated S9 run must prove at least:

- one real `attack_proc` playback record caused by the DB-owned Luna skill;
- real pre-combat/start-combat lifecycle hooks;
- real sub-combat proc hook execution;
- `cleanup_combat`;
- `end_combat`;
- `post_combat`;
- exact ordered hook records under Trace V1;
- exact reference/recovery comparator PASS using the identical fixture.

The Sol/max diagnostic reported one proc on both reference and recovery, matching state hash `979e24af7a3372fa10e5a3f104c76ecc40391d1ad11c161047a6ac8a5c1a5ade` and delta hash `c4156a9d240d3042b412c76cd2552393d7caf4fc01525e4725d7c98a4eb99537`. These hashes are diagnostic evidence, not permission to hard-code expected output without rerunning the integrated fixture.

### Bounded runner integration authorized

Resume with **GPT-5.6 Terra / high**.

Codex may make only the test-owned Scenario-9 fixture correction necessary to replace the failed multi-skill/seed attempts with the approved fixture above. It may retain observer-only diagnostics only if they are useful, bounded, and do not duplicate or alter gameplay execution; otherwise remove diagnostic-only WIP before the final P1-T03 commit.

Do not:

- modify production skill/combat/RNG code;
- modify `default.ltproj` project data;
- monkeypatch proc predicates or RNG results;
- inject `attack_proc` manually;
- carry Luna/Astra/Lethality multi-skill setup into the final fixture unless separately needed by another approved scenario;
- hard-code diagnostic state/delta hashes as a substitute for real reference capture;
- alter a golden after a recovery mismatch.

After integrating S9, rerun it on the isolated PC reference and recovery using the same authoritative fixture. If it matches as diagnosed, mark S9 PASS and continue S10–S18. If it does not reproduce the diagnosis, STOP under a new ESC-03/05 as appropriate.

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

## P1-T03 resume contract

Resume P1-T03 using **GPT-5.6 Terra / high**.

1. Integrate Scenario 9 using exactly the approved Luna/seed-0 fixture above.
2. Rerun S9 reference and recovery; require a real proc, required ordered lifecycle hooks, and exact Trace V1 comparator PASS.
3. If S9 passes, continue scenarios 10–16 and 18 as ordinary PC-reference comparisons.
4. Run scenario 17 under the approved hybrid observer contract.
5. The deterministic virtual-frame helper may be reused only where normal engine frame progression is naturally required; never use it to bypass semantic input/player decisions.
6. Never copy recovery output into reference fixtures.
7. Never silently regenerate a golden after a recovery mismatch.
8. Do not repair gameplay or begin Phase 2.
9. Report scenarios 1–18 individually. Scenario 3 N/A is resolved and is not a skip; overall PASS remains forbidden if any other required scenario is skipped or unresolved.

If a new reference ambiguity, deterministic non-presentation trace divergence, required player-choice ambiguity, save-format decision, competing semantic interpretation, cross-system invariant failure, repeated bounded failure, or other global ESC condition appears, STOP and request **GPT-5.6 Sol / max**. Do not self-escalate.

## Gate status

P1-T03 is authorized to resume with the approved Scenario-9 fixture. Phase 2 remains blocked until P1-T03 completes and receives controller review.
