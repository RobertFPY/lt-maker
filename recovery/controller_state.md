# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 1**
- Harness gate: **P1-T02 ACCEPTED**
- Executor evidence commit reviewed: `869d03692be1c56d6c074b18b93a1f781f1f38cb`
- P1-T03 scenario execution: **COMPLETE**
- P1-T03 controller result: **PARTIAL — FIXTURE PERSISTENCE GAP**
- Active task: **P1-T03-R1 only**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- Phase 2: **UNAUTHORIZED**
- Production gameplay/state-machine/save/project-data changes: **UNAUTHORIZED**
- Golden semantic changes: **UNAUTHORIZED**

## Controller review of `869d03692`

### Accepted

The commit is correctly bounded to test/evidence scope only:

- `app/tests/recovery_trace_runner.py`
- `app/tests/test_recovery_golden.py`
- `recovery/p1_t03_evidence.md`

No production engine or project-data files were changed.

Scenario status is accepted provisionally as reported:

1. **S1 PASS** — `player.control.ready`.
2. **S2 PASS** — `save.restore.complete`.
3. **S3 N/A — REFERENCE-UNSUPPORTED** — no golden.
4. **S4 PASS** — `restart.complete`.
5. **S5 PASS** — MapCombat cleanup.
6. **S6 PASS** — SimpleCombat cleanup.
7. **S7 PASS** — AnimationCombat cleanup.
8. **S8 PASS** — BaseCombat cleanup.
9. **S9 PASS** — DB-owned Luna proc + ordered combat hooks.
10. **S10 PASS** — durability/broken/unusable cleanup.
11. **S11 PASS** — promotion/class state fixture.
12. **S12 PASS** — aura propagation/load/teardown.
13. **S13 PASS** — FOW preview/cancel/wait using the approved deterministic host-time test shim and real InputManager.
14. **S14 PASS** — tilemap terminal commit.
15. **S15 PASS** — phase terminal commit.
16. **S16 PASS** — PC reference OFF == recovery OFF; recovery ON == recovery OFF under INV-06. The PC reference has no fast-forward driver helper, so no PC enabled-mode golden is required.
17. **S17 PASS** — approved hybrid observer contract.
18. **S18 PASS** — DB-owned `Global DeathEirika` -> real GameOver -> title -> real Restart Level / `RESTART_SLOTS` flow.

The reported validation set is also accepted provisionally:

- recovery trace/lifecycle + P1-T03 harness tests: 48 passed;
- `compileall` passed;
- `git diff --check` passed before commit;
- `git show --check` passed after commit;
- reference worktree reported clean at `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.

### Blocking deficiency

P1-T03 cannot be accepted yet because the reviewed Trace V1 design requires the PC-reference goldens to exist in a **versioned repository test-fixture directory** with a **manifest** recording reference revision, schema/input identity, and SHA-256.

`recovery/p1_t03_evidence.md` currently says the JSONL captures remain only in the executor temp directory and records their filenames/hashes. The commit contains no JSONL golden fixtures and no manifest.

This is not a gameplay or trace-semantic failure. It is an evidence persistence/reproducibility failure: later phases need an immutable, reviewable oracle rather than only hashes of temporary files.

## P1-T03-R1 — Persist and lock reviewed goldens

Resume **P1-T03 only** using **GPT-5.6 Terra / high**.

### Authorized scope

May add/update only:

- `app/tests/fixtures/recovery_traces/v1/*.jsonl`
- `app/tests/fixtures/recovery_traces/v1/manifest.json`
- `recovery/p1_t03_evidence.md`
- `app/tests/test_recovery_golden.py` only for bounded fixture/manifest integrity tests
- `app/tests/recovery_trace_runner.py` only if a minimal test-owned helper is strictly necessary to verify persisted fixtures; do not alter scenario semantics, inputs, checkpoints, allowlists, normalization, or comparator meaning

No production code, project data, Trace V1 schema semantics, or scenario contract changes are authorized.

### Golden materialization rule

For S1, S2, S4-S18, persist the **PC-reference JSONL bytes** corresponding to the SHA-256 values already recorded in `recovery/p1_t03_evidence.md` from commit `869d03692`.

Preferred path:

1. If the original executor temp files still exist, copy those exact bytes into the versioned fixture directory.
2. Compute SHA-256 after copying and require exact equality with the already-recorded hash.

If an original temp file no longer exists, regeneration is explicitly authorized only under all of these conditions:

1. generate from isolated PC reference `9314f54b49f4552b5a3d023b4da0012ce7dfbc89` using the already-accepted Trace V1 overlay and the scenario runner semantics from `869d03692`;
2. run the same reference scenario twice and require byte-identical JSONL output;
3. require the regenerated file SHA-256 to exactly equal the hash already recorded in `recovery/p1_t03_evidence.md`;
4. if the bytes/hash differ, **STOP** — do not update the recorded expected hash and do not regenerate until something passes.

S3 remains N/A and must not receive a fixture.

Do not copy recovery output into the golden directory.

### Manifest contract

Create `app/tests/fixtures/recovery_traces/v1/manifest.json`.

For every persisted golden, record at minimum:

- `schema_version: 1`;
- PC reference revision `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`;
- scenario ID;
- input fixture ID from the trace header;
- golden filename/path;
- SHA-256 of the exact JSONL bytes;
- ordered checkpoint IDs.

Represent S3 separately as `N/A — REFERENCE-UNSUPPORTED`, not as a fake/empty golden.

For S16 record that the persisted PC golden is the reference OFF run; recovery ON/OFF equality remains a metamorphic INV-06 assertion, not a second PC golden.

For S17 record that the persisted PC golden is the disabled observer baseline only; debugger/profiler enabled-idle equality remains recovery-side metamorphic evidence under the approved hybrid contract.

### Evidence update

Update `recovery/p1_t03_evidence.md` so fixture paths point to the committed versioned fixture files, not executor temp paths. Preserve the existing accepted SHA-256 values. Document any file that had to be re-materialized because its temp copy was unavailable and state that the regenerated bytes matched the pre-existing hash.

### Required tests

Add bounded tests that at minimum:

- load `manifest.json`;
- verify every non-N/A manifest fixture exists;
- verify every fixture byte SHA-256 matches the manifest and the evidence file values;
- verify each JSONL contains one Trace V1 header with the expected reference revision/schema/scenario/input fixture identity;
- verify ordered checkpoint IDs match the manifest;
- verify S3 has no golden fixture;
- keep the existing harness helper tests passing.

Do not make tests regenerate/update expected fixtures automatically.

### Final validation

Run:

- `python -m unittest app.tests.test_recovery_trace app.tests.test_state_machine_lifecycle app.tests.test_recovery_golden`
- `python -m compileall -q app`
- `git diff --check` before commit
- verify the isolated PC reference worktree is clean except explicitly ignored generated component-system outputs
- commit only the authorized P1-T03-R1 fixture/evidence/test changes
- `git show --check` after commit

Report:

- whether each golden came from the preserved temp file or explicitly authorized re-materialization;
- exact fixture paths and SHA-256 values;
- manifest validation results;
- test results;
- files changed;
- commit SHA.

Then **STOP FOR CONTROLLER REVIEW**.

## Gate status

P1-T03 scenario semantics are provisionally accepted, but **P1-T03 as a task is not yet accepted** until R1 persists and locks the reviewed goldens. Phase 2 remains blocked.