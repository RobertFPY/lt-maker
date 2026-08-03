# LT Android feasibility decisions

This directory implements only phases 0 and 1 of the Android work. It is an
isolated probe and does not package an LT project yet.

## Phase 0 decisions

- Output: debug-signed APK for direct installation.
- CPU architecture: `arm64-v8a` only.
- Display: landscape, fullscreen.
- Android target API: 36.
- Tentative minimum API: 26, subject to the device matrix after the probe runs.
- Python: CPython and hostpython 3.11.9, pinned to the same version as required
  by python-for-android.
- Rendering/audio: python-for-android SDL2 bootstrap with pygame-ce 2.3.2.
- Storage: app-private storage only; no external-storage permission.
- Distribution to Google Play, AAB, Play Asset Delivery, release signing, and
  LT Maker editor integration are explicitly out of scope.

## Phase 1 exit gate

Do not begin the LT runtime port until an arm64 device has demonstrated all of
the following from one APK build:

- SDL display, Surface conversion, PixelArray, alpha and blend operations;
- bundled PNG and OGG loading, font rendering and mixer playback;
- finger events, including two simultaneous touch IDs;
- Android background/foreground lifecycle events;
- bundled JSON loading and dynamic import from a Python source file;
- a persisted report in app-private storage which survives force-stop/relaunch;
- no Python exception or native crash in logcat.
