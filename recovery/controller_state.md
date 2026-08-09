# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 6**
- Phase 1 harness / immutable Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- Phase 5 save/load/restart consolidation: **ACCEPTED**
- P6-T01 runtime capability audit/design: **ACCEPTED** at `017e73c3164a56712a823016a7cfe642c75bbd17`
- P6-T02 Android audio/resource policy migration: **ACCEPTED** at `cb217eb4b10d993c14594ce30b98e22cec05b405`
- Active task: **P6-T03 only — Migrate accepted Android scheduling policy**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- Phase 7+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P6-T03: **YES — STOP FOR CONTROLLER REVIEW**

## P6-T02 acceptance record

The controller accepts `cb217eb4b10d993c14594ce30b98e22cec05b405` (`refactor(android): isolate audio policy`).

Accepted evidence:

- it is one direct descendant of P6-T02 authorization commit `a90ed76beccbafea423c82a0adf2a539d2c115ba`;
- production changes are bounded to `app/engine/sound.py` and the existing physical-audio/preload callers in animation combat, title, game over, sound room, and loading state, plus focused tests;
- no Event/tilemap scheduling, canonical load/restart, project data, Trace V1, comparator, manifest, or golden fixture changed;
- the implementation extends the existing `SoundController` abstraction rather than creating a parallel audio controller or service locator;
- semantic music NID selection and lifecycle timing remain in their existing callers; the sound subsystem owns only physical backend selection/fallback and playback restoration;
- desktop `play_music` remains the legacy cached/fade path;
- Android stream success uses the existing stream path once with no legacy double-play; stream failure falls back exactly once to the established legacy path;
- streamed battle playback returns a bounded restore handle owned by the sound subsystem; animation combat still decides when battle music starts/finishes and which NID is selected;
- Sound Room retains caller-owned `request_present` before synchronous Android stream loading and retains existing UI/action ordering;
- `LoadingState` still computes the exact level-song set; `SoundController.prepare_level_songs` owns only platform-specific flush/preload execution and receives only the controller plus NID set;
- worker audio preparation does not receive `GameState`, Event, solver, board, units, save publication, or state machine;
- timing-sensitive render/cache branches were intentionally not migrated;
- immutable S5/S7/S8/S16/S17/S18 and focused audio/loading/canonical/tilemap/debugger/profiler tests were reported PASS with unchanged goldens.

## Controller decision — Event.process Android 2 ms deadline

The unresolved P6-T01 scheduling question is now resolved.

### Decision: REJECT / RESTORE-PC-SEMANTICS

Current `Event.process()` uses `is_android_render_optimization_enabled()` plus a 2 ms `perf_counter()` deadline. After at least one command, expiration can set `_android_process_yielded` and return while the Event is still semantically in `processing`; `_update_state()` then stops further processor work for that outer update.

The PC behavioral reference has no wall-clock command deadline: while an Event remains in `processing`, commands continue synchronously until the event/command itself creates a semantic boundary such as waiting, pause/block, completion, or another explicit state transition.

Therefore the Android deadline is **not** an accepted presentation optimization and is not an approved `CAP-WORK-BUDGET` seam.

Classification:

- `GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK`
- `RESTORE-PC-SEMANTICS`

Rationale:

- the deadline can insert an outer-host-frame boundary solely because host wall-clock time elapsed;
- consecutive event commands may therefore become observable on different updates on Android even though no command requested a boundary;
- Event command ordering/lifecycle is authoritative gameplay semantics under INV-01/INV-04/INV-05;
- there is no proof that inter-command frame insertion is behaviorally equivalent;
- immutable traces passing under existing scenarios are insufficient proof for arbitrary event scripts.

P6-T03 must remove this deadline behavior completely. Do not replace it with a different command-count, wall-clock, coroutine, or frame budget.

Preserve separately accepted explicit semantic/presentation boundaries, including the fast-forward `waiting_for_present` fence where a command explicitly requests one presentation before continuation.

Performance consequence is accepted for recovery correctness: long uninterrupted event command batches may again consume one longer host frame. A future performance task may optimize individual expensive commands only through proven off-world/preparation boundaries; it may not reintroduce generic inter-command scheduling divergence.

## Accepted scheduling policy that MAY migrate

The only approved progressive gameplay-adjacent scheduling policy in P6-T03 is Phase-4 Android tilemap **off-world preparation**.

Accepted invariant:

```text
LIVE OLD WORLD
    -> progressively build pending TileMap/GameBoard/Boundary off-world
    -> validate complete pending structures
    -> one synchronous authoritative commit or synchronous rollback
LIVE NEW/RESTORED WORLD
```

The Event-local `_android_tilemap_pending` barrier remains mandatory. It blocks movement, gameplay input/listeners, later event commands, and presentation exposure as already accepted. It is semantic proof machinery, not a generic platform service.

The current 4 ms `TilemapChangeJob` preparation budget is eligible to move behind a narrow runtime work-budget policy.

## P6-T03 — authorized scope

Execute **P6-T03 only** using **GPT-5.6 Terra / high**.

Escalation target: **GPT-5.6 Sol / max**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Mandatory design input:

`recovery/p6_t01_runtime_capability_map.md`

### Goal A — restore shared Event command scheduling

Remove the Android generic command deadline from `app/events/event.py`.

Required resulting behavior:

- no `android_process_budget_seconds` gameplay scheduling constant;
- no `_android_process_yielded` lifecycle flag;
- no `perf_counter()` deadline deciding whether another EventProcessor command runs;
- while Event state remains `processing`, run commands synchronously until a command/event creates an existing semantic boundary;
- preserve command queue ordering and SAVE-command queue rules;
- preserve profiler observation without profiler state deciding lifecycle;
- preserve `waiting_for_present` as an explicit accepted presentation fence;
- preserve normal wait/dialog/paused/blocked/complete semantics;
- preserve fast-forward INV-06 behavior.

Do not redesign EventProcessor or introduce a replacement scheduler.

### Goal B — migrate only the accepted tilemap off-world work budget

Create/use a narrow work-budget capability only for the proven Phase-4 pending tilemap preparation.

Approved shape is equivalent to:

```python
@dataclass(frozen=True)
class OffWorldWorkBudget:
    enabled: bool
    deadline_ns: int


def tilemap_prepare_budget() -> OffWorldWorkBudget:
    ...
```

Exact naming/module may vary if a smaller source-aligned API is cleaner.

Default/desktop:

- progressive tilemap preparation disabled;
- `change_tilemap` remains the P4-T02 synchronous build + synchronous commit path.

Android:

- progressive pending/off-world preparation enabled;
- preserve the accepted 4,000,000 ns budget unless source/tests require escalation;
- `should_skip` may continue to drain pending preparation without the normal deadline as already established;
- final commit remains one synchronous operation.

Preferred dependency direction:

```text
event_functions -> narrow work-budget policy -> android_runtime/config
                  -> TilemapChangeJob receives immutable budget/config
```

The capability module must not import `GameState`, Event, action, combat, save, state machine, unit/board ownership, or other gameplay-critical modules.

Do not create a giant runtime capability registry/service locator.

### Tilemap barrier contract — locked

Do not weaken or move ownership of:

- `_android_tilemap_pending`;
- Event input/listener suspension while pending;
- movement suspension while pending;
- later Event command blocking while pending;
- `_defer_render` handling;
- synchronous commit;
- synchronous rollback-before-release;
- unit/region/aura/FOW/action-log ordering accepted in P4.

The work-budget policy may decide only whether pending preparation is enabled and the numeric budget for pending object construction/validation.

It may not own the Event barrier or authoritative commit.

### Explicitly rejected scheduling seams

Do not add/migrate budgets for:

- EventProcessor command batches;
- combat solver/actions/playback/cleanup;
- `GameState.load_iter` host-frame hydration;
- AddGroup/unit-by-unit live placement;
- save/load/restart publication;
- phase/initiative progression;
- aura/FOW/region live restoration;
- debugger/profiler execution.

### Authorized production surfaces

Expected:

- `app/events/event.py`
- `app/events/event_functions.py`
- `app/engine/jobs/tilemap_change_job.py`
- a narrow new `app/engine/runtime_capabilities/work_budget.py` (and minimal package `__init__.py`) if used

Narrow adjacent tests only.

If implementation requires changing P4 atomic commit architecture or P5 load/restart architecture, STOP under ESC-02/ESC-07/ESC-09.

## Required tests

At minimum prove:

1. With Android render optimization enabled, multiple consecutive EventProcessor commands with no semantic boundary execute in the same `Event.process()` call/update just as shared/reference semantics require.
2. Host wall-clock/perf-counter progression cannot itself defer the next Event command.
3. `_android_process_yielded` no longer controls Event lifecycle.
4. Explicit `waiting_for_present` still ends the current processing pass and resumes only on the established next-present boundary.
5. wait/dialog/paused/blocked/complete Event boundaries remain unchanged.
6. Event SAVE-command queue ordering remains unchanged.
7. fast-forward does not replay input edges or alter outcomes.
8. desktop tilemap change remains synchronous and registers no pending job/barrier.
9. Android tilemap preparation is enabled only through the narrow work-budget policy.
10. Android tilemap budget remains 4,000,000 ns unless explicitly escalated.
11. repeated pending updates mutate no live tilemap/board/unit/region/aura/FOW state before commit.
12. Event-local pending barrier still blocks movement, input/listeners, and later event commands.
13. final live tilemap commit remains synchronous and non-generator.
14. pending-build failure leaves old world authoritative.
15. live-commit failure rolls back synchronously before barrier release.
16. `should_skip` pending behavior remains bounded to off-world preparation and does not reintroduce partial live mutation.
17. the work-budget capability has no gameplay-critical imports.
18. P6-T02 audio policy tests remain green and no scheduling dependency leaks into sound policy.
19. P5 canonical load/restart tests remain green.
20. Phase-3 combat lifecycle tests remain green.

## Immutable proof

Run at minimum:

- S5 event scenario
- S12 aura
- S13 FOW/movement
- S14 tilemap
- S16 fast-forward
- S17 disabled/debugger-idle/profiler-idle
- S18 game-over/restart

Do not regenerate any golden.

Run focused suites for:

- Event/EventProcessor lifecycle and command ordering;
- fast-forward/presentation fence;
- tilemap change job/barrier/rollback;
- P6-T02 sound platform policy;
- canonical load/restart;
- combat lifecycle;
- debugger/profiler observer behavior;
- recovery trace/lifecycle/golden integrity.

Run broader unittest discovery and report known baseline/native Windows/test-isolation failures without repairing unrelated issues.

Then run:

- `python -m compileall -q app`
- `git diff --check`

Commit only bounded P6-T03 production/tests.

Then:

- `git show --check`
- `git status --short`

## Explicitly out of scope

Do not:

- begin Phase 7;
- retain the generic Event 2 ms deadline;
- replace it with another generic Event command scheduler;
- move the Event barrier into a generic capability;
- alter P4 live tilemap transaction ordering;
- alter P5 canonical load/restart semantics;
- alter P6-T02 audio policy semantics;
- migrate timing-sensitive render animation branches;
- change Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / high**.
Escalation target: **GPT-5.6 Sol / max**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** root cause requires unrelated architecture;
- **ESC-03** immutable trace divergence cannot be removed by bounded implementation;
- **ESC-04** competing Event semantics appear despite the explicit controller decision;
- **ESC-05** invariant failure/partial world becomes observable;
- **ESC-07** platform-policy boundary conflicts with gameplay semantics;
- **ESC-08** repeated bounded failure;
- **ESC-09** implementation requires new cross-cutting scheduler/platform architecture.

Do not self-escalate.

## Gate status

**P6-T02 is ACCEPTED. P6-T03 is the only authorized task. Phase 7 and later remain blocked pending controller review.**
