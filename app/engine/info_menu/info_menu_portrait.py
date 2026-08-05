import random

from app.engine import engine
from app import counters
from app.utilities import utils
from app.constants import COLORKEY

class InfoMenuPortrait():
    def __init__(self, portrait, should_blink: bool = False):
        self.portrait = portrait
        if not self.portrait.image:
            self.portrait.image = engine.image_load(self.portrait.full_path)
        # ``Surface.convert`` allocates a complete new portrait surface.  The
        # portrait prefab is shared for the lifetime of the loaded project, so
        # doing that again on every Info-menu open causes a visible Android
        # hitch without changing the resulting image.
        if not getattr(self.portrait, '_info_menu_surface_ready', False):
            self.portrait.image = self.portrait.image.convert()
            engine.set_colorkey(self.portrait.image, COLORKEY, rleaccel=True)
            self.portrait._info_menu_surface_ready = True
        self.main_portrait = engine.subsurface(self.portrait.image, self.portrait.get_face_frame())
        self.mouth_section = engine.subsurface(self.portrait.image, self.portrait.get_neutral_mouth())

        self.should_blink = should_blink
        offset_blinking = range(-2000, 2000, 125)
        self.blink_counter = \
            counters.BlinkCounter(portrait.blink_frames, [7000 + random.choice(offset_blinking), utils.frames2ms(3)])
        self.blink_counter.last_update = engine.get_time()
        self._cached_blink_frame = None
        self._cached_image = None

    def create_image(self):
        blink_frame = self.blink_counter.count if self.should_blink else 0
        if self._cached_image is not None and self._cached_blink_frame == blink_frame:
            return self._cached_image
        main_image = self.main_portrait.copy()

        if self.should_blink and self.blink_counter.count:
            blink_image = engine.subsurface(self.portrait.image,
                                self.portrait.get_blink_frame(self.blink_counter.count-1))
            main_image.blit(blink_image, self.portrait.get_blink_coord())

        main_image.blit(self.mouth_section, self.portrait.get_mouth_coord())
        self._cached_blink_frame = blink_frame
        self._cached_image = main_image
        return main_image

    def update(self):
        self.blink_counter.update(engine.get_time())
