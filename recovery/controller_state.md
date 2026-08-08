# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file resolves the current P1-T03 ambiguity and overrides stale execution-state text when needed.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Last executor stop: P1-T03 under **ESC-01 / ESC-04** on scenario 17
- Controller disposition: **ESC-01 / ESC-04 RESOLVED** by the decision below
- Resume model: **GPT-5.6 Terra / high**
- Escalation target remains: **GPT-5.6 Sol / max**
- Escalation pre-authorized for any new issue: **NO**
- Controller gate after P1-T03: **YES — STOP FOR CONTROLLER REVIEW**
- Phase 2 remains **UNAUTHORIZED**

## Accepted blocker evidence

At behavioral reference `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`, the later runtime debugger/profiler implementation does not exist. In particular, the reference has no `app/engine/runtime_debugger.py`, no `app/engine/performance.py`, and no native Trace V1 implementation. Therefore the reference cannot provide an authoritative "debugger/profiler enabled-idle" behavior.

The executor correctly stopped before generating fixtures or inventing reference behavior. The previously demonstrated reference-side Trace V1 compatibility overlay remains acceptable only as observer-only instrumentation; it must not simulate debugger/profiler semantics.

## Controller decision for scenario 17

**Do not create a no-op debugger/profiler implementation on the PC reference.** That would manufacture a post-reference feature and incorrectly bless test-authored behavior as the golden oracle.

**Do not remove scenario 17 from P1-T03.** INV-07 still requires proof that debugger/profiler observation is semantically inert.

Scenario 17 is redefined as a **hybrid reference-anchored + recovery metamorphic invariant**.

### 17A — Reference-disabled baseline

Use the PC reference with no debugger/profiler simulation. Run the deterministic scenario with the accepted instrumentation-only Trace V1 overlay and emit the test-runner checkpoint `debugger.observer.check` at the final committed synchronization point.

The checkpoint name is a test-harness marker only; it does **not** imply that the reference contains a debugger or profiler.

Generate the reference baseline fixture from this run.

### 17B — Recovery disabled vs PC reference

Run the same seed/input/scenario on the recovery branch with debugger/profiler disabled. It must compare equal to the 17A reference baseline under normal Trace V1 comparison rules.

This proves the later observer features do not alter default/disabled PC semantics.

### 17C — Recovery debugger enabled-idle metamorphic check

On the recovery branch, run the same seed/input twice:

1. debugger disabled;
2. debugger enabled/entered through an existing real debugger path, perform **no mutating debug command**, then return to the same committed gameplay synchronization point.

Compare the complete logical traces/final `debugger.observer.check` state. They must be logically equivalent after any temporary debugger UI/presentation state has been exited. Do not whitelist a persistent gameplay-state difference merely because the debugger UI uses a state object.

Use actual current debugger/controller/service code paths; do not replace them with a fake no-op debugger. Read-only inspection/snapshot operations are allowed. Any mutating RuntimeDebugger command is forbidden in the enabled-idle run.

### 17D — Recovery profiler enabled-idle metamorphic check

On the recovery branch, run the same deterministic workload twice:

1. profiler disabled;
2. profiler enabled using the existing profiler implementation/configuration path, with its real section/count/frame observer code executing where applicable.

The two logical traces/final committed states and RNG states must be equal. Profiler timing samples, wall time, log output, thread IDs, GC counters, and profiler buffers are diagnostic provenance and are not gameplay equality fields.

A test-scoped platform/environment setup may activate the existing profiler path when the host is not Android, but it must execute the real `RuntimeProfiler` implementation rather than stub profiler methods. If activation requires changing gameplay/lifecycle code or inventing a new profiler abstraction, STOP under ESC-09.

### Scenario 17 fixture/manifest rule

Scenario 17 should be recorded in the manifest as a hybrid comparison, for example:

- reference fixture: `reference_disabled_baseline` from `9314f54b...`;
- recovery check 1: disabled == reference baseline;
- recovery check 2: debugger-enabled-idle == recovery-disabled;
- recovery check 3: profiler-enabled-idle == recovery-disabled.

There is **no PC-reference enabled-idle golden fixture** and no simulated reference debugger/profiler.

Scenario 17 is PASS only if all required comparisons above pass. If an actual current observer path changes gameplay state/RNG/order at the committed checkpoint, report the divergence as evidence; do not weaken the trace or modify the golden.

## P1-T03 resume contract

Resume the same P1-T03 task; this is not a new phase or permission to fix gameplay.

- Scenarios 1–16 and 18 remain ordinary PC-reference golden scenarios exactly as defined in `plan.md` and the prior P1-T03 contract.
- Scenario 17 follows the hybrid contract above.
- The isolated reference worktree may be reused if still clean and still points to `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.
- The accepted Trace V1 overlay on the reference remains instrumentation-only.
- Do not generate current-branch output and copy it into reference fixtures.
- Do not silently regenerate fixtures after mismatch.
- Do not begin Phase 2 repairs.
- Report every scenario 1–18 individually. Overall PASS is forbidden if any scenario is skipped or unresolved.

## Model disposition

The original ESC-01 / ESC-04 required controller semantic judgment. That judgment is now explicitly supplied here, so the bounded execution can resume at the planned primary **GPT-5.6 Terra / high** rather than spending Sol/max on deterministic fixture generation.

If a **new** reference ambiguity, competing semantic interpretation, deterministic non-presentation trace conflict, save-format decision, cross-system invariant failure, or other listed ESC condition appears, STOP again and request the specified P1-T03 escalation target **GPT-5.6 Sol / max**. Do not self-escalate.

## Gate status

P1-T03 is authorized to resume under this decision. Phase 2 remains blocked until P1-T03 is completed and reviewed by the controller.
