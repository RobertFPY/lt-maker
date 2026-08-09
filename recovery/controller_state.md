# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 7**
- Phase 1 deterministic Trace V1 harness/goldens: **ACCEPTED**
- Phase 2 GameState/state-machine atomicity: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- Phase 5 save/load/restart consolidation: **ACCEPTED**
- Phase 6 platform-policy boundary: **ACCEPTED**
- P6-T01 runtime capability audit/design: **ACCEPTED** at `017e73c3164a56712a823016a7cfe642c75bbd17`
- P6-T02 Android audio/resource policy migration: **ACCEPTED** at `cb217eb4b10d993c14594ce30b98e22cec05b405`
- P6-T03 accepted scheduling migration / Event semantic restore: **ACCEPTED** at `3c8c5479d292ce43fd3347a12dffa9d7c32fa7db`
- Active task: **P7-T01 only — Fast-forward equivalence suite**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P7-T02/P7-T03/P7-T04 and Phase 8+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P7-T01: **YES — STOP FOR CONTROLLER REVIEW**

## Phase 6 acceptance record

The controller accepts `3c8c5479d292ce43fd3347a12dffa9d7c32fa7db` (`fix(android): restore semantic event scheduling`) and closes Phase 6.

Accepted evidence:

- the commit is exactly one descendant of P6-T03 authorization commit `887877114d1f4d9aa1b94fac6d7e3afe6bd19479`;
- scope is bounded to Event scheduling cleanup, the Phase-4 tilemap scheduling caller/job, a narrow runtime work-budget capability, and focused tests;
- `Event.process()` no longer contains the Android 2 ms wall-clock command deadline, `android_process_budget_seconds`, or `_android_process_yielded` lifecycle behavior;
- consecutive EventProcessor commands now continue under shared semantics until the event/command itself creates a semantic boundary;
- `waiting_for_present` remains an explicit presentation fence; SAVE-command queue ordering remains intact;
- `EventState.should_defer_render()` now retains a previous frame only for the explicit `_defer_render` tilemap barrier rather than a generic command-budget yield;
- `OffWorldWorkBudget` is immutable and the work-budget module depends only on `android_runtime` platform detection;
- desktop `change_tilemap` remains synchronous and registers no pending job/barrier;
- Android retains exactly the accepted `4_000_000 ns` budget only for pending/off-world tilemap preparation;
- `TilemapChangeJob` consumes the injected immutable budget while its final commit remains synchronous;
- the Phase-4 `_android_tilemap_pending` Event barrier, movement/input/listener suppression, synchronous commit, synchronous rollback-before-release, aura/FOW/region/action-log ordering remain owned by the existing Event/tilemap transaction;
- P6-T02 sound policy is unchanged;
- immutable S5/S12/S13/S14/S16/S17/S18 and focused Event/fast-forward/tilemap/audio/load/restart/combat/debugger/profiler tests were reported PASS with unchanged Trace V1/goldens/project data;
- the known broad-suite shared-test pollution involving `_Uses.tag` remains unrelated baseline evidence and was not repaired in Phase 6.

### Non-blocking source note

`StateMachine.update()` still contains historical wording / profiler counter naming referring to an `event_budget_deferred_draw`. No generic Event command scheduler remains attached to that name; current render deferral is driven by the explicit state-owned `should_defer_render()` path, which for EventState is the accepted tilemap `_defer_render` barrier. Do not treat the stale observer label/comment as authorization to reintroduce command budgeting. Rename only if a later bounded task already touches that observer surface and tests prove no semantic impact.

## Locked Phase-6 platform boundary

Later tasks must preserve:

1. **Audio/resource policy:** `SoundController` owns physical streamed/cached selection and preload policy only. Semantic music selection and lifecycle timing remain caller-owned.
2. **Event commands:** no Android-specific generic wall-clock/command-count scheduling. Event commands share one semantic execution model.
3. **Tilemap scheduling:** Android may progressively prepare pending TileMap/GameBoard/Boundary off-world under the 4 ms work budget; the live commit/rollback remains atomic and Event-local barrier semantics remain mandatory.
4. **No giant platform service:** runtime capabilities stay narrow and cannot own gameplay, save/load, combat, input, or state-machine semantics.
5. **Protected prior phases:** canonical GameState load, restart, combat lifecycle, aura/FOW and state publication contracts remain stronger than any platform policy.

---

# P7-T01 — Fast-forward equivalence suite

Execute **P7-T01 only** using **GPT-5.6 Terra / medium**.

Escalation target: **GPT-5.6 Sol / high**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Fast-forward is a later intended feature absent from the PC reference. Its accepted hybrid contract is:

```text
fast-forward OFF on recovery == accepted recovery gameplay semantics
fast-forward ON              == fast-forward OFF logical outcomes
```

Only presentation/host timing may differ.

## Goal

Build and run a deterministic ON/OFF equivalence suite proving INV-06 across representative gameplay lifecycles.

This is **test/evidence first**. Do not change production code merely to make a harness convenient.

A bounded production fix is allowed only if a failing equivalence test identifies a local fast-forward-specific defect whose correct behavior is unambiguous from the OFF path and whose fix does not reopen Phase-2/3/4/5/6 architecture. Otherwise STOP for controller review or named escalation.

## Current implementation contract to test

Current driver behavior includes:

- `FAST_FORWARD` held -> `get_fast_forward_steps()` uses normalized speed;
- supported speeds are 200..800 percent in 100-percent steps; default is 300 percent;
- one host input snapshot may drive multiple logical game updates;
- only the first logical substep receives the host input event; later substeps receive `[]`;
- transient input is consumed before repeat chains/additional logical substeps so key/click/text edges cannot replay;
- additional fast-forward substeps advance virtual engine time using the bounded fast-forward step;
- states with `blocks_fast_forward` may stop the extra substeps;
- a `request_present` / presentation barrier may force one draw and stop remaining fast-forward substeps;
- rendering intermediate substeps may be deferred, but logical `update_visuals()` still advances according to the established state-machine lifecycle.

These mechanisms are implementation details. P7-T01 proves their *outcomes*, not their exact current structure.

## Critical equivalence-runner rule

Do **not** pair ON/OFF runs by host-frame number.

Fast-forward intentionally changes how many logical substeps fit in one host frame, so `frame N` does not identify the same logical input opportunity.

Pair runs using the same:

- initial save/snapshot/world setup;
- RNG seed/state;
- configuration except fast-forward state/speed;
- ordered user-intent/input script;
- logical readiness condition/checkpoint for each input;
- terminal logical checkpoint.

Inputs must be injected when the same logical state is ready for that action, not after the same number of rendered frames.

Host frame count, number of draws, wall-clock time, profiler counters and audio/render state are not equality fields.

## Required equality dimensions

For each ON/OFF pair compare, where applicable:

- ordered state transitions at logical checkpoints;
- normalized action sequence/action log effects;
- RNG state and RNG-dependent outcomes;
- combat solver outcome and ordered gameplay playback effects;
- HP/mana and death state;
- EXP/level/promotion outcome;
- item durability/uses/costs/consumption;
- skills/statuses and proc outcomes;
- unit positions, finished/dead flags and team/phase state;
- FOW/visited/bounds/regions/aura logical state when exercised;
- triggered Event order and Event command completion;
- game/level variables touched by the scenario;
- save-relevant logical state when a scenario crosses a save-capable boundary;
- final active/pending state stack;
- final Trace V1 logical state / semantic delta hashes where the existing recorder supports the boundary.

Equal terminal state alone is insufficient if actions/hooks/events/RNG were duplicated, skipped or reordered.

## Required scenario matrix

Use existing recovery scenarios/harnesses whenever they provide sufficient semantic coverage rather than inventing duplicate infrastructure.

At minimum include deterministic ON/OFF pairs covering:

1. **Event command chain** — multiple consecutive semantic Event commands, waits/explicit presentation fence where applicable, and final Event completion. This must prove the removed P6 generic Event budget is not replaced by fast-forward scheduling divergence.
2. **Movement + Wait / FOW** — movement commits, FOW vantage/visited behavior and Wait finalization; no duplicate input edge on extra substeps.
3. **Combat** — at least one representative combat that exercises RNG, ordered actions/playback, durability/cost, HP/death and EXP/skill/status hooks as available in existing fixtures.
4. **Combat presentation lifecycle** — animated/map/simple path coverage sufficient to prove presentation acceleration does not change solver/actions/cleanup order. Reuse Phase-3 lifecycle tests rather than reopening combat architecture.
5. **Phase/upkeep transition** — turn/phase or initiative progression with statuses/upkeep if existing deterministic fixtures support it.
6. **Interactive blocking state** — a choice/menu/text/input-owned state with `blocks_fast_forward` or equivalent protection; holding FAST_FORWARD must not auto-consume/replay a selection edge.
7. **Explicit presentation fence** — `request_present` causes the required cue boundary without changing logical effects or replaying input.
8. **Speed invariance** — compare OFF against at least the default 300% and boundary speeds 200% and 800% for a deterministic representative scenario. All supported speeds must use the same semantic model; if exhaustive 200..800 is cheap, run all.
9. **Observer coexistence** — fast-forward with debugger/profiler idle where existing S17 harness supports it; observer enablement must not change the ON/OFF logical result.
10. **Game-over/restart boundary** if exercised by existing S18 without creating a new save-format test; fast-forward must not alter the resulting restart/game-over semantics.

S16 remains the existing hybrid fast-forward golden/oracle and must pass unchanged, but P7-T01 must add broader direct ON/OFF equivalence proof rather than treating one immutable S16 fixture as sufficient.

## Input-edge invariants

Explicitly prove:

- SELECT/BACK/START/directional/text/click edge used on the first logical substep is not replayed on additional substeps;
- held FAST_FORWARD itself may remain held and request extra updates;
- entering a fast-forward-blocking state during a host frame stops extra updates before a second logical input opportunity can be consumed;
- repeat chains receive no replayed transient input;
- explicit presentation fences do not cause the original input edge to be delivered again when processing resumes.

## Time/presentation handling

Do not assert equal:

- host-frame count;
- draw count;
- wall-clock duration;
- audio playback position;
- animation surface/cache state;
- profiler timing samples.

Do assert that virtual-time acceleration cannot change gameplay outcomes. If a timer/wait affects gameplay rather than presentation, compare its resulting logical effect/order, not the numeric host time used to reach it.

## Trace/golden rules

- Reuse immutable Trace V1 fixtures/comparator.
- Do not modify Trace V1 schema, normalizers, manifest or goldens.
- Do not regenerate S16 or any other fixture.
- If an existing immutable scenario diverges, determine the first logical checkpoint/delta difference.
- A golden mismatch is evidence; never normalize it away.
- If the harness cannot express ON/OFF equivalence without changing Trace V1 schema, STOP under ESC-03/ESC-09 rather than editing the oracle in this task.

## Production-change boundary

Default expected changes:

- focused tests;
- optionally `recovery/p7_t01_fast_forward_equivalence.md` for the final matrix/evidence.

Production files should remain unchanged if all equivalence tests pass.

If a local production defect is found, before changing code record:

```text
FAST-FORWARD DIVERGENCE
scenario:
OFF first differing checkpoint/effect:
ON first differing checkpoint/effect:
input readiness condition:
RNG before/after:
state stack before/after:
local suspected owner:
prior-phase contract touched: YES/NO
```

A local fix may touch only the demonstrated fast-forward/input/presentation owner. If the proposed fix changes combat solver/action ordering, Event semantics, canonical load/restart, Phase-4 live tilemap atomicity, or platform-policy boundaries, STOP and escalate/review.

## Required focused tests

Run/add focused coverage for at least:

- `driver.get_fast_forward_steps` and all supported speed normalization;
- `update_game_state` transient-input consumption;
- `update_game_state_for_frame` first-substep input / later-empty-input behavior;
- `blocks_fast_forward` entry and already-current behavior;
- presentation-barrier termination of remaining substeps;
- state-machine repeat chain input behavior;
- Event processing/presentation-fence tests from P6-T03;
- Phase-3 combat lifecycle tests;
- movement/FOW regression tests;
- phase/initiative/upkeep tests relevant to chosen scenario;
- debugger/profiler idle observer tests.

## Immutable proof

Run at minimum:

- S5
- S7
- S8
- S13
- S16
- S17 disabled
- S17 debugger-idle
- S17 profiler-idle
- S18

Add S12/S14 if touched by the chosen ON/OFF scenario or any production fix.

All invoked immutable scenarios must match existing fixtures exactly.

Run recovery trace/lifecycle/golden integrity suites.

Run broader unittest discovery and report known baseline/native/test-isolation failures without repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit bounded P7-T01 tests/report and only any explicitly justified local production fix
- `git show --check`
- `git status --short`

## Explicitly out of scope

Do not:

- begin P7-T02/P7-T03/P7-T04 or Phase 8;
- redesign fast-forward into a new scheduler;
- reintroduce Android Event command budgeting;
- alter combat solver/actions/hooks/cleanup semantics;
- alter P4 tilemap atomicity/barrier semantics;
- alter P5 load/restart/save schema semantics;
- alter P6 sound/work-budget policy semantics;
- change Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / medium**.
Escalation target: **GPT-5.6 Sol / high**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** divergence root cause is nonlocal;
- **ESC-03** immutable trace divergence cannot be resolved by a bounded local correctness fix;
- **ESC-04** multiple plausible fast-forward semantics exist instead of the OFF path being an unambiguous oracle;
- **ESC-05** invariant failure/partial gameplay state becomes observable;
- **ESC-07** fixing equivalence would require a new platform gameplay fork;
- **ESC-08** repeated local fix failure;
- **ESC-09** a new cross-cutting scheduler/harness architecture appears necessary.

Do not self-escalate.

## Gate status

**Phase 6 is ACCEPTED. P7-T01 is the only authorized task. P7-T02 and later remain blocked pending controller review.**
