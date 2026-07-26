from app.map_maker.painter_utils import Painter
from app.map_maker.palette_collection import Palette
from app.map_maker.pygame_renderers.pygame_palette import get_pygame_palette
from app.map_maker.pygame_renderers.renderer_utils import find_limit16

from app.map_maker.pygame_renderers import SimpleRenderer8

class SeaRenderer(SimpleRenderer8):
    def __init__(self, painter: Painter, palette: Palette):
        self.painter = painter
        self.set_palette(palette)

    def set_palette(self, palette: Palette):
        self.palette = get_pygame_palette(palette)

        limit = {k: find_limit16(self.palette.get_full_image(), k) for k in range(16)}
        sand_limit = {k: find_limit16(self.palette.get_full_image(), k, self.painter.sand_start_px) for k in range(16)}
        self.painter.set_limit(limit)
        self.painter.sand_limit = sand_limit
