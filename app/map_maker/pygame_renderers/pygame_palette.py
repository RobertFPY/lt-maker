from __future__ import annotations
from typing import TYPE_CHECKING, Dict

from dataclasses import dataclass

import pygame

from app.utilities.typing import Pos

from app.map_maker.painter_utils import Painter
from app.map_maker.pygame_renderers.renderer_utils import get_image8, get_image16
if TYPE_CHECKING:
    from app.map_maker.palette_collection import Palette, PaletteCollection

@dataclass
class PygamePalette:
    parent: PaletteCollection
    fn: str
    autotile_fn: str = None
    shading_fn: str = None
    image: pygame.Surface = None
    autotile_image: pygame.Surface = None
    shading_image: pygame.Surface = None

    def get_full_image(self) -> pygame.Surface:
        if self.image is None:
            self.image = pygame.image.load(self.fn)
        return self.image

    def get_image16(self, painter: Painter, coord: Pos, autotile_num: int) -> pygame.Surface:
        if self.image is None:
            self.image = pygame.image.load(self.fn)
        if painter.has_autotiles() and coord in painter.autotiles:
            column = painter.autotiles[coord]
            if self.autotile_image is None:
                self.autotile_image = pygame.image.load(self.autotile_fn)
            return get_image16(self.autotile_image, (column, autotile_num))
        else:
            return get_image16(self.image, coord)

    def get_shading_image16(self, painter: Painter, coord: Pos) -> pygame.Surface:
        if self.shading_image is None:
            self.shading_image = pygame.image.load(self.shading_fn)
        return get_image16(self.shading_image, coord)

    def subsurface8(self, painter: Painter, coord: Pos, autotile_num: int) -> pygame.Surface:
        if self.image is None:
            self.image = pygame.image.load(self.fn)
        if painter.has_autotiles() and coord in painter.autotiles:
            column = painter.autotiles[coord]
            if self.autotile_image is None:
                self.autotile_image = pygame.image.load(self.autotile_fn)
            return get_image8(self.autotile_image, (column, autotile_num))
        else:
            return get_image8(self.image, coord)

    def get_image8(
            self, painter: Painter,
            coord1: Pos, coord2: Pos, coord3: Pos, coord4: Pos,
            autotile_num: int) -> pygame.Surface:
        base_image = pygame.Surface((16, 16), pygame.SRCALPHA, 32)
        topleft = self.subsurface8(painter, coord1, autotile_num)
        topright = self.subsurface8(painter, coord2, autotile_num)
        bottomright = self.subsurface8(painter, coord3, autotile_num)
        bottomleft = self.subsurface8(painter, coord4, autotile_num)
        base_image.blit(topleft, (0, 0))
        base_image.blit(topright, (8, 0))
        base_image.blit(bottomleft, (0, 8))
        base_image.blit(bottomright, (8, 8))
        return base_image

_pygame_palette_cache: Dict[int, PygamePalette] = {}

def get_pygame_palette(palette: Palette) -> PygamePalette:
    """Wraps a framework-agnostic Palette in a PygamePalette (cached by identity
    so the underlying images are only loaded once per palette)."""
    key = id(palette)
    if key not in _pygame_palette_cache:
        _pygame_palette_cache[key] = PygamePalette(
            palette.parent, palette.fn, palette.autotile_fn, palette.shading_fn)
    return _pygame_palette_cache[key]
