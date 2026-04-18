from typing import Dict

import glob
from PyQt5.QtGui import QImage, qRgb, QColor

from app.editor.tile_editor.autotiles import PaletteData, check_hashes

from app.constants import TILEWIDTH, TILEHEIGHT
from app.utilities.typing import Pos

def load_palettes(fn: str) -> Dict[Pos, PaletteData]:
    palettes = {}
    image = QImage(fn)
    num_tiles_x = image.width() // TILEWIDTH
    num_tiles_y = image.height() // TILEHEIGHT
    for x in range(num_tiles_x):
        for y in range(num_tiles_y):
            rect = (x * TILEWIDTH, y * TILEHEIGHT, TILEWIDTH, TILEHEIGHT)
            palette = image.copy(*rect)
            d = PaletteData(palette)
            palettes[(x, y)] = d
    return palettes

def get_color_exchange(a: PaletteData, b: PaletteData) -> Dict[qRgb, qRgb]:
    exchange = {}
    width, height = a.im.width(), a.im.height()
    for x in range(width):
        for y in range(height):
            color_a = a.im.pixel(x, y)
            color_b = b.im.pixel(x, y)
            exchange[color_a] = color_b
    return exchange

# python -m app.map_maker.scripts.palette_generation.simple_palette_exchanger
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)

    # color_change_these_images = ['app/map_maker/palettes/monastery_outdoors/road.png',
    #                              'app/map_maker/palettes/monastery_outdoors/house.png',
    #                              'app/map_maker/palettes/monastery_outdoors/ruins.png',]
    # color_change_these_images = ['app/map_maker/palettes/autumn_ruins/pool.png',
    #                              'app/map_maker/palettes/autumn_ruins/pool_shading.png',
    #                              'app/map_maker/palettes/autumn_ruins/pool_bridge.png',
    #                              'app/map_maker/palettes/autumn_ruins/pool_autotiles.png']
    # color_change_these_images = ['app/map_maker/palettes/monastery_outdoors/bridge_h.png',
    #                              'app/map_maker/palettes/monastery_outdoors/bridge_v.png',
    #                              'app/map_maker/palettes/monastery_outdoors/castle.png',
    #                              'app/map_maker/palettes/monastery_outdoors/cliff.png',
    #                              'app/map_maker/palettes/monastery_outdoors/forest.png',
    #                              'app/map_maker/palettes/monastery_outdoors/grass.png',
    #                              'app/map_maker/palettes/monastery_outdoors/hill.png',
    #                              'app/map_maker/palettes/monastery_outdoors/house.png',
    #                              'app/map_maker/palettes/monastery_outdoors/mountain.png',
    #                              'app/map_maker/palettes/monastery_outdoors/river.png',
    #                              'app/map_maker/palettes/monastery_outdoors/river_autotiles.png',
    #                              'app/map_maker/palettes/monastery_outdoors/road.png',
    #                              'app/map_maker/palettes/monastery_outdoors/ruins.png',
    #                              'app/map_maker/palettes/monastery_outdoors/sand.png',
    #                              'app/map_maker/palettes/monastery_outdoors/sea.png',
    #                              'app/map_maker/palettes/monastery_outdoors/sea_autotiles.png',
    #                              'app/map_maker/palettes/monastery_outdoors/sparse_forest.png',
    #                              'app/map_maker/palettes/monastery_outdoors/thicket.png',
    #            
    # color_change_these_images = ['app/map_maker/palettes/greysnow_outdoors/desert.png',
    #                              'app/map_maker/palettes/greysnow_outdoors/desert_cliff.png',
    #                              'app/map_maker/palettes/greysnow_outdoors/desert_rock.png']
    color_change_these_images = ['app/map_maker/palettes/desert_ruins/*.png']
    original_palette = 'app/map_maker/palettes/monastery/main.png'
    new_palette = 'app/map_maker/palettes/desert/ImprovedDesert.png'

    change_images = []
    for c in color_change_these_images:
        change_images.extend(glob.glob(c))
    print("Loading original palette...")
    original_palettes = load_palettes(original_palette)
    print("Loading new palette...")
    new_palettes = load_palettes(new_palette)

    palette_exchange: Dict[qRgb, qRgb] = {}
    for ocoord, orig in original_palettes.items():
        for ncoord, new in new_palettes.items():
            if check_hashes(orig, new):
                conv = get_color_exchange(orig, new)
                palette_exchange.update(conv)

    # Remove 0, 0, 0 on both sides
    black = qRgb(0, 0, 0)
    # if black in palette_exchange:
    print(palette_exchange)
    palette_exchange.pop(black)
    for k, v in list(palette_exchange.items()):
        if v == black:
            palette_exchange.pop(k)
    # Print transfers
    for opalette, npalette in palette_exchange.items():
        k = QColor(opalette)
        v = QColor(npalette)
        print(f"({k.red()}, {k.green()}, {k.blue()}) -> ({v.red()}, {v.green()}, {v.blue()})")

    for im_path in change_images[:]:
        print(im_path)
        im = QImage(im_path)
        new_im = im.copy()
        for x in range(im.width()):
            for y in range(im.height()):
                color = im.pixel(x, y)
                new_color = palette_exchange.get(color, color)
                new_im.setPixel(x, y, new_color)
        new_im.save(im_path)

    print("Done!")
