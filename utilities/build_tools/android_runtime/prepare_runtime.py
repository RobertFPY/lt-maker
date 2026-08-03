from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tarfile
import tempfile
import zlib

from preflight import (
    BuildConfig,
    PreflightReport,
    atomic_write_json,
    load_build_config,
    load_toolchain_manifest,
    resolve_project,
    run_preflight,
    snapshot_digest,
)


RUNTIME_ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(
    os.environ.get("LT_REPO_ROOT", str(RUNTIME_ROOT.parents[2]))
).resolve()
TEMPLATE_DIR = RUNTIME_ROOT / "app_template"
STAGING_DIR = RUNTIME_ROOT / "staging"
DEFAULT_PROJECT = "default"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_project_name(project: str) -> str:
    return resolve_project(project).stem


def ignored_runtime_paths(_directory: str, names: list[str]) -> set[str]:
    blocked = {"editor", "extensions", "map_maker", "tests", "__pycache__"}
    return {
        name
        for name in names
        if name in blocked or name.endswith((".pyc", ".pyo"))
    }


def ignored_assets(_directory: str, names: list[str]) -> set[str]:
    blocked = {
        ".DS_Store",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        "Thumbs.db",
        "__pycache__",
        "tests",
    }
    return {
        name
        for name in names
        if name in blocked
        or name.endswith((".bak", ".pyc", ".pyo", ".tmp", "~"))
    }


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_runtime_icon(path: Path, width: int = 128, height: int = 128) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            border = x < 8 or y < 8 or x >= width - 8 or y >= height - 8
            blade = abs(x - y) < 6 or abs((width - 1 - x) - y) < 6
            color = (226, 232, 240, 255) if blade else (30, 64, 175, 255)
            if border:
                color = (15, 23, 42, 255)
            rows.extend(color)
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(
        header
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + png_chunk(b"IEND", b"")
    )


def write_runtime_presplash(path: Path, width: int = 1280, height: int = 720) -> None:
    rows = bytearray()
    logo_size = 180
    left = (width - logo_size) // 2
    top = (height - logo_size) // 2
    for y in range(height):
        rows.append(0)
        for x in range(width):
            color = (9, 16, 32, 255)
            in_logo = left <= x < left + logo_size and top <= y < top + logo_size
            if in_logo:
                lx, ly = x - left, y - top
                border = lx < 7 or ly < 7 or lx >= logo_size - 7 or ly >= logo_size - 7
                blade = abs(lx - ly) < 5 or abs((logo_size - 1 - lx) - ly) < 5
                color = (226, 232, 240, 255) if blade else (30, 64, 175, 255)
                if border:
                    color = (51, 65, 85, 255)
            rows.extend(color)
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(
        header
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + png_chunk(b"IEND", b"")
    )


def _replace_staging(temporary: Path, staging: Path) -> None:
    resolved = staging.resolve()
    parent = staging.parent.resolve()
    if resolved == parent or resolved.parent != parent or not staging.name:
        raise RuntimeError(f"Refusing to replace unexpected staging path: {staging}")
    if staging.exists():
        shutil.rmtree(staging)
    temporary.replace(staging)


def _ustar_compatible(relative_path: Path) -> bool:
    info = tarfile.TarInfo(relative_path.as_posix())
    try:
        info.tobuf(format=tarfile.USTAR_FORMAT)
    except ValueError:
        return False
    return True


def _catalog_nids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    nids: set[str] = set()
    for entry in payload:
        if isinstance(entry, str):
            nids.add(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("nid"), str):
            nids.add(entry["nid"])
        elif isinstance(entry, list) and entry and isinstance(entry[0], str):
            nids.add(entry[0])
    return nids


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def minify_project_json(project_snapshot: Path) -> dict[str, int]:
    """Compact copied project JSON without mutating the source project.

    LT projects are editor-friendly and heavily indented. Android parses the
    copied snapshot, so removing whitespace here cuts private.tar extraction
    and JSON decode work while preserving object order and values.
    """
    file_count = 0
    bytes_before = 0
    bytes_after = 0
    for path in sorted(project_snapshot.rglob("*.json")):
        original = path.read_bytes()
        try:
            payload = json.loads(
                original.decode("utf-8-sig"),
                object_pairs_hook=_unique_json_object,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            relative = path.relative_to(project_snapshot).as_posix()
            raise RuntimeError(
                f"Cannot safely compact project JSON {relative}: {exc}"
            ) from exc
        compact = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        path.write_bytes(compact)
        file_count += 1
        bytes_before += len(original)
        bytes_after += len(compact)
    return {
        "json_files_compacted": file_count,
        "json_bytes_before": bytes_before,
        "json_bytes_after": bytes_after,
        "json_bytes_saved": bytes_before - bytes_after,
    }


def prune_unpackageable_project_files(
    staging_root: Path,
    project_snapshot: Path,
) -> list[str]:
    """Drop known editor leftovers that cannot be represented in p4a's USTAR.

    python-for-android deliberately writes private.tar with USTAR, whose final
    path component is limited to 100 UTF-8 bytes. LT Maker portrait imports can
    leave original, non-catalogued source PNGs beside the actual ``<nid>.png``
    resource. They are not loaded by the engine and must not prevent packaging.
    """
    portrait_nids = _catalog_nids(
        project_snapshot / "resources" / "portraits" / "portraits.json"
    )
    excluded: list[str] = []
    unsupported: list[str] = []
    for path in sorted(project_snapshot.rglob("*")):
        if not path.is_file():
            continue
        package_relative = path.relative_to(staging_root)
        if _ustar_compatible(package_relative):
            continue

        project_relative = path.relative_to(project_snapshot)
        parts = project_relative.parts
        is_old_portrait = (
            len(parts) >= 3
            and parts[0] == "resources"
            and parts[1] == "old_portraits"
        )
        is_unlisted_portrait = (
            len(parts) == 3
            and parts[0] == "resources"
            and parts[1] == "portraits"
            and path.suffix.casefold() == ".png"
            and path.stem not in portrait_nids
        )
        if is_old_portrait or is_unlisted_portrait:
            excluded.append(project_relative.as_posix())
            path.unlink()
        else:
            unsupported.append(project_relative.as_posix())

    if unsupported:
        details = "\n- ".join(unsupported[:20])
        raise RuntimeError(
            "Android packaging cannot represent these project paths because "
            "a filename exceeds the USTAR 100-byte limit:\n- "
            + details
        )
    return excluded


def validate_ustar_paths(staging_root: Path) -> None:
    unsupported = [
        path.relative_to(staging_root).as_posix()
        for path in staging_root.rglob("*")
        if not _ustar_compatible(path.relative_to(staging_root))
    ]
    if unsupported:
        details = "\n- ".join(unsupported[:20])
        raise RuntimeError(
            "Android staging still contains paths unsupported by USTAR:\n- "
            + details
        )


def load_verified_preflight(
    report_path: Path,
    project_dir: Path,
    config: BuildConfig,
) -> PreflightReport:
    """Load one preflight result without trusting a stale project snapshot."""
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        preflight = PreflightReport(**payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not read Android preflight report {report_path}: {exc}"
        ) from exc
    if not preflight.passed:
        raise RuntimeError("Provided Android preflight report did not pass")
    if Path(preflight.project_path).resolve() != project_dir:
        raise RuntimeError("Provided Android preflight report is for another project")
    if preflight.config != asdict(config):
        raise RuntimeError("Provided Android preflight report uses another build config")
    current_digest, _, _ = snapshot_digest(project_dir)
    if current_digest != preflight.source_digest:
        raise RuntimeError(
            "Project changed after Android preflight; run a new preflight before staging"
        )
    return preflight


def prepare(
    project: str = DEFAULT_PROJECT,
    staging_dir: Path | None = None,
    config: BuildConfig | None = None,
    preflight_report: Path | None = None,
) -> Path:
    project_dir = resolve_project(project)
    config = config or load_build_config()
    preflight = (
        load_verified_preflight(preflight_report, project_dir, config)
        if preflight_report is not None
        else run_preflight(project_dir, config)
    )
    if not preflight.passed:
        raise RuntimeError(
            "Android preflight failed:\n- " + "\n- ".join(preflight.errors)
        )

    staging = (staging_dir or STAGING_DIR).resolve()
    staging.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{staging.name}.", dir=staging.parent)
    )
    try:
        shutil.copytree(
            TEMPLATE_DIR,
            temporary,
            ignore=ignored_assets,
            dirs_exist_ok=True,
        )

        shutil.copytree(
            REPO_ROOT / "app",
            temporary / "app",
            ignore=ignored_runtime_paths,
        )
        (temporary / "app" / "dark_theme.py").unlink(missing_ok=True)
        retained_math = (
            REPO_ROOT / "app" / "editor" / "lib" / "math" / "math_utils.py"
        )
        retained_math_target = (
            temporary / "app" / "editor" / "lib" / "math" / "math_utils.py"
        )
        retained_math_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            REPO_ROOT / "app" / "editor" / "__init__.py",
            temporary / "app" / "editor" / "__init__.py",
        )
        shutil.copy2(retained_math, retained_math_target)

        for asset_dir in ("resources", "sprites"):
            shutil.copytree(
                REPO_ROOT / asset_dir,
                temporary / asset_dir,
                ignore=ignored_assets,
            )
        shutil.copytree(
            project_dir,
            temporary / project_dir.name,
            ignore=ignored_assets,
        )
        copied_digest, _, _ = snapshot_digest(temporary / project_dir.name)
        if copied_digest != preflight.source_digest:
            raise RuntimeError(
                "Project changed while the Android staging snapshot was being copied"
            )
        excluded_project_files = prune_unpackageable_project_files(
            temporary,
            temporary / project_dir.name,
        )
        json_metrics = minify_project_json(temporary / project_dir.name)

        shutil.copy2(REPO_ROOT / "favicon.ico", temporary / "favicon.ico")
        if config.icon:
            shutil.copy2(Path(config.icon).expanduser(), temporary / "android_icon.png")
        else:
            write_runtime_icon(temporary / "android_icon.png")
        write_runtime_presplash(temporary / "android_presplash.png")
        validate_ustar_paths(temporary)
        packaging_warnings = list(preflight.warnings)
        if excluded_project_files:
            packaging_warnings.append(
                "Excluded unlisted editor portrait leftovers that exceed "
                "Android USTAR filename limits: "
                + ", ".join(excluded_project_files)
            )
        staging_metrics = dict(preflight.metrics)
        staging_metrics.update(json_metrics)
        atomic_write_json(
            temporary / "android_preflight.json",
            {
                "schema_version": preflight.schema_version,
                "phase": preflight.phase,
                "passed": preflight.passed,
                "project_dir": preflight.project_dir,
                "project_path": preflight.project_path,
                "source_digest": preflight.source_digest,
                "config": preflight.config,
                "errors": preflight.errors,
                "warnings": packaging_warnings,
                "metrics": staging_metrics,
            },
        )

        toolchain = load_toolchain_manifest()
        files = sorted(path for path in temporary.rglob("*") if path.is_file())
        manifest = {
            "schema_version": 2,
            "phase": 4,
            "project_dir": project_dir.name,
            "source_digest": preflight.source_digest,
            "excluded_project_files": excluded_project_files,
            "build": preflight.config,
            "toolchain": toolchain,
            "files": {
                path.relative_to(temporary).as_posix(): {
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
                for path in files
            },
        }
        atomic_write_json(temporary / "runtime_manifest.json", manifest)
        _replace_staging(temporary, staging)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return staging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare an LT Android runtime bundle")
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--preflight-report", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    prepared = prepare(
        args.project,
        staging_dir=args.staging,
        config=load_build_config(args.config),
        preflight_report=args.preflight_report,
    )
    print(f"Prepared LT Android runtime staging at {prepared}")
