# P9-T02 Android regression and performance matrix

## Task result

**PARTIAL.**  The current recovery host-side Android/platform contract matrix and
the required frozen Trace V1 scenarios passed.  ADB is installed, but `adb
devices -l` returned no connected or booted emulator target.  Consequently no
current-recovery APK could be installed, launched, observed, or profiled on a
real Android runtime.  This report makes no Android device, acoustic, or FPS
claim.

## Identity and scope

| Item | Value |
| --- | --- |
| Model / effort | GPT-5.6 Terra / medium |
| Branch | `recovery/pc-core-semantics` |
| Start HEAD | `4c7f418f43d9d8dd2541c9a6b408d63b26cd1ca5` |
| Scope | Validation/evidence only |
| Production/test/project/Trace changes | None |

## Android environment and build provenance

| Check | Result |
| --- | --- |
| Host | Windows 10.0.26200; baseline interpreter `utilities\\enemy_event_generator\\.python\\python.exe` (Python 3.11.9) |
| ADB | `C:\\Users\\ADMIN.DESKTOP-NG60QMN\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe`; Android Debug Bridge 1.0.41 / 37.0.0-14910828 |
| `adb devices -l` | No devices/emulators attached; no authorization state, model, API, or ABI available |
| Supported build path | `utilities\\build_tools\\android_runtime\\build_runtime.ps1` builds through WSL/Buildozer; `utilities\\build_tools\\android_emulator\\run_smoke_test.ps1` is the supported install/launch smoke route |
| Supported smoke behavior | Derives package/activity, installs a fixed APK, launches it, waits, captures logcat/screenshot, and fails on fatal/ANR/Python traceback |
| Latest discovered artifact | `Fire Emblem Tales of The Golden Knight_android_build\\fire-emblem-tales-of-the-golden-knight-android-0.2.0-20260807T155720Z-0a608ab3\\fire-emblem-tales-of-the-golden-knight-0.2.0-arm64-debug.apk` |
| Artifact metadata | debug, arm64-v8a, package `org.lextalionis.fire_emblem_tales_of_the_golden_knight`, min/target API 26/36, SHA-256 `0a608ab32ec56b9c5a112177212607b94c71c2ec25f3d534a7821ad7f6596ed5`; APK verification passed when built |
| Current-build provenance | Not current: the artifact manifest source digest is `0ec48c4c...`, dated 2026-08-07, and does not establish provenance for current HEAD `4c7f418...` |
| Build/install/launch | Not run: no usable target exists.  No rebuild was manufactured merely for validation. |

## PC/Android synchronization parity

The host suites exercise the Android policy seams against the shared gameplay
core.  They show the required invariant at the tested synchronization points:

`same seed/input/source/context -> shared authoritative transaction -> same logical state`.

The frozen Trace V1 comparison provides exact logical evidence for current
recovery behavior; it is not presented as a substitute for a device run.

| Synchronization surface | Evidence | Result |
| --- | --- | --- |
| Current save load / pristine restart | canonical-load, atomic-restore, restart-contract, project-save tests; S2/S4 | PASS |
| Gameplay/combat cleanup | S5/S7/S8 and accepted combat/profiler coverage | PASS |
| Aura/FOW/tilemap commit | tilemap job and atomic-restore suites; S12/S13/S14 | PASS |
| Phase and fast-forward | work-budget/fast-forward suites; S15/S16 | PASS |
| Debugger/profiler observer paths | debugger-parity and profiler suites; S17 three modes | PASS |
| Game-over restart | S18 | PASS |

## Immutable Trace V1 matrix

The locked comparator was run against the committed fixtures with profile
`recovery`.  All required scenarios matched exactly:

| Scenario | Result |
| --- | --- |
| S2 existing save load | PASS |
| S4 restart current chapter | PASS |
| S5 standard map combat | PASS |
| S7 animation combat | PASS |
| S8 base combat | PASS |
| S12 aura lifecycle | PASS |
| S13 FOW move/cancel/wait | PASS |
| S14 tilemap change | PASS |
| S15 phase transition | PASS |
| S16 fast-forward reference-off | PASS |
| S17 disabled / debugger-idle / profiler-idle | PASS / PASS / PASS |
| S18 game-over restart | PASS |

No fixture, manifest, normalizer, schema, or comparator was changed.

## Host Android/platform regression matrix

Each listed module was run in a fresh baseline-interpreter process unless
noted.  All invoked suites passed.

| Contract | Passing suites |
| --- | --- |
| Android render/resource/presentation | `test_android_render_optimization`, `test_android_performance_round3`, `test_android_performance_instrumentation`, `test_android_title_option_cache`, `test_info_menu_render_optimization`, `test_title_smoke_seed` |
| Audio / Sound Room | `test_android_soundroom_round2`, `test_sound_platform_policy` |
| P4 tilemap atomicity | `test_tilemap_change_job`, `test_atomic_restore`, `test_state_machine_lifecycle` |
| P5 load/restart | `test_canonical_load`, `test_restart_contract`, `test_project_save_transaction` |
| P6 work budget | `test_work_budget_policy` |
| P7 fast-forward/debugger/profiler | `test_fast_forward_equivalence`, `test_runtime_debugger_parity`, `test_performance_profiler` |
| P8 cache/render | `test_cache_memoization`, title/info/Android render suites above |
| Recovery/project integrity | `test_recovery_trace`, `test_recovery_golden`, `default_ltproj.test_base_project_integrity` |

`app.tests.test_android_restart_game` is not independently importable in this
headless fresh-process invocation: importing `general_states` constructs a
pygame alpha surface before a display is initialized (`pygame.error: cannot
convert without pygame.display initialized`).  This is an invocation/isolation
limit, not an asserted test failure or Android semantic divergence.  Its
covered restart contracts are exercised by the passing canonical-load,
restart-contract, atomic-restore, debugger-parity, S4, and S18 evidence.

## Tilemap / work-budget result

The accepted boundary remains intact.  `tilemap_prepare_budget()` is the sole
Android policy decision; `event_functions.change_tilemap` uses it to choose
either the synchronous desktop path or a `TilemapChangeJob` with immutable
budget configuration.  The job builds pending tilemap/board/boundary off-world.
The Event-local `_android_tilemap_pending` barrier blocks input, movement, and
later Event commands; success publishes once and failure restores before barrier
release.  There is no generic Event wall-clock command budget.

The locked Android budget is unchanged at 4,000,000 ns.  No device was present
to separate pending-build and final synchronous-commit timing.

## Save, load, restart, debugger, and input result

Passing host evidence preserves the accepted single `load_game_data` authority:
Android `SaveLoadJob` worker work is read/unpickle only, while the shared
main-thread transaction hydrates and publishes state once.  SAVE remains current
progress; RESTART remains matching pristine snapshot/restart material.  The
debugger routes through `RuntimeDebuggerController`, preserves requested
difficulty/source selection, and its Android touch consumer lifecycle is covered
by the debugger parity suite.  Fast-forward input edges remain first-substep
only, with matching S16 logical outcome.

No real touch hardware path was available, so this does not prove JNI/raw-touch
delivery on a device.

## Audio and resources

Host Android-policy tests passed for streamed-success and legacy fallback,
Sound Room preview lifecycle, caller-owned music selection, and loading resource
preparation.  This validates backend state/control-flow contracts only.  No
device launch means no packaged-resource check, logcat evidence, or acoustic
observation is available.

## Performance characterization

| Workload | Device data | Result |
| --- | --- | --- |
| Startup/title, map/movement, combat, tilemap change, save/load/restart, fast-forward | No usable device/emulator | Not measured |

There are therefore no median/p95/p99, stall, heap/RSS, or audio-preload
numbers for this current revision.  Existing P4/P8 host measurements remain
host-only structural evidence and are not Android performance claims.  No
policy value, cache capacity, renderer policy, or audio behavior was retuned.

## Commands and final checks

- `adb version`; `adb devices -l`
- Android builder/emulator route and artifact-manifest inspection
- Fresh-process host module matrix listed above
- Trace V1 runner/comparator for S2, S4, S5, S7, S8, S12-S18 as required
- `utilities\\enemy_event_generator\\.python\\python.exe -m compileall -q app` — PASS
- `git diff --check` — PASS before report creation

## Known baseline issues and limits

- No connected Android device/emulator is the release-gate blocker.
- The latest APK is historical and cannot evidence current HEAD.
- Headless isolated `test_android_restart_game` import requires display setup;
  this is reported separately from semantic suite results.
- Existing full-suite Windows native termination and component-registry ordering
  baseline belong to P9-T01 and were not reopened by this task.

## Escalation and disposition

No deterministic logical divergence, partial authoritative state, save-source
conflict, or platform-boundary regression was observed; no escalation was
triggered.  P9-T02 remains **PARTIAL** pending a usable Android target, a
current-provenance artifact built through the supported route, real launch/log
evidence, and device performance characterization.

**Next action: controller review.  Do not begin P9-T03.**
