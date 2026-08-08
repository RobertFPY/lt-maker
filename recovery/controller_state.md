# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 4**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- P3-T01 combat lifecycle reference map: **ACCEPTED** at `ab16e7a149deaeb17d4398f298b3aebc234bc22e`
- P3-T02 Simple/Map transaction restore: **ACCEPTED** at `c20b9e02f853b0e527cf074e8168a442f353136f`
- P3-T03 Base/Animation/Arena ordering restore: **ACCEPTED** at `3ab40895ef7170e01e55dc4f1bf2b63889383832`
- P3-T04 combat preservation sweep: **ACCEPTED** at `090a72d984f8912864e6607f037285f97a01ce69`
- Active task: **P4-T01 only — Decompose staged tilemap optimization**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- P4-T02/P4-T03 and Phase 5+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P4-T01: **YES — STOP FOR CONTROLLER REVIEW**

## Phase 3 acceptance record

The controller accepts `090a72d984f8912864e6607f037285f97a01ce69` (`docs(recovery): audit P3-T04 preservation`) and closes Phase 3.

Accepted evidence:

- the commit is a single direct descendant of P3-T04 authorization commit `2d6f4e7cd3daf8674a3ad3a3170be9c9ffe8beb2`;
- the only changed file is `recovery/p3_t04_combat_preservation.md`; no production, test, Trace V1, comparator, manifest, golden JSONL, save schema, or project-data file changed;
- the preservation sweep found no demonstrated bounded production regression after accepted P3-T02/P3-T03 ordering repairs;
- cleanup ordering remains protected: combat skill/item cleanup hooks precede unusable/broken handling, then WEXP/mana/EXP and `BeforeCombatEnd`; `clean_up2` preserves state-stack handling, `CombatEnd`, rewards/supports, end/post hooks, final RNG recording, and death handling;
- durability/use-cost handling remains the later correctness behavior: one loss per combat is committed in cleanup before broken/unusable handling;
- promotion/class-change behavior remains preserved, including cancellable map promotion and `BaseCombat.finalizes_turn=False` for prep/base use;
- targeted `CombatCondition` cache invalidation after publishing mutable condition state is retained; no broad speculative cache clear was introduced;
- aura child skills remain derived/nonserialized and authoritative source-owned teardown remains intact;
- fast-forward INV-06 and debugger/profiler INV-07 remain satisfied;
- Android streamed battle music, map-track restoration, render/UI caches, and resource staging remain platform/presentation policy and do not own authoritative combat mutation;
- immutable comparisons S5, S6, S7, S8, S9, S10, S11, S12, S16, and S17 PASS against unchanged Phase-1 oracle contracts;
- focused combat/component/observer tests and Android policy tests were reported PASS; broader-suite Windows native termination and known baseline/test-isolation issues remain unrelated and were not modified;
- `python -m compileall -q app`, `git diff --check`, and `git show --check` PASS.

Phase 3 therefore establishes the accepted combat contract for later phases:

1. Simple, Map, Base, Animation, and Arena authoritative ordering is reference-shaped at PC-reference logical boundaries;
2. solver formulas, RNG primitives, generated actions, and playback semantics remain shared and unchanged;
3. cleanup/durability/promotion/cache/aura correctness fixes are preserved;
4. presentation/resource work may remain progressive only when it cannot mutate or reorder authoritative gameplay;
5. Android streamed battle music remains platform policy;
6. later phases must not reopen combat lifecycle architecture without a demonstrated regression and controller authorization.

## P4-T01 — authorized audit scope

Execute **P4-T01 only** using **GPT-5.6 Terra / high**.

This is an **audit/decomposition task only**. It does not authorize P4-T02 or P4-T03 implementation.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Immutable Phase-1 goldens remain the behavioral oracle, especially S12 aura lifecycle, S13 FOW movement semantics, S14 tilemap change commit, S15 phase transition where board/event state can interact, and S17 observer equivalence. Do not regenerate or weaken them.

### Core invariant

P4 is governed by INV-03/INV-04/INV-05 and this transaction contract:

```text
LIVE OLD STATE
    -> build pending structures outside live authoritative gameplay state
    -> validate pending structures completely
    -> one atomic logical commit on the main thread
LIVE NEW STATE
```

No normal State/event/input/debugger observer may see a partially detached or partially published world.

### High-risk history to decompose

Audit individual operations, not whole commits:

- `cdd4be2a7ebc78131469d31da551f0f63bacd78d` — staged tilemap board rebuild;
- `6b96e2f10bbae2c039e4b2dc5e145fd30e2fdf2c` — batched tilemap transition state;
- `cd8607b6` — incremental event `add_group` work where relevant to event atomicity;
- any follow-up commit that changes board/tilemap/event scheduling, rollback, render deferral, aura/fog/region rebuilding, or commit visibility.

Important accepted starting observation for the audit:

- `cdd4be2a` introduced pending `TileMapObject`, `GameBoard`, and `BoundaryInterface` construction and validation before a final callback; this pending-build concept may be reusable if truly off-world;
- `6b96e2f1` then made the **commit callback itself a generator** and yielded between authoritative operations such as unit detachment, region removal, live tilemap/board/boundary publication, and unit/region restoration. That commit-phase yielding is presumptively unsafe and must be mapped precisely against the PC reference and S14 rather than retained for performance by default.

### Required surfaces

Audit at minimum:

- `app/engine/game_board.py`
  - `GameBoard.__init__`
  - `GameBoard.build_iter`
  - `_initialize_iter` and incremental helpers;
- `app/engine/jobs/tilemap_change_job.py`
  - state machine;
  - board iterator;
  - commit iterator;
  - frame budget;
  - validation/failure behavior;
- `app/events/event_functions.py`
  - `change_tilemap`;
  - its commit/rollback logic;
  - unit/region detach and restore;
  - `action_log.set_first_free_action`;
  - `game.on_alter_game_state`;
  - relevant `add_group`/incremental event helpers;
- `app/events/event.py` and `app/events/event_state.py`
  - `should_update`/blocked callbacks;
  - `_defer_render`;
  - Android/event yield scheduling;
  - whether blocked/event states can expose live partial gameplay state;
- board/tilemap consumers and reconstruction paths affecting:
  - aura propagation/teardown;
  - terrain skills/statuses;
  - FOW/visited tiles;
  - regions including FOG/VISION;
  - boundary registration;
  - cursor/movement/map_view replacement;
  - unit position/previous_position;
  - skill and terrain-status registries;
  - action-log/turnwheel boundary;
- tests added around tilemap jobs/rollback/batching and any later fixes.

### Required semantic analysis

For the PC reference and current recovery, produce exact ordered transaction maps for:

1. normal `change_tilemap` to a different map;
2. reload-map path with unit position restoration + offset;
3. region restoration including FOG/VISION effects;
4. overworld-to-level or any path that replaces cursor/movement/map_view;
5. failure during pending board construction;
6. failure during current commit/restore stages;
7. event blocking/render-deferral lifecycle while the job runs;
8. incremental `add_group` or other event work that can publish gameplay changes across frames.

For every yield/batch boundary answer:

- what authoritative objects have already mutated;
- what objects remain old versus new;
- what normal State/event/debugger code can execute before the next step;
- whether RNG, hook/event ordering, aura/FOW/region state, board occupancy, or action-log history can be observed in a reference-impossible intermediate state;
- whether the work is pure pending computation, presentation-only deferral, or authoritative mutation;
- whether Android-specific scheduling can be retained without a gameplay fork.

### Classification

Classify every relevant function/state/change as one of:

- KEEP-SHARED
- KEEP-PLATFORM
- REWRITE-PLATFORM
- RESTORE-PC-SEMANTICS
- REMOVE-WORKAROUND
- KEEP-CORRECTNESS-FIX

Also classify each operation by semantic category:

- pending/off-world computation;
- authoritative gameplay mutation;
- atomic publication;
- rollback/error recovery;
- presentation/render deferral;
- profiler/observer only.

### Deliverable

Create only:

`recovery/p4_t01_tilemap_atomicity_map.md`

The report must contain:

1. function/caller graph for GameBoard build, TilemapChangeJob, `change_tilemap`, Event/EventState scheduling, and affected board/aura/FOW/region helpers;
2. PC-reference vs current ordered transaction maps for all required paths;
3. a yield/batch boundary table showing exactly what is live at every boundary;
4. function-level classification with provenance, invariant/risk, proposed later treatment, dependencies, and exact Phase-1 proof;
5. rollback analysis distinguishing correctness recovery from permission to publish partial state;
6. event render-deferral analysis: what it hides visually versus what remains logically observable;
7. explicit P4-T02 candidate list for restoring desktop/reference atomic semantics;
8. explicit P4-T03 candidate list for Android-only pending/off-world preparation that could remain or be re-ported after P4-T02;
9. one proposed atomic commit boundary for later implementation, as design only;
10. unresolved controller decisions/escalation evidence.

### Design constraint for proposed P4-T02/P4-T03 boundary

The audit should prefer this shape unless source evidence proves it impossible:

- expensive tilemap/terrain/board/boundary construction may occur against pending objects only;
- live unit/region/aura/FOW/action-log state remains untouched during pending construction;
- once pending structures validate, perform the PC-reference detach/publish/restore/action-log sequence as one synchronous main-thread logical transaction;
- no yield inside that authoritative commit;
- rollback may be retained as a correctness safeguard, but rollback does not make intermediate publication safe;
- Android frame-spreading is allowed only before the atomic commit and only on non-authoritative pending data.

Do not implement this during P4-T01.

### Validation

Because P4-T01 is audit-only:

- run existing S12, S13, S14, S15, and S17 immutable comparisons without modifying fixtures;
- run existing tilemap-change/job/event/FOW/aura/region tests needed to support claims;
- run `git diff --check`;
- commit only `recovery/p4_t01_tilemap_atomicity_map.md`;
- run `git show --check`;
- report exact source/history/test evidence used.

### Explicitly out of scope

Do not:

- modify production code;
- modify tests to change semantics;
- begin P4-T02/P4-T03;
- change GameBoard/tilemap/event behavior;
- change Trace V1/comparator/manifest/goldens;
- change project data;
- reopen accepted Phase-2 restore or Phase-3 combat semantics;
- revert `cdd4be2a`, `6b96e2f1`, `52bd0403`, or other mixed commits wholesale;
- merge master.

## Escalation and stop rules

P4-T01 escalation target is **GPT-5.6 Sol / max**, not pre-authorized.

STOP and request controller authorization on:

- **ESC-01** PC-reference tilemap/event semantics are ambiguous;
- **ESC-02** root cause crosses into an unplanned correctness-critical subsystem;
- **ESC-04** multiple plausible atomic transaction boundaries remain after source/history review;
- **ESC-05** aura/FOW/region/action-log invariants conflict;
- **ESC-07** Android performance requirement conflicts with one shared gameplay semantic contract;
- **ESC-09** safe pending construction requires a new cross-cutting lifecycle architecture.

Do not self-escalate.

## Gate status

**Phase 3 is ACCEPTED. P4-T01 is the only authorized task. P4-T02/P4-T03 and later phases remain blocked pending P4-T01 controller review.**
