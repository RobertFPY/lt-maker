"""Generate LT-maker info-menu title sprites (e.g. info_title_skills.png).

The info-menu page titles (``sprites/info_menu/info_title_*.png``) are built from
the project's ``chapter`` bitmap font, recoloured to a gold palette, given a 1px
black outline, and stacked into 8 animation frames whose fill colour shimmers
from pale cream down to deep gold.

This script reproduces that exact look so you can mint new titles ("Skills",
"Spells", ...) that blend in with the originals.

Usage
-----
    python generate_info_title.py "Skills"
    python generate_info_title.py "Spells" --name info_title_spellbook
    python generate_info_title.py "Skills" --out sprites/info_menu/info_title_skills.png
    python generate_info_title.py "Magic" --style gold --scale 6 --preview

Notes
-----
* Only Pillow is required (``pip install pillow``); the game engine is not loaded.
* The ``chapter`` font only contains the glyphs listed in ``chapter.idx``
  (A-Z, a-z, 0-9 and ``- : ' . , ! ?``). Unknown characters fall back to a space.
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, List, Tuple

from PIL import Image

RGB = Tuple[int, int, int]

# --- Project paths -----------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(PROJECT_ROOT, "default.ltproj", "resources", "fonts")
DEFAULT_OUT_DIR = os.path.join(PROJECT_ROOT, "sprites", "info_menu")

# --- Source colours in the bare ``chapter`` font -----------------------------
# These are the only non-transparent colours present in the high (top) layer of
# each glyph in chapter.png.
SRC_EDGE = (0xF8, 0xF8, 0xF8)   # the lit top/left edge of every stroke
SRC_FILL = (0xA8, 0xB0, 0x80)   # the main body fill -> becomes the shimmer
SRC_ACCENT = {                  # darker corner/highlight pixels -> solid accent
    (0xE8, 0xF0, 0x60),
    (0x80, 0x80, 0x60),
    (0x58, 0x58, 0x40),
}

OUTLINE = (0x00, 0x00, 0x00)

# --- Target palettes ---------------------------------------------------------
# A "style" maps the three logical roles (edge / accent / fill) to output
# colours. ``fill_frames`` is the per-frame shimmer sequence (8 frames).

GOLD_FILL_FRAMES: List[RGB] = [
    (0xF8, 0xF8, 0xC8),
    (0xF8, 0xF8, 0xB8),
    (0xF8, 0xF0, 0xA0),
    (0xF8, 0xE8, 0x88),
    (0xF8, 0xE0, 0x78),
    (0xF8, 0xE0, 0x60),
    (0xF8, 0xD8, 0x48),
    (0xF8, 0xD0, 0x30),
]

# A cool blue variant, matching the "Weapon and support Level" title's fill.
BLUE_FILL_FRAMES: List[RGB] = [
    (0xE0, 0xF0, 0xF8),
    (0xD8, 0xEC, 0xF8),
    (0xD0, 0xE8, 0xF8),
    (0xC8, 0xE0, 0xF8),
    (0xC0, 0xD8, 0xF8),
    (0xC8, 0xE0, 0xF8),
    (0xD0, 0xE8, 0xF8),
    (0xD8, 0xEC, 0xF8),
]

STYLES: Dict[str, Dict] = {
    "gold": {
        "edge": (0xF0, 0xF0, 0xF8),
        "accent": (0xB0, 0x90, 0x28),
        "fill_frames": GOLD_FILL_FRAMES,
    },
    "blue": {
        "edge": (0xF0, 0xF0, 0xF8),
        "accent": (0xB0, 0x90, 0x28),
        "fill_frames": BLUE_FILL_FRAMES,
    },
}


def parse_idx(path: str) -> Tuple[int, int, Dict[str, Tuple[int, int, int]]]:
    """Parse a ``*.idx`` font index into (cell_w, cell_h, {char: (x, y, advance)})."""
    lines = open(path, encoding="utf-8").read().splitlines()
    # Line 0 may be the mode flag ("stacked"); width/height follow.
    cell_w = cell_h = None
    table: Dict[str, Tuple[int, int, int]] = {}
    for ln in lines:
        if not ln.strip():
            continue
        parts = ln.split()
        key = parts[0]
        if key == "stacked":
            continue
        if key == "width":
            cell_w = int(parts[1])
            continue
        if key == "height":
            cell_h = int(parts[1])
            continue
        # Glyph rows: "<char> <col> <row> <advance>" (space is spelled out).
        if key == "space":
            char = " "
            col, row, adv = parts[1], parts[2], parts[3]
        else:
            char = key
            col, row, adv = parts[1], parts[2], parts[3]
        table[char] = (int(col) * cell_w, int(row) * cell_h, int(adv))
    if cell_w is None or cell_h is None:
        raise ValueError(f"Missing width/height in {path}")
    return cell_w, cell_h, table


def map_color(rgb: RGB, edge: RGB, accent: RGB, fill: RGB) -> RGB:
    if rgb == SRC_EDGE:
        return edge
    if rgb == SRC_FILL:
        return fill
    if rgb in SRC_ACCENT:
        return accent
    # Any stray anti-alias pixel: treat as fill so nothing is lost.
    return fill


def build_glyph_tile(char: str, png: Image.Image, cell_w: int, cell_h: int,
                     table: Dict, edge: RGB, accent: RGB, fill: RGB
                     ) -> Tuple[Image.Image, int]:
    """Recolour a single glyph (high layer only) and wrap it in a 1px outline."""
    cx, cy, adv = table.get(char, table.get(" ", (0, 0, 4)))
    src = png.crop((cx, cy, cx + cell_w, cy + cell_h))
    sp = src.load()

    tile = Image.new("RGBA", (cell_w + 2, cell_h + 2), (0, 0, 0, 0))
    tp = tile.load()

    colored: Dict[Tuple[int, int], RGB] = {}
    for y in range(cell_h):
        for x in range(cell_w):
            r, g, b, a = sp[x, y]
            if a == 0:
                continue
            colored[(x + 1, y + 1)] = map_color((r, g, b), edge, accent, fill)

    # Black outline first (8-directional), then the glyph on top.
    for (x, y) in colored:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (x + dx, y + dy) not in colored:
                    tp[x + dx, y + dy] = OUTLINE + (255,)
    for (x, y), col in colored.items():
        tp[x, y] = col + (255,)

    return tile, adv


def render_frame(text: str, png: Image.Image, cell_w: int, cell_h: int,
                 table: Dict, edge: RGB, accent: RGB, fill: RGB,
                 letter_spacing: int) -> Image.Image:
    total = sum(table.get(c, table.get(" "))[2] + letter_spacing for c in text)
    frame = Image.new("RGBA", (total + 2, cell_h + 2), (0, 0, 0, 0))
    x = 0
    for c in text:
        tile, adv = build_glyph_tile(c, png, cell_w, cell_h, table, edge, accent, fill)
        frame.alpha_composite(tile, (x, 0))
        x += adv + letter_spacing
    return frame


def generate(text: str, style: str = "gold", font: str = "chapter",
             letter_spacing: int = 0) -> Image.Image:
    """Return the finished, 8-frame stacked title sprite for ``text``."""
    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Choices: {', '.join(STYLES)}")
    spec = STYLES[style]
    cell_w, cell_h, table = parse_idx(os.path.join(FONT_DIR, f"{font}.idx"))
    png = Image.open(os.path.join(FONT_DIR, f"{font}.png")).convert("RGBA")

    frames = [
        render_frame(text, png, cell_w, cell_h, table,
                     spec["edge"], spec["accent"], fill, letter_spacing)
        for fill in spec["fill_frames"]
    ]

    # Trim every frame to a single shared bounding box so they stay aligned.
    bbox = None
    for f in frames:
        b = f.getbbox()
        if b is None:
            continue
        bbox = b if bbox is None else (
            min(bbox[0], b[0]), min(bbox[1], b[1]),
            max(bbox[2], b[2]), max(bbox[3], b[3]),
        )
    if bbox is None:
        raise ValueError("Nothing was rendered (empty text?)")
    frames = [f.crop(bbox) for f in frames]

    fw, fh = frames[0].size
    out = Image.new("RGBA", (fw, fh * len(frames)), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        out.alpha_composite(f, (0, i * fh))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate an LT-maker info-menu title sprite.")
    ap.add_argument("text", help='The title text, e.g. "Skills".')
    ap.add_argument("--name", help="Output file stem, e.g. info_title_skills "
                                    "(default: info_title_<slug>).")
    ap.add_argument("--out", help="Explicit output path (overrides --name/--dir).")
    ap.add_argument("--dir", default=DEFAULT_OUT_DIR,
                    help="Output directory (default: sprites/info_menu).")
    ap.add_argument("--style", default="gold", choices=sorted(STYLES),
                    help="Colour style (default: gold).")
    ap.add_argument("--font", default="chapter", help="Font stem (default: chapter).")
    ap.add_argument("--letter-spacing", type=int, default=0,
                    help="Extra pixels between glyphs (default: 0).")
    ap.add_argument("--scale", type=int, default=1,
                    help="Upscale factor for the saved image (default: 1 = native).")
    ap.add_argument("--preview", action="store_true",
                    help="Also save a 6x nearest-neighbour preview next to the output.")
    args = ap.parse_args()

    img = generate(args.text, style=args.style, font=args.font,
                   letter_spacing=args.letter_spacing)

    if args.out:
        out_path = args.out
    else:
        stem = args.name or ("info_title_" + _slug(args.text))
        out_path = os.path.join(args.dir, stem + ".png")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    saved = img
    if args.scale > 1:
        saved = img.resize((img.width * args.scale, img.height * args.scale), Image.NEAREST)
    saved.save(out_path)
    print(f"Saved {out_path}  ({img.width}x{img.height}, {len(GOLD_FILL_FRAMES)} frames)")

    if args.preview:
        prev = img.resize((img.width * 6, img.height * 6), Image.NEAREST)
        prev_path = os.path.splitext(out_path)[0] + "_preview.png"
        prev.save(prev_path)
        print(f"Saved {prev_path}")


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


if __name__ == "__main__":
    main()
