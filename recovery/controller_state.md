# Recovery Controller State

> This file is the live controller-gate state for the recovery program.
> `plan.md` remains authoritative for architecture, task definitions, model assignments, escalation conditions, invariants, and acceptance criteria.
> This file overrides only the stale/static `CURRENT EXECUTION STATE` section in `plan.md` when they disagree.

## Current authorization

- Current phase: Phase 1
- Last reviewed task: `P0-T02`
- Last reviewed commit: `d57a2fbd913a67c4a08472a0737a2ddae8a2fa8c`
- Review result: **ACCEPTED**
- Next authorized task: **`P1-T01` only**
- P1-T01 primary: `GPT-5.6 Terra / high`
- P1-T01 escalation target: `GPT-5.6 Sol / max`
- Escalation pre-authorized: **NO**
- Controller gate after P1-T01: **YES — STOP FOR CONTROLLER REVIEW**

## P0-T02 controller review

Accepted evidence:

- Commit `d57a2fbd913a67c4a08472a0737a2ddae8a2fa8c` adds only `recovery/change_inventory.md`.
- No engine, test, project-content, or baseline-failure changes were made.
- Inventory explicitly covers all 81 `app/engine` paths changed between `9314f54b` and recovery starting HEAD.
- High-risk staged restore, tilemap/board jobs, staged combat, fast-forward/state-machine, save/load/restart, profiler/debugger, and Android audio/runtime surfaces are separated rather than treated as one mixed rollback.
- `52bd0403` and `0821182a` are correctly treated as mixed commits that must not be reverted wholesale.
- Confirmed staged gameplay clusters are classified as `RESTORE-PC-SEMANTICS`, `REWRITE-PLATFORM`, or `REMOVE-WORKAROUND` as appropriate.
- Independent profiler/debugger/audio/correctness work is protected with `KEEP-SHARED`, `KEEP-PLATFORM`, or `KEEP-CORRECTNESS-FIX` classifications.
- Unresolved semantic cases are marked `NEEDS-CONTROLLER-DECISION` rather than guessed.
- Adjacent `app/events` transaction partners are identified for later trace/lifecycle work without incorrectly counting them in the 81-engine-file acceptance set.
- No model escalation was used.

Non-blocking note:

- The P0-T02 report says `P0-T03` remains unauthorized; there is no P0-T03 in the plan. This is a wording error only and does not affect the inventory or gate result.

## Controller disposition of P0-T02 open questions

The four architecture questions at the end of `recovery/change_inventory.md` are intentionally **deferred**, not answered during Phase 0:

1. Pending-world GameState/board/tilemap preparation vs full removal will be decided only after deterministic trace evidence and the Phase 2/4 audits.
2. State-machine deferred-render/presentation-barrier behavior will be separated from staged loading only after trace design and fast-forward evidence.
3. Mixed `52bd0403` gameplay/data-facing edits will be classified by behavioral evidence, not provenance.
4. Android streamed battle music remains a protected platform feature; its separation from authoritative animation-combat advancement is resolved during combat/platform phases.

Codex must not treat these deferred questions as permission to choose an implementation during P1-T01.

## P1-T01 execution constraints

Codex must execute only `P1-T01 — Design deterministic trace schema` from `plan.md`.

This task is **design only**. Do not broadly instrument or modify production gameplay code yet.

The trace design must compare logical state at synchronization points, not render-frame timing. It must be sufficient to distinguish:

- canonical PC state-machine ordering from staged/deferred restore behavior;
- combat solver/action/hook/cleanup ordering;
- event ordering and transaction boundaries;
- RNG consumption/checkpoints where feasible;
- tilemap/board/aura/fog consistency;
- save/load/restart transaction completion;
- fast-forward ON/OFF logical equivalence;
- debugger/profiler observer-equivalence.

Prefer a minimal, deterministic, serialization-friendly schema with explicit normalization rules for volatile/non-gameplay fields. Include proposed helper APIs, synchronization-point hooks, state-hash strategy, golden-fixture strategy, and how reference-vs-recovered traces will be compared.

Do not encode current Android staging behavior as expected behavior. `9314f54b` remains the behavioral reference unless a later correctness fix is explicitly allowlisted.

Escalate only under the P1-T01 conditions in `plan.md`, especially if reference semantics are genuinely ambiguous or the tracing design itself requires a new core lifecycle semantic. Do not self-escalate.
