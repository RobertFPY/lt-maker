# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **ESC-01 / ESC-04** on scenario 3 (`Save/load during event where supported`)
- Controller disposition: **RESOLVED — scenario 3 is N/A (REFERENCE-UNSUPPORTED), not FAIL and not SKIPPED**
- Resume model: **GPT-5.6 Terra / high**
- Escalation target remains: **GPT-5.6 Sol / max**
- Escalation pre-authorized for any new issue: **NO**
- Controller gate after P1-T03: **YES — STOP FOR CONTROLLER REVIEW**
- Phase 2 remains **UNAUTHORIZED**
- Gameplay repair remains **UNAUTHORIZED** during P1-T03

## Scenario 3 controller decision — N/A at PC behavioral reference

`plan.md` intentionally defines scenario 3 as **“Save/load during event where supported.”** The `where supported` qualifier is authoritative.

The PC behavioral reference is `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.

Repository history establishes that an explicit mid-event/load-anytime save-state feature existed temporarily before the behavioral reference and was then deliberately removed before the reference:

- `708feadf88274d8953bbf3bc0b72831641f2e96e` (`update save state`) added a separate `app/engine/save_state.py` system and F1–F9 quick save/load paths. Its implementation explicitly described live event snapshots and load-while-event behavior.
- `157c09b23ac18989c1e214801d9b0b1707600f2e` (`xoá save state`) removed `app/engine/save_state.py`, the F1–F9 mappings, driver checkpointing, and quick save/load handling.
- `157c09b23ac18989c1e214801d9b0b1707600f2e` is an ancestor of the behavioral reference; `9314f54b...` is 110 commits ahead of it with no ancestry break.
- The behavioral reference therefore does not contain that user-facing load-anytime/mid-event feature.

The reference core does serialize event processor state as part of ordinary `GameState.save()` / `GameState.load()`:

- state-machine names/temp state are saved;
- `EventManager.save()` serializes active events;
- `Event.save()` stores event identity and processor state;
- `EventProcessor.save()` stores command pointer/iterator state;
- restore reconstructs those objects.

That internal serialization capability is useful evidence, but it does **not** authorize P1-T03 to manufacture a synthetic mid-event save/load entry point after the explicit feature that exposed that behavior was removed before the behavioral reference.

### Scenario 3 disposition

Scenario 3 must be reported in the P1-T03 matrix as:

`N/A — REFERENCE-UNSUPPORTED`

with the history evidence above.

Rules:

- Do **not** select `testing_proj` chapter-1 `New Event`, `Switch`, or `TurnChange` and invent a save boundary merely to create a golden.
- Do **not** create a synthetic in-memory event fixture and call its interrupted/resumed behavior a PC-reference golden contract.
- Do **not** add or restore `save_state.py`, F-key handling, hard-reset load behavior, or any compatibility overlay on the reference.
- Do **not** generate a Scenario-3 golden trace/fixture.
- Scenario 3 is **resolved**, not skipped. Its N/A status satisfies the `where supported` qualifier; it does not permit any other required scenario to be skipped.
- Preserve later/current save-load functionality under INV-08. Its intended behavior must be audited under the later save/load recovery work (Phase 5 and the save/load/restart feature sweep), using the appropriate later-feature contract rather than inventing a PC-reference golden for a feature absent at `9314f54b`.

## Provisional P1-T03 evidence accepted so far

The following executor evidence may be retained as P1-T03 work in progress, subject to final commit/diff/fixture review at the P1-T03 controller gate:

- **Scenario 1 PASS:** new-game deterministic seed is supplied through `cf.SETTINGS['random_seed']` before `GameState.build_new()`, and the modified setting is restored after the run; reference/recovery Trace V1 comparison passes.
- **Scenario 2 PASS:** real in-memory `game.save()` -> `game.load()` reference/recovery comparison passes.
- **Scenario 3 N/A — REFERENCE-UNSUPPORTED:** disposition defined above; no golden fixture is expected.

Do not treat this provisional acceptance as approval of uncommitted WIP or as authorization to weaken later final review.

## Resolved ESC-03 — new-game seed authority

For every scenario that crosses `GameState.build_new()` / new-game initialization, deterministic seed setup must use the engine-authoritative input:

```python
cf.SETTINGS['random_seed'] = <scenario seed>
game.build_new()
```

Do not treat an earlier direct `static_random.set_seed(...)` call as authoritative across `build_new()`. Restore any test-mutated configuration after each run so global settings do not leak between scenarios or processes.

Scenario 1 remains a strict PC-reference comparison under this corrected deterministic input contract.

## Reference component-system bootstrap

`app/engine/skill_system.py` and `app/engine/item_system.py` are reference-owned generated artifacts. The behavioral reference contains their generator and authoritative inputs, while `app/engine/.gitignore` intentionally ignores the generated outputs.

Authorized reference bootstrap remains:

1. verify reference HEAD exactly `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`;
2. run only `generate_component_system_source()`;
3. do not hand-edit generated files;
4. do not copy generated files from recovery;
5. record generated SHA-256 hashes;
6. ensure normal git status remains clean;
7. use those outputs only to make that exact reference revision runnable.

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

- Retain the current uncommitted Scenario-1/Scenario-2 test-owned WIP if it conforms to the contracts above.
- Record Scenario 3 as `N/A — REFERENCE-UNSUPPORTED` with history evidence and no golden fixture.
- Continue scenarios 4–16 and 18 as ordinary PC-reference golden scenarios.
- Run scenario 17 under the hybrid contract above.
- Use the accepted Trace V1 reference overlay only as instrumentation.
- Never copy recovery output into reference fixtures.
- Never silently regenerate a golden after a recovery mismatch.
- Do not repair gameplay or begin Phase 2.
- Report all scenarios 1–18 individually. Scenario 3 N/A is resolved and is not a skip; overall PASS remains forbidden if any other required scenario is skipped or unresolved.

If a new reference ambiguity, deterministic non-presentation trace divergence, save-format decision, competing semantic interpretation, cross-system invariant failure, or other global ESC condition appears, STOP and request **GPT-5.6 Sol / max**. Do not self-escalate.

## Gate status

P1-T03 is authorized to resume under the Scenario-3 decision above. Phase 2 remains blocked until P1-T03 completes and receives controller review.
