# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. Historical evidence remains in prior controller commits and committed recovery reports.

## Current authorization

- Current phase: **Phase 5**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- P5-T01 initial save compatibility audit `280b5fec9e0e6b7dae620d2a6d3f9af5ac47ba92`: **PARTIAL — R1 REQUIRED**
- Active task: **P5-T01-R1 only — close phase/initiative save-compatibility gap**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- P5-T02/P5-T03 and Phase 6+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Production behavior/schema changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P5-T01-R1: **YES — STOP FOR CONTROLLER REVIEW**

## P5-T01 initial review

The controller does **not** yet accept P5-T01 as complete. The initial audit is otherwise well-scoped and useful:

- `280b5fec9e0e6b7dae620d2a6d3f9af5ac47ba92` is a single direct descendant of P5-T01 authorization commit `58f06f6cb75f673ec7355132d931d565ced65f4c`;
- it changes only `recovery/p5_t01_save_compatibility_audit.md`;
- current and PC-reference `GameState.save()` have the same top-level key set and no payload schema discriminator;
- reader defaults/fallbacks, internal Event/EventProcessor serialization, SAVE_SLOTS vs RESTART_SLOTS separation, chapter-start snapshot timing, aura child nonserialization/reconstruction, Android worker-only read/unpickle, and transaction-local S/Q ownership are mapped correctly at a useful level;
- immutable S1/S2/S4/S12/S18 and targeted restore/restart suites were reported PASS without fixture changes;
- absence of an archived PC-reference binary `.p` fixture is correctly stated as a limitation, so the report does not overclaim arbitrary pickle-byte compatibility.

However P5-T01 explicitly required inventory of **turn/phase/current-mode/difficulty** and **initiative** data where applicable. The report maps turncount/current_mode but does not close the serialization/restore contract for `game.phase` or `game.initiative`.

Accepted source facts that R1 must incorporate:

1. Neither PC-reference nor current `GameState.save()` contains a top-level `phase` or `initiative` field.
2. Current `GameState.generic()` constructs a fresh `PhaseController`; `GameState.load_iter()` does not deserialize a phase controller.
3. `PhaseController.__init__` derives its initial non-initiative state from `game.turncount`; under initiative mode its getters depend on `game.initiative`.
4. `GameState.level_setup_iter()` creates and starts an `InitiativeTracker` for a new chapter before `chapter_start_snapshot` is captured.
5. `GameState.load_iter()` currently does not create/restore `InitiativeTracker`, and `InitiativeTracker` has no save/restore API.
6. The same absence exists in the PC-reference top-level save writer, so this must not be silently labeled a post-reference regression without supported-path evidence.
7. `bounds` and `fog_state` themselves are serialized reconstruction inputs; the board/boundary/occupancy/visible-FOW/aura structures derived from them are the nonserialized state. The audit wording should distinguish those two categories explicitly.

P5-T02 cannot be authorized until the controller knows whether supported normal/start/suspend/restart/overworld save routes require exact phase/initiative restoration or whether those controllers are intentionally reconstructed/irrelevant at every supported save boundary.

## P5-T01-R1 — authorized audit/test correction

Execute **P5-T01-R1 only** using **GPT-5.6 Terra / medium**.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

P5-T01-R1 remains **audit/test only**. Do not modify production behavior or save bytes/schema.

### Required phase ownership audit

Map the exact writer/reader/runtime ownership of phase state for PC reference and current recovery:

- `GameState.save` / `load` or `load_iter`;
- `GameState.generic`;
- `PhaseController.__init__`, `get_current`, `next`;
- state-machine S/Q states that may encode a phase transition indirectly;
- every supported save kind/entry point that can persist a map while a non-player phase is authoritative;
- normal save, suspend, battle/turn-change saves where applicable, start save, restart save, overworld save.

Determine whether exact current phase is:

- serialized directly;
- derived safely from other saved data at every supported save boundary;
- intentionally restricted by save routing so only a deterministic phase can be loaded;
- or not preserved for a supported path.

Do not assume `turncount` alone is sufficient. Prove it from callers/save-point constraints.

### Required initiative ownership audit

Map PC-reference and current initiative behavior:

- when `game.initiative` is constructed;
- mutable fields: `unit_line`, `initiative_line`, `current_idx`, and any runtime behavior depending on them;
- whether any of those fields are serialized directly or indirectly;
- whether load/restart/start-level reconstructs them and at what boundary;
- whether supported saves can occur after initiative has advanced from its chapter-start value;
- whether loading such a save is supported by current UI/runtime routing;
- whether current behavior equals the PC reference or differs because of later orchestration.

Run a bounded programmatic probe/test with initiative enabled if feasible without project-data changes. The probe must distinguish:

1. new chapter/start-save reconstruction;
2. normal/suspend save after initiative advancement;
3. restart/chapter-start reconstruction.

If a supported save/load path demonstrably loses initiative/current-phase semantics, **do not fix it in P5-T01-R1**. Record the exact evidence and STOP for controller review. If resolving whether to preserve reference behavior or introduce a compatibility fix requires a semantic choice or schema change, report **ESC-04/ESC-06** and request escalation/authorization.

### Required report corrections

Update only:

`recovery/p5_t01_save_compatibility_audit.md`

plus narrow test-only coverage if necessary.

The report must add explicit rows/sections for:

- `phase` serialization/reconstruction classification;
- `initiative` serialization/reconstruction classification;
- supported save-kind reachability for each;
- PC-reference vs current comparison;
- P5-T02 constraint resulting from the finding;
- P5-T03 restart constraint resulting from the finding;
- `bounds` / `fog_state` as **serialized reconstruction inputs**, distinct from derived nonserialized board/boundary/FOW/aura state.

Use only the existing classification vocabulary. If the semantics cannot be classified without a controller choice, use `NEEDS-CONTROLLER-DECISION`.

### Preserve the already accepted P5-T01 findings

Do not weaken or reopen without contrary source evidence:

- identical reference/current top-level save-key set;
- no payload schema discriminator;
- internal Event/EventProcessor serialization remains payload support while S3 stays `REFERENCE-UNSUPPORTED`;
- SAVE_SLOTS and RESTART_SLOTS remain distinct;
- chapter_start_snapshot is captured after chapter setup and before LevelStart mutation;
- aura children are nonserialized/derived;
- Android worker owns immutable read/unpickle only and main thread owns authoritative hydration/S/Q publication;
- Phase-4 pending tilemap structures are not save truth.

### Validation

Run focused phase/initiative/save/load/restart tests or probes needed to support the new findings.

Re-run at minimum:

- `app.tests.test_atomic_restore`
- relevant save/restart/runtime-debugger tests
- recovery trace/lifecycle/golden integrity
- S1, S2, S4, S12, S18 immutable comparisons
- `python -m compileall -q app`
- `git diff --check`
- commit bounded R1 audit/tests
- `git show --check`

Do not claim PASS if required supported-path phase/initiative behavior remains unknown.

### Explicitly out of scope

Do not:

- modify `GameState.save/load/load_iter` production behavior;
- add phase/initiative save fields;
- change save schema/versioning;
- implement P5-T02;
- implement P5-T03;
- change restart precedence;
- change Phase-4 policy;
- modify Trace V1/comparator/manifest/goldens;
- modify project data;
- merge master.

## Escalation and stop rules

Primary remains **GPT-5.6 Terra / medium**. Escalation target is **GPT-5.6 Sol / high**, not pre-authorized.

STOP on:

- **ESC-01** supported reference save semantics remain ambiguous;
- **ESC-02** root cause crosses into an unplanned subsystem;
- **ESC-04** preserving reference behavior versus fixing supported phase/initiative persistence requires a semantic choice;
- **ESC-06** old/current or supported-save compatibility conflict requires schema/reader behavior changes;
- **ESC-09** safe compatibility requires new cross-cutting serialization architecture.

Do not self-escalate.

## Gate status

**P5-T01 is PARTIAL. P5-T01-R1 is the only authorized task. P5-T02/P5-T03 and later phases remain blocked pending controller review.**
