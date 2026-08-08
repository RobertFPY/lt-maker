# P0-T01 Recovery Baseline

Date: 2026-08-08 (Asia/Bangkok)
Task: P0-T01 — Capture recovery baseline
Execution: GPT-5.6 Luna / low
Escalation: GPT-5.6 Terra / medium (not authorized or used)

## Scope and safety

This report records the baseline only. No engine behavior, project content, or
tests were modified for P0-T01. The full-suite failures below are recorded,
not fixed.

## Git ancestry and starting point

| Item | Value |
|---|---|
| Recovery branch | `recovery/pc-core-semantics` |
| Recovery starting HEAD | `0821182a717de2baaf52a699ee325241ffaddd03` |
| Current HEAD during collection | `7f2a0cc5079bdbf39ff26d80d551ea7d10ec1daa` |
| PC behavioral reference | `9314f54b49f4552b5a3d023b4da0012ce7dfbc89` |
| Reference is ancestor of starting HEAD | Yes |
| Starting HEAD is ancestor of current HEAD | Yes |
| Current branch is tracking | `origin/recovery/pc-core-semantics` |
| Working tree before report | Clean |

The current HEAD contains the recovery-plan/controller documentation commits
after the stated starting HEAD. The engine inventory below is intentionally
computed against the stated recovery starting HEAD, not the current document
tip.

## Python, OS, and dependency versions

Runtime executable:
`utilities\enemy_event_generator\.python\python.exe`

- OS: Windows 10 `10.0.26200-SP0`
- PowerShell: `5.1.26100.8972`
- Git: `2.55.0.windows.3`
- Python: CPython `3.11.9` (`MSC v.1938 64 bit (AMD64)`)
- pygame-ce: `2.3.2` with SDL `2.26.5`
- PyQt5: `5.15.10`; Qt: `5.15.2`

`pip freeze` at collection time:

```text
altgraph==0.17.5
packaging==26.2
pefile==2024.8.26
pygame-ce==2.3.2
pyinstaller==6.2.0
pyinstaller-hooks-contrib==2026.6
PyQt5==5.15.10
PyQt5-Qt5==5.15.2
PyQt5_sip==12.18.0
pywin32-ctypes==0.2.3
typing_extensions==4.8.0
```

## Full test-suite baseline

Command:

```powershell
utilities\enemy_event_generator\.python\python.exe -m unittest discover -s app/tests -p 'test*.py' -v
```

Result:

- Process exit: `-1073740791` (`0xC0000409`), abnormal termination.
- The process terminated before unittest printed its normal final summary;
  an exact `Ran N tests` total is therefore unavailable from this run.
- Observed result lines before termination: 311 `ok`, 8 `FAIL`, 1 `ERROR`.
- The output ended while entering
  `test_workspace_is_not_a_child_window_of_main_editor`.
- Repeated `libpng` iCCP warnings and expected test logging warnings were
  observed; they are recorded as noise, not classified as test failures.

Observed failing/error results, categorized by functional area only (not a
root-cause claim):

1. Event-command catalog/parser/validator results:
   - `events.test_event_commands.EventCommandUnitTests.test_check_event_functions_match_event_commands`
   - `events.test_event_commands.EventCommandUnitTests.test_determine_command_type_nickname`
   - `events.test_event_commands.EventCommandUnitTests.test_parse_text_to_command_typing`
   - `events.test_event_commands.EventCommandUnitTests.test_validators`
2. Python-event integration:
   - `events.test_event_start_pointer.EventTestLevelIntegrationTests.test_python_event_query_runs_against_real_game`
3. Combat calculation:
   - `test_combat_calcs.CombatCalcTests.test_counter_logic` (ERROR)
4. Project/content-facing Dragon Medal assertions:
   - `test_dragon_medal.DragonMedalTest.test_both_medals_use_the_same_restriction_and_effect` — subtests `Dragon_Medal`, `Dragon_Medal_Pro2`
   - `test_dragon_medal.DragonMedalTest.test_medal_description_changes_for_martin_and_other_dragons`
5. Process-level termination:
   - The suite ended abnormally before its final summary; no fix or further
     diagnosis is part of P0-T01.

## Android and runtime flags

The Android bootstrap in
`utilities/build_tools/android_runtime/app_template/main.py` sets these
defaults before importing pygame/application modules:

| Flag | Baseline behavior |
|---|---|
| `LT_ANDROID_RUNTIME` | Set to `1` by Android bootstrap; `app.engine.android_runtime.is_android_runtime()` requires a truthy value. |
| `LT_ANDROID_RENDER_OPT` | Set to `1`; render optimization is enabled only when both this and `LT_ANDROID_RUNTIME` are truthy. |
| `LT_ANDROID_PROFILE` | Set to `1` by the diagnostics APK bootstrap; profiler still requires Android runtime. |
| `LT_DISABLE_JOYSTICK` | Set to `1` for touch-only Android input. |
| `LT_HARDWARE_SCALE` | Set to `1`; engine uses the hardware-scaled display path when available. |
| `SDL_ACCELEROMETER_AS_JOYSTICK` | Set to `0` to prevent accelerometer joystick input. |
| `SDL_RENDER_VSYNC` | Set to `0` by the Android bootstrap. |

Runtime/build inputs also inspected:

- `ANDROID_ARGUMENT`, `ANDROID_APP_PATH`, `ANDROID_UNPACK`, and
  `ANDROID_PRIVATE` identify the Python-for-Android app/runtime and private
  storage paths.
- `LT_USER_DATA_DIR` can override the user-data root; the Android bootstrap
  derives it from private storage when needed.
- `LT_PRECISE_FRAME_PACING` is recognized by the engine, but the inspected
  Android bootstrap does not set it by default.
- `LT_REPO_ROOT` is a build/preflight tooling override, not a gameplay flag.
- `ANDROID_DATA=/data` and `ANDROID_ROOT=/system` are used by the bundled
  platform-directory detection.
- Tests use `SDL_VIDEODRIVER=dummy` in selected headless modules.

The desktop path does not enable the Android render path unless the explicit
Android runtime flag is present. The central runtime flag implementation is
`app/engine/android_runtime.py`.

## Profiling controls

There are two baseline profiling paths:

1. Legacy frame timing in `app/engine/driver.py`:
   - `LT_PROFILE` enables slow-frame timing output when the variable exists.
   - `LT_PROFILE_THRESHOLD` is parsed as a millisecond threshold; invalid
     values disable that legacy profile path.
2. `RuntimeProfiler` in `app/engine/performance.py`:
   - Enabled only when Android runtime is active and `LT_ANDROID_PROFILE` is
     truthy.
   - `LT_PROFILE_INTERVAL` controls aggregate report interval; default `5`
     seconds.
   - `LT_PROFILE_SLOW_FRAME_MS` controls slow-frame capture threshold; default
     `100` ms.
   - Records are aggregated in memory and include nested section timing,
     counters, frame metadata, and slow-frame context.

Instrumented consumers include frame input/update/draw/present stages, state
transitions, events, map composition, combat phases and rendering, title/load
steps, sound, save/restore, tilemap jobs, and Android menu paths. Save timing
records include `save_load_read`, `save_load_unpickle`, restore phases,
`save_io`, and `save_snapshot`.

## Engine files changed since the PC reference

Comparison: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89..0821182a717de2baaf52a699ee325241ffaddd03 -- app/engine`

Count: **81 engine files**; **11,120 lines added**, **1,675 lines deleted**.

```text
app/engine/achievements.py
app/engine/action.py
app/engine/android_debugger.py
app/engine/android_runtime.py
app/engine/banner.py
app/engine/base.py
app/engine/battle_animation.py
app/engine/bmpfont.py
app/engine/combat/animation_combat.py
app/engine/combat/base_combat.py
app/engine/combat/interaction.py
app/engine/combat/map_combat.py
app/engine/combat/mock_combat.py
app/engine/combat/simple_combat.py
app/engine/combat/solver.py
app/engine/combat_calcs.py
app/engine/config.py
app/engine/convoy_funcs.py
app/engine/debug_mode.py
app/engine/dialog.py
app/engine/driver.py
app/engine/engine.py
app/engine/feat_choice.py
app/engine/fluid_scroll.py
app/engine/fonts.py
app/engine/game_board.py
app/engine/game_menus/menu_components/unit_menu/unit_menu.py
app/engine/game_menus/menu_components/unit_menu/unit_table.py
app/engine/game_menus/menu_options.py
app/engine/game_menus/menu_states/unit_menu_state.py
app/engine/game_over.py
app/engine/game_state.py
app/engine/general_states.py
app/engine/health_bar.py
app/engine/help_menu.py
app/engine/highlight.py
app/engine/icons.py
app/engine/info_menu/info_graph.py
app/engine/info_menu/info_menu_portrait.py
app/engine/info_menu/info_menu_state.py
app/engine/info_menu/multi_desc.py
app/engine/input_manager.py
app/engine/item_components/__init__.py
app/engine/item_components/utility_components.py
app/engine/item_funcs.py
app/engine/jobs/__init__.py
app/engine/jobs/add_group_job.py
app/engine/jobs/tilemap_change_job.py
app/engine/map_view.py
app/engine/menus.py
app/engine/movement/unit_path_movement_component.py
app/engine/objects/overworld/overworld.py
app/engine/objects/tilemap.py
app/engine/objects/unit.py
app/engine/overworld/overworld_states.py
app/engine/particles.py
app/engine/performance.py
app/engine/persistent_records.py
app/engine/phase.py
app/engine/player_choice.py
app/engine/prep.py
app/engine/promotion.py
app/engine/runtime_debugger.py
app/engine/runtime_debugger_controller.py
app/engine/runtime_debugger_service.py
app/engine/runtime_reset.py
app/engine/save.py
app/engine/settings.py
app/engine/settings_menu.py
app/engine/skill_components/__init__.py
app/engine/sound.py
app/engine/sprites.py
app/engine/state.py
app/engine/state_machine.py
app/engine/status_upkeep.py
app/engine/text_entry.py
app/engine/title_screen.py
app/engine/trade.py
app/engine/ui_view.py
app/engine/unit_funcs.py
app/engine/unit_sprite.py
```

## P0-T01 disposition

- Baseline collection complete.
- No engine behavior changes made.
- Existing test failures and abnormal termination recorded; none fixed.
- No escalation condition was acted on; no model escalation was requested.
- This report is the only artifact for P0-T01. P0-T02 remains unauthorized.
