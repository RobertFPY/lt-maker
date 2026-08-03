# LT Android emulator smoke test

This workflow installs and launches a verified LT Android APK on a local
Android Virtual Device without requiring a physical phone.

The Android 36 Google APIs x86_64 image advertises ARM64 translation, so the
existing `arm64-v8a` APK can be smoke-tested without changing the release ABI.
Emulator timings are not valid measurements of phone startup time, frame rate,
thermal throttling, touch latency, audio latency, or vendor GPU behavior.

## One-time setup

Run from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\utilities\build_tools\android_emulator\setup_emulator.ps1
```

The default AVD is `LT_API36`, using Pixel 6 hardware and:

`system-images;android-36;google_apis;x86_64`

The script is idempotent. Pass `-Recreate` only when the AVD needs to be
replaced.

## Automated smoke test

The default command finds the newest
`*_android_build\lt-android-runtime-arm64-debug.apk` alias:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\utilities\build_tools\android_emulator\run_smoke_test.ps1
```

The alias is intentionally mutable after each successful Android build. For a
release regression, pass `-ApkPath` to an APK inside its immutable timestamped
artifact directory. Every report records the tested APK's SHA-256 and the test
fails if that file changes during installation.

The smoke test:

1. Starts only the named emulator on fixed port 5556 with Quick Boot snapshots
   disabled for deterministic runs.
2. Waits for Android to finish booting.
3. Installs the APK and derives its package ID with `aapt`.
4. Clears logcat and launches the main activity.
5. Waits 20 seconds, takes a screenshot, and checks that the app process lives.
6. Fails on detected Android fatal exceptions, native fatal signals, ANRs for
   the package, or Python tracebacks.
7. Writes `report.json`, `logcat.txt`, `fatal-lines.txt`, and `final.png` below
   an `emulator-tests\<UTC timestamp>` directory beside the APK.
8. Stops an emulator that the script started.

Use `-ShowWindow -KeepEmulator` for an interactive debugging session.

## Optional scripted input

`-InputScript` accepts a JSON array. Supported actions are:

- `wait` with `milliseconds`
- `tap` with `x` and `y`
- `keyevent` with an Android keycode such as `KEYCODE_BACK`
- `screenshot` with `name`

Example:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\utilities\build_tools\android_emulator\run_smoke_test.ps1 `
  -InputScript `
  .\utilities\build_tools\android_emulator\smoke_actions.example.json
```

Because pygame/SDL renders the game as one surface, Android UI Automator
cannot identify LT menu buttons semantically. Coordinate scripts should be
created for a fixed AVD resolution, while deeper deterministic gameplay tests
should use an in-engine test scenario.
