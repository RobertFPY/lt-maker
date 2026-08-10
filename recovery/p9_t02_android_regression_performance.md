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

## P9-T02-R1 device-gate recheck (2026-08-10)

**Result: PARTIAL, unchanged.**  This continuation was run at
`392a8f5fb260a8b84ff86fc767c1b2e3136f1968`, a direct descendant of controller
commit `a890539c52fddbfa3e5c07602fb356a9ec00c798`.  The intervening commit is
this report's prior PARTIAL evidence only; no production source, tests,
project/assets, Trace fixtures, or Android build policy changed.  The accepted
host-side matrix and immutable trace evidence above are therefore carried
forward rather than mechanically rerun.

### Recheck record

| Required gate | Observation |
| --- | --- |
| Branch / tracked worktree | `recovery/pc-core-semantics`; clean |
| ADB | Android Debug Bridge 1.0.41 / 37.0.0-14910828 |
| `adb devices -l` | No device or emulator attached/authorized |
| Device model / API / ABI | Unavailable: no target |
| Current-provenance APK | Unavailable: no target justifies a new supported build/install run; historical 2026-08-07 artifact remains ineligible |
| Install / real launch / startup logs | Not run: no target |
| Touch/movement/combat/tilemap/save/restart/fast-forward/debugger/profiler runtime observations | Not available without a real target |
| Audio/resource observation | No device log or acoustic observation available |
| Performance characterization | No device samples, frame percentiles, stalls, or memory/RSS data available |

`utilities\\enemy_event_generator\\.python\\python.exe -m compileall -q app`
passed for the unchanged source scope.  No Android knob, including the
4,000,000 ns off-world tilemap budget, was modified.  No deterministic logical
divergence or invariant failure was observed, so no escalation is triggered.

P9-T02 cannot pass until a usable target is connected and a current-provenance
artifact is built, installed, launched, and characterized through the supported
Android route.  **Stop for controller review; do not begin P9-T03.**

## P9-T02-R2 real Android target result (2026-08-10)

**TASK RESULT: FAIL — ESC-02 required.**  A real authorized target was available
and the repository-supported pipeline produced a current-source artifact, but
the installed application deterministically died before project/resource/DB or
title startup.  This is a packaging/runtime ABI failure outside this
validation-only task; no gameplay, Android policy, build configuration, test,
or project-data change was made.

### Target and artifact

| Field | Evidence |
| --- | --- |
| Target | `127.0.0.1:58526`, authorized `device`; Windows Subsystem for Android |
| Device / API | `Subsystem for Android(TM)`, Android 13 / API 33 |
| ABI | `x86_64,arm64-v8a,x86,armeabi-v7a,armeabi` |
| ADB | 1.0.41 / 37.0.0-14910828 |
| Build route | `utilities\\build_tools\\android_runtime\\build_runtime.ps1 -Project "Fire Emblem Tales of The Golden Knight.ltproj"` |
| Build result | PASS: preflight, static validation, packaging, signing, and APK verification |
| Build provenance | current clean recovery HEAD `f3b5330a33fbde920a8b3619042441958b491392`; build ID `fire-emblem-tales-of-the-golden-knight-android-0.2.0-20260810T013837Z-b15b4de6` |
| APK | `fire-emblem-tales-of-the-golden-knight-0.2.0-arm64-debug.apk`; SHA-256 `b15b4de64a1b7e15600405cc854d95fdad87c67094f7a030ac462530c484d9f2` |
| Verification | `arm64-v8a`, min/target API 26/36, v2 signature, launcher `org.lextalionis.android.LtPythonActivity`, documents provider; `errors: []` |

### Install and launch evidence

`adb install -r -t` returned `Success`.  `am start -W` returned `Status: ok`,
`LaunchState: COLD`, and `TotalTime: 211 ms`.  Python-for-Android initialized
and reported `pygame-ce 2.3.2 (SDL 2.30.11, Python 3.11.9)`, then the process
died.  After the bounded 25-second observation there was no package PID and
`dumpsys activity exit-info` recorded signal 11.

The decisive logcat failure is:

```text
CANNOT LINK EXECUTABLE "/system/bin/ifconfig":
.../lib/arm64/libcrypto.so is for EM_AARCH64 (183) instead of EM_X86_64 (62)
Process ... exited due to signal 11 (Segmentation fault)
```

The crashing stack includes `_posixsubprocess.cpython-311.so`, `libpython3.11`,
and the arm64 app libraries.  It occurs before any observed project selection,
metadata validation, `RESOURCES.load`, `DB.load`, title state, gameplay input,
audio transition, or profiler/gameplay checkpoint.

### Consequence and disposition

- PC/Android gameplay synchronization, tilemap, SAVE/RESTART, fast-forward,
  debugger, profiler, and audio/resource runtime evidence cannot be collected:
  the process never reaches those paths.
- No device frame-time, p95/p99, memory/RSS, or runtime audio measurement is
  available; launch duration is not an engine performance result.
- Host-side Android/platform and immutable Trace V1 evidence from the accepted
  392a8f5f/81670bb6 runs remains valid carry-forward evidence because source,
  tests, and policy remain unchanged.
- This is not an immutable Trace V1 divergence.  The observed current-build
  Android startup failure requires source-proven packaging/runtime ABI diagnosis
  outside P9-T02-R2.  **Stop under ESC-02; GPT-5.6 Sol / high controller
  authorization is required before any repair.**

No P9-T03 work was started.

## P9-T02-R2 real-target attempt (2026-08-10)

**Result: PARTIAL.**  This run began at controller HEAD
`d8388ee30037c71f33ec862666388b2e5692a469`.  The only intervening changes
since the accepted host/Trace evidence were controller documentation and this
evidence report, so the Phase 1--8 host and frozen Trace V1 results above remain
carry-forward evidence.

### Target and current artifact

| Item | Evidence |
| --- | --- |
| Initial ADB target | `127.0.0.1:58526 device product:windows_x86_64 model:Subsystem_for_Android_TM_ device:windows_x86_64` |
| Device details while connected | Subsystem for Android(TM); Android 13 / API 33; ABI list `x86_64,arm64-v8a,x86,armeabi-v7a,armeabi` |
| ADB | 1.0.41 / 37.0.0-14910828 |
| Build route | Repository `utilities\\build_tools\\android_runtime\\build_runtime.ps1`, WSL pipeline, Golden Knight project, debug + runtime debugger |
| Build preflight | PASS: 2,527 files, 243,045,060 bytes |
| Current artifact | `fire-emblem-tales-of-the-golden-knight-android-0.2.0-20260810T012939Z-000f44aa` |
| APK provenance | `arm64-v8a`, package `org.lextalionis.fire_emblem_tales_of_the_golden_knight`, version 0.2.0 / code 1026410, source digest `83d286840a8f12e2a03e7c7306f3dbc56ea6a29c3e231efb68847777ce1f2324` |
| APK verification | PASS: phase-4 manifest, signature v2, migration activity, DocumentsProvider, API 26/36, package metadata all verified |
| APK SHA-256 | `000f44aa4611a37b7fb23cdd9f4f0a8644a4a751c85d76bb5d8570f38d43124c` |

### Device-gate result

The target disappeared between the initial authorized-device probe and the
supported `adb install -r -t` invocation.  The install command returned:

```text
adb.exe: device '127.0.0.1:58526' not found
```

Two subsequent bounded `adb devices -l` probes returned no devices.  Therefore
no APK was installed, no activity was launched, and no project/resource/DB/title
log, touch/movement/combat/tilemap/save/restart/fast-forward/debugger/profiler,
audio/resource, or device performance observation can be claimed.  This is an
environment/device-availability limit, not an APK startup or semantic failure.

No current artifact may be represented as device-tested until the WSA target
remains connected through install and launch.  The locked 4,000,000 ns budget,
cache capacities, renderer/audio policies, gameplay source, tests, project data
and Trace fixtures remain unchanged.  No divergence was observed and no
escalation is triggered.

**R2 next action: controller review.  Reattempt only after an authorized target
is stable; do not begin P9-T03.**
