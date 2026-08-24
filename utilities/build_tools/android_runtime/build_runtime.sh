#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SOURCE_DIR}/../../.." && pwd)"
OUTPUT_DIR="${1:-${SOURCE_DIR}/artifacts}"
PROJECT_ARG="${2:-default}"
PACKAGE_ID="${3:-}"
APP_NAME="${4:-}"
VERSION_NAME="${5:-}"
VERSION_CODE="${6:-}"
ICON_PATH="${7:-}"
RUNTIME_DEBUGGER="${8:-0}"
MODE="${9:-}"
ARCH="${10:-}"
DEFAULT_SENTINEL="__LT_DEFAULT__"
[[ "${PACKAGE_ID}" == "${DEFAULT_SENTINEL}" ]] && PACKAGE_ID=""
[[ "${APP_NAME}" == "${DEFAULT_SENTINEL}" ]] && APP_NAME=""
[[ "${VERSION_NAME}" == "${DEFAULT_SENTINEL}" ]] && VERSION_NAME=""
[[ "${VERSION_CODE}" == "${DEFAULT_SENTINEL}" ]] && VERSION_CODE=""
[[ "${ICON_PATH}" == "${DEFAULT_SENTINEL}" ]] && ICON_PATH=""
[[ "${MODE}" == "${DEFAULT_SENTINEL}" ]] && MODE=""
[[ "${ARCH}" == "${DEFAULT_SENTINEL}" ]] && ARCH=""

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

for command_name in python3 buildozer java javac keytool sha256sum tar unzip flock; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "Missing prerequisite: ${command_name}" >&2
        echo "Follow README.md before running the Android build." >&2
        exit 2
    fi
done

export LT_REPO_ROOT="${REPO_ROOT}"
CACHE_BASE="${XDG_CACHE_HOME:-${HOME}/.cache}/lt-maker/android-runtime"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN_DIR="${CACHE_BASE}/runs/${RUN_ID}"
mkdir -p "${RUN_DIR}"
BUILD_LOG="${RUN_DIR}/build.log"
exec > >(tee -a "${BUILD_LOG}") 2>&1
BUILD_TIMER_START=${SECONDS}
LAST_TIMING_SECONDS=0

mark_timing() {
    local phase="$1"
    local elapsed=$((SECONDS - BUILD_TIMER_START))
    local delta=$((elapsed - LAST_TIMING_SECONDS))
    LAST_TIMING_SECONDS=${elapsed}
    echo "ANDROID_TIMING phase=${phase} elapsed_seconds=${elapsed} step_seconds=${delta}"
}

echo "LT Android phase 4 build ${RUN_ID}"
echo "Project input: ${PROJECT_ARG}"
echo "Linux cache: ${CACHE_BASE}"

PREFLIGHT_REPORT="${RUN_DIR}/preflight.json"
RESOLVED_CONFIG="${RUN_DIR}/android-build-config.json"
PREFLIGHT_ARGS=(
    python3 "${SOURCE_DIR}/preflight.py"
    --project "${PROJECT_ARG}"
    --report "${PREFLIGHT_REPORT}"
    --resolved-config "${RESOLVED_CONFIG}"
)
if [[ -n "${PACKAGE_ID}" ]]; then
    PREFLIGHT_ARGS+=(--package-id "${PACKAGE_ID}")
fi
if [[ -n "${APP_NAME}" ]]; then
    PREFLIGHT_ARGS+=(--app-name "${APP_NAME}")
fi
if [[ -n "${VERSION_NAME}" ]]; then
    PREFLIGHT_ARGS+=(--version-name "${VERSION_NAME}")
fi
if [[ -n "${VERSION_CODE}" ]]; then
    PREFLIGHT_ARGS+=(--version-code "${VERSION_CODE}")
fi
if [[ -n "${ICON_PATH}" ]]; then
    PREFLIGHT_ARGS+=(--icon "${ICON_PATH}")
fi
if [[ -n "${MODE}" ]]; then
    PREFLIGHT_ARGS+=(--mode "${MODE}")
fi
if [[ -n "${ARCH}" ]]; then
    PREFLIGHT_ARGS+=(--arch "${ARCH}")
fi
if [[ "${RUNTIME_DEBUGGER}" == "1" ]]; then
    PREFLIGHT_ARGS+=(--runtime-debugger)
fi
"${PREFLIGHT_ARGS[@]}"
mark_timing "preflight"

PROJECT_PATH="$(
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["project_path"])' \
        "${PREFLIGHT_REPORT}"
)"
PROJECT_DIGEST="$(
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["source_digest"])' \
        "${PREFLIGHT_REPORT}"
)"
MINIMUM_FREE="$(
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["minimum_linux_build_free_bytes"])' \
        "${SOURCE_DIR}/toolchain_manifest.json"
)"
LINUX_FREE_KIB="$(df -Pk "${CACHE_BASE}" | awk 'NR == 2 {print $4}')"
LINUX_FREE_BYTES="$((LINUX_FREE_KIB * 1024))"
if (( LINUX_FREE_BYTES < MINIMUM_FREE )); then
    echo "Insufficient Linux build-cache space: need ${MINIMUM_FREE} bytes, found ${LINUX_FREE_BYTES}" >&2
    exit 2
fi
echo "Linux build-cache free bytes: ${LINUX_FREE_BYTES}"

NATIVE_FILES_HASH="$(
    {
        printf '%s\0' \
            "${SOURCE_DIR}/buildozer.spec" \
            "${SOURCE_DIR}/toolchain_manifest.json"
        find \
            "${SOURCE_DIR}/android_native" \
            "${SOURCE_DIR}/p4a-recipes" \
            -type f \
            ! -path '*/__pycache__/*' \
            ! -name '*.pyc' -print0
    } \
    | sort -z \
    | xargs -0 sha256sum \
    | sha256sum \
    | cut -d' ' -f1
)"
BUILD_MODE="$(
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["mode"])' \
        "${RESOLVED_CONFIG}"
)"
BUILD_ARCH="$(
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["arch"])' \
        "${RESOLVED_CONFIG}"
)"
echo "Android packaging mode: ${BUILD_MODE}"
echo "Android packaging ABI: ${BUILD_ARCH}"
APKSIGNER_PATH=""
KEYTOOL_PATH="$(command -v keytool)"
if [[ "${BUILD_MODE}" == "release" ]]; then
    APKSIGNER_PATH="$(
        PYTHONPATH="${SOURCE_DIR}${PYTHONPATH:+:${PYTHONPATH}}" python3 -c \
            'from verify_apk import _default_build_tool; print(_default_build_tool("apksigner"))'
    )"
    python3 "${SOURCE_DIR}/sign_apk.py" \
        --check \
        --keytool "${KEYTOOL_PATH}" \
        --apksigner "${APKSIGNER_PATH}"
fi
P4A_COMMIT="$(
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["python_for_android_commit"])' \
        "${SOURCE_DIR}/toolchain_manifest.json"
)"
NATIVE_HASH="$(
    printf '%s\n%s\n%s\n%s\n%s\n%s\n' \
        "${NATIVE_FILES_HASH}" \
        "${P4A_COMMIT}" \
        "$(buildozer --version)" \
        "$(java -version 2>&1 | head -n 1)" \
        "${BUILD_MODE}" \
        "${BUILD_ARCH}" \
    | sha256sum \
    | cut -d' ' -f1
)"
RUNTIME_HASH="$(
    {
        find "${SOURCE_DIR}" -type f \
            ! -path '*/.buildozer/*' \
            ! -path '*/artifacts/*' \
            ! -path '*/staging/*' \
            ! -path '*/__pycache__/*' \
            ! -name '*.pyc' -print0
        find \
            "${REPO_ROOT}/app" \
            "${REPO_ROOT}/resources" \
            "${REPO_ROOT}/sprites" \
            -type f \
            ! -path '*/__pycache__/*' \
            ! -name '*.pyc' -print0
        printf '%s\0' \
            "${REPO_ROOT}/favicon.ico"
    } \
    | sort -z \
    | xargs -0 sha256sum \
    | sha256sum \
    | cut -d' ' -f1
)"
CONFIG_HASH="$(sha256sum "${RESOLVED_CONFIG}" | cut -d' ' -f1)"
BUILD_HASH="$(
    printf '%s\n%s\n%s\n%s\n' \
        "${NATIVE_HASH}" "${RUNTIME_HASH}" "${PROJECT_DIGEST}" "${CONFIG_HASH}" \
    | sha256sum \
    | cut -d' ' -f1
)"
PACKAGE_ID="$(
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["package_id"])' \
        "${RESOLVED_CONFIG}"
)"
# Keep python-for-android's mutable distribution under a key that changes only
# when native inputs change. Project, engine and version edits still rebuild
# staging and package a fresh APK, but no longer recompile CPython/SDL.
#
# This path must stay short: python-for-android writes executable pip launchers
# whose shebang points into this workspace, and Linux rejects shebangs longer
# than 255 bytes. The full native hash and package ID remain in the lock and
# log; compact hash prefixes keep each workspace both isolated and short.
PACKAGE_WORKSPACE_KEY="$(printf '%s' "${PACKAGE_ID}" | sha256sum | cut -c1-8)"
NATIVE_WORKSPACE_KEY="${NATIVE_HASH:0:16}-${PACKAGE_WORKSPACE_KEY}"
WORK_DIR="${CACHE_BASE}/n/${NATIVE_WORKSPACE_KEY}"
LOCK_DIR="${CACHE_BASE}/locks/native"
mkdir -p "${LOCK_DIR}"
exec 9>"${LOCK_DIR}/${NATIVE_HASH}-${PACKAGE_ID}.lock"
if ! flock -n 9; then
    echo "Another Android build is using this native cache; waiting for it to finish."
    flock 9
fi
echo "ANDROID_NATIVE_CACHE key=${NATIVE_HASH} workspace=${NATIVE_WORKSPACE_KEY} package=${PACKAGE_ID}"
echo "ANDROID_BUILD_INPUT key=${BUILD_HASH}"

if [[ ! -f "${WORK_DIR}/.workspace-ready" ]]; then
    TEMP_WORK_DIR="${CACHE_BASE}/native/.${NATIVE_HASH}.$$.tmp"
    rm -rf "${TEMP_WORK_DIR}"
    mkdir -p "${TEMP_WORK_DIR}"
    cp "${SOURCE_DIR}/buildozer.spec" "${TEMP_WORK_DIR}/buildozer.spec"
    cp -a "${SOURCE_DIR}/android_native" "${TEMP_WORK_DIR}/android_native"
    cp -a "${SOURCE_DIR}/p4a-recipes" "${TEMP_WORK_DIR}/p4a-recipes"
    touch "${TEMP_WORK_DIR}/.workspace-ready"
    if [[ -e "${WORK_DIR}" ]]; then
        rm -rf "${WORK_DIR}"
    fi
    mkdir -p "$(dirname "${WORK_DIR}")"
    mv "${TEMP_WORK_DIR}" "${WORK_DIR}"
fi

cp "${RESOLVED_CONFIG}" "${WORK_DIR}/android-build-config.json"
cp "${PREFLIGHT_REPORT}" "${WORK_DIR}/preflight-source.json"
cd "${WORK_DIR}"
python3 "${SOURCE_DIR}/prepare_runtime.py" \
    --project "${PROJECT_PATH}" \
    --staging "${WORK_DIR}/staging" \
    --config "${WORK_DIR}/android-build-config.json" \
    --preflight-report "${WORK_DIR}/preflight-source.json"
mark_timing "staging"
python3 "${SOURCE_DIR}/configure_build.py" \
    --config "${WORK_DIR}/android-build-config.json" \
    --spec "${WORK_DIR}/buildozer.spec"
python3 "${SOURCE_DIR}/validate_runtime.py" \
    --project "${PROJECT_PATH}" \
    --prepared \
    --staging "${WORK_DIR}/staging" \
    --spec "${WORK_DIR}/buildozer.spec"
mark_timing "static_validation"

if [[ -f "${WORK_DIR}/.dirty" ]]; then
    BUILDOZER_STATE="${WORK_DIR}/.buildozer"
    if [[ "$(dirname "${BUILDOZER_STATE}")" != "${WORK_DIR}" ]]; then
        echo "Refusing to clear an unexpected Buildozer cache path: ${BUILDOZER_STATE}" >&2
        exit 4
    fi
    echo "Native cache is marked dirty; rebuilding it before packaging."
    rm -rf -- "${BUILDOZER_STATE}"
    rm -f "${WORK_DIR}/.native-verified" "${WORK_DIR}/.dirty"
fi

APK_MARKER="${RUN_DIR}/apk-start"
touch "${APK_MARKER}"

set +e
buildozer -v android "${BUILD_MODE}"
BUILD_STATUS=$?
set -e

if [[ ${BUILD_STATUS} -ne 0 ]]; then
    P4A_BUILD_ROOT="${WORK_DIR}/.buildozer/android/platform/build-${BUILD_ARCH}/build"
    HOSTPYTHON="${P4A_BUILD_ROOT}/other_builds/hostpython3/desktop/hostpython3/native-build/root/usr/local/bin/python3.11"
    P4A_VENV="${P4A_BUILD_ROOT}/venv"
    if [[ -x "${HOSTPYTHON}" && -x "${P4A_VENV}/bin/python" ]] \
        && ! "${P4A_VENV}/bin/python" -c 'import pip._internal.resolution.resolvelib.resolver' >/dev/null 2>&1; then
        echo "Detected a partially upgraded p4a pip venv; rebuilding it once."
        "${HOSTPYTHON}" -m venv --clear "${P4A_VENV}"
        set +e
        buildozer -v android "${BUILD_MODE}"
        BUILD_STATUS=$?
        set -e
    else
        touch "${WORK_DIR}/.dirty"
        exit "${BUILD_STATUS}"
    fi
fi
mark_timing "android_packaging"

if [[ ${BUILD_STATUS} -ne 0 ]]; then
    touch "${WORK_DIR}/.dirty"
    exit "${BUILD_STATUS}"
fi

APK_PATH="$(find bin -maxdepth 1 -type f -name '*.apk' -newer "${APK_MARKER}" | sort | tail -n 1)"
if [[ -z "${APK_PATH}" ]]; then
    echo "Build completed without producing a new APK under ${WORK_DIR}/bin" >&2
    touch "${WORK_DIR}/.dirty"
    exit 3
fi

if [[ "${BUILD_MODE}" == "release" ]]; then
    RELEASE_SIGNED_APK="${RUN_DIR}/$(basename "${APK_PATH%.apk}")-dev-signed.apk"
    python3 "${SOURCE_DIR}/sign_apk.py" \
        --input "${APK_PATH}" \
        --output "${RELEASE_SIGNED_APK}" \
        --keytool "${KEYTOOL_PATH}" \
        --apksigner "${APKSIGNER_PATH}"
    APK_PATH="${RELEASE_SIGNED_APK}"
fi

VERIFICATION_REPORT="${RUN_DIR}/apk-verification.json"
VERIFY_ARGS=(
    python3 "${SOURCE_DIR}/verify_apk.py"
    --apk "${APK_PATH}"
    --config "${WORK_DIR}/android-build-config.json"
    --report "${VERIFICATION_REPORT}"
)
if [[ -n "${APKSIGNER_PATH}" ]]; then
    VERIFY_ARGS+=(--apksigner "${APKSIGNER_PATH}")
fi
if ! "${VERIFY_ARGS[@]}"; then
    exit 1
fi
touch "${WORK_DIR}/.native-verified"
mark_timing "apk_verification"

echo "Build and APK verification completed; publishing immutable artifact batch."
sync "${BUILD_LOG}" || true
python3 "${SOURCE_DIR}/publish_artifacts.py" \
    --apk "${APK_PATH}" \
    --preflight "${PREFLIGHT_REPORT}" \
    --verification "${VERIFICATION_REPORT}" \
    --build-log "${BUILD_LOG}" \
    --config "${WORK_DIR}/android-build-config.json" \
    --output "${OUTPUT_DIR}"
mark_timing "artifact_publication"
