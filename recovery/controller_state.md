# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **ESC-03** during scenario 1 (`New game -> first playable map`)
- Controller disposition: **ESC-03 RESOLVED — harness/scenario mismatch, not a recovery regression**
- Resume model: **GPT-5.6 Terra / high**
- Escalation target remains: **GPT-5.6 Sol / max**
- Escalation pre-authorized for any new issue: **NO**
- Controller gate after P1-T03: **YES — STOP FOR CONTROLLER REVIEW**
- Phase 2 remains **UNAUTHORIZED**
- Gameplay repair remains **UNAUTHORIZED** during P1-T03

## Resolved ESC-03 — new-game seed authority

The scenario-1 RNG divergence was caused by the harness seeding the wrong layer.

Both the PC reference and recovery branch use the same `GameState.build_new()` seed logic:

```python
if cf.SETTINGS['random_seed'] >= 0:
    random_seed = int(cf.SETTINGS['random_seed'])
else:
    random_seed = random.randint(0, 1023)
static_random.set_seed(random_seed)
```

Therefore calling `static_random.set_seed(1701)` before `build_new()` is not authoritative. When `cf.SETTINGS['random_seed'] == -1`, `build_new()` immediately replaces that state with a value drawn from Python's stdlib `random` generator. Separate processes may therefore diverge even when the direct static RNG setup matched.

The Sol/max diagnosis established:

- module-initial static RNG state matched;
- scenario-requested direct `static_random.set_seed(1701)` matched;
- no combat-RNG consumption occurred before divergence;
- the first divergent mutation was the `static_random.set_seed(random_seed)` call inside `GameState.build_new()`;
- the reference and recovery call-site logic is semantically identical and predates the behavioral reference;
- project content, generated component-system artifacts, persistent records, and static RNG starting state matched;
- the non-equivalent input was Python stdlib `random` process state;
- using the engine-authoritative input `cf.SETTINGS['random_seed'] = 1701` before `game.build_new()` produced matching reference/recovery Trace V1 state and RNG states.

Classification: **Harness/scenario mismatch.** There is no post-reference recovery regression identified by this ESC-03.

### Mandatory seed rule for P1-T03

For every scenario that crosses `GameState.build_new()` / new-game initialization, deterministic seed setup must use the engine-authoritative input:

```python
cf.SETTINGS['random_seed'] = <scenario seed>
game.build_new()
```

Do not treat an earlier direct `static_random.set_seed(...)` call as authoritative across `build_new()`.

The scenario runner must restore any test-mutated configuration after each run so global settings do not leak between scenarios or reference/recovery processes.

For scenarios that do not cross `build_new()`, use the actual authoritative seed/load mechanism for that path rather than mechanically applying this rule.

Scenario 1 may remain a **strict PC-reference golden comparison** under this corrected deterministic input contract.

## Reference component-system bootstrap

Behavioral reference: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.

`app/engine/skill_system.py` and `app/engine/item_system.py` are reference-owned generated artifacts. The reference `.gitignore` ignores them, and the reference-owned component generator deterministically creates them from source inputs at the same revision.

Authorized bootstrap remains:

1. verify reference HEAD exactly;
2. run only `generate_component_system_source()`;
3. do not hand-edit generated files;
4. do not copy generated files from recovery;
5. record generated SHA-256 hashes;
6. ensure normal git status remains clean;
7. use the generated outputs only to make that exact reference revision runnable.

A different missing artifact may be generated without escalation only if the exact reference contains its generator and authoritative inputs, the output is clearly generated, and no recovery implementation is copied in.

## Scenario 17 contract

Scenario 17 remains a hybrid reference-anchored + recovery metamorphic invariant:

- **17A:** PC reference with debugger/profiler absent/disabled establishes the baseline;
- **17B:** recovery disabled must equal the reference baseline;
- **17C:** recovery debugger enabled-idle must equal recovery disabled after exiting temporary UI state and without mutating debug commands;
- **17D:** recovery profiler enabled-idle must equal recovery disabled in logical state/order/RNG; profiler diagnostics are provenance only.

There is no simulated PC-reference enabled-idle debugger/profiler golden.

## P1-T03 resume contract

Resume the same P1-T03 task using **GPT-5.6 Terra / high**.

- Re-run scenario 1 using the corrected engine-authoritative seed input and establish its reference/recovery result.
- Continue scenarios 2–16 and 18 as ordinary PC-reference golden scenarios.
- Run scenario 17 under the hybrid contract above.
- Use the accepted Trace V1 reference overlay only as instrumentation.
- Never copy recovery output into reference fixtures.
- Never silently regenerate a golden after a recovery mismatch.
- Do not repair gameplay or begin Phase 2.
- Report scenarios 1–18 individually; overall PASS is forbidden if any required scenario is skipped or unresolved.

If a new reference ambiguity, deterministic non-presentation trace divergence, save-format decision, competing semantic interpretation, cross-system invariant failure, or other global ESC condition appears, STOP and request **GPT-5.6 Sol / max**. Do not self-escalate.

## Gate status

P1-T03 is authorized to resume. Phase 2 remains blocked until P1-T03 completes and receives controller review.
