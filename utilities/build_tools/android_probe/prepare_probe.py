from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import zlib


PROBE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROBE_ROOT.parents[2]
TEMPLATE_DIR = PROBE_ROOT / "app_template"
STAGING_DIR = PROBE_ROOT / "staging"
DEFAULT_OGG = Path(
    os.environ.get(
        "LT_ANDROID_PROBE_OGG",
        REPO_ROOT / "default.ltproj" / "resources" / "sfx" / "Silence.ogg",
    )
)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_probe_png(path: Path, width: int = 128, height: int = 128) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            checker = ((x // 16) + (y // 16)) % 2
            color = (37, 99, 235, 255) if checker else (15, 23, 42, 255)
            if abs(x - y) < 5 or abs((width - 1 - x) - y) < 5:
                color = (250, 204, 21, 255)
            rows.extend(color)
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(
        header
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + png_chunk(b"IEND", b"")
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(ogg_source: Path = DEFAULT_OGG) -> Path:
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(f"Missing probe template: {TEMPLATE_DIR}")
    ogg_source = ogg_source.resolve()
    if not ogg_source.is_file():
        raise FileNotFoundError(f"Missing OGG fixture: {ogg_source}")

    staging = STAGING_DIR.resolve()
    if staging.parent != PROBE_ROOT.resolve():
        raise RuntimeError(f"Refusing to replace unexpected staging path: {staging}")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(TEMPLATE_DIR, staging)
    shutil.copy2(ogg_source, staging / "probe.ogg")
    write_probe_png(staging / "probe.png")

    files = sorted(path for path in staging.rglob("*") if path.is_file())
    manifest = {
        "schema_version": 1,
        "pygame_ce": "2.3.2",
        "python": "3.11.9",
        "android_api": 36,
        "android_minapi": 26,
        "android_arch": "arm64-v8a",
        "files": {
            path.relative_to(staging).as_posix(): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        },
    }
    (staging / "build_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return staging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the LT Android probe staging tree")
    parser.add_argument("--ogg", type=Path, default=DEFAULT_OGG)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    prepared = prepare(args.ogg)
    print(f"Prepared Android probe staging at {prepared}")
