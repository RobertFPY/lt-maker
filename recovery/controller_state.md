# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 9 — Full validation and release candidate**
- Phases 1–8: **ACCEPTED**
- P9-T01 full PC regression matrix: **PARTIAL / NOT ACCEPTED** at `dcf9c937a3276109aa9f3ded9f1f7155e6b5377c`
- Active task: **P9-T01-R1 only — PC validation blocker resolution**
- Original P9-T01 primary: **GPT-5.6 Luna / medium**
- Authorized R1 model: **GPT-5.6 Terra / high**
- Escalation authorization: **YES — Terra/high for P9-T01-R1 only**
- P9-T02/P9-T03/P9-T04: **UNAUTHORIZED**
- Expected production behavior changes: **NONE**
- Test-only cleanup is allowed only if a deterministic recovery-added test-isolation leak is proven and the correction is narrow, semantic-neutral, and does not hide an assertion.
- Environment-only launch configuration through an existing supported repository/runtime seam is allowed.
- Product logger/runtime behavior must not be patched merely to bypass the current sandbox/AppData permission restriction.
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Merge to `master`: **UNAUTHORIZED**
- Controller gate after P9-T01-R1: **YES — STOP FOR CONTROLLER REVIEW**

## P9-T01 partial review record

The controller reviews `dcf9c937a3276109aa9f3ded9f1f7155e6b5377c` (`docs(recovery): record P9 PC matrix`) as **PARTIAL, not accepted**.

Accepted evidence already established by that run:

- the commit is exactly one descendant of P9-T01 authorization commit `b13b85b1cdb67b7e1167ece0e6b03616bb6760b7`;
- scope is evidence-only: `recovery/p9_t01_pc_regression_matrix.md`;
- no production source, tests, project data/assets, Trace V1 schema/comparator/manifest/goldens, Android policy, or master branch changed;
- the authoritative baseline interpreter/command reproduced the historical native Windows exit `-1073740791` (`0xC0000409`) at the same workspace-test location;
- historical named event-command, Python-event, combat-calculation and Dragon Medal failures reproduced;
- isolated accepted Phase-3-through-8/recovery suites are green except the recorded historical `test_combat_calcs` baseline error;
- every frozen supported Trace V1 scenario S1/S2/S4-S16/S17-disabled/S17-debugger-idle/S17-profiler-idle/S18 matched exactly; S3 remains reference-unsupported/N-A;
- runtime importability without PyQt5, compileall and git validation checks passed;
- `mypy` is unavailable in the current environment and remains an `ENVIRONMENT/TOOLING` limitation rather than a reason to modify dependencies in this task.

P9-T01 is not accepted because two required release-validation gates remain unresolved:

1. **Aggregate full-suite delta.** The full discovery produced additional aggregate-only FAIL/ERROR markers beyond the recorded P0 baseline before reaching the same native termination. Fresh owner processes did not reproduce those results, but that alone does not prove they are harmless. P9-T01-R1 must deterministically identify the earliest polluter/root cause and classify whether it is a recovery-added test leak, a pre-existing framework/test-order interaction, or a production semantic regression.
2. **Representative real project launch.** `run_engine.py` selected the real `default.ltproj`, initialized pygame, then stopped in `lt_log.create_logger()` because the Windows AppData known-folder is not writable in the current execution environment. The process therefore did not reach project DB/resource validation or normal engine startup. P9-T01 cannot PASS until a real project launch reaches that checkpoint through an existing supported route, or remains PARTIAL if the environment provides no such route.

## Locked contracts during P9-T01-R1

All Phase-1-through-8 contracts remain immutable for this diagnostic task:

1. One shared gameplay core; no PC/Android gameplay fork.
2. No partial live gameplay state or new yielded authoritative transaction.
3. Combat solver/action/RNG/hook/cleanup/state-stack/end-combat ordering remains unchanged.
4. Canonical save/load/restart and pristine restart source precedence remain unchanged.
5. Fast-forward changes presentation/host time only, not logical outcomes/input-edge semantics.
6. Debugger/profiler observer contracts remain unchanged.
7. P6 platform boundaries remain unchanged; no Event wall-clock command scheduler.
8. P8 cache decisions remain locked: `GC-REGION` is NOT CERTIFIED SAFE; battle source-frame caching is REJECTED; title smoke is accepted KEEP-PLATFORM; styled-text optimization remains deferred.
9. Immutable Trace V1 fixtures/goldens are read-only release oracles.
10. Project data/assets are protected.

---

# P9-T01-R1 — PC validation blocker resolution

Execute **P9-T01-R1 only** using **GPT-5.6 Terra / high**.

This is an explicitly authorized escalation from the original P9-T01 Luna/medium validation task because the remaining blockers require bounded diagnosis. The authorization applies only to this R1. Do not begin P9-T02.

## Goal A — full-suite aggregate pollution

Re-run the exact authoritative baseline command with the recorded interpreter and capture the complete observable failure ordering before the native termination.

For every additional result not present in `recovery/baseline.md`:

- identify exact test/module and exception/assertion;
- prove whether it passes in a fresh process;
- perform a bounded order/process bisect to identify the earliest preceding test/module whose execution causes the later failure;
- inspect only relevant leaked global state, especially component subclass/catalog registries, dynamically created component classes such as `_Uses`, DB/RESOURCES singleton state, global `game`, LTCache/global component caches, and codegen/component-access registries where evidence points there;
- distinguish cause from downstream cascade; do not count every later error as an independent regression.

Classify the root cause as exactly one:

- `RECOVERY-ADDED-TEST-LEAK`
- `PRE-EXISTING-FRAMEWORK/TEST-ORDER-DEBT`
- `PRODUCTION-SEMANTIC-REGRESSION`
- `ENVIRONMENT/TOOLING`
- `UNRESOLVED`

If a deterministic **RECOVERY-ADDED-TEST-LEAK** is proven, a narrow test-only teardown/reset correction is authorized only when it restores process isolation without weakening assertions, changing test expectations, or altering production semantics. Rerun the authoritative full suite after that correction.

If the root cause is production behavior, requires broad registry/framework architecture changes, or is not local/unambiguous: **STOP for controller review**. Do not repair production code under P9-T01-R1.

An isolated PASS is evidence, not a waiver for a new aggregate-order regression.

## Goal B — representative real project launch

Inspect the actual current:

- `run_engine.py` startup path;
- `lt_log.create_logger()` implementation;
- user/log-data path resolver used before project loading;
- existing repository/runtime environment variables, CLI options or official smoke/launch helpers.

Find whether the repository already exposes a supported way to redirect logger/user-data output to a writable temporary location without changing product code.

Allowed:

- environment-only setup through an existing supported variable/config seam;
- existing repository CLI option;
- existing official bounded engine smoke/launch helper;
- controlled termination of the real engine process after evidence proves that real project DB/resources were loaded, project validation ran, and normal engine startup was reached.

Not allowed:

- monkeypatching `lt_log.create_logger`;
- editing logger/platform-directory production code merely for this sandbox;
- fake `GameState`, fake project, or import-only smoke presented as a project launch;
- modifying `.ltproj` data/assets;
- bypassing project validation.

Record exact launch evidence:

```text
PROJECT:
COMMAND:
LOGGER/USER-DATA ROUTE:
PROJECT LOAD CHECKPOINT:
VALIDATION CHECKPOINT:
ENGINE STARTUP CHECKPOINT:
EXIT/TERMINATION METHOD:
RESULT:
```

If there is no supported writable-path route in the current environment, classify `ENVIRONMENT/TOOLING` and keep P9-T01 `PARTIAL`; do not patch production to manufacture a PASS.

## Type check

`mypy` being unavailable may remain `ENVIRONMENT/TOOLING`.

Do not install or modify dependencies merely to satisfy P9-T01-R1.

## Required revalidation

After any permitted test-only isolation correction, or after completing diagnosis if no code changes are allowed, run as applicable:

- exact authoritative full-suite baseline command;
- all frozen supported Trace V1 scenarios S1/S2/S4-S16/S17 three modes/S18;
- focused accepted Phase-3-through-8/recovery regression suites;
- canonical save/load/restart regressions;
- fast-forward equivalence;
- debugger parity/controller regressions;
- profiler observer regressions;
- project/base integrity;
- runtime importability without PyQt5;
- `utilities\enemy_event_generator\.python\python.exe -m compileall -q app`;
- `git diff --check`;
- `git show --check` after commit;
- clean final `git status --short`.

No golden regeneration.

## Change policy

Allowed files by default:

- update `recovery/p9_t01_pc_regression_matrix.md`;
- optional `recovery/p9_t01_r1_blocker_resolution.md`.

A test file may change only for a proven `RECOVERY-ADDED-TEST-LEAK` and only with a minimal reset/teardown fix.

Production files remain unauthorized.

Do not modify Trace V1/comparator/manifest/goldens, project data/assets, Android policy, or master.

## PASS / PARTIAL rules

P9-T01-R1 may report `PASS` only if all P9-T01 acceptance requirements are now satisfied, including:

- no unexplained immutable Trace divergence;
- accepted focused matrix remains green aside from explicitly recorded historical baseline failures;
- the additional aggregate pollution is deterministically resolved/restored to baseline-safe behavior, or proven not to be a recovery regression with evidence sufficient for controller acceptance;
- a representative **real** PC project launch reaches project load/validation/normal engine startup;
- no production/project/Trace changes occurred.

If either aggregate pollution or real project launch remains unresolved, report `PARTIAL`.

Do not self-advance to P9-T02 even if R1 reports PASS.

## Escalation / stop rules

Terra/high is already authorized for this R1 only.

STOP without further escalation if diagnosis shows:

- immutable Trace divergence (`ESC-03`);
- partial/live invalid state (`ESC-05`);
- save compatibility conflict (`ESC-06`);
- PC/Android gameplay-boundary conflict (`ESC-07`);
- repeated local remediation failure (`ESC-08`);
- cross-cutting production/registry/lifecycle architecture would be required (`ESC-09`).

Do not self-escalate to Sol.

## Report

TASK RESULT: PASS | PARTIAL | FAIL
MODEL/EFFORT
BRANCH
START HEAD
FILES CHANGED
FULL SUITE RESULT
FULL SUITE BASELINE DELTA
AGGREGATE POLLUTION ROOT CAUSE
POLLUTER BISECT EVIDENCE
TEST-ISOLATION FIX
REAL PROJECT LAUNCH RESULT
LOGGER/USER-DATA ROUTE
PROJECT LOAD/VALIDATION CHECKPOINT
IMMUTABLE TRACE MATRIX
FOCUSED REGRESSION MATRIX
SAVE/LOAD/RESTART RESULT
FAST-FORWARD RESULT
DEBUGGER RESULT
PROFILER RESULT
TYPE CHECK RESULT
IMPORT/COMPILE RESULT
PROJECT-DATA INTEGRITY
PRODUCTION CHANGES
COMMANDS RUN
KNOWN-BASELINE-SAME
KNOWN-BASELINE-CHANGED
NEW REGRESSIONS
ENVIRONMENT/TOOLING LIMITS
ESCALATION TRIGGERS
COMMIT SHA
WORKING TREE STATUS
NEXT ACTION: CONTROLLER REVIEW

STOP FOR CONTROLLER REVIEW.
