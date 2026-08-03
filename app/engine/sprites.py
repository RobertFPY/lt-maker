import os

from app.sprites import SPRITES

from app.engine import engine

_images_loaded = False
_optimized_display_format = None


def _has_writable_image(sprite) -> bool:
    descriptor = getattr(type(sprite), "image", None)
    return not isinstance(descriptor, property) or descriptor.fset is not None


def _optimize_loaded_images(display_format) -> None:
    for sprite in SPRITES.values():
        # SpecialSprite lazily converts its generated surface through a
        # read-only image property. Accessing it is enough; assigning back
        # would crash Android startup.
        if _has_writable_image(sprite) and sprite.image is not None:
            sprite.image = engine.convert_for_display(sprite.image)


def load_images(force: bool = False, optimize_for_display: bool = False):
    global _images_loaded, _optimized_display_format
    # RESOURCES.load() can replace every BasicSprite through
    # app.sprites.reset(). In that case the module-level flag is still True,
    # but the new sprite objects have not been decoded yet.
    all_images_present = all(
        not sprite.full_path or sprite.image is not None
        for sprite in SPRITES.values()
    )
    display_format = (
        engine.display_format_signature() if optimize_for_display else None
    )
    if _images_loaded and all_images_present and not force:
        if display_format and display_format != _optimized_display_format:
            _optimize_loaded_images(display_format)
            _optimized_display_format = display_format
        return
    for sprite in SPRITES.values():
        if sprite.full_path and _has_writable_image(sprite):
            sprite.image = engine.image_load(sprite.full_path)
    _images_loaded = True
    if display_format:
        _optimize_loaded_images(display_format)
        _optimized_display_format = display_format

# Desktop modules historically received decoded surfaces when they imported
# app.engine.sprites. Keep that behavior so module/class attributes cannot
# permanently cache None before driver.start(). Android must wait until
# driver.start() installs its runtime image loader.
if not os.environ.get("ANDROID_ARGUMENT"):
    load_images()
