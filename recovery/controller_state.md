# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 2**
- Phase 1 harness: **ACCEPTED**
- P1-T02 trace harness: **ACCEPTED**
- P1-T03 scenario evidence: **ACCEPTED**
- P1-T03 persistence correction R1: **ACCEPTED** at `6f1da4bcc53f26237b0b2150a128420ecd9aa7cb`
- Active task: **P2-T01 only — Audit GameState/load/state-restore delta**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- P2-T02 implementation: **UNAUTHORIZED**
- Production gameplay/state-machine/save behavior changes during P2-T01: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Controller gate after P2-T01: **YES — STOP FOR CONTROLLER REVIEW**

## Phase 1 acceptance record

The controller accepts `6f1da4bcc53f26237b0b2150a128420ecd9aa7cb` (`test(recovery): lock P1-T03 PC goldens`) as closing the P1-T03 fixture-persistence gap.

Accepted evidence:

- the commit is descended directly from the controller R1 authorization commit `72cc9da59a80276ce48bb2573e7b2b8672537158`;
- R1 changes are limited to the 17 PC-reference JSONL fixtures, `manifest.json`, bounded fixture-integrity tests, and `recovery/p1_t03_evidence.md`;
- no production engine or project-data file was changed by R1;
- all 17 persisted goldens are the exact preserved PC-reference bytes previously reviewed in `869d03692be1c56d6c074b18b93a1f781f1f38cb`;
- no golden was re-materialized and no recovery output was used as expected data;
- `manifest.json` locks Trace V1 schema version 1, reference revision, scenario/input identity, ordered checkpoints, fixture paths, and exact SHA-256 values;
- S3 remains `N/A — REFERENCE-UNSUPPORTED` and has no fixture;
- S16 persists only the PC-reference OFF golden; recovery ON == recovery OFF remains the INV-06 metamorphic assertion;
- S17 persists only the PC-reference disabled baseline; debugger/profiler enabled-idle equality remains the recovery-side INV-07 metamorphic assertion;
- the integrity tests recompute fixture hashes and validate Trace V1 headers/checkpoint order rather than regenerating or updating expected data.

The executor reports final Phase 1 validation as:

- trace/lifecycle/golden suite: **50 passed**;
- `python -m compileall -q app`: PASS;
- `git diff --check`: PASS;
- PC reference worktree clean at `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`;
- `git show --check`: PASS.

All P1-T03 scenario results are accepted as the Phase 1 behavioral oracle: S1-S2 and S4-S18 PASS under their reviewed contracts; S3 is the resolved reference-unsupported N/A case.

The committed oracle lives under:

`app/tests/fixtures/recovery_traces/v1/`

These fixtures are immutable expected PC behavior for later recovery work. A later recovery mismatch is evidence to diagnose, not permission to rewrite a golden.

## P2-T01 — authorized audit scope

P2-T01 is an **audit and function-level restore/re-port map only**. It does not authorize implementation.

Primary task definition from `plan.md`:

- inspect `app/engine/game_state.py`;
- inspect state-machine files;
- inspect title/load jobs;
- inspect chapter and overworld restore entry points;
- inspect staged-state fields and commit paths;
- inspect restart/save dependencies;
- deliver a function-level restore/re-port map before implementation.

### Required behavioral comparison

Compare the PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

against the current recovery branch. The reference is a behavioral oracle, not a textual revert target.

At minimum audit the complete restore transaction through all paths that can make saved/current world state authoritative:

1. `GameState.clear`, `build_new`, `save`, `load`, `load_iter`, level/overworld setup and board/controller setup paths;
2. `StateMachine` state installation, queued transitions, `load_states`, `process_temp_state`, and any staged/deferred interaction relevant to restore;
3. desktop title load and restart paths;
4. Android title/load job paths and in-chapter loading paths;
5. `save.load_game`, save-slot/restart-slot dependencies, and any later save-format or restart feature that must be preserved under INV-08;
6. chapter start/restart paths, including start-save semantics;
7. overworld restore paths;
8. staged fields/paths including `_staged_state_data`, `chapter_start_snapshot`, `commit_staged_state`, `load_iter(... replace_state_machine=...)`, and every caller/consumer found in the current tree;
9. map-safety/camera/null guards added because staged restore can expose an incomplete world;
10. Android progressive preparation that may be retained only if it can remain outside authoritative live gameplay state and finish with one main-thread atomic commit.

### Atomicity questions the report must answer

For every restore entry point, state explicitly:

- what the authoritative live state is before restore begins;
- what structures are built or mutated and in what order;
- exactly when the saved state stack becomes authoritative;
- when level/overworld, tilemap, board, units, aura/fog/regions, events, controllers, and RNG are valid;
- whether any normal state `begin`/`update` can observe a partially restored world;
- whether the PC reference performs the operation as one synchronous logical transaction;
- which later feature/fix must survive even if its current staging implementation is removed;
- whether an Android optimization can be re-ported as off-world/pending preparation plus one atomic commit.

INV-03 remains the governing rule: no observable partial gameplay state.

### Required function-level classification

For every changed function/field in the P2-T01 surface, produce a row with at least:

- file and symbol;
- PC-reference behavior;
- current recovery behavior;
- relevant introducing/follow-up commit(s) where identifiable;
- semantic risk/invariant affected;
- classification using the existing recovery labels (`KEEP-SHARED`, `KEEP-PLATFORM`, `REWRITE-PLATFORM`, `RESTORE-PC-SEMANTICS`, `REMOVE-WORKAROUND`, `KEEP-CORRECTNESS-FIX`);
- proposed Phase 2 treatment: retain / restore / re-port / remove-after-proof / controller decision;
- dependencies and tests/goldens that would prove the treatment.

Do not classify a whole mixed commit as one unit. In particular, never revert `52bd0403` or `0821182a` wholesale.

### Protected behavior

The audit must preserve/separate rather than accidentally roll back:

- current save-format/features that are independent of staged scheduling;
- restart game/chapter intent and current restart-slot behavior;
- aura load/teardown correctness already protected by the Phase 1 oracle;
- later independent correctness fixes;
- fast-forward, debugger, profiler, and Android platform policy unrelated to restore semantics;
- project data/assets/resources.

### Deliverable

Create/update only the bounded audit report:

`recovery/p2_t01_state_restore_map.md`

The report must contain:

1. reference-vs-recovery transaction diagrams or ordered step maps for desktop load, Android title load, in-chapter load if present, restart, and overworld restore;
2. the function/field classification table described above;
3. one proposed authoritative atomic restore boundary for P2-T02, stated as a design recommendation only;
4. an explicit list of workarounds that become candidates for P2-T03 removal only after P2-T02 proves the invalid partial state impossible;
5. exact P2-T02 implementation slices/dependencies in a safe order, without implementing them;
6. unresolved controller decisions or escalation evidence.

No production code, tests that mutate expected semantics, project data, Trace V1 schema, comparator, manifest, or golden fixture may be changed during P2-T01.

### Validation

Because P2-T01 is documentation/audit only:

- verify the recovery branch and HEAD before work;
- verify the Phase 1 manifest/integrity tests still pass without modification;
- run `git diff --check` before commit;
- commit only `recovery/p2_t01_state_restore_map.md`;
- run `git show --check` after commit;
- report exact source/ref comparisons used and any uncertainty.

## Escalation and stop rules

P2-T01 escalation target is **GPT-5.6 Sol / max**, but it is not pre-authorized.

STOP and request escalation on the plan-defined P2-T01 triggers:

- **ESC-01** reference ambiguity;
- **ESC-02** nonlocal root cause crossing another correctness-critical subsystem;
- **ESC-04** competing plausible gameplay semantics;
- **ESC-09** an unplanned cross-cutting architecture decision is required.

Do not self-escalate. Do not begin P2-T02 after completing the map.

## Gate status

**Phase 1 is ACCEPTED. P2-T01 is the only authorized task. P2-T02 remains blocked until P2-T01 receives controller review.**
