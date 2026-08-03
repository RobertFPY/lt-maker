from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageChops


PROJECT_ROOT = Path("Fire Emblem Tales of The Golden Knight.ltproj")
SKID_SOURCE = Path(
    r"E:\FE\FE-Repo\Spells n Skills\7. Spells\1. Anima"
    r"\[Ice] Aqua {SkidMarc25, Alice}"
)
ALUSQ_SOURCE = Path(
    r"E:\FE\FE-Repo\Spells n Skills\7. Spells\1. Anima"
    r"\[Ice] Aqua {Alusq}"
)

SKID_CONTROLLER = "Aqua_SkidMarc25_Alice"
SKID_BURST = f"{SKID_CONTROLLER}_Burst"
ALUSQ_CONTROLLER = "Aqua_Alusq"
ALUSQ_OBJECT = f"{ALUSQ_CONTROLLER}_Object"
ALUSQ_BACKGROUND = f"{ALUSQ_CONTROLLER}_Background"

Color = tuple[int, int, int]
Command = list[object]


def cmd(nid: str, *values: object) -> Command:
    return [nid, list(values) if values else None]


def quantize_gba(color: Color) -> Color:
    return tuple(channel // 8 * 8 for channel in color)


def normalize_image(path: Path, split_at: int | None = None) -> list[Image.Image]:
    image = Image.open(path).convert("RGB")
    image = image.point(lambda channel: channel // 8 * 8)
    if split_at is None:
        images = [image]
    else:
        images = [
            image.crop((0, 0, split_at, image.height)),
            image.crop((split_at, 0, image.width, image.height)),
        ]

    normalized: list[Image.Image] = []
    for part in images:
        background = part.getpixel((0, 0))
        pixels = part.load()
        # CSA stores a small palette marker in the top-right corner.
        for x in range(max(0, part.width - 8), part.width):
            for y in range(min(2, part.height)):
                pixels[x, y] = background
        for y in range(part.height):
            for x in range(part.width):
                pixels[x, y] = (
                    (0, 0, 0)
                    if pixels[x, y] == background
                    else quantize_gba(pixels[x, y])
                )
        normalized.append(part)
    return normalized


def crop_nonblack(image: Image.Image) -> tuple[Image.Image, tuple[int, int]] | None:
    bbox = ImageChops.difference(
        image, Image.new("RGB", image.size, (0, 0, 0))
    ).getbbox()
    if not bbox:
        return None
    left, top, right, bottom = bbox
    return image.crop(bbox), (left, top)


def collect_palette(images: Iterable[Image.Image]) -> list[Color]:
    colors: list[Color] = [(0, 0, 0)]
    seen = {(0, 0, 0)}
    for image in images:
        for color in image.get_flattened_data():
            if color not in seen:
                seen.add(color)
                colors.append(color)
    if len(colors) > 2048:
        raise ValueError(f"Effect palette has {len(colors)} colors; maximum is 2048")
    return colors


def encode_palette(image: Image.Image, palette: Sequence[Color]) -> Image.Image:
    coords = {
        color: (0, index % 8, index // 8)
        for index, color in enumerate(palette)
    }
    encoded = Image.new("RGB", image.size, (0, 0, 0))
    encoded.putdata([coords[color] for color in image.get_flattened_data()])
    return encoded


def pack_frames(
    raw_frames: Sequence[tuple[str, Image.Image, tuple[int, int]]],
    palette: Sequence[Color],
) -> tuple[Image.Image, list[list[object]]]:
    width_limit = 1200
    x = 0
    y = 0
    row_height = 0
    max_width = 0
    packed: list[tuple[str, Image.Image, tuple[int, int], tuple[int, int, int, int]]] = []

    for name, image, offset in raw_frames:
        width, height = image.size
        if x and x + width > width_limit:
            x = 0
            y += row_height
            row_height = 0
        rect = (x, y, width, height)
        packed.append((name, image, offset, rect))
        x += width
        row_height = max(row_height, height)
        max_width = max(max_width, x)

    total_height = y + row_height
    if not packed or max_width <= 0 or total_height <= 0:
        raise ValueError("Cannot pack an effect with no visible frames")

    sheet = Image.new("RGB", (max_width, total_height), (0, 0, 0))
    metadata: list[list[object]] = []
    for name, image, offset, rect in packed:
        left, top, width, height = rect
        sheet.paste(encode_palette(image, palette), (left, top))
        metadata.append([name, [left, top, width, height], list(offset)])
    return sheet, metadata


def palette_entry(nid: str, colors: Sequence[Color]) -> list[object]:
    return [
        nid,
        [
            [[index % 8, index // 8], list(color)]
            for index, color in enumerate(colors)
        ],
    ]


def effect_entry(
    nid: str,
    attack: Sequence[Command],
    miss: Sequence[Command],
    frames: Sequence[list[object]] | None = None,
    palette_nid: str | None = None,
) -> dict[str, object]:
    palettes = [["Image", palette_nid]] if palette_nid else []
    return {
        "nid": nid,
        "poses": [["Attack", list(attack)], ["Miss", list(miss)]],
        "frames": list(frames or []),
        "palettes": palettes,
    }


def build_skid(source: Path) -> tuple[list[dict[str, object]], list[list[object]], dict[str, Image.Image]]:
    durations = {
        2: 2, 3: 2, 4: 2, 5: 2,
        6: 2, 7: 3, 8: 3, 9: 3,
        10: 3, 11: 3, 12: 3,
    }
    images: dict[int, tuple[Image.Image, tuple[int, int]]] = {}
    raw_frames: list[tuple[str, Image.Image, tuple[int, int]]] = []
    for index in range(2, 13):
        normalized = normalize_image(source / f"Spell_b_{index:03d}.png")[0]
        cropped = crop_nonblack(normalized)
        if not cropped:
            raise ValueError(f"Unexpected empty Skid frame {index}")
        image, offset = cropped
        images[index] = (image, offset)
        raw_frames.append((f"Burst_{index:03d}", image, offset))

    palette_nid = f"{SKID_BURST}_Image"
    palette = collect_palette(image for image, _ in images.values())
    sheet, frames = pack_frames(raw_frames, palette)

    prehit = [cmd("wait", 6)]
    for index in range(2, 6):
        prehit.append(cmd("frame", durations[index], f"Burst_{index:03d}"))

    posthit: list[Command] = []
    for index in (6, 7, 8, 9, 4, 10, 11, 12):
        posthit.append(cmd("frame", durations[index], f"Burst_{index:03d}"))
    posthit.extend([cmd("wait", 3), cmd("wait", 1)])

    child_attack = [cmd("blend", True), cmd("opacity", 191), *prehit, *posthit]
    child_miss = [cmd("blend", True), cmd("opacity", 191), *prehit, cmd("wait", 1)]

    white = [255, 255, 255]
    controller_attack = [
        cmd("darken"),
        cmd("wait", 4),
        cmd("pan"),
        cmd("wait", 4),
        cmd("enemy_effect", SKID_BURST),
        cmd("wait", 6),
        cmd("sound", "Fenrir4"),
        cmd("wait", 8),
        cmd("enemy_tint", 8, white),
        cmd("screen_blend", 4, white),
        cmd("spell_hit"),
        cmd("wait", 26),
        cmd("lighten"),
        cmd("wait", 4),
        cmd("pan"),
        cmd("wait", 4),
        cmd("end_parent_loop"),
        cmd("wait", 1),
    ]
    controller_miss = [
        cmd("darken"),
        cmd("wait", 4),
        cmd("pan"),
        cmd("wait", 4),
        cmd("enemy_effect", SKID_BURST),
        cmd("wait", 6),
        cmd("sound", "Fenrir4"),
        cmd("wait", 8),
        cmd("miss"),
        cmd("wait", 1),
        cmd("lighten"),
        cmd("wait", 4),
        cmd("pan"),
        cmd("wait", 4),
        cmd("end_parent_loop"),
        cmd("wait", 1),
    ]

    effects = [
        effect_entry(SKID_CONTROLLER, controller_attack, controller_miss),
        effect_entry(SKID_BURST, child_attack, child_miss, frames, palette_nid),
    ]
    return effects, [palette_entry(palette_nid, palette)], {f"{SKID_BURST}.png": sheet}


def object_frame_command(
    duration: int,
    index: int,
    available: set[str],
) -> Command:
    front = f"Object_{index:03d}"
    under = f"Object_{index:03d}_Under"
    if front in available and under in available:
        return cmd("dual_frame", duration, front, under)
    if front in available:
        return cmd("frame", duration, front)
    if under in available:
        return cmd("under_frame", duration, under)
    return cmd("wait", duration)


def build_alusq(source: Path) -> tuple[list[dict[str, object]], list[list[object]], dict[str, Image.Image]]:
    object_indices = [5, 7, 9, *range(11, 22), 23, 25, 27, 29, 31]
    object_raw: list[tuple[str, Image.Image, tuple[int, int]]] = []
    available: set[str] = set()
    for index in object_indices:
        front, under = normalize_image(source / f"Spell_o_{index:03d}.png", split_at=240)
        for suffix, part in (("", front), ("_Under", under)):
            cropped = crop_nonblack(part)
            if cropped:
                image, offset = cropped
                name = f"Object_{index:03d}{suffix}"
                available.add(name)
                object_raw.append((name, image, offset))

    object_palette_nid = f"{ALUSQ_OBJECT}_Image"
    object_palette = collect_palette(image for _, image, _ in object_raw)
    object_sheet, object_frames = pack_frames(object_raw, object_palette)

    background_indices = [2, 3, 4, 6, 8, 22, 24, 26, 28, 30, 32]
    background_raw: list[tuple[str, Image.Image, tuple[int, int]]] = []
    for index in background_indices:
        normalized = normalize_image(source / f"Spell_b_{index:03d}.png")[0]
        cropped = crop_nonblack(normalized)
        if not cropped:
            raise ValueError(f"Unexpected empty Alusq background frame {index}")
        image, offset = cropped
        background_raw.append((f"Background_{index:03d}", image, offset))

    background_palette_nid = f"{ALUSQ_BACKGROUND}_Image"
    background_palette = collect_palette(image for _, image, _ in background_raw)
    background_sheet, background_frames = pack_frames(background_raw, background_palette)

    # Four blank object frames accompany B2, B2, B3 and B4.
    object_prehit: list[Command] = [cmd("wait", 8)]
    for index in (5, 7, 9, *range(11, 21)):
        object_prehit.append(object_frame_command(1, index, available))

    object_posthit: list[Command] = []
    for index in (21, 21, 23, 23, 25, 27, 29, 31):
        object_posthit.append(object_frame_command(1, index, available))
    object_posthit.extend([cmd("wait", 1), cmd("wait", 2), cmd("wait", 1)])

    object_attack = [*object_prehit, *object_posthit]
    object_miss = [*object_prehit, cmd("wait", 1)]

    background_prehit = [
        cmd("wait", 4),
        cmd("blend", True),
        cmd("opacity", 127),
        cmd("frame", 1, "Background_002"),
        cmd("opacity", 191),
        cmd("frame", 1, "Background_002"),
        cmd("opacity", 223),
        cmd("frame", 1, "Background_003"),
        cmd("opacity", 255),
        cmd("frame", 1, "Background_004"),
        cmd("frame", 1, "Background_006"),
        cmd("opacity", 207),
        cmd("frame", 1, "Background_008"),
        cmd("opacity", 255),
        cmd("wait", 11),
    ]
    background_posthit = [
        cmd("partial_blend", 175),
        cmd("frame", 1, "Background_022"),
        cmd("partial_blend", 207),
        cmd("frame", 1, "Background_022"),
        cmd("partial_blend", 223),
        cmd("frame", 1, "Background_024"),
        cmd("partial_blend", 239),
        cmd("frame", 1, "Background_024"),
        cmd("partial_blend", 0),
        cmd("opacity", 239),
        cmd("frame", 1, "Background_026"),
        cmd("opacity", 223),
        cmd("frame", 1, "Background_028"),
        cmd("opacity", 207),
        cmd("frame", 1, "Background_030"),
        cmd("opacity", 175),
        cmd("frame", 1, "Background_032"),
        cmd("opacity", 127),
        cmd("frame", 1, "Background_032"),
        cmd("wait", 2),
        cmd("wait", 1),
    ]
    background_attack = [*background_prehit, *background_posthit]
    background_miss = [*background_prehit, cmd("wait", 1)]

    white = [255, 255, 255]
    controller_attack = [
        cmd("darken"),
        cmd("wait", 2),
        cmd("pan"),
        cmd("enemy_effect", ALUSQ_OBJECT),
        cmd("enemy_under_effect", ALUSQ_BACKGROUND),
        cmd("wait", 5),
        cmd("sound", "Purge3"),
        cmd("wait", 16),
        cmd("sound", "Fenrir4"),
        cmd("enemy_tint", 8, white),
        cmd("screen_blend", 4, white),
        cmd("spell_hit"),
        cmd("wait", 11),
        cmd("lighten"),
        cmd("wait", 4),
        cmd("pan"),
        cmd("wait", 4),
        cmd("end_parent_loop"),
        cmd("wait", 1),
    ]
    controller_miss = [
        cmd("darken"),
        cmd("wait", 2),
        cmd("pan"),
        cmd("enemy_effect", ALUSQ_OBJECT),
        cmd("enemy_under_effect", ALUSQ_BACKGROUND),
        cmd("wait", 5),
        cmd("sound", "Purge3"),
        cmd("wait", 16),
        cmd("miss"),
        cmd("wait", 1),
        cmd("lighten"),
        cmd("wait", 4),
        cmd("pan"),
        cmd("wait", 4),
        cmd("end_parent_loop"),
        cmd("wait", 1),
    ]

    effects = [
        effect_entry(ALUSQ_CONTROLLER, controller_attack, controller_miss),
        effect_entry(
            ALUSQ_OBJECT,
            object_attack,
            object_miss,
            object_frames,
            object_palette_nid,
        ),
        effect_entry(
            ALUSQ_BACKGROUND,
            background_attack,
            background_miss,
            background_frames,
            background_palette_nid,
        ),
    ]
    palettes = [
        palette_entry(object_palette_nid, object_palette),
        palette_entry(background_palette_nid, background_palette),
    ]
    images = {
        f"{ALUSQ_OBJECT}.png": object_sheet,
        f"{ALUSQ_BACKGROUND}.png": background_sheet,
    }
    return effects, palettes, images


def append_json_items(path: Path, items: Sequence[object]) -> None:
    original = path.read_bytes().decode("utf-8")
    parsed = json.loads(original)
    if not isinstance(parsed, list):
        raise ValueError(f"{path} is not a JSON array")

    closing = original.rfind("]")
    if closing < 0:
        raise ValueError(f"Cannot find closing array bracket in {path}")
    prefix = original[:closing].rstrip()
    newline = "\r\n" if "\r\n" in original else "\n"
    blocks = []
    for item in items:
        serialized = json.dumps(item, ensure_ascii=False, indent=4)
        blocks.append(newline.join("    " + line for line in serialized.splitlines()))
    separator = "," + newline if parsed else newline
    updated = (
        prefix
        + separator
        + ("," + newline).join(blocks)
        + newline
        + "]"
        + newline
    )
    json.loads(updated)

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(updated.encode("utf-8"))
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_output(
    effects_path: Path,
    palettes_path: Path,
    image_dir: Path,
    expected_effects: set[str],
    expected_palettes: set[str],
) -> None:
    effects = json.loads(effects_path.read_text(encoding="utf-8"))
    palettes = json.loads(palettes_path.read_text(encoding="utf-8"))
    effects_by_nid = {effect["nid"]: effect for effect in effects}
    palette_nids = {palette[0] for palette in palettes}
    if not expected_effects <= effects_by_nid.keys():
        raise ValueError("Not all generated effects were saved")
    if not expected_palettes <= palette_nids:
        raise ValueError("Not all generated palettes were saved")

    known_commands = {
        "blend", "darken", "dual_frame", "end_parent_loop", "enemy_effect",
        "enemy_tint", "enemy_under_effect", "frame", "lighten", "miss",
        "opacity", "pan", "partial_blend", "screen_blend", "sound",
        "spell_hit", "under_frame", "wait",
    }
    for nid in expected_effects:
        effect = effects_by_nid[nid]
        frame_names = {frame[0] for frame in effect["frames"]}
        for _palette_name, palette_nid in effect["palettes"]:
            if palette_nid not in palette_nids:
                raise ValueError(f"Missing palette {palette_nid} used by {nid}")
        for pose_name, timeline in effect["poses"]:
            for command_nid, values in timeline:
                if command_nid not in known_commands:
                    raise ValueError(f"Unknown command {command_nid} in {nid}/{pose_name}")
                if command_nid in {"enemy_effect", "enemy_under_effect"}:
                    if values[0] not in effects_by_nid:
                        raise ValueError(f"Missing child effect {values[0]} used by {nid}")
                if command_nid in {"frame", "under_frame"} and values[1] not in frame_names:
                    raise ValueError(f"Missing frame {values[1]} in {nid}")
                if command_nid == "dual_frame":
                    for frame_name in values[1:3]:
                        if frame_name not in frame_names:
                            raise ValueError(f"Missing dual frame {frame_name} in {nid}")

        if effect["frames"]:
            image_path = image_dir / f"{nid}.png"
            with Image.open(image_path) as image:
                for frame_name, rect, _offset in effect["frames"]:
                    left, top, width, height = rect
                    if left < 0 or top < 0 or left + width > image.width or top + height > image.height:
                        raise ValueError(f"Frame {frame_name} is outside {image_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert the two Aqua GBA examples into LT combat effects")
    parser.add_argument("--project", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--skid-source", type=Path, default=SKID_SOURCE)
    parser.add_argument("--alusq-source", type=Path, default=ALUSQ_SOURCE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    effects_path = project / "resources" / "combat_effects" / "combat_effects.json"
    palettes_path = (
        project / "resources" / "combat_palettes" / "palette_data" / "combat_palettes.json"
    )
    image_dir = effects_path.parent

    skid_effects, skid_palettes, skid_images = build_skid(args.skid_source)
    alusq_effects, alusq_palettes, alusq_images = build_alusq(args.alusq_source)
    new_effects = [*skid_effects, *alusq_effects]
    new_palettes = [*skid_palettes, *alusq_palettes]
    new_images = {**skid_images, **alusq_images}

    existing_effects = {
        effect["nid"]
        for effect in json.loads(effects_path.read_text(encoding="utf-8"))
    }
    existing_palettes = {
        palette[0]
        for palette in json.loads(palettes_path.read_text(encoding="utf-8"))
    }
    effect_nids = {effect["nid"] for effect in new_effects}
    palette_nids = {palette[0] for palette in new_palettes}
    collisions = sorted(effect_nids & existing_effects)
    palette_collisions = sorted(palette_nids & existing_palettes)
    image_collisions = sorted(name for name in new_images if (image_dir / name).exists())
    if collisions or palette_collisions or image_collisions:
        raise FileExistsError(
            f"Refusing to overwrite existing resources: "
            f"effects={collisions}, palettes={palette_collisions}, images={image_collisions}"
        )

    print("Effects:", ", ".join(sorted(effect_nids)))
    print("Palettes:", ", ".join(sorted(palette_nids)))
    for name, image in new_images.items():
        print(f"Image: {name} {image.width}x{image.height}")
    if args.dry_run:
        print("Dry run complete; project was not changed.")
        return

    original_effects = effects_path.read_bytes()
    original_palettes = palettes_path.read_bytes()
    created_images: list[Path] = []
    try:
        append_json_items(effects_path, new_effects)
        append_json_items(palettes_path, new_palettes)
        for name, image in new_images.items():
            destination = image_dir / name
            temporary = destination.with_suffix(".tmp.png")
            image.save(temporary, format="PNG")
            os.replace(temporary, destination)
            created_images.append(destination)
        validate_output(
            effects_path,
            palettes_path,
            image_dir,
            effect_nids,
            palette_nids,
        )
    except Exception:
        effects_path.write_bytes(original_effects)
        palettes_path.write_bytes(original_palettes)
        for path in created_images:
            path.unlink(missing_ok=True)
        raise

    print("combat_effects.json SHA256:", sha256(effects_path))
    print("combat_palettes.json SHA256:", sha256(palettes_path))
    print("Conversion complete.")


if __name__ == "__main__":
    main()
