from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import tempfile
from typing import Any, Iterable


RUNTIME_ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(
    os.environ.get("LT_REPO_ROOT", str(RUNTIME_ROOT.parents[2]))
).resolve()
TOOLCHAIN_MANIFEST_PATH = RUNTIME_ROOT / "toolchain_manifest.json"
DEFAULT_PROJECT = "default"
RELEASE_CONFIG_RELATIVE_PATH = Path("android-release.json")
EDITOR_CONFIG_RELATIVE_PATH = Path("build") / "android.json"

PACKAGE_SEGMENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_NAME_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z.-]+)?$")
IGNORED_NAMES = {
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "Thumbs.db",
}
IGNORED_SUFFIXES = (".bak", ".pyc", ".pyo", ".tmp", "~")
DESKTOP_ONLY_IMPORTS = {
    "PyInstaller",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "tkinter",
    "win32api",
    "win32con",
    "win32gui",
}
DESKTOP_ONLY_APP_PREFIXES = (
    "app.editor",
    "app.extensions",
    "app.map_maker",
)


@dataclass(frozen=True)
class BuildConfig:
    package_id: str
    app_name: str
    version_name: str
    version_code: int
    icon: str | None = None
    arch: str = "arm64-v8a"
    mode: str = "debug"
    runtime_debugger: bool = False

    @property
    def package_name(self) -> str:
        return self.package_id.rsplit(".", 1)[-1]

    @property
    def package_domain(self) -> str:
        return self.package_id.rsplit(".", 1)[0]


@dataclass
class PreflightReport:
    schema_version: int
    phase: int
    passed: bool
    project_dir: str
    project_path: str
    source_digest: str
    config: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)


def load_toolchain_manifest() -> dict[str, Any]:
    return json.loads(TOOLCHAIN_MANIFEST_PATH.read_text(encoding="utf-8"))


def supported_android_arches(toolchain: dict[str, Any] | None = None) -> tuple[str, ...]:
    toolchain = toolchain or load_toolchain_manifest()
    configured = toolchain.get("supported_android_arches")
    if isinstance(configured, list) and all(isinstance(arch, str) for arch in configured):
        return tuple(configured)
    return (str(toolchain["android_arch"]),)


def load_build_config(path: Path | None = None, **overrides: Any) -> BuildConfig:
    toolchain = load_toolchain_manifest()
    payload = dict(toolchain["default_build"])
    if path is not None:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Android build config must be a JSON object")
        payload.update(loaded)
    payload.update({key: value for key, value in overrides.items() if value is not None})
    payload.setdefault("arch", toolchain["android_arch"])
    payload.setdefault("mode", toolchain["build_mode"])
    return BuildConfig(
        package_id=str(payload["package_id"]).strip(),
        app_name=str(payload["app_name"]).strip(),
        version_name=str(payload["version_name"]).strip(),
        version_code=int(payload["version_code"]),
        icon=str(payload["icon"]).strip() if payload.get("icon") else None,
        arch=str(payload["arch"]).strip(),
        mode=str(payload["mode"]).strip(),
        runtime_debugger=bool(payload.get("runtime_debugger", False)),
    )


def validate_build_config(config: BuildConfig) -> list[str]:
    errors: list[str] = []
    package_parts = config.package_id.split(".")
    if len(package_parts) < 3 or any(
        not PACKAGE_SEGMENT_RE.fullmatch(part) for part in package_parts
    ):
        errors.append(
            "package_id must contain at least three lowercase Java identifier "
            f"segments, got {config.package_id!r}"
        )
    if not config.app_name or len(config.app_name) > 50:
        errors.append("app_name must contain 1-50 characters")
    if not VERSION_NAME_RE.fullmatch(config.version_name):
        errors.append(
            "version_name must be a dotted numeric version with an optional suffix"
        )
    if not 1 <= config.version_code <= 2_100_000_000:
        errors.append("version_code must be between 1 and 2100000000")
    supported = supported_android_arches()
    if config.arch not in supported:
        errors.append(
            f"Unsupported Android ABI {config.arch!r}; expected one of {supported}"
        )
    if config.mode not in {"debug", "release"}:
        errors.append("mode must be either debug or release")
    return errors


def resolve_project(project: str | os.PathLike[str]) -> Path:
    raw = Path(project).expanduser()
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend(
            (
                REPO_ROOT / raw,
                REPO_ROOT / f"{raw}.ltproj",
            )
        )
    if raw.suffix != ".ltproj":
        candidates.append(raw.with_name(f"{raw.name}.ltproj"))
    for candidate in candidates:
        if candidate.is_dir() and candidate.name.endswith(".ltproj"):
            return candidate.resolve()
    raise FileNotFoundError(f"Could not find LT project directory: {project}")


def discover_project_build_config(
    project_dir: Path,
    explicit_config: Path | None = None,
) -> Path | None:
    """Prefer the saved editor selection, then the tracked fallback identity."""
    if explicit_config is not None:
        return explicit_config
    for relative_path in (
        EDITOR_CONFIG_RELATIVE_PATH,
        RELEASE_CONFIG_RELATIVE_PATH,
    ):
        candidate = project_dir / relative_path
        if candidate.is_file():
            return candidate
    return None


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts) or path.name.endswith(
        IGNORED_SUFFIXES
    )


def iter_snapshot_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_file() and not is_ignored(path.relative_to(root)):
            yield path


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_digest(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    count = 0
    total_bytes = 0
    for path in iter_snapshot_files(root):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(hash_file(path).encode("ascii"))
        digest.update(b"\0")
        count += 1
        total_bytes += size
    return digest.hexdigest(), count, total_bytes


def _read_json(path: Path, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid JSON {path}: {exc}")
        return None


def _entry_nid(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict) and isinstance(entry.get("nid"), str):
        return entry["nid"]
    if isinstance(entry, list) and entry and isinstance(entry[0], str):
        return entry[0]
    return None


def _relative_index(project_dir: Path) -> tuple[set[str], dict[str, list[str]]]:
    exact: set[str] = set()
    folded: dict[str, list[str]] = {}
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(project_dir).as_posix()
        exact.add(relative)
        folded.setdefault(relative.casefold(), []).append(relative)
    return exact, folded


def _require_exact_resource(
    relative: str,
    exact: set[str],
    folded: dict[str, list[str]],
    errors: list[str],
) -> None:
    normalized = PurePosixPath(relative).as_posix()
    if normalized in exact:
        return
    alternatives = folded.get(normalized.casefold(), [])
    if alternatives:
        errors.append(
            f"Resource path has wrong letter case: expected {normalized}, "
            f"found {alternatives[0]}"
        )
    else:
        errors.append(f"Missing resource file: {normalized}")


def validate_case_collisions(
    folded: dict[str, list[str]],
    errors: list[str],
) -> None:
    for paths in sorted(folded.values(), key=lambda values: values[0].casefold()):
        unique = sorted(set(paths))
        if len(unique) > 1:
            errors.append(
                "Case-insensitive path collision: " + ", ".join(unique)
            )


def validate_resource_catalogs(project_dir: Path, errors: list[str]) -> None:
    exact, folded = _relative_index(project_dir)
    validate_case_collisions(folded, errors)
    resources = project_dir / "resources"

    simple_png_catalogs = (
        "icons16",
        "icons32",
        "icons80",
        "portraits",
        "animations",
        "map_icons",
    )
    for catalog in simple_png_catalogs:
        manifest_path = resources / catalog / f"{catalog}.json"
        if not manifest_path.is_file():
            continue
        entries = _read_json(manifest_path, errors)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            nid = _entry_nid(entry)
            if nid:
                _require_exact_resource(
                    f"resources/{catalog}/{nid}.png", exact, folded, errors
                )

    map_sprites_path = resources / "map_sprites" / "map_sprites.json"
    if map_sprites_path.is_file():
        entries = _read_json(map_sprites_path, errors)
        if isinstance(entries, list):
            for entry in entries:
                nid = _entry_nid(entry)
                if not nid:
                    continue
                for suffix in ("-stand.png", "-move.png"):
                    _require_exact_resource(
                        f"resources/map_sprites/{nid}{suffix}",
                        exact,
                        folded,
                        errors,
                    )

    fonts_path = resources / "fonts" / "fonts.json"
    if fonts_path.is_file():
        entries = _read_json(fonts_path, errors)
        if isinstance(entries, list):
            for entry in entries:
                nid = _entry_nid(entry)
                if not nid:
                    continue
                for suffix in (".png", ".idx"):
                    _require_exact_resource(
                        f"resources/fonts/{nid}{suffix}", exact, folded, errors
                    )
                if isinstance(entry, dict) and entry.get("fallback_ttf"):
                    _require_exact_resource(
                        f"resources/fonts/{entry['fallback_ttf']}",
                        exact,
                        folded,
                        errors,
                    )

    panoramas_path = resources / "panoramas" / "panoramas.json"
    if panoramas_path.is_file():
        entries = _read_json(panoramas_path, errors)
        if isinstance(entries, list):
            for entry in entries:
                nid = _entry_nid(entry)
                if not nid:
                    continue
                frame_count = (
                    int(entry[1])
                    if isinstance(entry, list)
                    and len(entry) > 1
                    and isinstance(entry[1], int)
                    else 1
                )
                names = (
                    [f"{nid}.png"]
                    if frame_count <= 1
                    else [f"{nid}{index}.png" for index in range(frame_count)]
                )
                for name in names:
                    _require_exact_resource(
                        f"resources/panoramas/{name}", exact, folded, errors
                    )

    tilesets_path = resources / "tilesets" / "tilesets.json"
    if tilesets_path.is_file():
        entries = _read_json(tilesets_path, errors)
        if isinstance(entries, list):
            for entry in entries:
                nid = _entry_nid(entry)
                if not nid:
                    continue
                _require_exact_resource(
                    f"resources/tilesets/{nid}.png", exact, folded, errors
                )
                if isinstance(entry, dict) and entry.get("autotiles"):
                    _require_exact_resource(
                        f"resources/tilesets/{nid}_autotiles.png",
                        exact,
                        folded,
                        errors,
                    )

    for catalog in ("music", "sfx"):
        manifest_path = resources / catalog / f"{catalog}.json"
        if not manifest_path.is_file():
            continue
        entries = _read_json(manifest_path, errors)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            nid = _entry_nid(entry)
            if not nid:
                continue
            expected = [f"{nid}.ogg"]
            if catalog == "music" and isinstance(entry, list):
                if len(entry) > 1 and entry[1] is True:
                    expected.append(f"{nid}-intro.ogg")
                if len(entry) > 2 and entry[2] is True:
                    expected.append(f"{nid}-battle.ogg")
            for name in expected:
                _require_exact_resource(
                    f"resources/{catalog}/{name}", exact, folded, errors
                )


def validate_audio(project_dir: Path, errors: list[str]) -> int:
    audio_roots = (
        project_dir / "resources" / "music",
        project_dir / "resources" / "sfx",
    )
    count = 0
    for root in audio_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() == ".json":
                continue
            count += 1
            if path.suffix.lower() != ".ogg":
                errors.append(f"Unsupported Android audio codec: {path}")
                continue
            try:
                if path.read_bytes()[:4] != b"OggS":
                    errors.append(f"Invalid OGG header: {path}")
            except OSError as exc:
                errors.append(f"Could not read audio file {path}: {exc}")
    return count


def _import_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else ""
    return node.module or ""


def validate_custom_components(project_dir: Path, errors: list[str]) -> int:
    custom_root = project_dir / "resources" / "custom_components"
    if not custom_root.is_dir():
        return 0
    count = 0
    for path in sorted(custom_root.rglob("*.py")):
        count += 1
        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f"Custom component syntax error in {path}: {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [_import_name(node)]
            )
            for imported in names:
                root = imported.split(".", 1)[0]
                if root in DESKTOP_ONLY_IMPORTS or imported.startswith(
                    DESKTOP_ONLY_APP_PREFIXES
                ):
                    errors.append(
                        f"Desktop-only import {imported!r} in custom component {path}"
                    )
    return count


def validate_icon(config: BuildConfig, errors: list[str]) -> None:
    if not config.icon:
        return
    path = Path(config.icon).expanduser()
    if not path.is_file():
        errors.append(f"Configured icon PNG does not exist: {path}")
        return
    try:
        header = path.read_bytes()[:24]
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            errors.append(f"Configured icon is not a PNG: {path}")
            return
        width, height = struct.unpack(">II", header[16:24])
        if width != height or width < 48:
            errors.append(
                f"Configured icon must be square and at least 48x48, got "
                f"{width}x{height}: {path}"
            )
    except OSError as exc:
        errors.append(f"Could not read configured icon {path}: {exc}")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(payload, temporary, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def run_preflight(
    project: str | os.PathLike[str],
    config: BuildConfig,
    report_path: Path | None = None,
) -> PreflightReport:
    project_dir = resolve_project(project)
    errors = validate_build_config(config)
    warnings: list[str] = []

    metadata_path = project_dir / "metadata.json"
    metadata = _read_json(metadata_path, errors) if metadata_path.is_file() else None
    if metadata is None:
        errors.append(f"Missing project metadata: {metadata_path}")
    elif not isinstance(metadata, dict):
        errors.append(f"Project metadata must be a JSON object: {metadata_path}")
    else:
        if metadata.get("has_fatal_errors"):
            errors.append(
                "Project metadata reports fatal errors; save and repair the project "
                "in LT Maker before building"
            )
        current_serialization = int(load_toolchain_manifest().get("serialization_version", 1))
        if int(metadata.get("serialization_version", 0)) != current_serialization:
            errors.append(
                "Project serialization version does not match the Android runtime; "
                "open and save it with the current LT Maker first"
            )

    validate_icon(config, errors)
    validate_resource_catalogs(project_dir, errors)
    audio_files = validate_audio(project_dir, errors)
    custom_python_files = validate_custom_components(project_dir, errors)
    source_digest, file_count, project_bytes = snapshot_digest(project_dir)
    free_bytes = shutil.disk_usage(project_dir).free
    required_snapshot_bytes = max(256 * 1024 * 1024, project_bytes * 2)
    if free_bytes < required_snapshot_bytes:
        errors.append(
            f"Insufficient free space beside project: need at least "
            f"{required_snapshot_bytes} bytes, found {free_bytes}"
        )
    elif free_bytes < project_bytes * 4:
        warnings.append(
            "Free space is low relative to project size; the Linux build cache "
            "has a separate 8 GiB requirement"
        )

    report = PreflightReport(
        schema_version=1,
        phase=4,
        passed=not errors,
        project_dir=project_dir.name,
        project_path=str(project_dir),
        source_digest=source_digest,
        config=asdict(config),
        errors=errors,
        warnings=warnings,
        metrics={
            "project_files": file_count,
            "project_bytes": project_bytes,
            "project_filesystem_free_bytes": free_bytes,
            "audio_files": audio_files,
            "custom_python_files": custom_python_files,
        },
    )
    if report_path is not None:
        atomic_write_json(report_path, asdict(report))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight an LT project for Android")
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--resolved-config", type=Path)
    parser.add_argument("--package-id")
    parser.add_argument("--app-name")
    parser.add_argument("--version-name")
    parser.add_argument("--version-code", type=int)
    parser.add_argument("--icon")
    parser.add_argument("--arch")
    parser.add_argument("--mode", choices=("debug", "release"))
    parser.add_argument("--runtime-debugger", action="store_true", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = resolve_project(args.project)
    config_path = discover_project_build_config(project_dir, args.config)
    config = load_build_config(
        config_path,
        package_id=args.package_id,
        app_name=args.app_name,
        version_name=args.version_name,
        version_code=args.version_code,
        icon=args.icon,
        arch=args.arch,
        mode=args.mode,
        runtime_debugger=args.runtime_debugger,
    )
    if args.resolved_config is not None:
        atomic_write_json(args.resolved_config, asdict(config))
    report = run_preflight(project_dir, config, args.report)
    print(
        f"ANDROID_PREFLIGHT_{'OK' if report.passed else 'FAILED'} "
        f"project={report.project_dir} files={report.metrics['project_files']} "
        f"bytes={report.metrics['project_bytes']}"
    )
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
