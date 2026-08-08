# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 5**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- P4-T01 tilemap/board/event atomicity audit: **ACCEPTED** at `5c94701d936a5ebbb3ebc0147e9e16e5e1d0ef25`
- P4-T02 desktop atomic tilemap semantics: **ACCEPTED** at `02f959b98d3f20f254acbc2f6a2842d0f53dd7c4`
- P4-T03 Android progressive board policy: **ACCEPTED** at `b8563c8e45e635b558582f9836ebaa7698d2fbc0`
- Active task: **P5-T01 only — Save format and compatibility audit**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P5-T02/P5-T03 and Phase 6+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P5-T01: **YES — STOP FOR CONTROLLER REVIEW**

## Phase 4 acceptance record

The controller accepts `b8563c8e45e635b558582f9836ebaa7698d2fbc0` (`fix(tilemap): fence Android preparation`) and closes Phase 4.

Accepted evidence:

- the commit is a single direct descendant of P4-T03 authorization commit `78f0befe0b96e5a07c35575ceb14e76da3c7d7c1`;
- production changes are limited to the narrow Event-local Android pending barrier in `app/events/event.py` and barrier setup/release in `app/events/event_functions.py`; remaining changes are bounded tests and `recovery/p4_t03_android_board_policy.md`;
- no StateMachine/shared scheduler, GameBoard algorithm, aura/FOW/region algorithm, Trace V1, comparator, manifest, golden JSONL, save schema, combat code, or project data changed;
- profiling used existing project maps and repeated host measurements: 150-tile Prologue remained below the 4 ms preparation budget, while 600-tile Magvel and 899-tile Chapter 14B materially exceeded it at reported p95 totals of about 7.38 ms and 18.34 ms respectively; this is accepted as host evidence of main-thread stall risk, not Android-device latency evidence;
- the RETAIN decision is limited to progressive construction/validation of pending `TileMapObject`, `GameBoard`, and `BoundaryInterface` objects; the P4-T02 synchronous live commit remains shared and unchanged;
- `_android_tilemap_pending` is Event-local and active only during the Android pending-build interval;
- while the barrier is active, only the `tilemap_change` pending callback advances; unrelated Event callbacks remain registered but do not execute, `game.movement.update()` does not run, gameplay input/listeners return without mutation, and the existing blocked predicate prevents processor progression before the job completes;
- repeated pending-build operations leave the old live tilemap/board/unit/region world authoritative and unchanged;
- when the pending job reaches completion, the P4-T02 live commit/rollback has already completed synchronously before the barrier is released; no generator commit, prefix world publication, or incremental `add_group` behavior is reintroduced;
- success and failure both clear the pending barrier and render deferral; commit failure still uses the accepted synchronous rollback-before-return contract;
- the completion outer update continues to suppress movement because the pending flag is sampled at update entry; Event processor continuation after the completed synchronous commit is acceptable because it can only observe the coherent new world, not a partial state;
- immutable S12, S13, S14, S15, and S17 comparisons are reported PASS against unchanged Phase-1 oracle contracts;
- focused Event/tilemap/Android tests, recovery trace/lifecycle/golden suites, compileall, diff check, and show check are reported PASS; broader Windows native termination remains baseline and unrelated.

Phase 4 therefore establishes the accepted world-transition contract for later phases:

```text
LIVE OLD STATE
    -> optional Android-only pending/off-world preparation under an opaque Event-local barrier
    -> complete validation
    -> one synchronous shared authoritative commit
LIVE NEW STATE
```

No live unit/region/aura/FOW/action-log mutation may be spread across frames. Desktop remains fully synchronous. `add_group` remains synchronous on all platforms. Android device performance remains unmeasured and may be revisited only in a separately authorized performance task without weakening this semantic barrier.

## P5-T01 — authorized audit scope

Execute **P5-T01 only** using **GPT-5.6 Terra / medium**.

This is a **save-format / compatibility audit and test task**. It does not authorize P5-T02 canonical load implementation or P5-T03 restart redesign.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Use accepted Phase-2 restore evidence, especially `recovery/p2_t01_state_restore_map.md`, as the current lifecycle baseline. Do not reopen accepted Phase-2 atomic restore semantics merely because Phase 5 will later consolidate the API.

Immutable Phase-1 goldens remain fixed. Do not regenerate or weaken them.

### Goal

Produce an authoritative compatibility inventory of the current save/load/restart format and lifecycle dependencies so P5-T02 can define one canonical transactional load API without accidentally breaking old/current saves, restart slots, chapter-start snapshots, aura reconstruction, intended post-reference fixes, or Android orchestration.

P5-T01 must answer **what data/compatibility contracts exist** and **which current load/restart paths depend on them**. It is not permission to change those contracts yet.

### Required save-format inventory

Audit the complete in-memory and serialized payload produced/consumed by current save code and compare it with the PC reference and relevant post-reference history.

At minimum map:

- top-level save dictionary fields;
- game-state/world fields;
- level/overworld identity;
- unit serialization including items/skills/status/state needed by restore;
- state-machine payload `S/Q` and its exact meaning/order;
- game/level variables;
- RNG/random-state fields;
- turn/phase/current-mode/difficulty fields;
- regions/terrain/FOW/visited/bounds data where serialized or reconstructed;
- records/supports/initiative/party data where applicable;
- event-state serialization, if any remains supported;
- any version/schema discriminator or absence thereof;
- fields added after the PC reference and their introducing commits;
- fields removed/renamed or interpreted differently after the reference.

For every field classify:

- REFERENCE-COMPATIBLE
- LATER-FEATURE-REQUIRED
- LATER-CORRECTNESS-FIX
- DERIVED/RECONSTRUCTED — NOT SERIALIZED
- LEGACY/OPTIONAL
- OBSOLETE/UNREAD
- NEEDS-CONTROLLER-DECISION

Do not infer compatibility from field names alone; trace writer and reader behavior.

### Event-state serialization

Explicitly determine the current supported contract for event state.

Preserve the accepted Phase-1 finding that user-facing arbitrary mid-event save/load was removed before the PC reference and S3 is `REFERENCE-UNSUPPORTED`.

Audit:

- any internal Event/EventProcessor serialization still present;
- whether it is used by normal save slots, suspended events, turnwheel/restart internals, tests, or only dead/internal paths;
- whether current save payload can contain active/pending event state;
- whether current load code restores it;
- whether later code assumes event serialization despite the user-facing feature being unsupported.

Do not re-enable arbitrary mid-event save/load in P5-T01.

### SAVE_SLOTS / RESTART_SLOTS contract

Map exact callers and semantics for:

- `SAVE_SLOTS`;
- `RESTART_SLOTS`;
- normal Load Game;
- Restart Level;
- game-over restart;
- debug-triggered restart;
- title-screen restart/load routing;
- start-save versus normal-save distinction;
- any slot key/naming assumptions.

Preserve the established rule that SAVE_SLOTS and RESTART_SLOTS are distinct concepts even if they share serialization helpers.

Identify any compatibility dependency that P5-T02 or P5-T03 must not collapse accidentally.

### Chapter-start snapshot / pristine restart

Audit the current `chapter_start_snapshot` lifecycle end-to-end:

- when it is captured;
- exact payload shape;
- whether it is before LevelStart/authoritative chapter mutation;
- how it is converted/written into restart material;
- how Restart Level consumes it;
- Test Chapter behavior when no pristine restart file existed at initial entry;
- first-save fallback behavior;
- game-over restart behavior;
- interaction with start-save routing.

The audit must explicitly protect the accepted Phase-2 requirement that the snapshot represents the pristine chapter-start transaction, not an accidental mid-chapter save.

Do not redesign restart behavior in P5-T01.

### Aura reconstruction / derived-state contract

Audit serialization and reconstruction for aura-related skills and other derived board state.

At minimum prove:

- aura child skills are not serialized as authoritative owned skills;
- source relationships needed for teardown/reconstruction are preserved or re-derived;
- load rebuild order recreates aura/FOW/board/boundary relationships only after the required authoritative world exists;
- old/current saves cannot duplicate aura children merely because both serialized and derived representations are consumed;
- Phase-4 pending board policy does not become a second source of save-state truth.

Use S12 and existing aura tests as evidence.

### Old/current save compatibility matrix

Build a matrix for at least:

1. PC-reference-era save payload loaded by current recovery code;
2. current recovery save payload loaded by current recovery code;
3. current payload fields absent from an older save;
4. legacy/optional fields present but unused;
5. normal save versus start save;
6. SAVE_SLOT versus RESTART_SLOT consumers;
7. overworld save/load path;
8. chapter-start snapshot/restart path.

Where practical, construct compatibility tests using programmatically built/minimal or existing test payloads. Do not commit user/project save files or modify project data.

If byte-for-byte old reference save files are not available, state that limitation and test field-level/schema compatibility rather than inventing evidence.

### Android load orchestration dependency map

Audit, but do not redesign, the current Android load path established in Phase 2.

Map which pieces are:

- immutable file read/unpickle/background I/O;
- authoritative main-thread hydration;
- destination stack installation;
- title/in-chapter loader presentation;
- platform-only resource/audio/render preparation;
- compatibility-only fields/helpers remaining after P2-T03;
- restart/start/overworld routing dependencies.

Confirm no Phase-4 tilemap pending barrier/job is being treated as save-format state or a second authoritative load-world representation.

P5-T02 will later decide the canonical transactional API boundary; P5-T01 only supplies the dependency map.

### Required history/provenance audit

Inspect relevant post-reference commits individually, especially those that affected:

- save/load format;
- restart/current chapter behavior;
- `chapter_start_snapshot`;
- deferred/staged state restore history from `6bd9da4b` / `8306e1a9` and their Phase-2 cleanup;
- start-save routing;
- aura serialization/reconstruction correctness;
- difficulty/restart correctness;
- title Load Game / Restart Level orchestration.

Do not classify a mixed commit wholesale.

### Required proof/tests

Use existing tests first and add bounded audit/compatibility tests only where the contract is not already proved.

At minimum validate:

- normal save/load round-trip;
- start-save load routing;
- Restart Level / RESTART_SLOTS behavior;
- chapter-start snapshot capture/consumption;
- game-over restart route;
- title normal/start/overworld destination behavior from accepted Phase 2;
- Test Chapter restart edge case where coverage exists;
- aura reconstruction/nonserialization;
- old/missing optional field compatibility where demonstrable;
- Android loader dependency behavior without changing semantics.

Run immutable comparisons at minimum:

- S1 new game first playable;
- S2 save/load;
- S4 restart;
- S12 aura lifecycle;
- S18 game-over/restart.

S3 remains N/A / REFERENCE-UNSUPPORTED and must not be converted into a golden.

Also run relevant save/title/restart/atomic-restore/runtime-debugger tests and broader unit discovery. Report known baseline failures/native termination without repairing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit only bounded P5-T01 report/tests
- `git show --check`

### Deliverable

Create:

`recovery/p5_t01_save_compatibility_audit.md`

Required sections:

1. serialized schema/field inventory;
2. reference vs current field/provenance table;
3. Event serialization support decision;
4. SAVE_SLOTS vs RESTART_SLOTS caller/semantic map;
5. normal/start/overworld save-load matrix;
6. chapter-start snapshot / pristine restart lifecycle;
7. aura/derived-state serialization and reconstruction map;
8. old/current compatibility matrix;
9. Android load orchestration dependency map;
10. P5-T02 canonical-load constraints;
11. P5-T03 restart constraints;
12. unresolved compatibility questions / escalation evidence.

### Explicitly out of scope

Do not:

- implement P5-T02 canonical load API;
- redesign P5-T03 restart semantics;
- change save bytes/schema merely for cleanliness;
- re-enable arbitrary user-facing mid-event save/load;
- replace SAVE_SLOTS/RESTART_SLOTS with one concept;
- modify accepted Phase-2 restore ordering;
- change Phase-4 tilemap policy;
- modify Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- fix unrelated baseline test problems;
- merge master.

## Escalation and stop rules

P5-T01 escalation target is **GPT-5.6 Sol / high**, not pre-authorized.

STOP and request controller authorization on:

- **ESC-01** legacy/reference save semantics are ambiguous in a way that blocks compatibility classification;
- **ESC-02** compatibility root cause crosses into an unplanned subsystem;
- **ESC-04** multiple plausible save/restart semantics require a controller choice;
- **ESC-06** old/current save compatibility conflict;
- **ESC-09** compatibility would require a new cross-cutting serialization/lifecycle architecture.

Do not self-escalate.

## Gate status

**Phase 4 is ACCEPTED. P5-T01 is the only authorized task. P5-T02/P5-T03 and later phases remain blocked pending P5-T01 controller review.**
