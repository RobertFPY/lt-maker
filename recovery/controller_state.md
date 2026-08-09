# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. Historical evidence remains in prior controller commits and committed recovery reports.

## Current authorization

- Current phase: **Phase 5**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- P5-T01 save-format/compatibility audit: **ACCEPTED** at `f0abf0cb4f4aa05df9f6bff86a959f203d25553f`, including R1 phase/initiative evidence
- Active task: **P5-T02 only — Canonical transactional load API**
- Primary model: **GPT-5.6 Sol / max**
- Escalation target: **GPT-5.6 Sol / ultra**
- Escalation pre-authorized: **NO**
- P5-T03 and Phase 6+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P5-T02: **YES — STOP FOR CONTROLLER REVIEW**

## P5-T01 acceptance and compatibility decision

The controller accepts `f0abf0cb4f4aa05df9f6bff86a959f203d25553f` (`docs(recovery): audit phase initiative saves`) as completion of P5-T01.

Accepted evidence:

- the commit is one direct descendant of the controller cleanup-authorization commit `e45442a17ebe7aefa391a4113a9f195ca10ae47c`;
- the R1 commit changes only `recovery/p5_t01_save_compatibility_audit.md`; the accidental portrait-resource probe modifications were restored to HEAD and were not committed;
- current and PC-reference `GameState.save()` share the same baseline top-level payload key set and no payload schema discriminator;
- Event/EventProcessor payload support remains internal while user-facing arbitrary mid-event save/load stays `REFERENCE-UNSUPPORTED` (S3 remains N/A);
- SAVE_SLOTS and RESTART_SLOTS remain separate slot-keyed contracts;
- `chapter_start_snapshot` remains chapter-start material captured after chapter setup and before LevelStart mutation;
- aura children remain nonserialized derived state and are rebuilt only after authoritative board/unit state exists;
- Android worker I/O remains immutable read/unpickle only; authoritative hydration and S/Q publication remain main-thread;
- `bounds` and `fog_state` are serialized reconstruction inputs, distinct from nonserialized derived GameBoard/BoundaryInterface/occupancy/visible-FOW/aura state;
- immutable S1/S2/S4/S12/S18 and focused restore/restart suites are reported PASS with unchanged goldens;
- no archived PC-reference binary `.p` fixture exists, so arbitrary byte-level legacy compatibility is not claimed.

R1 also proves two reference-era limitations on supported/currently exposed paths:

1. **Non-initiative phase:** neither reference nor current serializes `PhaseController.current/previous`. Ordinary player-control saves reconstruct player phase from current routing/turncount, but `PhaseChangeState.save_state()` creates `enemy_turn_change` autosaves while enemy phase is authoritative, and Title Extras -> All Saves exposes those saves when debug or `all_saves` is enabled. Loading the raw legacy payload reconstructs player phase rather than the saved enemy phase.
2. **Initiative:** neither reference nor current serializes `InitiativeTracker.unit_line`, `initiative_line`, or `current_idx`; clean loading of a current-progress initiative save can leave `game.initiative is None`, after which `PhaseController.get_current()` raises because it dereferences the missing tracker. Initiative player-control saves are a real supported gameplay route, not dead/debug-only data.

The controller resolves ESC-04 / ESC-06 as follows.

### Controller choice: COMPATIBILITY RESTORATION

Do **not** preserve these demonstrated limitations as intended semantics merely because the PC reference has the same omission. The PC reference remains the behavioral oracle for defined behavior, not a requirement to preserve a proven supported-feature crash or a deterministically wrong debug/all-saves phase restoration.

Do **not** solve this by globally disabling/restricting current save routes. Normal initiative save/load must remain supported. Existing `enemy_turn_change` All Saves behavior must not silently load the wrong phase.

Classify the bounded repair as **LATER-CORRECTNESS-FIX** under INV-08, subject to all compatibility rules below.

### Legacy compatibility rule

No exact initiative current-progress state can be recovered from historical payload bytes that never contained tracker lines/index. Therefore:

- never guess a legacy initiative `current_idx` from turncount, unit `finished`, S/Q names, action-log history, or sort order unless source/tests prove a unique reconstruction;
- for a legacy current-progress initiative save whose exact tracker state is absent and whose route requires resuming that saved progress, fail **before authoritative publication** with an explicit compatibility error rather than producing a corrupted world or later `AttributeError`;
- legacy chapter-start/start/restart material may continue through deterministic chapter-start reconstruction when the whole transaction immediately rebuilds the chapter and initiative tracker before publication;
- legacy overworld saves are phase/initiative irrelevant;
- legacy non-initiative ordinary player-control saves keep historical compatible reconstruction;
- legacy `enemy_turn_change` has an unambiguous routing discriminator (`SaveSlot.kind == 'enemy_turn_change'`); P5-T02 may use that source-proven context to restore enemy phase for old payloads without inventing general inference.

No schema version discriminator is authorized merely for this repair. Missing optional compatibility state is itself the legacy signal unless implementation evidence requires escalation.

### New-save compatibility state

P5-T02 is authorized to persist the minimum exact controller state necessary for future supported current-progress saves, but the representation must be additive and backward-readable.

Prefer narrow optional state rather than serializing whole controller objects.

At minimum exact new initiative progress must preserve the authoritative mutable tracker values needed to resume semantics:

- `unit_line`;
- `initiative_line`;
- `current_idx`.

Exact non-initiative phase progress must preserve the authoritative phase identity/state needed where routing cannot safely derive it. Preserve `current/previous` if both are semantically relevant to phase transition behavior.

Do not serialize presentation-only objects such as phase banner surfaces/timers or whole `PhaseController`/`InitiativeTracker` instances.

Avoid changing ordinary default-player, non-initiative save payloads unless necessary. In particular, do not add unconditional fields merely for symmetry if conditional compatibility data can preserve immutable default recovery traces. If a required correctness fix changes an immutable Trace V1 save payload hash, STOP under ESC-03/ESC-06 for controller review rather than regenerating goldens.

## P5-T02 — authorized implementation scope

Execute **P5-T02 only** using **GPT-5.6 Sol / max**.

Escalation target: **GPT-5.6 Sol / ultra**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Use accepted Phase-2 restore semantics and `recovery/p5_t01_save_compatibility_audit.md` as mandatory constraints.

### Goal

Implement one authoritative transactional load API used by desktop and Android so platform orchestration differs only in immutable I/O/presentation policy, not in hydration, compatibility decisions, S/Q ownership, destination publication, or failure semantics.

The canonical transaction must own:

```text
read payload/context
    -> validate compatibility
    -> build/reset target world
    -> hydrate all authoritative save data
    -> reconstruct derived board/aura/FOW/controllers
    -> resolve legacy/new phase+initiative compatibility
    -> validate complete world
    -> install S/Q + destination exactly once
    -> publish coherent loaded world
```

Android may still perform immutable file read/unpickle off-thread and show an opaque loader, but once authoritative hydration starts it must remain one main-thread logical transaction with no frame-visible partial GameState.

Desktop remains synchronous from the public caller's perspective.

### Required API consolidation

Audit current callers, then route supported loads through one bounded core transaction instead of duplicating transaction semantics across title/in-chapter/debug/load helpers.

At minimum cover:

- desktop `save.load_game`;
- Android `SaveLoadJob` authoritative hydration;
- title Load Game;
- in-chapter load;
- start-save routing;
- overworld routing;
- restart-slot load preparation without redesigning P5-T03 restart semantics;
- in-memory `chapter_start_snapshot`/debugger load compatibility where it already uses core load primitives.

Do not merge SAVE_SLOTS and RESTART_SLOTS.

Do not redesign pristine restart ownership; P5-T03 owns that task.

### Phase / initiative correctness repair

Implement the controller compatibility decision above.

Required behavior:

1. New supported current-progress initiative saves round-trip exact tracker order/index.
2. Load restores tracker state before any published state can call `game.phase.get_current()` or otherwise require initiative.
3. New non-initiative saves that require exact non-player phase restoration preserve it without changing unrelated player-save semantics.
4. Legacy non-initiative player-control saves remain loadable with historical deterministic behavior.
5. Legacy `enemy_turn_change` loaded through its known SaveSlot context restores enemy phase rather than silently player phase.
6. Legacy current-progress initiative payload missing exact tracker state fails atomically with a clear compatibility error; no partial world/S/Q publication and no later AttributeError.
7. Legacy start/restart material with initiative may proceed only if the same outer transaction deterministically rebuilds the chapter-start tracker before publication.
8. Overworld load remains phase/initiative irrelevant.
9. No whole-controller pickle objects; only bounded primitive/list state.
10. No attempt to infer missing legacy initiative index from ambiguous runtime state.

If exact legacy initiative reconstruction turns out source-provable and unique, report the proof before using it. Otherwise keep fail-closed behavior.

### S/Q and destination contract

Preserve accepted Phase-2 semantics:

- saved `S/Q` remains transaction-local during Android/main-thread hydration;
- no saved stack is published before world/RNG/events/board/aura/controller state is complete;
- install the final saved stack/destination once at the transaction boundary;
- desktop/reference title normal/start/restart/overworld destination shapes remain as accepted in P2-T01/P2-T02;
- loader states/callbacks are presentation/orchestration and must leave no residue in the final authoritative stack.

### Save-format compatibility constraints

Preserve all P5-T01 accepted fields/defaults.

Do not:

- add a global schema migration framework;
- rewrite existing historical fields;
- remove Event serialization;
- serialize P4 pending tilemap/board jobs;
- serialize aura children;
- serialize GameBoard/BoundaryInterface/pygame objects;
- alter SAVE_SLOTS/RESTART_SLOTS naming;
- modify project data.

Any new compatibility fields must be optional on read and bounded on write.

### Failure semantics

All compatibility/read/hydration failures must leave the singleton in a coherent recoverable state.

For Android worker read/unpickle failure: no authoritative mutation.

For main-thread validation/hydration failure: no frame may observe a partially restored gameplay world. Existing reset/abort behavior may be retained/refined, but do not invent a second persistent GameState/pending-world architecture.

A legacy initiative compatibility failure must occur before final S/Q publication and surface as an explicit load/compatibility error, not a null tracker crash later.

### Required tests

Add focused tests proving at minimum:

1. one core transaction is used for desktop synchronous load and Android authoritative hydration;
2. Android worker remains read/unpickle only;
3. S/Q is installed exactly once after complete world/controller reconstruction;
4. normal desktop S2 behavior remains exact;
5. restart/start S4 behavior remains exact;
6. game-over/restart S18 remains exact;
7. aura S12 remains exact;
8. new initiative current-progress save/load round-trips `unit_line`, `initiative_line`, `current_idx` and current acting team/unit;
9. initiative tracker exists before any restored state can query phase;
10. legacy initiative current-progress payload without tracker state fails atomically and explicitly;
11. legacy start/restart initiative path can deterministically rebuild chapter start if applicable;
12. legacy enemy_turn_change context restores enemy phase;
13. ordinary legacy/current non-initiative player save behavior is unchanged;
14. overworld load is unaffected;
15. internal Event serialization still restores;
16. debugger/profiler remain observers;
17. no P4 pending-board state enters save/load truth.

Use temporary/minimal test data only. Do not mutate tracked project resources.

### Immutable proof

Run at minimum:

- S1
- S2
- S4
- S12
- S17
- S18

S3 remains N/A / REFERENCE-UNSUPPORTED.

If any immutable trace diverges solely because new compatibility fields altered a default reference-compatible save payload, do not regenerate the fixture. First reduce the write scope so the extra fields exist only where semantically required. If divergence remains necessary for correctness, STOP under ESC-03/ESC-06 and request controller authorization.

Also run relevant:

- `test_atomic_restore`;
- save/load/title load tests;
- restart/runtime-debugger tests;
- Event serialization tests;
- initiative/phase tests;
- recovery trace/lifecycle/golden integrity;
- Android load/performance tests relevant to orchestration.

Run broader unittest discovery and report known baseline failures/native Windows termination without fixing unrelated issues.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit bounded P5-T02 implementation/tests
- `git show --check`

## Explicitly out of scope

Do not:

- begin P5-T03;
- begin Phase 6;
- merge SAVE_SLOTS and RESTART_SLOTS;
- redesign pristine restart semantics;
- re-enable arbitrary user-facing mid-event saves;
- add a generic serialization-version/migration subsystem;
- preserve a broken initiative load merely for textual reference parity;
- guess missing legacy initiative state;
- regenerate Trace V1 goldens;
- modify project data/assets;
- reopen Phase 3/4 behavior;
- merge master.

## Escalation and stop rules

STOP and request controller authorization on:

- **ESC-02** canonical transaction requires unrelated subsystem redesign;
- **ESC-03** immutable trace divergence remains after bounded conditional-write correction;
- **ESC-04** more than one semantically valid phase/initiative repair remains after this controller decision;
- **ESC-05** atomic publication/invariant cannot be preserved;
- **ESC-06** legacy compatibility requires guessing or destructive schema behavior;
- **ESC-08** repeated local failure;
- **ESC-09** implementation requires a second persistent GameState/pending-world or generic cross-cutting load architecture beyond the bounded canonical transaction.

Do not self-escalate.

## Gate status

**P5-T01 is ACCEPTED. P5-T02 is the only authorized task. P5-T03 and later phases remain blocked pending P5-T02 controller review.**
