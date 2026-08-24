from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import struct
import tempfile
from typing import Any, Optional


CONFIG_RELATIVE_PATH = Path("build") / "android.json"
RELEASE_CONFIG_RELATIVE_PATH = Path("android-release.json")
PACKAGE_SEGMENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_NAME_RE = re.compile(
    r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z.-]+)?$"
)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
STAGE_MARKERS = (
    ("LT Android phase 4 build", 10, "Starting Android build"),
    ("ANDROID_PREFLIGHT_OK", 25, "Project preflight passed"),
    ("Prepared LT Android runtime", 35, "Staging snapshot prepared"),
    ("ANDROID_RUNTIME_STATIC_OK", 45, "Runtime validation passed"),
    ("# Android packaging done!", 78, "APK packaged"),
    ("ANDROID_DEVELOPMENT_APK_SIGNED", 84, "Release APK development-signed"),
    ("ANDROID_APK_VERIFIED", 90, "APK signature and manifest verified"),
    (
        "Build and APK verification completed",
        94,
        "Publishing build artifacts",
    ),
    ("ARTIFACT_DIR:", 98, "Artifacts published"),
)
SUPPORTED_ANDROID_ABIS = ("arm64-v8a", "x86_64")


@dataclass(frozen=True)
class AndroidEditorBuildConfig:
    package_id: str
    app_name: str
    version_name: str
    version_code: int
    icon: Optional[str] = None
    arch: str = "arm64-v8a"
    mode: str = "debug"
    runtime_debugger: bool = False
    output_directory: str = ""
    distro: str = "Ubuntu-24.04"

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update({"schema_version": 1, "phase": 5})
        return payload


@dataclass(frozen=True)
class BuildOutputUpdate:
    progress: Optional[int] = None
    description: str = ""
    artifact_dir: str = ""
    apk_path: str = ""


def _safe_package_segment(value: str) -> str:
    segment = re.sub(r"[^a-z0-9_]+", "_", value.casefold()).strip("_")
    if not segment:
        segment = "game"
    if not segment[0].isalpha():
        segment = f"game_{segment}"
    return segment


def default_config(
    project_path: Path,
    app_name: Optional[str] = None,
) -> AndroidEditorBuildConfig:
    project_path = project_path.resolve()
    project_stem = project_path.name.removesuffix(".ltproj")
    safe_name = _safe_package_segment(project_stem)
    return AndroidEditorBuildConfig(
        package_id=f"org.lextalionis.{safe_name}",
        app_name=(app_name or project_stem or "LT Android Game")[:50],
        version_name="0.4.0",
        version_code=1026400,
        output_directory=str(
            project_path.parent / f"{project_stem}_android_build"
        ),
    )


def config_path(project_path: Path) -> Path:
    return project_path / CONFIG_RELATIVE_PATH


def release_config_path(project_path: Path) -> Path:
    return project_path / RELEASE_CONFIG_RELATIVE_PATH


def load_config(
    project_path: Path,
    app_name: Optional[str] = None,
) -> tuple[AndroidEditorBuildConfig, Optional[str]]:
    defaults = default_config(project_path, app_name)
    warnings: list[str] = []
    # The tracked release file makes a clean checkout reproduce the Android
    # upgrade identity. The editor-local build/android.json can still override
    # it for a developer's output location and in-progress version choice.
    for path in (config_path(project_path), release_config_path(project_path)):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Android build config must be a JSON object")
            known = {
                key: payload[key]
                for key in asdict(defaults)
                if key in payload
            }
            merged = asdict(defaults)
            merged.update(known)
            merged["version_code"] = int(merged["version_code"])
            merged["runtime_debugger"] = bool(merged.get("runtime_debugger", False))
            merged["icon"] = str(merged["icon"]) if merged.get("icon") else None
            return AndroidEditorBuildConfig(**merged), "\n".join(warnings) or None
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"Could not load {path}: {exc}")
    return defaults, "\n".join(warnings) or None


def save_config(project_path: Path, config: AndroidEditorBuildConfig) -> Path:
    path = config_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            json.dump(
                config.to_json_dict(),
                output,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def validate_config(config: AndroidEditorBuildConfig) -> list[str]:
    errors: list[str] = []
    package_parts = config.package_id.split(".")
    if len(package_parts) < 3 or any(
        not PACKAGE_SEGMENT_RE.fullmatch(part) for part in package_parts
    ):
        errors.append(
            "Package ID must have at least three lowercase identifier "
            "segments, for example com.example.mygame."
        )
    if not 1 <= len(config.app_name) <= 50:
        errors.append("App name must contain 1-50 characters.")
    if not VERSION_NAME_RE.fullmatch(config.version_name):
        errors.append(
            "Version name must be a dotted version such as 1.0.0."
        )
    if not 1 <= config.version_code <= 2_100_000_000:
        errors.append("Version code must be between 1 and 2100000000.")
    if config.arch not in SUPPORTED_ANDROID_ABIS:
        errors.append(
            f"Unsupported Android ABI {config.arch!r}; choose one of "
            f"{', '.join(SUPPORTED_ANDROID_ABIS)}."
        )
    if config.mode not in {"debug", "release"}:
        errors.append("Build mode must be debug or release.")
    if not config.output_directory.strip():
        errors.append("Choose an output directory.")
    if config.icon:
        icon_path = Path(config.icon)
        if not icon_path.is_file():
            errors.append(f"Icon PNG was not found: {icon_path}")
        elif icon_path.suffix.casefold() != ".png":
            errors.append("Android icon must be a PNG file.")
        else:
            try:
                header = icon_path.read_bytes()[:24]
                if (
                    len(header) < 24
                    or header[:8] != b"\x89PNG\r\n\x1a\n"
                    or header[12:16] != b"IHDR"
                ):
                    errors.append(f"Android icon is not a valid PNG: {icon_path}")
                else:
                    width, height = struct.unpack(">II", header[16:24])
                    if width != height or width < 48:
                        errors.append(
                            "Android icon must be square and at least 48x48 "
                            f"pixels; got {width}x{height}."
                        )
            except OSError as exc:
                errors.append(f"Could not read Android icon {icon_path}: {exc}")
    if not config.distro.strip():
        errors.append("WSL distro cannot be empty.")
    return errors


def powershell_arguments(
    script_path: Path,
    project_path: Path,
    config: AndroidEditorBuildConfig,
) -> list[str]:
    arguments = [
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Project",
        str(project_path),
        "-OutputDirectory",
        config.output_directory,
        "-Distro",
        config.distro,
        "-PackageId",
        config.package_id,
        "-AppName",
        config.app_name,
        "-VersionName",
        config.version_name,
        "-VersionCode",
        str(config.version_code),
        "-Arch",
        config.arch,
        "-Mode",
        config.mode,
    ]
    if config.icon:
        arguments.extend(("-Icon", config.icon))
    if config.runtime_debugger:
        arguments.append("-EnableRuntimeDebugger")
    return arguments


def parse_build_output_line(
    line: str,
    output_directory: Path,
    current_artifact_dir: str = "",
) -> BuildOutputUpdate:
    clean_line = ANSI_ESCAPE_RE.sub("", line).strip()
    progress: Optional[int] = None
    description = ""
    for marker, marker_progress, marker_description in STAGE_MARKERS:
        if marker in clean_line:
            progress = marker_progress
            description = marker_description
            break

    artifact_dir = ""
    apk_path = ""
    if clean_line.startswith("ARTIFACT_DIR:"):
        wsl_path = clean_line.partition(":")[2].strip()
        artifact_name = PurePosixPath(wsl_path).name
        artifact_dir = str(output_directory / artifact_name)
    elif clean_line.startswith("APK:") and current_artifact_dir:
        wsl_path = clean_line.partition(":")[2].strip()
        apk_name = PurePosixPath(wsl_path).name
        apk_path = str(Path(current_artifact_dir) / apk_name)
    return BuildOutputUpdate(
        progress=progress,
        description=description,
        artifact_dir=artifact_dir,
        apk_path=apk_path,
    )
