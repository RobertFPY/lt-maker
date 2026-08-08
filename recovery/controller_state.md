# Recovery Controller State

> This file is the live controller-gate state for the recovery program.
> `plan.md` remains authoritative for architecture, task definitions, model assignments, escalation conditions, invariants, and acceptance criteria.
> This file overrides only the stale/static `CURRENT EXECUTION STATE` section in `plan.md` when they disagree.

## Current authorization

- Current phase: Phase 1
- Last reviewed task: `P1-T01-R1`
- Last reviewed commit: `d7538402cc3919cf0bb79b1dc3e6db1800a691fd`
- Review result: **ACCEPTED**
- `P1-T01` design gate: **ACCEPTED after R1 revision**
- Next authorized task: **`P1-T02` only**
- P1-T02 primary: `GPT-5.6 Terra / medium`
- P1-T02 escalation target: `GPT-5.6 Sol / high`
- Escalation pre-authorized: **NO**
- Controller gate after P1-T02: **NO** (do not self-advance; P1-T03 still requires its prerequisite and controller authorization state)

## P1-T01-R1 controller review

Accepted evidence:

- Commit `d7538402cc3919cf0bb79b1dc3e6db1800a691fd` modifies only `recovery/trace_schema.md`.
- No recorder, production hook, fixture, gameplay code, test implementation, or baseline-failure repair was introduced.
- R1: `semantic_delta.hook_calls` preserves correctness-critical hook invocation order/count with stable subject/context identities and fails loudly on unmapped hooks.
- R2: `object_graph` preserves shared-object aliasing using deterministic local IDs while excluding raw Python identity/UID/address from equality output.
- R3: event execution state now models the active frame plus pending LIFO event frames, command ordinal/identity, and caller provenance where available.
- R4: terminal synchronization checkpoints require an empty pending state-transition queue unless a checkpoint-specific controller-approved exception exists; invalid partial state raises `TraceInvariantError`.
- R5: save-write tracing is unambiguously defined as `save.payload.captured` after complete in-memory logical payload assembly and before filesystem I/O.
- The schema remains V1 because no V1 golden fixture has yet been accepted/generated.
- No model escalation was used or required.

## P1-T02 execution constraints

Codex must execute only P1-T02 from `plan.md`: implement the approved trace/test harness with minimal production intrusion.

Required implementation principles:

- The recorder must be test-owned/injected and inactive by default.
- No-recorder behavior must be covered by tests and must not alter lifecycle ordering, RNG consumption, action dispatch, error handling, or scheduling.
- Production instrumentation is limited to the approved synchronization/observer seams needed by the Trace V1 contract; do not broadly instrument render loops or every staged/yield boundary.
- Unknown semantic action/playback/hook types must fail loudly rather than fall back to `repr` or disappear.
- Stable local references must preserve aliasing while remaining independent of runtime allocation IDs.
- Unit/object serializers must capture the authoritative logical fields required by scenarios; use existing save/runtime semantics as evidence and add deterministic serializer tests rather than speculative broad dumps.
- Do not generate or bless PC-reference golden fixtures in P1-T02; that belongs to P1-T03.
- Do not fix baseline suite failures unless a new P1-T02 harness test itself exposes a defect in the harness implementation.
- Escalate only under the P1-T02 conditions in `plan.md`; do not self-escalate.
- Do not start P1-T03 in the same task/session.
