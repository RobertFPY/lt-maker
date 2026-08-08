# Recovery Controller State

> This file is the live controller-gate state for the recovery program.
> `plan.md` remains authoritative for architecture, task definitions, model assignments, escalation conditions, invariants, and acceptance criteria.
> This file overrides only the stale/static `CURRENT EXECUTION STATE` section in `plan.md` when they disagree.

## Current authorization

- Current phase: Phase 1
- Last reviewed task: `P1-T01`
- Last reviewed commit: `37a8be4de0613691b70bb6bf5dcd48034b5532ea`
- Review result: **CHANGES REQUESTED**
- Next authorized work: **`P1-T01-R1` trace-schema revision only**
- Primary: `GPT-5.6 Terra / high`
- Escalation target: `GPT-5.6 Sol / max`
- Escalation pre-authorized: **NO**
- `P1-T02` remains **UNAUTHORIZED**
- Controller gate after P1-T01-R1: **YES — STOP FOR CONTROLLER REVIEW**

## P1-T01 controller review

Accepted parts of `recovery/trace_schema.md`:

- Design is documentation-only; no gameplay, test, fixture, recorder, or production hook implementation was introduced.
- JSONL + canonical normalization + SHA-256 state/delta hashes are suitable for deterministic comparison.
- Volatile render/audio/profiler/thread/object-address state is explicitly excluded from equality.
- State, world, turn, units, variables, RNG, board/tilemap/aura/fog, event, and save/restart completion surfaces are represented.
- Synchronization points are terminal logical boundaries rather than render frames or iterator yields.
- Action/playback/event deltas are ordered and unknown semantic types fail loudly instead of falling back to `repr`.
- Golden fixtures are tied to the PC reference and cannot be silently regenerated to hide a regression.
- Fast-forward and debugger/profiler observer-equivalence are compared by logical traces, not host-frame count.
- No escalation was used and none is currently required.

The design is close to approval, but the following semantic gaps must be fixed before P1-T02.

## Required P1-T01-R1 revisions

### R1 — Explicit ordered gameplay-hook trace

The current `semantic_delta` contains actions, combat playback, and triggered events, but does not explicitly preserve **hook invocation order/count**. That is insufficient for later combat recovery because two executions can reach the same final state while calling an item/skill/combat hook twice, skipping it, or reordering hooks.

Revise the Trace V1 contract to include an ordered hook stream, e.g. `hook_calls`, with enough stable logical identity to compare:

- dispatcher/system (`item`, `skill`, combat/lifecycle owner as applicable);
- hook name;
- logical subject/source references (unit/item/skill using stable local references);
- target/context identity needed to distinguish invocations;
- lifecycle phase/checkpoint context;
- optional normalized semantic result only when the return value is gameplay-relevant.

Tracing must observe the **original invocation**. It must never call a hook a second time merely to record it. P1-T02 may use a test-only observer seam around approved dispatch points; broad invasive instrumentation is not authorized by this revision.

Unknown/unmapped correctness-critical hook observations must fail loudly rather than be dropped.

### R2 — Preserve shared-object aliasing in stable local references

The current owner/category/slot/path tuple is not sufficient by itself for shared runtime objects. Aura children are the key example: one `SkillObject` instance can legitimately appear in multiple units' skill lists.

Revise the identity contract so the serializer preserves aliasing without hashing raw UID/address values:

- build a capture-time object graph using identity only internally for deduplication;
- assign each logical object a deterministic local ID from the first canonical traversal/reference path;
- subsequent references to the same runtime object must reuse that same local ID;
- raw Python identity/UID/address must never enter equality/hash output unless the UID is itself an explicitly approved gameplay-semantic field;
- include a harness test requirement proving a shared aura child serializes as one shared logical object/reference rather than independent copies.

This is required to detect aura/source corruption across load/restart while remaining allocation-order independent.

### R3 — Represent nested/stacked event execution state

The schema currently shows one `events.active` frame. Recovery explicitly needs save/load during events and the engine has event-stack behavior.

Revise the contract to represent the ordered active event execution stack (or an equivalent structure justified against the actual event runtime), including at least stable event identity and command position/ordinal per frame. Parent/caller relationship must survive normalization where applicable.

Do not include dialogue/render wait state unless it changes logical execution semantics, but do preserve enough execution-stack state to detect resuming the wrong event/command after save/load.

### R4 — Define pending state-transition semantics at synchronization points

`state_stack.pending` is currently hash-compared without a rule distinguishing logical queued transitions from staging/presentation artifacts.

Define a precise rule:

- terminal synchronization checkpoints should normally represent a fully committed logical transaction;
- if a pending transition means the transaction is not actually complete, trace generation should fail that checkpoint/invariant rather than normalize an invalid partial state as expected behavior;
- if a specific checkpoint legitimately permits a pending logical transition, that exception must be explicit and scenario/checkpoint-specific;
- Android-only render/defer scheduling must not become golden gameplay state merely because it exists in `pending`.

### R5 — Remove ambiguity around save-write checkpoint timing

`save.write.complete` is described as immediately before/after logical save capture. Choose one canonical semantic boundary or define separate checkpoint IDs. The trace must make it unambiguous which logical state is being asserted and must not depend on filesystem timing.

## P1-T01-R1 constraints

- Modify only `recovery/trace_schema.md` unless a tiny recovery-document cross-reference is strictly necessary.
- Do not implement recorder code, production hooks, fixtures, or P1-T02.
- Do not fix baseline failures.
- Do not change `plan.md` architecture or model policy.
- Use the same primary `GPT-5.6 Terra / high`.
- No escalation is required for these revisions. If a genuine ESC condition appears, STOP and report instead of using Sol.
- Prefer a new documentation commit rather than rewriting the reviewed commit, so controller history remains auditable.

## Gate status

`P1-T01` is **not yet accepted**. `P1-T02` remains blocked until a revision commit satisfies R1–R5 and is reviewed by the controller.
