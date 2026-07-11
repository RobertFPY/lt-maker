from typing import Dict

from app.map_maker.painters import CliffPainter
from app.map_maker.palette_collection import Palette
from app.map_maker.pygame_renderers.pygame_palette import get_pygame_palette
from app.map_maker.pygame_renderers.renderer_utils import find_limit16
from app.map_maker.pygame_renderers import SimpleRenderer

class CliffRenderer(SimpleRenderer):
    """
    The specific renderer used from CliffPainter
    """
    def __init__(self, painter: CliffPainter, palette: Palette):
        self.painter = painter
        self.set_palette(palette)

    def set_palette(self, palette: Palette):
        self.palette = get_pygame_palette(palette)
        limit: Dict[int, int] = {i: find_limit16(self.palette.get_full_image(), i) for i in range(16)}
        self.painter.set_limit(limit)
        second_limit: Dict[int, int] = {i: find_limit16(self.palette.get_full_image(), i, self.painter.second_start_px) for i in range(16)}
        self.painter.set_second_limit(second_limit)
