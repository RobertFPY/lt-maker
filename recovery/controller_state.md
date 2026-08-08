# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the current P1-T03 authorization and resolved blockers.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor result: **Scenario 5 PASS** under the approved deterministic virtual-frame contract
- Controller disposition: **Scenario 5 provisionally accepted; resume scenarios 6–18**
- Resume model: **GPT-5.6 Terra / high**
- Escalation target remains: **GPT-5.6 Sol / max**
- Escalation pre-authorized for any new issue: **NO**
- Controller gate after P1-T03: **YES — STOP FOR CONTROLLER REVIEW**
- Phase 2 remains **UNAUTHORIZED**
- Gameplay repair remains **UNAUTHORIZED** during P1-T03

## Scenario 5 controller decision — deterministic virtual frame driver

Scenario 5 originally reached a real `MapCombat` and then stopped at an active state stack equivalent to `['free', 'combat', 'exp']`, with the combat object in `post_combat`, because the test runner repeatedly called the state machine without advancing `app.engine.engine.constants['current_time']`.

This was a harness mismatch, not evidence of a recovery regression.

### Reference behavior

The PC reference game loop performs this order once per outer frame:

1. `engine.update_time()` updates `engine.constants['last_time']`, `current_time`, and `delta_t`;
2. one `game.state.update(event, surf)` executes;
3. any `repeat` chain is executed immediately with `game.state.update([], surf)` **without another time update**;
4. the next outer frame updates engine time again.

`engine.get_time()` returns the stored `engine.constants['current_time']`; it does not itself read wall clock time.

The PC reference targets 60 FPS and defines `FRAMERATE = 1000 // FPS = 16` ms. `utils.frames2ms(1)` also truncates to 16 ms.

### Why EXP must be drained before the terminal checkpoint

EXP is not merely cosmetic presentation. `ExpState` uses engine time to gate gameplay mutations including, depending on the result:

- `GainExp`;
- mana changes;
- level increments/decrements;
- growth-point changes;
- stat changes;
- record updates;
- level-up triggers;
- WEXP and learned-skill effects.

For standard `MapCombat`, `clean_up1()` schedules/handles EXP-related work and the map combat enters `post_combat`. Only after the EXP state leaves the stack can combat resume and execute `clean_up2()`, which performs final state-stack handling, `CombatEnd`, post-combat/end-combat behavior, records/messages/death handling, and other terminal effects.

Therefore `combat.cleanup.complete` remains a fully committed terminal synchronization point. There is **no pending-transition exception** and no checkpoint while `exp` or `combat` remains active.

### Authorized P1-T03 virtual-frame contract

P1-T03 may use a **test-owned runner helper only** that deterministically emulates the normal outer-frame timing contract on both the PC reference process and the recovery process.

For each scenario using this helper:

1. Before constructing any time-sensitive scenario object, save the original values of:
   - `engine.constants['current_time']`;
   - `engine.constants['last_time']`;
   - `engine.constants['delta_t']`.
2. Initialize a deterministic scenario clock, normally `current_time = 0`, `last_time = 0`, `delta_t = 0`, unless an already-approved scenario setup requires another deterministic starting value.
3. At the start of each **outer virtual frame**:
   - set `last_time = current_time`;
   - increment `current_time` by `FRAMERATE` (16 ms);
   - set `delta_t = FRAMERATE`.
4. Run one `game.state.update(event, surf)`.
5. While that call returns `repeat`, run `game.state.update([], surf)` repeatedly **without advancing virtual time**, matching `driver.run()`.
6. Advance time again only for the next outer virtual frame.
7. Use only scenario-authorized logical input. EXP draining itself receives no synthetic gameplay input.
8. Restore the saved engine timing constants in `finally`/teardown so time state cannot leak between scenarios.

The helper must remain test-owned and must not modify production `engine.update_time()`, `engine.get_time()`, combat code, EXP code, or state-machine semantics.

The virtual timestamp/frame count is driver provenance only and must not be added to Trace V1 logical equality or golden state.

### Forbidden shortcuts

For Scenario 5 and any later scenario reusing this helper, do **not**:

- call combat `skip()` merely to bypass timing unless that scenario explicitly tests fast-forward/skip behavior;
- use a no-EXP/no-growth/no-level-up flag to avoid EXP;
- mutate `exp_instance` or combat state directly;
- jump an `ExpState` internal state manually;
- monkeypatch gameplay functions to force completion;
- use a pending-transition exception;
- checkpoint with `combat`, `exp`, `wait`, or another incomplete terminal state still active;
- use host/wall-clock sleeps as the deterministic contract.

### Scenario 5 result

Scenario 5 now satisfies the approved terminal contract:

- the test-owned virtual-frame helper uses `FRAMERATE = 16`;
- time advances only on outer frames and repeat chains run at fixed virtual time;
- original `current_time`, `last_time`, and `delta_t` are restored in `finally`;
- real `MapCombat` completes naturally through EXP and terminal cleanup;
- no skip/no-EXP/state mutation/pending exception is used;
- the PC reference and recovery Trace V1 comparison passes.

Scenario 5 is therefore **provisionally accepted as PASS**, subject to final P1-T03 commit/diff/fixture review.

## Provisional P1-T03 evidence accepted so far

The following executor evidence may be retained as P1-T03 work in progress, subject to final commit/diff/fixture review at the P1-T03 controller gate:

- **Scenario 1 PASS:** still passes after the runner uses a real committed map-control `free` state; new-game deterministic seed is supplied through `cf.SETTINGS['random_seed']` and restored after the run.
- **Scenario 2 PASS:** real in-memory `game.save()` -> `game.load()` reference/recovery comparison passes.
- **Scenario 3 N/A — REFERENCE-UNSUPPORTED:** no golden fixture is expected; see the controller decision below.
- **Scenario 4 PASS:** real PC restart-slot flow using `save.save_io(kind='start')` followed by `save.load_game` matches reference/recovery.
- **Scenario 5 PASS:** real `MapCombat` completes under the approved deterministic virtual-frame driver through EXP and `clean_up2()`/terminal cleanup, and reference/recovery Trace V1 comparison passes.

Do not treat this provisional acceptance as approval of uncommitted WIP or as authorization to weaken later final review.

## Scenario 3 controller decision — N/A at PC behavioral reference

`plan.md` intentionally defines scenario 3 as **“Save/load during event where supported.”** The `where supported` qualifier is authoritative.

The PC behavioral reference is `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.

Repository history establishes that an explicit mid-event/load-anytime save-state feature existed temporarily before the behavioral reference and was then deliberately removed before the reference:

- `708feadf88274d8953bbf3bc0b72831641f2e96e` (`update save state`) added a separate `app/engine/save_state.py` system and F1–F9 quick save/load paths. Its implementation explicitly described live event snapshots and load-while-event behavior.
- `157c09b23ac18989c1e214801d9b0b1707600f2e` (`xoá save state`) removed `app/engine/save_state.py`, the F1–F9 mappings, driver checkpointing, and quick save/load handling.
- `157c09b23ac18989c1e214801d9b0b1707600f2e` is an ancestor of the behavioral reference; `9314f54b...` is 110 commits ahead of it with no ancestry break.
- The behavioral reference therefore does not contain that user-facing load-anytime/mid-event feature.

The reference core does serialize event processor state as part of ordinary `GameState.save()` / `GameState.load()`, but that internal serialization capability does not authorize P1-T03 to manufacture a synthetic mid-event save/load entry point after the explicit feature that exposed that behavior was removed before the behavioral reference.

Scenario 3 must be reported as:

`N/A — REFERENCE-UNSUPPORTED`

Do not create a Scenario-3 golden fixture, synthetic event/save boundary, or reference overlay implementing the removed feature. Preserve later/current save-load functionality under INV-08 for later save/load recovery work.

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

- Retain the current uncommitted Scenario-1 through Scenario-5 WIP only if it conforms to the approved contracts above.
- Continue scenarios 6–16 and 18 as ordinary PC-reference comparisons.
- The approved virtual-frame helper may be reused where a scenario naturally depends on normal engine frame progression, but it may not be used to bypass required player decisions or semantic inputs.
- Run scenario 17 under the hybrid contract above.
- Use the accepted Trace V1 reference overlay only as instrumentation.
- Never copy recovery output into reference fixtures.
- Never silently regenerate a golden after a recovery mismatch.
- Do not repair gameplay or begin Phase 2.
- Report all scenarios 1–18 individually. Scenario 3 N/A is resolved and is not a skip; overall PASS remains forbidden if any other required scenario is skipped or unresolved.

If a new reference ambiguity, deterministic non-presentation trace divergence, required player-choice ambiguity, save-format decision, competing semantic interpretation, cross-system invariant failure, or other global ESC condition appears, STOP and request **GPT-5.6 Sol / max**. Do not self-escalate.

## Gate status

P1-T03 is authorized to continue from Scenario 6. Phase 2 remains blocked until P1-T03 completes and receives controller review.
