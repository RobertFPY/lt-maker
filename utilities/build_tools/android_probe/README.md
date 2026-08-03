# LT Android pygame-ce feasibility probe

This is the implementation of phases 0 and 1 only. It deliberately does not
modify the LT engine or build a `.ltproj` yet.

The probe exercises the native/runtime boundaries which must work before an LT
Android port is justified: SDL display and blending, PixelArray, fonts, PNG,
OGG mixer playback, multi-touch, lifecycle events, dynamic imports, JSON and
app-private persistence.

## Host requirements

Buildozer requires Linux. On Windows, use WSL2 with Ubuntu and build inside the
WSL filesystem. `build_probe.sh` copies this directory into a content-addressed
folder below the WSL cache before running Buildozer; it does not build under
`/mnt/e`.

Recommended Ubuntu 24.04 prerequisites:

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
  python3-virtualenv autoconf libtool pkg-config zlib1g-dev \
  libncurses5-dev libncursesw5-dev libtinfo6 cmake libffi-dev \
  libssl-dev automake autopoint gettext

python3 -m venv ~/.venvs/lt-android-probe
source ~/.venvs/lt-android-probe/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install buildozer==1.6.0 cython==0.29.37 \
  python-for-android==2026.5.9
```

The first build downloads the Android SDK, NDK, Gradle dependencies, CPython,
SDL2 and pygame-ce sources. Accept the Android SDK licenses when prompted.

## Static validation

From this directory:

```bash
python3 validate_probe.py
```

Expected output:

```text
ANDROID_PROBE_STATIC_OK
```

## Build on Windows through WSL2

After the WSL virtual environment above has been created, run from PowerShell:

```powershell
.\build_probe.ps1
```

The script automatically uses `~/.venvs/lt-android-probe` inside WSL when it
exists, so the virtual environment does not need to be activated in the
PowerShell session.

The resulting APK and SHA-256 file are placed under `artifacts/`.

## Device verification

Install and capture logs with Android platform-tools:

```powershell
adb install -r .\artifacts\lt-android-probe-arm64-debug.apk
adb logcat -c
adb logcat -s python:D SDL:D AndroidRuntime:E
```

On the probe screen:

1. Confirm startup checks show PASS, except checks which require interaction.
2. Touch with two fingers simultaneously.
3. Send the app to the background and return to it.
4. Exit with Android Back, force-stop, and launch it again.
5. Confirm `previous_run_persisted` becomes PASS and logcat contains no Python
   traceback or native crash.

The report is written to `lt_android_probe_report.json` in app-private storage
and every update is also printed with the `LT_ANDROID_PROBE` prefix.
