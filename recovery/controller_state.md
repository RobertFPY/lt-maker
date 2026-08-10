# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, task definitions, and global escalation rules.

## Current authorization

- Current phase: **Phase 9 — Full validation and release candidate**
- Phases 1–8: **ACCEPTED**
- P9-T01 full PC regression matrix: **ACCEPTED** at `50e7339986d3eff2998d49000c3b61437949e358`
- P9-T02 full Android regression/performance matrix: **NOT ACCEPTED**
  - host/Trace PARTIAL evidence: `392a8f5fb260a8b84ff86fc767c1b2e3136f1968`, `81670bb6ca194217e78a652ac7e57e6e42387063`;
  - real-target evidence-only attempt: `f3b5330a33fbde920a8b3619042441958b491392`;
  - current WSA ABI/runtime failure evidence: `23f31e9e62e02754fbe62f48b9f1b75c6fdad634`.
- Active task: **P9-T02-R3 only — Android ABI/runtime root-cause diagnosis**
- Authorized model: **GPT-5.6 Sol / high**
- Authorization basis: **ESC-02 nonlocal root cause from P9-T02 Terra/medium**
- Further escalation: **NOT PRE-AUTHORIZED**
- P9-T03/P9-T04: **UNAUTHORIZED**
- Expected production/test/build-policy changes: **NONE — diagnosis/evidence only**
- Allowed evidence change: `recovery/p9_t02_android_regression_performance.md` and optional `recovery/p9_t02_r3_abi_runtime_diagnosis.md`
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project data/assets: **UNAUTHORIZED**
- Merge to `master`: **UNAUTHORIZED**
- Controller gate after R3: **YES — STOP FOR CONTROLLER REVIEW**

## P9-T02 ESC-02 review record

The controller accepts `23f31e9e62e02754fbe62f48b9f1b75c6fdad634` as valid failure/diagnostic evidence, but does **not** accept P9-T02.

Accepted facts:

- ancestry from controller `d8388ee30037c71f33ec862666388b2e5692a469` is evidence-only; the intervening executor commits change only `recovery/p9_t02_android_regression_performance.md`;
- the real target was Windows Subsystem for Android, Android 13/API 33, device/product `windows_x86_64`, advertising ABI list including `x86_64` and `arm64-v8a`;
- a current-provenance APK was built through the repository WSL/Buildozer pipeline from clean source; preflight, package metadata, native-library inventory and signature verification passed;
- the APK is ARM64-only by the repository's current build contract (`android.archs = arm64-v8a`; verification expects only `arm64-v8a` native libraries);
- install succeeded and the launcher Activity returned `Status: ok`;
- Python-for-Android/pygame initialized, then the process died before project selection, metadata validation, `RESOURCES.load`, `DB.load`, title state or gameplay startup;
- decisive device evidence shows `/system/bin/ifconfig` attempting to load the packaged ARM64 `libcrypto.so` while the system executable is x86_64, producing an ELF machine mismatch and SIGSEGV near `_posixsubprocess`;
- therefore no device gameplay-parity, audio/resource or performance characterization can be accepted from that run;
- no production source, tests, project data/assets, Trace/goldens, cache/audio/work-budget policy or build configuration changed;
- host Android/platform suites and immutable Trace V1 evidence remain valid carry-forward while source/test/build-policy behavior is unchanged.

The current evidence does **not** yet establish that the current APK is generically broken on a native ARM64 Android target. It establishes a mixed-ABI failure on an x86_64 WSA system running the repository's intentionally ARM64-only artifact. The root owner of the `/system/bin/ifconfig` subprocess and linker environment must be identified before any repair is designed.

## Locked contracts during R3

1. One shared gameplay core; no Android gameplay fork.
2. No observable partial authoritative gameplay state.
3. Combat/action/Event/RNG/hook/cleanup ordering remains locked.
4. Canonical save/load/restart remains one authoritative transaction; SAVE != pristine RESTART.
5. Fast-forward changes time/presentation only, not outcomes/input-edge semantics.
6. Debugger/profiler remain observers absent explicit commands.
7. No Event wall-clock command scheduler may return.
8. Android work budgeting remains limited to accepted off-world tilemap preparation; `4_000_000 ns` is not a tuning target.
9. P8 cache decisions remain locked (`GC-REGION` not certified; battle source-frame cache rejected; title smoke keep-platform; styled-text deferred).
10. Trace/goldens and project content/assets remain protected.
11. Do not infer generic Android failure from WSA mixed-ABI evidence without target/runtime ownership proof.

---

# P9-T02-R3 — Android ABI/runtime root-cause diagnosis

Execute **P9-T02-R3 only** using **GPT-5.6 Sol / high**.

This is the controller-authorized escalation for ESC-02. Do not begin P9-T03. Do not implement a production or packaging fix during R3.

## Goal

Classify the startup failure as one of:

- `WSA-MIXED-ABI-TRANSLATION-LIMITATION`
- `CURRENT-APK/P4A-PACKAGING-DEFECT`
- `REPO-OWNED-ANDROID-RUNTIME-DEFECT`
- `DEPENDENCY/TOOLCHAIN-DEFECT`
- `UNRESOLVED`

Do not collapse these categories merely because the observed linker error contains an app-library path.

## A. Freeze provenance

Before diagnosis:

- read `AGENTS.md`, `AGENTS.override.md`, entire `plan.md`, this file and the P9-T02 report;
- verify branch/HEAD/model/effort and print the mandatory pre-task report;
- record exact WSA properties (`ro.product.*`, API, ABI lists), package `primaryCpuAbi`/`nativeLibraryDir`, artifact SHA-256 and build manifest/source digest;
- preserve the current APK and logs read-only for diagnosis.

## B. Trace `/system/bin/ifconfig` ownership

Determine exactly what launches `/system/bin/ifconfig` before project startup.

Search/inspect, in order:

1. repository Python/Java/native startup code;
2. packaged project/runtime Python archive;
3. Python 3.11 stdlib and `_posixsubprocess` caller chain;
4. python-for-android SDL2 bootstrap and pinned p4a commit;
5. local p4a recipes / packaged dependencies.

Required output:

```text
IFCONFIG CALLER:
CALL CHAIN:
OWNER: REPO | PYTHON-STDLIB | P4A/BOOTSTRAP | DEPENDENCY | UNKNOWN
WHY IT RUNS BEFORE PROJECT LOAD:
```

A native stack containing `_posixsubprocess` is not by itself proof that `_posixsubprocess` initiated the command; identify the Python/Java caller if possible.

## C. ABI/linker diagnosis

Use read-only tooling such as `aapt`, `apkanalyzer`, `unzip`, `readelf`/`llvm-readelf`, `dumpsys package`, `getprop`, logcat/tombstone and packaged manifests.

Establish:

- ELF machine for relevant APK native libraries, especially `libcrypto.so`, Python and `_posixsubprocess`;
- ELF machine for `/system/bin/ifconfig` on WSA;
- process architecture from tombstone/runtime;
- package primary ABI/native library path;
- whether app linker environment (`LD_LIBRARY_PATH` or equivalent p4a/bootstrap namespace/environment) is inherited by the child `exec`;
- why the child resolves app `libcrypto.so` instead of the system-compatible dependency;
- whether this behavior is specific to WSA ARM translation or would occur on native ARM64 Android.

Do not mutate `LD_LIBRARY_PATH`, replace system binaries or delete packaged libraries as an accepted workaround during diagnosis.

## D. Build-contract inspection

Inspect current repository build policy and dependency constraints:

- `utilities/build_tools/android_runtime/buildozer.spec`;
- project Android config used for the Golden Knight build;
- `configure_build.py`, preflight/APK verification policy;
- p4a pin/bootstrap/local recipes;
- any pass-through/prebuilt dependency that constrains `arm64-v8a`.

Record why the artifact is ARM64-only and whether x86_64 is an intended/supported repository target today.

Do not change ABI list or build recipes in R3.

## E. Target A/B test

Strongly prefer an authorized **native ARM64 Android device/emulator** for one bounded A/B startup test using the same provenance-valid ARM64 APK.

If native ARM64 reaches project/resource/DB/title startup while WSA fails at the mixed-ABI child exec, classify the WSA failure as `WSA-MIXED-ABI-TRANSLATION-LIMITATION` unless contrary evidence exists.

If native ARM64 reproduces the same pre-project failure, classify toward packaging/runtime/toolchain defect and stop with evidence.

If no native ARM64 target is available, do not assert generic Android packaging failure; leave target-general classification `UNRESOLVED` if static/runtime evidence cannot prove it.

## F. Fix-design boundary

Production/build fixes remain unauthorized.

If diagnosis finds:

- a narrow repo-owned pre-project subprocess call with a clearly platform-safe replacement: document the proposed minimal fix and STOP for controller approval;
- a p4a/bootstrap/linker-environment defect: document the smallest upstream/local recipe/bootstrap remediation options and STOP;
- x86_64/multi-ABI support would require new dependency/toolchain architecture: report `ESC-09` and STOP;
- WSA is simply outside the currently supported native ARM64 target contract: document the support limitation and what native ARM64 evidence is still required for P9-T02 acceptance.

Do not implement speculative fixes, environment hacks or gameplay changes.

## Carry-forward evidence

Host Android/platform suites and immutable Trace V1 results from earlier accepted P9-T02 evidence may be carried forward because no source/test/build-policy behavior changed.

R3 should run only diagnostics and bounded sanity checks needed for the root-cause classification, plus `compileall`, `git diff --check`, `git show --check`, final clean status.

## Report

TASK RESULT: PASS-DIAGNOSIS | PARTIAL | FAIL
MODEL/EFFORT
BRANCH / START HEAD
FILES CHANGED
ARTIFACT/DEVICE PROVENANCE
WSA ABI FACTS
APK ABI FACTS
IFCONFIG CALLER
CALL CHAIN / OWNER
LINKER ENVIRONMENT FINDING
ROOT-CAUSE CLASSIFICATION
NATIVE ARM64 A/B RESULT
TARGET SUPPORT MATRIX
PROPOSED REMEDIATION OPTIONS
IMPLEMENTATION AUTHORIZED: NO
HOST/TRACE CARRY-FORWARD BASIS
COMMANDS RUN
NEW REGRESSIONS
ESCALATION/STOP TRIGGERS
COMMIT SHA
WORKING TREE STATUS
NEXT ACTION: CONTROLLER REVIEW

STOP FOR CONTROLLER REVIEW. Do not begin P9-T03.
