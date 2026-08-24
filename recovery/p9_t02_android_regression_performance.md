# P9-T02 Android regression and performance matrix

## Task result

**PASS after the controller-authorized ESC-02 continuation.**  The earlier
PARTIAL/FAIL results are retained below as historical evidence.  The confirmed
arm64-only-on-x86_64 WSA blocker was repaired at the Android build-policy layer,
a strict x86_64 APK was built and statically verified, and the current artifact
was installed and exercised on WSA through title, chapter start, Event/combat,
tilemap preparation/commit, movement/Wait/FOW, SAVE load, pristine RESTART,
fast-forward, debugger-idle, profiler, and streamed-audio/resource paths.  The
former ELF mismatch/SIGSEGV did not recur.  No gameplay, project, save schema,
Trace V1, golden, or Android runtime-policy constant changed.

## ESC-02 authorized ABI repair and resumed Android matrix (2026-08-10)

### Authorization, prior result, and root cause

The controller accepted the previous stop, confirmed ESC-02, and authorized
GPT-5.6 Sol / high solely to repair the Android ABI build-policy blocker and
resume P9-T02.  P9-T03 remained unauthorized.  Work started at
`0400b8a7021f8863ecd913706e097fc58c539947` on
`recovery/pc-core-semantics`.  The unexpected zero-byte untracked path
`recovery/pc-core-semantics` was preserved without reading, editing, renaming,
deleting, or staging it.

The prior current-build APK packaged only AArch64 native libraries.  WSA's
native process and `/system/bin/ifconfig` are x86_64, so the subprocess inherited
the application's arm64 `libcrypto.so`; the loader reported EM_AARCH64 instead
of EM_X86_64 and the app died with SIGSEGV before project startup.  This was a
strict build-policy/toolchain mismatch, not gameplay divergence.

### ABI source of truth and bounded policy change

| Surface | Before | After |
| --- | --- | --- |
| Toolchain manifest | Default and only accepted ABI `arm64-v8a` | Default remains `arm64-v8a`; supported set is `arm64-v8a`, `x86_64` |
| PowerShell/WSL build route | No requested-ABI input | Explicit `-Arch`; selected ABI reaches preflight and generated Buildozer config |
| Runtime validation | Required configured ABI to equal global arm64 pin | Requires staged selected ABI to be supported and generated config to match it exactly |
| APK verification | Required arm64 directory/advertisement | Requires exactly the selected ABI directory/advertisement and checks every executable `.so` ELF machine |
| Editor | ARM64-only UI/validation | Offers only supported ARM64/x86_64 choices and forwards the selected ABI |
| Publication | arm64-named output | Preserves old arm64 names; uses x86_64 names for x86_64 builds and verifies ABI identity |

`toolchain_manifest.json` remains the upstream default/support policy.  The
effective per-build JSON is authoritative for the requested artifact; generated
Buildozer/Gradle files remain outputs, not policy sources.  Verification stays
strict: extra ABI directories, a wrong advertised ABI, a wrong ELF machine, or
an unknown ABI fails the build.  The only non-ELF `.so` accepted is the exact
python-for-android `libpybundle.so` gzip payload, verified by magic bytes.

Changed files and rationale:

| Files | Rationale |
| --- | --- |
| `toolchain_manifest.json`, `preflight.py`, `validate_runtime.py` | Declare supported ABIs while preserving the ARM64 default; validate selected config through staging |
| `build_runtime.ps1`, `build_runtime.sh` | Carry the explicit ABI through the supported Windows/WSL build path and isolate native-cache identity by ABI |
| `verify_apk.py`, `publish_artifacts.py` | Strictly bind APK contents/ELF machines and published identity to the selected ABI |
| `android_build_config.py`, `android_build_dialog.py` | Validate, expose, and forward the explicit editor ABI choice |
| `test_android_build_config.py`, `test_phase4_pipeline.py` | Cover selection, forwarding, generation, publication, strict ABI directory/machine rejection, and pybundle handling |
| `README.md`, `DECISIONS.md` | Record the selected-ABI source and strict verification contract |
| This report | Preserve ESC-02, build, WSA runtime, parity, and performance evidence |

### x86_64 toolchain and dependency support

The pinned python-for-android checkout (`58d21141`, release lineage
2026.05.09) contains `Archx86_64`; Android NDK r29 provides the x86_64 clang
toolchain/sysroot; the OpenSSL recipe selects `android-x86_64`; and SDL2,
SDL2_image, SDL2_mixer, SDL2_ttf, CPython 3.11.9, pygame-ce, and the remaining
startup native recipes built for the selected architecture.  This is source
build support, not relabeling or verifier suppression.

The first complete x86_64 build exposed one packaging fact: python-for-Android
stores its compressed Python bundle under `libpybundle.so`.  A narrow verifier
rule now accepts only that exact path when its payload begins with gzip magic;
all other `.so` entries must be valid ELF with the requested machine value.

### Current artifact and static APK verification

| Field | Result |
| --- | --- |
| Build route | `build_runtime.ps1` -> WSL `build_runtime.sh` -> Buildozer/python-for-android |
| Project | `Fire Emblem Tales of The Golden Knight.ltproj` |
| Build config | debug, runtime debugger enabled, `arch=x86_64` |
| Build ID | `fire-emblem-tales-of-the-golden-knight-android-0.2.0-20260810T040804Z-026a5385` |
| APK | `fire-emblem-tales-of-the-golden-knight-0.2.0-x86_64-debug.apk` |
| Size / SHA-256 | 232,670,293 bytes / `026a53851b747b85cad5b89be1de65f4dfc9166f2114e60f3ccb6237229b8ff5` |
| Package/version | `org.lextalionis.fire_emblem_tales_of_the_golden_knight`; 0.2.0 / 1026410 |
| APIs/signature | min 26, target 36, APK Signature Scheme v2, development certificate |
| Native ABI directories | exactly `lib/x86_64/` |
| ELF machine | 62 / EM_X86_64 for every executable native `.so` |
| Required samples | EM_X86_64: `libpython3.11.so`, `libcrypto.so`, `libSDL2.so`, `libSDL2_image.so`, `libSDL2_mixer.so`, `libSDL2_ttf.so` |
| Python bundle | exact `lib/x86_64/libpybundle.so`, gzip magic `1f 8b` |
| Repository verifier | PASS; no errors; ABI report `x86_64` |

The first uncached x86_64 build completed in 663 seconds.  After the narrow
pybundle verifier correction, the final cache-backed build completed in 87.5
seconds.  These are host build times, not device frame-time claims.

### WSA install, launch, and former crash result

| Field | Evidence |
| --- | --- |
| ADB | 1.0.41 / 37.0.0-14910828; `127.0.0.1:58526 device` |
| Target | Subsystem for Android(TM), Android 13 / API 33 |
| Native ABI/list | `x86_64`; `x86_64,arm64-v8a,x86,armeabi-v7a,armeabi` |
| Install | `adb install -r -t` returned `Success` |
| Installed package | version 0.2.0 / 1026410; `primaryCpuAbi=x86_64`; update time 2026-08-10 11:21:56 |
| Launch | normal `org.lextalionis.android.LtPythonActivity`; COLD, 194 ms ActivityManager launch time |
| Startup | Python 3.11 and pygame initialized; metadata/project/resources loaded; DB deserialized (101.24 ms); `Engine Init Completed`; title state reached |
| Prior crash scan | no EM_AARCH64/EM_X86_64 mismatch, wrong-ELF, linker-fatal, SIGSEGV, signal-11, or fatal-exception match |

The process remained alive through the full interactive run.  The former
`/system/bin/ifconfig`/arm64 `libcrypto.so` failure did not reproduce.

### Real-runtime semantic matrix

All inputs below were sent to the real WSA application after focusing its
native window.  Keyboard and raw-touch differences are presentation/input
mapping only; synchronization checks use the resulting logical state.

| Workload | Synchronization-point evidence | Result |
| --- | --- | --- |
| Title/new chapter | Title -> mode/save-slot -> level resources/DB -> chapter events -> coherent `free` stack | PASS |
| Event/combat | Intro Event executed consecutive commands; scripted combat completed through accepted combat render/lifecycle scopes and returned to Event | PASS |
| Tilemap | Pending `CREATE_TILEMAP`/`BUILD_BOARD` work spanned profiler scopes; final published world was matched `tilemap=Prologue`, board/regions/29 units; later command did not run through the pending barrier | PASS |
| Movement/Wait/FOW | One SELECT entered move; RIGHT+SELECT committed movement; one Wait returned to `free`; action log recorded Camus movement to `(47,8)` and `UpdateFogOfWar` once | PASS |
| Current SAVE | Save snapshot 5.6 ms, worker I/O 8.8 ms; distinct `FETOGK-0.p` (114,086 bytes) and pristine `FETOGK-restart0.p` (37,738 bytes) were persisted | PASS |
| Current SAVE load | Android `in_chapter_load_job` read/unpickled, then one main-thread restore transaction (230.0 ms; 286.0 ms containing frame) published coherent `free`, 29 units/14 on-map, Prologue/4 regions; progressed `(47,8)` Wait/FOW state returned | PASS |
| Pristine RESTART | Real UI: Restart Game -> title -> Restart Level. `title_load_job` read/unpickled the restart slot; one 288.0 ms restore transaction (290.6 ms frame) entered deterministic chapter-start handling. Progressed `(47,8)` state did not resume; pristine sequence showed Camus at `(49,5)` before opening script mutation | PASS |
| Phase | Restart rebuilt chapter-start status-upkeep/phase-change/Event sequence before control | PASS |
| Fast-forward/input | Raw-touch hold produced `ff_requested=3`, `ff_updates=3`, one draw/present. `player_choice` and Android debugger reduced to one update, so no duplicate confirmation/input opportunity occurred | PASS |
| Debugger | Android drawer opened one `android_debugger` state over `free`; shared-controller observer path left units/tilemap/regions unchanged; close returned cleanly | PASS |
| Profiler | Enabled observer recorded main-thread scopes and logical metadata without becoming a scheduler; worker/load/tilemap sections did not publish gameplay. Disabled/observer equivalence remains covered by accepted host S17 and P7 tests | PASS |

No Android-only gameplay mutation path, partial GameState publication, changed
SAVE/RESTART source, action/Event/RNG ordering divergence, or generic Event
wall-clock budget was observed.  The exact immutable PC/host Trace V1 matrix
from the accepted P9-T02 runs remains carry-forward evidence because gameplay,
tests, Trace contracts, project data, and runtime policy values did not change.
The device synchronization points match those accepted transaction shapes;
device profiler logs are not misrepresented as a second Trace V1 serializer.

### Audio/resource evidence

Title and chapter transitions loaded the selected music resources through the
existing Android sound subsystem.  Profiler/log evidence includes
`music_stream_load`, `GlobalMusicState.PLAYING`, song object/cache creation,
and Android `AudioTrack` frame delivery/stop records.  Resource preparation
completed before chapter publication and did not mutate gameplay from worker
threads.  No fallback duplication, missing packaged resource, or ordering
change was observed.  This validates backend/logical playback state only; no
claim of acoustic quality or audibility is made.

### Device performance characterization

This is an x86_64 WSA debug/instrumented artifact, not physical-device FPS.
No knobs were changed: tilemap pending budget remains 4,000,000 ns; cache,
renderer, audio, and fast-forward policies are unchanged.

| Workload | Samples / distribution | Major work/stall |
| --- | --- | --- |
| Startup/title steady state | repeated 300-frame windows; median cadence approximately 16.0 ms, p95 16.7-16.8 ms, maxima 16.9-17.7 ms (one transition window 21.0 ms) | DB load 101.24 ms before title; title music stream load p95 3.3-3.6 ms |
| Map idle/movement | repeated 300-frame windows; average/median cadence approximately 16.0 ms, p95 16.6-16.8 ms, maxima 16.9-17.7 ms | map draw approximately 6-8 ms; input/update sub-millisecond in steady state |
| Combat | representative scripted combat window; approximately 16.0 ms average, p95 16.6 ms, max 37.4 ms | presentation/lifecycle scopes only; logical combat completed |
| Tilemap/Event skip | bounded transition | 154.9 ms worst observed transition frame; off-world create/build scopes visible before one coherent final world |
| Current SAVE | one operation | snapshot 5.6 ms; worker I/O 8.8 ms |
| Current SAVE load | one operation | restore transaction 230.0 ms; containing frame 286.0 ms |
| Pristine RESTART | one operation plus chapter-start events | restore transaction 288.0 ms; containing frame 290.6 ms; later chapter-start Event frame 555.9 ms, dominated by event chain/turn-change and resource/song work |
| Fast-forward | 300-frame representative map windows | approximately 16.0 ms cadence, p95 about 16.8 ms; three logical updates with one draw/present while held |
| Memory after restart Event | one `dumpsys meminfo` sample | TOTAL PSS 307,387 KB; TOTAL RSS 407,780 KB; native heap PSS 181,288 KB; no swap |

The profiler emits average and p95 over 300-frame windows, not raw p99; maxima
above are the available worst meaningful stalls.  WSA host scheduling and debug
instrumentation limit transferability to physical Android hardware.  No
historical x86_64 WSA baseline exists, so this is characterization rather than
an FPS-regression claim.

### Tests, checks, and exact command families

- `utilities\\enemy_event_generator\\.python\\python.exe -m unittest app.tests.test_android_build_config -v`: 16 passed.
- `utilities\\enemy_event_generator\\.python\\python.exe utilities/build_tools/android_runtime/test_phase4_pipeline.py`: 29 passed.
- PowerShell parser validation for `build_runtime.ps1`: PASS.
- WSL `bash -n utilities/build_tools/android_runtime/build_runtime.sh`: PASS.
- `build_runtime.ps1 ... -Arch x86_64 -EnableRuntimeDebugger`: final build and strict verifier PASS.
- Independent ZIP/ELF inspection: exactly x86_64; all executable `.so` machine 62; pybundle gzip only.
- `adb devices -l`, `getprop`, `install -r -t`, `am start -W`, `dumpsys package`, `pidof`, `run-as` save inventory, `dumpsys meminfo`, bounded `logcat` capture/crash scan: PASS as described above.
- Real UI input used Android key/touch injection only after native WSA window focus: title/new game, Event skip/choice, movement/Wait, Save/Load, Restart Game/title Restart Level, debugger open/close, and fast-forward hold.
- `python -m compileall -q app utilities/build_tools/android_runtime`, targeted tests, script syntax checks, strict APK verification, `git diff --check`, `git show --check`, and final status are the final delivery gates.

No generated APK/build artifact is committed.  No project/asset, gameplay,
save schema, Trace/golden/comparator/manifest, 4 ms work-budget, cache,
renderer, audio, or runtime scheduling policy was modified.  No further
escalation trigger was encountered after the authorized ESC-02 repair.

## Initial P9-T02 identity and scope (historical)

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

## Android-on-WSA ABI gate revalidation (2026-08-10)

**TASK RESULT: PARTIAL — ANDROID ABI BUILD BLOCKER.**  This revalidation did
not rebuild or install another known-incompatible arm64-only artifact.  The
authorized WSA target is connected, but its native execution ABI is x86_64 and
the currently authorized repository pipeline is deliberately arm64-only.
The earlier current-build launch failure is therefore confirmed as an ABI gate,
not valid engine-startup or gameplay evidence.

```text
ANDROID ABI BUILD BLOCKER

WSA NATIVE ABI: x86_64 (uname -m; ro.product.cpu.abi)
WSA ABI LIST: x86_64,arm64-v8a,x86,armeabi-v7a,armeabi
CURRENT BUILD ABI: arm64-v8a only
SUPPORTED BUILD ABIS: arm64-v8a only
REQUIRED BUILD-CONFIG CHANGE: add and validate x86_64 or a verified multi-ABI
  Python-for-Android/Buildozer artifact, including native recipe, verifier,
  signing/publishing, and editor validation support.
FILES THAT WOULD NEED TO CHANGE: at minimum
  utilities/build_tools/android_runtime/toolchain_manifest.json,
  buildozer.spec, preflight.py, configure_build.py, verify_apk.py,
  validate_runtime.py, publish_artifacts.py, and Android editor build-config
  validation/UI; recipe/toolchain compatibility also requires proof.
ACTION: controller authorization required before build-policy modification.
```

### Concrete WSA and APK evidence

| Field | Result |
| --- | --- |
| ADB serial/state | `127.0.0.1:58526`, `device` (authorized) |
| WSA product/model/device | `windows_x86_64` / `Subsystem for Android(TM)` / `windows_x86_64` |
| Android | 13 / API 33 |
| WSA ABI properties | `ro.product.cpu.abi=x86_64`; `ro.product.cpu.abilist64=x86_64,arm64-v8a`; `ro.dalvik.vm.isa.x86_64=x86_64`; no arm64 VM ISA value |
| Pipeline enforcement | `android.archs = arm64-v8a`; toolchain manifest is arm64; preflight/editor validation reject any non-arm64 configuration; verifier requires exactly `{arm64-v8a}` |
| Latest APK library directories | `lib/arm64-v8a/` only |
| Critical packaged libraries | arm64 `libpython3.11.so`, `libcrypto.so`, `libSDL2*.so`; no `lib/x86_64/` directory |
| Previous launch chain | `_posixsubprocess` invoked `/system/bin/ifconfig` on the x86_64 WSA process, which attempted to load app `lib/arm64/libcrypto.so` and terminated with SIGSEGV |

No source/test/build-policy/project/Trace change was made.  The final working
tree also contains an unexpected zero-byte untracked path
`recovery/pc-core-semantics`; it was not created as an authorized evidence
artifact and was deliberately not deleted by this task.  Host/Trace evidence
from `392a8f5f` and `81670bb6` remains carry-forward evidence only.  Current
WSA install, engine startup, title/window, logical-runtime, audio/resource, and
performance evidence cannot be claimed until an ABI-compatible supported build
exists.  **Stop for controller authorization; do not begin P9-T03.**

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
