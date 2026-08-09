# P9-T01-R1 — Full PC Regression Matrix

Date: 2026-08-10
Primary: GPT-5.6 Terra / high (controller-authorized P9-T01-R1 escalation)
Branch: `recovery/pc-core-semantics`
Start HEAD: `d54decd31cdd36d8d60f7df669d5b515ccce43f3`
PC reference: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
Initial P9-T01 evidence: `dcf9c937a3276109aa9f3ded9f1f7155e6b5377c`

## TASK RESULT

**PASS — CONTROLLER REVIEW.**

Both P9-T01 blockers are resolved with bounded evidence:

- the aggregate discovery delta was caused by a recovery-added test import
  leak and is restored to the recorded P0 failure set with a test-only fixture
  lifetime correction;
- a real `default.ltproj` engine process reached resource load, database load,
  `driver.start`, title-state execution, and normal running status through its
  existing Windows AppData logger path before controlled termination.

No production, project-data, Trace V1, comparator, manifest, or golden change
was made.

## MODEL/EFFORT

GPT-5.6 Terra / high. This escalation was explicitly authorized for
P9-T01-R1 only.

## FILES CHANGED

- `app/tests/test_recovery_trace.py` — test-only synthetic Component fixture
  lifetime correction;
- `recovery/p9_t01_pc_regression_matrix.md` — this R1 evidence update.

## FULL SUITE RESULT

Required command:

```powershell
utilities\enemy_event_generator\.python\python.exe -m unittest discover -s app/tests -p 'test*.py' -v
```

After the test-only correction:

- exit: `-1073740791` (`0xC0000409`);
- no normal unittest summary, as in P0;
- termination while entering
  `test_workspace_is_not_a_child_window_of_main_editor`;
- observed logical result set before termination: 8 FAIL and 1 ERROR, matching
  the recorded P0 baseline;
- no additional aggregate project-integrity, Event runtime, component,
  canonical-load, or CSV-exporter error remains.

## FULL SUITE BASELINE DELTA

| Baseline result | R1 result | Classification |
|---|---|---|
| Native exit `-1073740791` at workspace test | Same exit and location | `KNOWN-BASELINE-SAME` |
| Four event-command failures | Same named failures | `KNOWN-BASELINE-SAME` |
| Python-event integration failure | Same named failure | `KNOWN-BASELINE-SAME` |
| `test_counter_logic` error | Same named error | `KNOWN-BASELINE-SAME` |
| Dragon Medal two subtests plus description failure | Same named failures | `KNOWN-BASELINE-SAME` |
| Additional aggregate failures from initial P9-T01 | Absent after correction | resolved recovery test leak |

## AGGREGATE POLLUTION ROOT CAUSE

The first additional failure was:

```text
default_ltproj.test_base_project_integrity.
BaseProjectIntegrityTests.testDefaultProjectNoWarningsOrErrors
AttributeError: type object '_Uses' has no attribute 'tag'
```

Its complete failing path was:

```text
DB.load -> items.restore -> item_component_access.get_cached_item_components
-> recursive_subclasses(ItemComponent) -> sort by x.tag -> _Uses.tag
```

`_Uses` and the equivalent `_Marker` were top-level synthetic subclasses in
`app.tests.test_recovery_trace`. Python discovery imports every test module
before running the first discovered test, so these classes were already in the
global `ItemComponent` and `SkillComponent` subclass trees before the base
project integrity test built the uncached production component catalog.

### FIRST ADDITIONAL FAILURE

`BaseProjectIntegrityTests.testDefaultProjectNoWarningsOrErrors` was the first
extra discovery failure after the initial raw-data test. The paired testing
project integrity test failed for the same reason.

### POLLUTER BISECT EVIDENCE

1. A fresh `default.ltproj` base-integrity test passed before importing the
   recovery trace module.
2. Importing `app.tests.test_recovery_trace` added exactly
   `app.tests.test_recovery_trace._Uses` to recursive item-component subclasses
   and `_Marker` to recursive skill-component subclasses.
3. After clearing only the component-access LRU caches, the same base-integrity
   test deterministically failed at `_Uses.tag`.
4. Full discovery imports the recovery trace module before the base-integrity
   test executes, reproducing that uncached catalog condition.

This is an import-time module bisect, not an inferred test-order explanation.

### ROOT-CAUSE CLASSIFICATION

`RECOVERY-ADDED-TEST-LEAK`.

Git provenance identifies the top-level fixture introduction in recovery
commit `adc9ec753e6bf6623a31e013c762c10b01e53482`
(`fix(trace): complete R2 semantic oracle`). No production component behavior
or project component data was changed.

### TEST-ISOLATION FIX

The synthetic `_Uses` and `_Marker` component classes now exist only inside
`RecoveryTraceR2AcceptanceTests.test_r2_2_real_item_skill_components_and_alias_relationships`,
the sole test that uses them. Assertions and expected values are unchanged.

Isolation proof in one process:

- importing `test_recovery_trace` leaves no test classes in either recursive
  component subclass tree;
- the base integrity test passes before the R2 component test;
- after the R2 test, collection, and component-cache clear, both subclass trees
  remain free of test component classes;
- the following testing-project integrity test passes.

The correction is test-only and removes only global state introduced by that
test fixture.

## REAL PROJECT LAUNCH RESULT

**PASS.**

```text
PROJECT: default.ltproj
COMMAND: utilities\enemy_event_generator\.python\python.exe -u run_engine.py
         (real child process, SDL_VIDEODRIVER=dummy, controlled after 6 s)
LOGGER/USER-DATA ROUTE:
  C:\Users\ADMIN.DESKTOP-NG60QMN\AppData\Local\rainlash\Lex Talionis\Logs
PROJECT LOAD CHECKPOINT:
  RESOURCES.load logged all default project catalogs, including tilemaps.
VALIDATION CHECKPOINT:
  run_engine.py passed metadata fatal-error validation and reached DB.load;
  DB logged complete default.ltproj game_data deserialization.
ENGINE STARTUP CHECKPOINT:
  driver.start printed Version: 2026.02.17a; engine logged Engine Init
  Completed; title music Main Theme entered GlobalMusicState.PLAYING.
EXIT/TERMINATION METHOD:
  process was still running after six seconds and was explicitly terminated;
  exit code 1 is the controlled child termination, not a startup exception.
RESULT: PASS
```

The initial AppData failure was sandbox write isolation, not a repository
logger-path defect. `LT_USER_DATA_DIR`, `APPDATA`, and `LOCALAPPDATA` are not
logger-routing seams in this bundled Windows platformdirs path; the successful
run used the actual existing Windows known-folder route without product
modification. This is a real project startup proof, not an import-only smoke.

## IMMUTABLE TRACE MATRIX

After the test-only correction, every locked comparison passed:

| Scenario | Result |
|---|---|
| S1 | PASS |
| S2 | PASS |
| S3 | N/A — REFERENCE-UNSUPPORTED |
| S4–S16 | PASS exact logical records |
| S17 disabled | PASS |
| S17 debugger-idle | PASS |
| S17 profiler-idle | PASS |
| S18 | PASS |

No fixture, manifest, comparator, normalizer, or Trace V1 schema was changed.

## FOCUSED REGRESSION MATRIX

Fresh baseline-interpreter processes passed after the correction:

| Phase/area | Evidence |
|---|---|
| Phase 3 | combat transaction, animation transaction, interaction, missing-item solver |
| Phase 4 | tilemap change job and atomic restore |
| Phase 5 | canonical load, restart contract, project save transaction |
| Phase 6 | work budget, sound policy, Android render/audio/resource policy suites |
| Phase 7 | fast-forward, debugger, debugger controller/parity, profiler |
| Phase 8 | cache memoization, title smoke, info-menu and title option render caches |
| Recovery | trace, state-machine lifecycle, golden integrity |
| Project/base | default project integrity, user-data paths, unit path movement |

All listed suites passed. The full-suite-only historical
`test_combat_calcs` error remains unchanged and is not repaired.

## SAVE/LOAD/RESTART RESULT

PASS. `test_atomic_restore`, `test_canonical_load`, `test_restart_contract`,
and `test_project_save_transaction` passed. Immutable S1, S2, S4, S12, and S18
passed exactly.

## FAST-FORWARD RESULT

PASS. `test_fast_forward`, `test_fast_forward_equivalence`, and immutable S16
passed.

## DEBUGGER RESULT

PASS. Runtime debugger, controller, parity suites and S17 debugger-idle passed.

## PROFILER RESULT

PASS. `test_performance_profiler` and S17 profiler-idle passed.

## TYPE CHECK RESULT

`mypy app/` remains `ENVIRONMENT/TOOLING`: `mypy` is unavailable. No dependency
was installed and no typing code was changed.

## IMPORT/COMPILE RESULT

After the correction:

- bounded runtime import without PyQt5 — PASS;
- `utilities\enemy_event_generator\.python\python.exe -m compileall -q app` — PASS;
- `git diff --check` — PASS.

## PROJECT-DATA INTEGRITY

No `.ltproj` or asset path has a tracked diff. The real launch wrote only its
normal AppData debug log outside the repository.

## PRODUCTION CHANGES

None.

## TEST CHANGES

One recovery-test-only fixture lifetime correction in
`app/tests/test_recovery_trace.py`; no assertion, expected result, skip, or
test input was changed.

## COMMANDS RUN

- exact authoritative discovery before and after the correction;
- bounded discovery/import/component-cache polluter reproducer;
- ordered component-test to base-project follower isolation proof;
- full immutable Trace V1 matrix;
- focused Phase 3–8, recovery, canonical load/restart, fast-forward, debugger,
  profiler, and project/base matrix;
- real controlled `run_engine.py` launch via existing AppData logger route;
- runtime importability, compileall, and git checks.

## KNOWN-BASELINE-SAME

- native `-1073740791` at the workspace test;
- four event-command failures;
- Python-event integration failure;
- combat-calculation error;
- Dragon Medal failures.

## KNOWN-BASELINE-CHANGED

None after the R1 test isolation correction.

## NEW REGRESSIONS

None.

## ENVIRONMENT/TOOLING LIMITS

`mypy` remains unavailable. The real launch proof uses the SDL dummy video
backend for controlled headless execution; it proves actual project/engine/title
startup, not desktop-window presentation fidelity.

## ESCALATION TRIGGERS

None reached. The confirmed leak was local and recovery-test-owned; no
production or framework architecture change was required.

## COMMIT SHA

The final content-addressed commit SHA is reported in the task handoff after
this report is committed.

## WORKING TREE STATUS

The final post-commit status is reported in the task handoff.

## NEXT ACTION

CONTROLLER REVIEW. Do not begin P9-T02.
