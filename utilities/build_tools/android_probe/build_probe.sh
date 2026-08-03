#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-${SOURCE_DIR}/artifacts}"
OGG_FIXTURE="${SOURCE_DIR}/../../../default.ltproj/resources/sfx/Silence.ogg"
if [[ ! -f "${OGG_FIXTURE}" ]]; then
    echo "Missing LT OGG fixture: ${OGG_FIXTURE}" >&2
    exit 2
fi
export LT_ANDROID_PROBE_OGG="${OGG_FIXTURE}"

PROBE_VENV="${HOME}/.venvs/lt-android-probe"
if [[ -x "${PROBE_VENV}/bin/buildozer" ]]; then
    export PATH="${PROBE_VENV}/bin:${PATH}"
elif [[ -x "${HOME}/.local/bin/buildozer" ]]; then
    export PATH="${HOME}/.local/bin:${PATH}"
fi

if command -v buildozer >/dev/null 2>&1; then
    BUILDOZER_LAUNCHER="$(command -v buildozer)"
    BUILDOZER_PYTHON="$(head -n 1 "${BUILDOZER_LAUNCHER}" | sed 's/^#!//')"
    if [[ -x "${BUILDOZER_PYTHON}" ]]; then
        BUILDOZER_VENV="$(dirname "$(dirname "${BUILDOZER_PYTHON}")")"
        export VIRTUAL_ENV="${BUILDOZER_VENV}"
        export PATH="${BUILDOZER_VENV}/bin:${PATH}"
    fi
fi

for command_name in python3 buildozer java javac sha256sum tar; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "Missing prerequisite: ${command_name}" >&2
        echo "Follow README.md before running the probe build." >&2
        exit 2
    fi
done

CACHE_BASE="${XDG_CACHE_HOME:-${HOME}/.cache}/lt-maker/android-probe"
SOURCE_HASH="$(
    find "${SOURCE_DIR}" -type f \
        ! -path '*/.buildozer/*' \
        ! -path '*/artifacts/*' \
        ! -path '*/staging/*' \
        ! -path '*/__pycache__/*' \
        ! -name '*.pyc' \
        -print0 \
    | sort -z \
    | xargs -0 sha256sum \
    | sha256sum \
    | cut -d' ' -f1
)"
WORK_DIR="${CACHE_BASE}/${SOURCE_HASH}"

if [[ ! -d "${WORK_DIR}" ]]; then
    mkdir -p "${WORK_DIR}"
    tar \
        --exclude='.buildozer' \
        --exclude='artifacts' \
        --exclude='staging' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        -C "${SOURCE_DIR}" -cf - . \
    | tar -C "${WORK_DIR}" -xf -
fi

cd "${WORK_DIR}"
python3 validate_probe.py
buildozer -v android debug

APK_PATH="$(find bin -maxdepth 1 -type f -name '*.apk' | sort | tail -n 1)"
if [[ -z "${APK_PATH}" ]]; then
    echo "Build completed without producing an APK under ${WORK_DIR}/bin" >&2
    exit 3
fi

mkdir -p "${OUTPUT_DIR}"
FINAL_APK="${OUTPUT_DIR}/lt-android-probe-arm64-debug.apk"
cp "${APK_PATH}" "${FINAL_APK}"
sha256sum "${FINAL_APK}" > "${FINAL_APK}.sha256"

echo "APK: ${FINAL_APK}"
echo "SHA256: $(cut -d' ' -f1 "${FINAL_APK}.sha256")"
