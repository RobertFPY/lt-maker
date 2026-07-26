from app.map_maker.painter_utils import Painter
from app.map_maker.palette_collection import Palette
from app.map_maker.pygame_renderers.pygame_palette import get_pygame_palette
from app.map_maker.pygame_renderers import SimpleRenderer

class MountainRenderer(SimpleRenderer):
    def __init__(self, painter: Painter, palette: Palette):
        self.painter = painter
        self.palette = get_pygame_palette(palette)
        # No Qt event loop in the engine, so the painter solves
        # mountain groups synchronously during single_process
        self.painter.gui_processing = False
