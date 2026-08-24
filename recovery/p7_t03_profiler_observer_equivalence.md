# P7-T03 profiler observer-equivalence evidence

## Scope and contract

`RUNTIME_PROFILER` remains an observer.  This task adds test-owned evidence
only; no production profiler or gameplay code was changed.  Equality is based
on logical gameplay effects, not timing samples, scope durations, counters,
GC diagnostics, or other profiler-owned state.

## ON/OFF and logical evidence

The focused profiler suite proves a deterministic seeded path has identical
RNG state, ordered effects, HP result, and one gameplay execution with the
profiler disabled and enabled.  Existing accepted Trace V1 evidence covers the
same observer contract for S17 disabled, debugger-idle, and profiler-idle;
`app.tests.test_recovery_trace` and `app.tests.test_recovery_golden` passed
without changing fixtures, the comparator, or the manifest.

The accepted P7-T01 fast-forward equivalence suite remains green, including
S16 and its 200%, 300%, and 800% logical comparisons.  The accepted P7-T02
debugger parity and P5 canonical load/restart suites also remain green.

## Main-thread and worker scope isolation

The real-thread test starts a main-frame outer section, runs a real secondary
Python thread whose `section('worker')` body executes once, then creates a
main-thread nested section.  The worker section is absent from the frame scope
tree, does not alter `_scope_stack`, parentage, or `_frame_thread_id`, and the
main-thread tree remains correctly nested through `finish_frame()`.

This verifies the existing implementation contract: sections record only when
enabled and running on the frame thread; worker sections still execute their
wrapped body but are observer no-ops.

## GC and disabled mode

The deterministic GC callback test registers the existing callback only when
needed, invokes `start` and `stop` directly, checks that only `_gc_started` and
`_gc_finished` change, and restores callback membership.  Disabled-mode proof
checks that wrapped code executes once, `count()` has no gameplay effect, no
scope is recorded, and no warning is emitted merely by disabled instrumentation.

## Source-level branch audit

Test-owned source checks cover representative StateMachine lifecycle branches,
Event command execution, and driver frame profiling.  Both profiler branches
execute the same gameplay call once; profiling surrounds the call and is not a
condition for a different operation.  Existing combat lifecycle tests cover
combat ordering and remain green.  `_performance_counters()` and profiler
aggregation remain diagnostic consumers only.

## Validation

Focused results from this task:

- `app.tests.test_performance_profiler`: **37 passed**.
- profiler/P7-T01/P7-T02/P5 load-restart batch: **94 passed**.
- combat/lifecycle/tilemap/sound/Android/Trace/golden/Event batch:
  **114 passed**.
- `python -m compileall -q app`: passed.
- `git diff --check`: passed.

The broader unittest discovery was run as a gate.  Its known failures remain
baseline test-isolation/component-registry pollution (`_Uses.tag`), the
existing unrelated Windows/native termination where reproduced, and the
known `text_renderer`/`text_funcs` import-order circularity when that test is
selected.  None required a P7-T03 production change.

No PC-reference fixture was regenerated.  The immutable S5, S16, S17 observer
modes, and S18 contracts remain unchanged; their integrity tests passed.

## Result and limits

**PASS — observer equivalence evidence complete.**  Production changes: none.
Device/JNI timing and visual behavior are not claimed by these host-side
tests; profiler timing values are intentionally excluded from logical
comparison.
