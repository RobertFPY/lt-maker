# LT Android runtime - phase 4

This directory is the Android APK builder for Lex Talionis projects. It
packages a read-only `.ltproj` snapshot with the proven phase-3 pygame-ce/SDL2
runtime, builds on the Linux filesystem under WSL, verifies the result, and
publishes an immutable artifact batch. Phase 5 exposes the same pipeline in LT
Maker while retaining this command-line entry point.

## Phase 4 pipeline

1. Resolve and validate the requested build identity.
2. Run project preflight and write a machine-readable JSON report.
3. Fingerprint the project snapshot, packaged runtime inputs, build identity,
   and the pinned native toolchain separately.
4. Reuse one Buildozer/python-for-android workspace per native-toolchain key
   under `~/.cache/lt-maker/android-runtime/n/`. Its short directory name keeps
   python-for-android's generated executable shebangs below Linux's path limit.
   A per-workspace `flock` serializes access before staging or p4a mutation.
   Project and version edits produce a fresh APK but reuse compiled native
   recipes.
5. Copy a filtered project snapshot into Linux staging. The source `.ltproj`
   is re-hashed after the copy; a concurrent source change aborts the build.
6. Materialize `buildozer.spec`, then run Buildozer/python-for-android with the
   SDL2 bootstrap and the custom pygame-ce 2.3.2 recipe.
7. Verify package ID, version name/code, min/target API, ARM64-only native
   libraries, v2 signature, and the packaged phase-4 runtime/preflight
   manifests. The runtime and packaged preflight source digests must match.
8. Publish APK, SHA-256, preflight, verification report, effective config, and
   complete build log as one atomic artifact directory. Previous immutable
   artifact directories are never removed.

`toolchain_manifest.json` is the authoritative pin set: CPython 3.11.9,
pygame-ce 2.3.2, python-for-android 2026.05.09, API 36, minimum API 26, NDK 29,
and `arm64-v8a` debug APK.

## Build from LT Maker (phase 5)

Save or open a non-default project, then choose:

`File -> Build Android APK...`

The dialog provides package ID, app name, version name/code, optional PNG
icon, ABI, build mode, output directory, and WSL distro fields. It:

- checks PowerShell, WSL distro, Buildozer, Java, Python, and archive tools;
- forces a non-chunked project save and reads the saved `metadata.json`;
- rejects fatal validation errors before starting the build;
- streams build output without blocking the editor;
- shows milestone progress and final APK/build-log paths;
- permits cancellation and opening the result/log from the dialog.

The tracked `<project>.ltproj/android-release.json` is the canonical package
identity for command-line and clean-checkout builds. The editor loads it when
its local `<project>.ltproj/build/android.json` is absent; that local file can
override it for output locations and in-progress work. Package ID changes
display a warning because Android will treat the result as a different app and
will not upgrade the old app's persistent player data. Keystores and passwords
are not represented in either project configuration.

The current pipeline supports `arm64-v8a` Debug signing and native-optimized
Release builds signed with the established development certificate. The latter
is for private installation and testing only; it is not a Play Store release.

## Preflight

Preflight checks:

- package ID, app name, version name/code, ABI, mode, and optional icon PNG;
- saved fatal-error and serialization metadata;
- case-insensitive filename collisions;
- missing or wrong-case catalog resources;
- OGG extension and `OggS` headers for music/SFX;
- syntax and desktop-only imports in custom components;
- project/file counts, size, source digest, and free space;
- at least 8 GiB free on the Linux build-cache filesystem.

Run it independently in WSL:

```bash
cd /mnt/e/FE/lt-maker/utilities/build_tools/android_runtime
python3 preflight.py --project /mnt/e/FE/lt-maker/default.ltproj \
  --report /tmp/lt-android-preflight.json
```

No source file is edited by preflight or staging. `.pyc`, caches, tests,
backups, and editor temporary files are excluded from the snapshot.
Unlisted portrait-import leftovers whose filenames exceed p4a's USTAR limit
are also omitted from the APK snapshot and recorded in `runtime_manifest.json`;
catalogued portrait resources are never silently omitted.

## Build from PowerShell

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\utilities\build_tools\android_runtime\build_runtime.ps1 `
  -Project "default"
```

The project may be a repository project name or an absolute `.ltproj` path.
Optional phase-4 CLI identity overrides:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\utilities\build_tools\android_runtime\build_runtime.ps1 `
  -Project "E:\Games\MyGame.ltproj" `
  -OutputDirectory "E:\Builds\MyGame" `
  -PackageId "com.example.mygame" `
  -AppName "My Game" `
  -VersionName "1.0.0" `
  -VersionCode 100 `
  -Icon "E:\Games\MyGameIcon.png"
```

The build dialog supports `debug` and native-optimized `release` APK modes for
`arm64-v8a`. Release output is development-signed after Buildozer packages it,
then verified against the existing development certificate before publication.
No keystore credentials are stored in project Android JSON. AAB, production
keystores, and Play delivery remain out of scope.
or later.

## Artifact layout

Each successful build creates a new directory such as:

```text
artifacts/
  mygame-android-1.0.0-20260728T170000Z-a1b2c3d4/
    mygame-1.0.0-arm64-debug.apk
    mygame-1.0.0-arm64-debug.apk.sha256
    android-build-config.json
    apk-verification.json
    build-manifest.json
    preflight.json
    build.log
```

The compatibility aliases `lt-android-runtime-arm64-debug.apk` and
`.apk.sha256` are replaced atomically only after the immutable batch passes all
checks.

## Runtime controls retained from phase 3

- D-pad: cursor/menu movement.
- `A`: LT `SELECT`; `B`: LT `BACK`.
- `X`: LT `INFO`; `Y`: LT `AUX`.
- `START`: LT `START`.
- `>>`: hold LT `FAST_FORWARD` (Space by default).
- Android system Back maps to LT `BACK`.

On Android, `Options` > `Controls` displays `Press DOWN to configure virtual
controls.` instead of the desktop keyboard-binding table. The editor keeps the
gameplay map visible behind its translucent controls. Drag controls anywhere on
the full physical-aspect canvas, including the top edge and black areas beside
the centered 240x160 game. A centered top ruler changes D-pad style, opacity,
the selected control's size, resets the draft, and explicitly saves or cancels;
use `HIDE` to collapse it to a small `SHOW` tab while positioning controls.
The layout is stored in persistent app-private `user_data/saves/android_controls.json`.
The first APK upgrade migrates legacy `app/saves` to that directory before
python-for-android replaces its runtime payload. Multi-touch
ownership, SDL-finger reconciliation, opposite-direction suppression,
lifecycle release, accelerometer joystick isolation, and hardware scaling
remain enabled.

All player-owned files use the same persistent directory: saves, `config.ini`,
achievements, persistent records, suspend/restart/preload data, and Android
control settings. The desktop fallback remains `./saves`; Android sets
`LT_USER_DATA_DIR` to `<files>/user_data`. Installing over the same package and
signer preserves this directory; uninstalling the app or changing either
identity follows Android's normal data removal rules.

## Device gate

Install the newest verified alias:

```powershell
adb install -r `
  .\utilities\build_tools\android_runtime\artifacts\lt-android-runtime-arm64-debug.apk
adb logcat -c
adb logcat -s python:D SDL:D AndroidRuntime:E
```

Phase 4 exits when a clean build emits a passing preflight report, passing APK
verification report, signed ARM64 APK, SHA-256, and complete build log without
mutating the source project. Full gameplay/device acceptance remains the
project-level release gate and should be repeated for Golden Knight before
distribution.
