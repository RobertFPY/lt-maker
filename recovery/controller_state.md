# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 2**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- P2-T01 audit/map: **ACCEPTED**
- P2-T02 authoritative restore implementation: **ACCEPTED** at `0a6b854e0943905dc472986d4a2d9e5f95962ab4`
- Active task: **P2-T03 only — Remove obsolete staged-restore workarounds after proof**
- Primary model: **GPT-5.6 Terra / medium**
- Escalation target: **GPT-5.6 Sol / high**
- Escalation pre-authorized: **NO**
- Phase 3: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P2-T03: **YES — STOP FOR CONTROLLER REVIEW**

## P2-T02 acceptance record

The controller accepts commit `0a6b854e0943905dc472986d4a2d9e5f95962ab4` (`fix(save): restore atomic state transactions`).

Accepted implementation properties:

- Android worker execution is limited to save-file read/unpickle and diagnostics; it does not hydrate gameplay state.
- `SaveLoadJob.advance()` returns across frames only while worker I/O is incomplete. Once authoritative hydration begins, `build_new()` plus the complete `load_iter(..., replace_state_machine=True)` sequence is drained in the same main-thread call before control returns to the outer frame loop.
- Saved state payload `S/Q` is kept job-local and may be consumed only after hydration reports complete; normal Android restore no longer writes `_staged_state_data`.
- `GameState.install_state_machine()` installs the transaction-local destination only after world hydration and preserves the active Trace recorder.
- start/restart chapter snapshots receive the reference-shaped destination state explicitly so the pristine snapshot remains equivalent without publishing saved states early.
- Android title normal/start/restart/overworld destinations are installed once; the prior duplicate title-overworld `OverworldFreeState` append is removed.
- Android in-chapter normal/start/overworld destinations install saved `S/Q` plus the same destination policy as the synchronous desktop path, without leaving the loader as gameplay state.
- restore/read failure is handled before the loader update returns: transaction-local payload is discarded, partial world fields are reset, a clean base session is rebuilt, and control returns through `title_start` rather than exposing a half-restored map.
- desktop `save.load_game`, `GameState.load`, title/restart, save schema, slot kinds, restart-slot behavior, aura/FOW/RNG ordering, debugger/profiler, fast-forward, and project content were not intentionally changed.

Controller-reviewed scope is exactly:

- `app/engine/game_state.py`
- `app/engine/save.py`
- `app/engine/title_screen.py`
- `app/engine/general_states.py`
- `app/tests/test_atomic_restore.py`
- `app/tests/test_android_performance_round3.py`

No Trace V1 schema/comparator/manifest/golden JSONL or project-data file changed.

Reported validation accepted for the implementation:

- targeted restore/title/restart/debugger/save/lifecycle tests: **144/144 PASS**;
- recovery trace/lifecycle/golden suite: **50/50 PASS**;
- S1, S12, S18 strict immutable-oracle comparisons: PASS;
- S2 and S4 strict comparisons against their locked initial-state contract: PASS;
- all 17 persisted golden hashes/manifest unchanged;
- `python -m compileall -q app`: PASS;
- `git diff --check`: PASS;
- `git show --check`: PASS;
- broader suite still terminates in the pre-existing baseline failure stream; no P2-specific failure was demonstrated.

The correctness-first tradeoff is accepted: Android restore may now produce a longer single main-thread stall. Reintroducing progressive world hydration is not authorized here and requires a later phase to prove off-world construction plus atomic publication.

## Pre-existing S2/S4 runner drift — mandatory P2-T03 prerequisite

This is a test-harness defect, not a P2-T02 production regression.

The current `app/tests/recovery_trace_runner.py` installs `free` in `_prepare_playable_game()` before S2/S4 setup. The persisted S2/S4 PC-reference goldens were captured under an earlier runner state and lock a different initial state-stack contract (`active=[]`). Running the current runner against the PC reference therefore reproduces the same S2/S4 mismatch seen on recovery.

The runner file was unchanged by P2-T02, so the mismatch predates `0a6b854e...`.

Before removing any P2-T03 production workaround, the executor must make a **bounded test-only correction** so S2 and S4 can be rerun from their already-locked fixture contract through the normal runner without manual invocation edits.

Rules:

- do not change any golden JSONL byte, manifest value, Trace V1 semantics, comparator semantics, checkpoint meaning, seed, project fixture, or reference revision;
- determine from the persisted evidence/fixture contract which scenarios require `free` and which require an empty initial stack;
- make the smallest scenario-specific runner correction;
- rerun S2 and S4 on PC reference twice and require byte/logical stability against the existing persisted goldens;
- rerun S2 and S4 on recovery and require exact comparator PASS against those same goldens;
- if the existing hashes cannot be reproduced without changing semantic inputs, STOP under ESC-03/ESC-05 and request controller review.

No staged-workaround removal is authorized until this prerequisite passes.

## P2-T03 authorized scope

Execute **P2-T03 only** using **GPT-5.6 Terra / medium**.

Goal: remove or narrow only workarounds whose invalid partial-restore condition P2-T02 has now made impossible. Keep independently useful defensive behavior.

Candidate surfaces from the accepted P2-T01 map include:

- legacy `_staged_state_data` field and `commit_staged_state()` compatibility path;
- `prepare_for_load()` if it no longer has an independently necessary failure/reset role;
- `MapState.update_visuals` camera/tilemap and map-view/tilemap guards added specifically for staged restore;
- transparent-map/settings null guards added specifically for staged restore;
- related stale comments/tests that encode the old frame-sliced restore contract.

Do **not** assume every null guard is obsolete. Debugger/title/overworld/no-map states can make some guards independently correct. For each candidate, prove provenance, current callers, and a real invariant before removal.

### Required order

1. Fix and prove the S2/S4 runner drift above, test-only.
2. Re-run atomic restore tests and the relevant Phase-1 semantic scenarios before production cleanup.
3. Inventory current callers/writers of `_staged_state_data`, `commit_staged_state`, and `prepare_for_load` after P2-T02.
4. Remove a staging field/method only if no valid caller/compatibility requirement remains; otherwise narrow/document it.
5. Evaluate each camera/map/settings/debugger guard independently. Remove only guards whose sole reachable purpose was the now-impossible partial restore state.
6. After each production cleanup cluster, rerun the targeted lifecycle/restore tests and relevant immutable goldens.
7. Stop for controller review; do not begin Phase 3.

### Protected behavior

Preserve:

- INV-03 atomic restore transaction from P2-T02;
- desktop and Android destination-stack semantics;
- save schema and SAVE_SLOTS/RESTART_SLOTS behavior;
- `chapter_start_snapshot` behavior;
- aura/FOW/RNG ordering;
- fast-forward INV-06;
- debugger/profiler INV-07;
- Android audio/resource/render policy unrelated to staged restore;
- project data/assets;
- immutable Phase-1 oracle bytes.

### Validation

At minimum run:

- corrected S2/S4 PC-reference reproducibility and recovery comparisons;
- `app.tests.test_atomic_restore`;
- `app.tests.test_state_machine_lifecycle`;
- `app.tests.test_recovery_trace`;
- `app.tests.test_recovery_golden`;
- targeted title/load/restart/debugger/settings tests for touched guards;
- relevant S1/S2/S4/S12/S13/S14/S18 immutable semantic comparisons;
- broader unit suite, recording the known baseline termination if it persists;
- `python -m compileall -q app`;
- `git diff --check` before commit;
- `git show --check` after commit.

Do not modify expected goldens after a mismatch.

## Escalation and stop rules

P2-T03 escalation target is **GPT-5.6 Sol / high**, not pre-authorized.

STOP on:

- ESC-02 nonlocal correctness root cause;
- ESC-03 deterministic trace divergence;
- ESC-05 invariant failure;
- ESC-06 save compatibility conflict;
- ESC-07 Android boundary conflict;
- ESC-08 repeated local failure;
- ESC-09 unplanned architecture.

Do not self-escalate.

## Gate status

**P2-T02 is ACCEPTED. P2-T03 is the only authorized task. Phase 3 remains blocked pending P2-T03 controller review.**
