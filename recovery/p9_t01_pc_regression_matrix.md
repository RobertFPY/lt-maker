# P9-T01 — Full PC Regression Matrix

Date: 2026-08-10
Primary: GPT-5.6 Luna / medium
Branch: `recovery/pc-core-semantics`
Start HEAD: `b13b85b1cdb67b7e1167ece0e6b03616bb6760b7`
PC reference: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

## TASK RESULT

**PARTIAL**.

All isolated accepted regression suites and all frozen Trace V1 scenarios
completed without an unexplained logical divergence. The authoritative full
suite reproduced the native termination signature, but its aggregate output
contains additional test-order/global-registry pollution markers compared with
the recorded baseline. A real `run_engine.py` launch was exercised, but this
environment stops in `lt_log.create_logger()` because the Windows AppData
known-folder is not writable. The required representative launch PASS
criterion is therefore not met.

No production code, tests, project content, Trace V1 schema, comparator,
manifest, or golden fixture was changed.

## FULL SUITE RESULT

Required command, using the recorded interpreter:

```powershell
utilities\enemy_event_generator\.python\python.exe -m unittest discover -s app/tests -p 'test*.py' -v
```

Observed:

- exit `-1073740791` (`0xC0000409`);
- no normal unittest summary;
- termination while entering
  `test_workspace_is_not_a_child_window_of_main_editor`;
- exit signature and last-test location match `recovery/baseline.md`;
- captured verbose stream contained 6 `FAIL` and 29 `ERROR` status markers
  before termination. Because wrapped verbose lines can split names/statuses,
  these markers are not a trustworthy final unique-test total.

Historical named failures all reproduced:

- `events.test_event_commands.EventCommandUnitTests.test_check_event_functions_match_event_commands`
- `events.test_event_commands.EventCommandUnitTests.test_determine_command_type_nickname`
- `events.test_event_commands.EventCommandUnitTests.test_parse_text_to_command_typing`
- `events.test_event_commands.EventCommandUnitTests.test_validators`
- `events.test_event_start_pointer.EventTestLevelIntegrationTests.test_python_event_query_runs_against_real_game`
- `test_combat_calcs.CombatCalcTests.test_counter_logic`
- `test_dragon_medal.DragonMedalTest.test_both_medals_use_the_same_restriction_and_effect`
  (subtests `Dragon_Medal` and `Dragon_Medal_Pro2`)
- `test_dragon_medal.DragonMedalTest.test_medal_description_changes_for_martin_and_other_dragons`

Additional aggregate-only markers appeared in project-integrity, event
runtime/inspection, event-start setup, skill/aura, canonical-load setup, and
CSV-exporter areas. Fresh owner processes did not reproduce those additional
results. They are recorded as aggregate test-order/global-registry pollution,
not diagnosed or fixed here.

## FULL SUITE BASELINE DELTA

| Result | Classification | Evidence |
|---|---|---|
| Native exit and last test | `KNOWN-BASELINE-SAME` | Same `-1073740791` and workspace-test location |
| Historical event-command failures | `KNOWN-BASELINE-SAME` | Same four tests and assertion families in isolation |
| Historical Python-event failure | `KNOWN-BASELINE-SAME` | Same test; `HasRapier` remained `0` instead of `True` |
| Historical combat-calculation error | `KNOWN-BASELINE-SAME` | Same test; isolated error at `MockUnit.skills` |
| Historical Dragon Medal failures | `KNOWN-BASELINE-SAME` | Same three logical failures in isolation |
| Additional aggregate-only errors | `KNOWN-BASELINE-CHANGED` | Not reproduced by fresh-process owner suites |
| New isolated gameplay regression | `NOT-REPRODUCED` | Focused matrix and immutable traces below |

## FOCUSED REGRESSION MATRIX

Each row used a fresh baseline-interpreter process.

| Area | Suites | Result |
|---|---|---|
| Phase 3 combat transaction/lifecycle | `test_combat_transaction_order`, `test_animation_combat_transaction_order` | PASS |
| Phase 3 combat calculation | `test_combat_calcs` | `KNOWN-BASELINE-SAME` error |
| Phase 4 tilemap/restore | `test_tilemap_change_job`, `test_atomic_restore` | PASS |
| Phase 5 load/restart | `test_canonical_load`, `test_restart_contract`, `test_project_save_transaction` | PASS |
| Phase 6 platform/audio/resource | `test_android_render_optimization`, `test_android_soundroom_round2`, `test_android_performance_round3`, `test_android_performance_instrumentation`, `test_sound_platform_policy` | PASS |
| Phase 7 fast-forward | `test_fast_forward`, `test_fast_forward_equivalence` | PASS |
| Phase 7 debugger | `test_runtime_debugger`, `test_runtime_debugger_controller`, `test_runtime_debugger_parity` | PASS |
| Phase 7 profiler | `test_performance_profiler` | PASS |
| Phase 8 cache/render/title | `test_cache_memoization`, `test_title_smoke_seed`, `test_info_menu_render_optimization`, `test_android_title_option_cache` | PASS |
| Recovery | `test_recovery_trace`, `test_state_machine_lifecycle`, `test_recovery_golden` | PASS |
| Project/user-data/movement | `default_ltproj.test_base_project_integrity`, `test_user_data_paths`, `test_unit_path_movement` | PASS |

## IMMUTABLE TRACE MATRIX

The accepted recovery runner and locked comparator were used against existing
fixtures. No fixture or expected record was regenerated.

| Scenario | Result |
|---|---|
| S1 | PASS |
| S2 | PASS |
| S3 | N/A — REFERENCE-UNSUPPORTED; no fixture |
| S4 | PASS |
| S5 | PASS |
| S6 | PASS |
| S7 | PASS |
| S8 | PASS |
| S9 | PASS |
| S10 | PASS |
| S11 | PASS |
| S12 | PASS |
| S13 | PASS |
| S14 | PASS |
| S15 | PASS |
| S16 | PASS |
| S17 disabled | PASS |
| S17 debugger-idle | PASS |
| S17 profiler-idle | PASS |
| S18 | PASS |

All comparisons passed with exact logical records. No first divergent
checkpoint exists.

## PC PROJECT LAUNCH RESULT

Root inventory:

- `autosave_FETOGK.ltproj` — ignored by `run_engine.py` because it starts with
  `autosave`;
- `default.ltproj` — selected real project in this checkout;
- `Fire Emblem Tales of The Golden Knight.ltproj`;
- `testing_proj.ltproj`.

The real command `python run_engine.py` was run with the required interpreter.
It reached pygame initialization and the startup logger, then exited before
project validation/game startup:

```text
pygame-ce 2.3.2 (SDL 2.26.5, Python 3.11.9)
debug: 1
No permission to write to AppData.
```

The result persisted with temporary `LT_USER_DATA_DIR`, `APPDATA`, and
`LOCALAPPDATA`; the bundled Windows platform-directory code uses the known
folder API for the logger. No project file changed. Classification:
`ENVIRONMENT/TOOLING`.

## SAVE/LOAD/RESTART RESULT

`test_canonical_load`, `test_atomic_restore`, `test_restart_contract`, and
`test_project_save_transaction` passed in fresh processes. S1, S2, S4, S12,
and S18 passed immutable comparisons. This covers current SAVE loading,
pristine restart source selection, persistent fallback, game-over restart,
difficulty/context routing, initiative/phase, aura/FOW, and atomic failure
contracts through the accepted routes.

## FAST-FORWARD RESULT

`test_fast_forward` and `test_fast_forward_equivalence` passed. S16 passed the
immutable oracle, including logical OFF/ON equivalence and input/presentation
behavior.

## DEBUGGER RESULT

`test_runtime_debugger`, `test_runtime_debugger_controller`, and
`test_runtime_debugger_parity` passed. S17 disabled and debugger-idle passed;
no shared-controller or restart-routing regression was observed.

## PROFILER RESULT

`test_performance_profiler` passed. S17 profiler-idle passed with exact logical
Trace V1 equality. No profiler production behavior changed.

## TYPE CHECK RESULT

`mypy app/` is `ENVIRONMENT/TOOLING`: `mypy` is unavailable. No dependency was
installed and no typing code was changed.

## IMPORT/COMPILE RESULT

- `import app.engine.engine, app.engine.game_state, app.events.event` — PASS;
  no PyQt5 import was required;
- baseline `python -m compileall -q app` — PASS;
- `git diff --check` — PASS before this report was created.

## PROJECT-DATA INTEGRITY

`git status --short` and `git diff --name-only` were clean after validation.
No project data/assets, Trace V1 fixtures, manifest, comparator, or production
file changed.

## PRODUCTION CHANGES

None.

## COMMANDS RUN

- required authoritative full discovery;
- fresh-process Phase 3–8 and recovery focused suites listed above;
- fresh-process historical event-command, Python-event, combat-calculation,
  and Dragon Medal suites;
- all frozen Trace V1 captures/comparisons for S1–S18, with S3 N/A and all S17
  observer modes;
- bounded real `python run_engine.py` launch attempts;
- `mypy app/` availability check;
- bounded runtime import;
- baseline `python -m compileall -q app`;
- `git diff --check`, `git status --short`, and `git diff --name-only`.

## KNOWN-BASELINE-SAME

Four event-command failures, one Python-event integration failure, one
combat-calculation error, three Dragon Medal logical failures/subtests, and
the native Windows termination at the workspace test.

## KNOWN-BASELINE-CHANGED

The full discovery run emitted additional aggregate-only errors/status markers
in project-integrity, event runtime/inspection, event-start setup, skill/aura,
canonical-load setup, and CSV-exporter areas before the same native termination.
They were not reproduced by fresh-process owner suites. No root-cause diagnosis
or fix was attempted.

## NEW REGRESSIONS

None identified in an isolated accepted Phase 3–8 contract or immutable Trace
V1 scenario.

## ENVIRONMENT/TOOLING LIMITS

1. Real project launch is blocked at the Windows AppData logger permission
   boundary, so the task cannot be marked PASS.
2. `mypy` is unavailable.
3. Full discovery terminates before summary, as in the baseline, with
   additional aggregate-only pollution markers.

## ESCALATION TRIGGERS

No ESC-03 trace divergence, partial-state failure, or isolated new production
regression was observed. The aggregate `KNOWN-BASELINE-CHANGED` pollution and
AppData launch limitation remain controller-review items. No Terra/high
escalation was self-requested.

## COMMIT SHA

The final content-addressed commit SHA is reported in the task handoff after
this report is committed.

## WORKING TREE STATUS

The final post-commit status is reported in the task handoff.

## NEXT ACTION

CONTROLLER REVIEW. Do not begin P9-T02.
