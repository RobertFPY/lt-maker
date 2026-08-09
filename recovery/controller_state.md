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
- Project-data changes: **UNAUTHORIZED except the exact cleanup authorization below**
- Controller gate after P5-T01-R1: **YES — STOP FOR CONTROLLER REVIEW**

## P5-T01-R1 required finding

R1 remains audit/test-only. It must close the save compatibility ownership of `game.phase` and `game.initiative` before P5-T02 can be authorized.

Accepted facts:

1. Neither PC-reference nor current `GameState.save()` serializes top-level `phase` or `initiative` state.
2. Current `GameState.generic()` creates a fresh `PhaseController`; `load_iter()` does not deserialize one.
3. Under initiative mode, `PhaseController` depends on `game.initiative`.
4. `level_setup_iter()` creates/starts `InitiativeTracker` before `chapter_start_snapshot` capture.
5. `load_iter()` does not restore `InitiativeTracker`, whose mutable state includes `unit_line`, `initiative_line`, and `current_idx`.
6. The same top-level omission exists in the PC reference, so a supported-path mismatch must not be silently labeled a post-reference regression.
7. `bounds` and `fog_state` are serialized reconstruction inputs; derived board/boundary/occupancy/visible-FOW/aura structures are not serialized authoritative objects.

R1 must determine supported save-kind reachability for exact phase/initiative state. If a supported current-progress save demonstrably loses semantics and resolving it requires choosing between preserving reference behavior and adding a compatibility fix/schema behavior, report **ESC-04 / ESC-06** and stop. Do not repair production during R1.

## Explicit cleanup authorization — unintended initiative probe side effects

The controller explicitly authorizes cleanup of the accidental tracked project-resource modifications created by the temporary P5-T01-R1 initiative probe, subject to all constraints below.

### Authorized paths only

Restore tracked modifications under exactly these two path prefixes to the current branch `HEAD` version:

- `default.ltproj/resources/portraits/`
- `default.ltproj/resources/old_portraits/`

This authorization exists solely to remove unintended probe side effects. It is **not** authorization to restore all of `default.ltproj`, delete project data, modify assets, or change any intended project content.

### Required pre-cleanup verification

Before restoring anything, record:

- `git status --short`
- `git diff --name-only`
- `git diff --name-only -- default.ltproj/resources/portraits default.ltproj/resources/old_portraits`

The executor must verify that the dirty project-resource files it intends to restore are tracked modifications under only those two prefixes and are the unintended probe output described in the task report.

Do **not** restore or discard:

- `recovery/p5_t01_save_compatibility_audit.md` R1 evidence;
- any test file intentionally created/modified for R1;
- any production file;
- any file outside the two authorized project-resource prefixes.

If additional dirty project-data paths exist outside the two prefixes, STOP and report them instead of broadening cleanup.

### Authorized cleanup operation

A path-scoped restore from the current branch `HEAD` is explicitly authorized for the two prefixes above. Equivalent safe commands include:

```text
git restore --source=HEAD -- default.ltproj/resources/portraits default.ltproj/resources/old_portraits
```

or a more granular restore of the exact tracked files returned by the pre-cleanup diff.

Do not use:

- `git reset --hard`;
- `git clean`;
- `git checkout -- default.ltproj`;
- `git restore --source=HEAD -- default.ltproj`;
- any command that discards unrelated working-tree changes.

### Required post-cleanup verification

Immediately after cleanup, verify:

- no tracked diff remains under either authorized prefix;
- `git diff --name-only` contains only intended P5-T01-R1 report/test changes;
- no production/schema/golden/project-data changes remain.

The cleanup itself must not be committed because it restores tracked files back to `HEAD`; only the bounded R1 audit/test changes are eligible for commit.

## R1 continuation and stop rules

After the authorized cleanup:

- finish only the P5-T01-R1 audit/test work already authorized;
- do not rerun any probe that writes into project resources unless redesigned to operate in a temporary/copy-only location;
- preserve the existing R1 evidence already collected if valid;
- run the required focused phase/initiative/save/load/restart validation and immutable S1/S2/S4/S12/S18 comparisons;
- run `python -m compileall -q app`, `git diff --check`, commit bounded R1 audit/tests, then `git show --check`;
- STOP for controller review.

P5-T02/P5-T03 remain blocked. Do not self-escalate. Production/save-schema changes remain unauthorized.

## Gate status

**P5-T01 is PARTIAL. Cleanup of only the two accidental portrait-resource prefixes is explicitly authorized. P5-T01-R1 remains the only active task. P5-T02/P5-T03 and later phases remain blocked.**
