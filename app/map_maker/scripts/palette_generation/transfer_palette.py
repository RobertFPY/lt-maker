from typing import Dict

import glob
from PyQt5.QtGui import QImage, QPainter

from app.editor.tile_editor.autotiles import PaletteData, check_hashes

from app.constants import TILEWIDTH, TILEHEIGHT
from app.utilities.typing import Pos

def load_palettes(fn: str) -> Dict[Pos, PaletteData]:
    palettes = {}
    image = QImage(fn)
    num_tiles_x = image.width() // (TILEWIDTH // 2)
    num_tiles_y = image.height() // (TILEHEIGHT // 2)
    for x in range(num_tiles_x):
        for y in range(num_tiles_y):
            rect = (x * (TILEWIDTH // 2), y * (TILEHEIGHT // 2), TILEWIDTH // 2, TILEHEIGHT // 2)
            palette = image.copy(*rect)
            d = PaletteData(palette)
            palettes[(x, y)] = d
    return palettes

# python -m app.map_maker.scripts.palette_generation.transfer_palette
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)

    color_change_these_images = ['app/map_maker/palettes/greysnow_outdoors/*.png']
    original_image = 'app/map_maker/palettes/monastery_outdoors/main.png'
    new_image = 'app/map_maker/palettes/Snow_Ruins.png'

    change_images = []
    for c in color_change_these_images:
        change_images.extend(glob.glob(c))
    print("Loading original palette...")
    original_palettes = load_palettes(original_image)
    print("Loading new palette...")
    new_palettes = load_palettes(new_image)

    for im_path in change_images[:]:
        print(im_path)
        im = QImage(im_path)
        new_im = im.copy()
        painter = QPainter(new_im)
        num_tiles_x = im.width() // (TILEWIDTH // 2)
        num_tiles_y = im.height() // (TILEHEIGHT // 2)
        for x in range(num_tiles_x):
            for y in range(num_tiles_y):
                rect = (x * TILEWIDTH // 2, y * TILEHEIGHT // 2, TILEWIDTH // 2, TILEHEIGHT // 2)
                pal = im.copy(*rect)
                d = PaletteData(pal)
                # Skip palettes with one or less colors
                if len(d.uniques) <= 1:
                    continue
                # Match where this palette is found in original image
                for ocoord, opalette in original_palettes.items():
                    if check_hashes(opalette, d):
                        # new_im.paste(new_palettes[ocoord].im)
                        painter.drawImage(rect[0], rect[1], new_palettes[ocoord].im)
                        break
                else:
                    print(f"Could not find sprite at {rect[0]}, {rect[1]}.")
        painter.end()
        new_im.save(im_path)
    print("Done!")
