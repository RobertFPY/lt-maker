#!/usr/bin/env python3
"""Create LT portrait ``_Dark`` variants from hand-made reference pairs.

The Golden Knight's existing dark portraits are palette conversions rather
than ordinary luminance-based grayscale images.  This utility learns the
conversion table from every ``Name.png`` + ``Name_Dark.png`` pair in the
portrait directory.  Exact source colours use the learned conversion exactly;
new colours use the closest reference colour.

The PNG reader/writer deliberately uses only Python's standard library so the
tool can run with a plain Python installation (Pillow is not required).
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import struct
import sys
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DEFAULT_BACKGROUND = (128, 160, 128)
DEFAULT_PORTRAIT_DIR = (
    Path(__file__).resolve().parents[1]
    / "Fire Emblem Tales of The Golden Knight.ltproj"
    / "resources"
    / "portraits"
)

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]


@dataclass(frozen=True)
class PngImage:
    width: int
    height: int
    pixels: tuple[RGBA, ...]
    has_alpha: bool


def _paeth(a: int, b: int, c: int) -> int:
    prediction = a + b - c
    distance_a = abs(prediction - a)
    distance_b = abs(prediction - b)
    distance_c = abs(prediction - c)
    if distance_a <= distance_b and distance_a <= distance_c:
        return a
    if distance_b <= distance_c:
        return b
    return c


def _unfilter_scanline(
    filtered: bytes, previous: bytes, filter_type: int, bytes_per_pixel: int
) -> bytes:
    result = bytearray(len(filtered))
    for index, value in enumerate(filtered):
        left = result[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        above = previous[index] if previous else 0
        upper_left = (
            previous[index - bytes_per_pixel]
            if previous and index >= bytes_per_pixel
            else 0
        )
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = above
        elif filter_type == 3:
            predictor = (left + above) // 2
        elif filter_type == 4:
            predictor = _paeth(left, above, upper_left)
        else:
            raise ValueError(f"Unsupported PNG filter type: {filter_type}")
        result[index] = (value + predictor) & 0xFF
    return bytes(result)


def read_png(path: Path) -> PngImage:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"Not a PNG file: {path}")

    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = colour_type = interlace = None
    palette: list[RGB] = []
    transparency = b""
    compressed = bytearray()

    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, colour_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
        elif chunk_type == b"PLTE":
            palette = [
                (chunk_data[i], chunk_data[i + 1], chunk_data[i + 2])
                for i in range(0, len(chunk_data), 3)
            ]
        elif chunk_type == b"tRNS":
            transparency = chunk_data
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if None in (width, height, bit_depth, colour_type, interlace):
        raise ValueError(f"PNG is missing IHDR data: {path}")
    if bit_depth != 8 or interlace != 0 or colour_type not in (2, 3, 6):
        raise ValueError(
            f"Unsupported PNG format in {path.name}: bit depth {bit_depth}, "
            f"colour type {colour_type}, interlace {interlace}. "
            "Use an 8-bit non-interlaced RGB, RGBA, or indexed PNG."
        )

    bytes_per_pixel = {2: 3, 3: 1, 6: 4}[colour_type]
    row_size = width * bytes_per_pixel
    raw = zlib.decompress(bytes(compressed))
    expected_size = height * (row_size + 1)
    if len(raw) != expected_size:
        raise ValueError(f"Unexpected decompressed PNG size in {path}")

    rows: list[bytes] = []
    previous = b""
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        filtered = raw[cursor + 1 : cursor + 1 + row_size]
        row = _unfilter_scanline(filtered, previous, filter_type, bytes_per_pixel)
        rows.append(row)
        previous = row
        cursor += row_size + 1

    pixels: list[RGBA] = []
    if colour_type == 2:
        for row in rows:
            pixels.extend((row[i], row[i + 1], row[i + 2], 255) for i in range(0, len(row), 3))
    elif colour_type == 6:
        for row in rows:
            pixels.extend(
                (row[i], row[i + 1], row[i + 2], row[i + 3])
                for i in range(0, len(row), 4)
            )
    else:
        if not palette:
            raise ValueError(f"Indexed PNG has no palette: {path}")
        for row in rows:
            for palette_index in row:
                if palette_index >= len(palette):
                    raise ValueError(f"Invalid palette index in {path}")
                red, green, blue = palette[palette_index]
                alpha = transparency[palette_index] if palette_index < len(transparency) else 255
                pixels.append((red, green, blue, alpha))

    return PngImage(width, height, tuple(pixels), colour_type in (3, 6))


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def write_png(path: Path, image: PngImage) -> None:
    colour_type = 6 if image.has_alpha else 2
    rows = bytearray()
    for y in range(image.height):
        rows.append(0)  # PNG filter: None
        start = y * image.width
        for red, green, blue, alpha in image.pixels[start : start + image.width]:
            rows.extend((red, green, blue))
            if image.has_alpha:
                rows.append(alpha)

    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, colour_type, 0, 0, 0)
    encoded = (
        PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(encoded)


def learn_palette(portrait_dir: Path, suffix: str) -> dict[RGB, RGB]:
    observations: dict[RGB, Counter[RGB]] = defaultdict(Counter)
    pair_count = 0
    for dark_path in sorted(portrait_dir.glob(f"*{suffix}.png")):
        normal_path = dark_path.with_name(dark_path.stem[: -len(suffix)] + ".png")
        if not normal_path.is_file():
            continue
        normal = read_png(normal_path)
        dark = read_png(dark_path)
        if (normal.width, normal.height) != (dark.width, dark.height):
            print(
                f"Warning: skipped mismatched pair {normal_path.name}/{dark_path.name}",
                file=sys.stderr,
            )
            continue
        for source, target in zip(normal.pixels, dark.pixels):
            if source[3] and target[3]:
                observations[source[:3]][target[:3]] += 1
        pair_count += 1

    if not observations:
        raise ValueError(
            f"No reference pairs (*{suffix}.png) were found in {portrait_dir}"
        )
    print(
        f"Learned {len(observations)} source colours from {pair_count} reference pairs."
    )
    return {
        source: targets.most_common(1)[0][0]
        for source, targets in observations.items()
    }


def _colour_distance(left: RGB, right: RGB) -> int:
    # Green contributes most to perceived brightness, then red, then blue.
    red = left[0] - right[0]
    green = left[1] - right[1]
    blue = left[2] - right[2]
    return 3 * red * red + 6 * green * green + 2 * blue * blue


def convert_image(
    image: PngImage, palette: dict[RGB, RGB], background: RGB
) -> PngImage:
    references = tuple(palette)
    nearest_cache: dict[RGB, RGB] = {}
    converted: list[RGBA] = []

    for red, green, blue, alpha in image.pixels:
        source = (red, green, blue)
        if alpha == 0 or source == background:
            target = source
        elif source in palette:
            target = palette[source]
        else:
            target = nearest_cache.get(source)
            if target is None:
                closest = min(references, key=lambda colour: _colour_distance(source, colour))
                target = palette[closest]
                nearest_cache[source] = target
        converted.append((*target, alpha))

    return PngImage(image.width, image.height, tuple(converted), image.has_alpha)


def parse_rgb(value: str) -> RGB:
    try:
        parts = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("RGB must contain three integers") from exc
    if len(parts) != 3 or any(part < 0 or part > 255 for part in parts):
        raise argparse.ArgumentTypeError("RGB must be formatted as R,G,B (0-255)")
    return parts  # type: ignore[return-value]


def output_path_for(source: Path, output: Path | None, suffix: str) -> Path:
    if output is not None:
        return output
    return source.with_name(f"{source.stem}{suffix}.png")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert LT portraits to the project's hand-made Dark palette."
    )
    parser.add_argument("sources", nargs="*", type=Path, help="portrait PNG file(s)")
    parser.add_argument(
        "--portrait-dir",
        type=Path,
        default=DEFAULT_PORTRAIT_DIR,
        help="directory containing portraits and reference pairs",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="convert every normal PNG in --portrait-dir that has no Dark output",
    )
    parser.add_argument("--output", type=Path, help="output path (single source only)")
    parser.add_argument("--suffix", default="_Dark", help="output/reference suffix")
    parser.add_argument(
        "--background",
        type=parse_rgb,
        default=DEFAULT_BACKGROUND,
        metavar="R,G,B",
        help="chroma background colour to preserve (default: 128,160,128)",
    )
    parser.add_argument("--force", action="store_true", help="overwrite existing output")
    parser.add_argument("--dry-run", action="store_true", help="show actions without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    portrait_dir = args.portrait_dir.resolve()
    if not portrait_dir.is_dir():
        print(f"Portrait directory does not exist: {portrait_dir}", file=sys.stderr)
        return 2
    if args.output and (args.all or len(args.sources) != 1):
        print("--output requires exactly one source and cannot be used with --all", file=sys.stderr)
        return 2

    sources = [source.resolve() for source in args.sources]
    if args.all:
        sources.extend(
            path.resolve()
            for path in sorted(portrait_dir.glob("*.png"))
            if not path.stem.endswith(args.suffix)
        )
    # Preserve order while removing duplicates.
    sources = list(dict.fromkeys(sources))
    if not sources:
        print("Provide one or more PNG files, or use --all.", file=sys.stderr)
        return 2

    try:
        palette = learn_palette(portrait_dir, args.suffix)
    except (OSError, ValueError, zlib.error) as exc:
        print(f"Could not learn Dark palette: {exc}", file=sys.stderr)
        return 1

    converted_count = skipped_count = 0
    for source in sources:
        if not source.is_file():
            print(f"Missing source: {source}", file=sys.stderr)
            skipped_count += 1
            continue
        if source.suffix.lower() != ".png" or source.stem.endswith(args.suffix):
            print(f"Skipped non-source portrait: {source.name}")
            skipped_count += 1
            continue
        target = output_path_for(source, args.output.resolve() if args.output else None, args.suffix)
        if target.exists() and not args.force:
            print(f"Skipped existing: {target.name} (use --force to overwrite)")
            skipped_count += 1
            continue
        print(f"{source.name} -> {target.name}")
        if args.dry_run:
            continue
        try:
            image = read_png(source)
            converted = convert_image(image, palette, args.background)
            target.parent.mkdir(parents=True, exist_ok=True)
            write_png(target, converted)
        except (OSError, ValueError, zlib.error) as exc:
            print(f"Failed {source.name}: {exc}", file=sys.stderr)
            skipped_count += 1
            continue
        converted_count += 1

    if args.dry_run:
        print("Dry run complete; no files were written.")
    else:
        print(f"Created {converted_count} Dark portrait(s); skipped {skipped_count}.")
    return 0 if skipped_count == 0 or converted_count > 0 or args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
