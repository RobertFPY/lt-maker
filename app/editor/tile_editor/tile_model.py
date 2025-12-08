from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage, QPainter, QIcon, QColor

import os

from app.constants import TILEWIDTH, TILEHEIGHT
from app.data.resources.resources import RESOURCES
from app.data.resources.tiles import TileSet, TileMapPrefab

from app.utilities.data import Data
from app.data.database.database import DB

from app.editor.base_database_gui import ResourceCollectionModel
from app.extensions.custom_gui import DeletionTab, DeletionDialog
from app.editor.tilemap_editor import MapEditor
from app.editor.settings import MainSettingsController

from app.utilities import str_utils
import app.editor.utilities as editor_utilities

def read_mapchip_file(filename: str) -> list:
    mapchip = []
    with open(filename, 'rb') as f:
        data = f.read()
    for i in range(0, len(data), 2):
        # Each subtile data has 2 bytes, so 16 bits:     0123 4567 89ab cdef
            #    89ab stores the palette
            #      cd stores the rotation
            #   ef012 stores the row
            #   34567 stores the column
        p = data[i+1] >> 4
        r = data[i+1] >> 2 & 3
        y = (data[i+1] & 3) << 3 | data[i] >> 5
        x = data[i] & 31
        mapchip.append((p, r, x, y))
    return mapchip

def read_palette_file(filename: str) -> list:
    palette = []
    with open(filename, 'rb') as f:
        signature = f.read(8)
        while True:
            chunk_len = int.from_bytes(f.read(4), "big")
            type = f.read(4)
            data = f.read(chunk_len)
            crc = f.read(4)
            if type == b'IEND':
                return
            elif type != b'PLTE':
                continue
            for i in range(0, len(data), 16*3):
                pal = [(data[i+j], data[i+j+1], data[i+j+2]) for j in range(0, 16*3, 3)]
                palette.append(pal)
            return palette

def draw_tileset_from_mapchip(mapchip: list, palette: list, object_palette: QImage) -> QPixmap:
    tileset_size = 32   # tiles
    subtile_size = 8    # px
    colored_im = [object_palette.copy()]
    for pal in palette[1:]:
        conv_dict = dict(zip(palette[0], pal))
        color_transform = editor_utilities.rgb_convert(conv_dict)
        im = editor_utilities.color_convert(object_palette.copy(), color_transform)
        colored_im.append(im)

    new_pix = QPixmap(tileset_size * subtile_size * 2, tileset_size * subtile_size * 2)
    painter = QPainter()
    painter.begin(new_pix)

    for i, subtile in enumerate(mapchip):
        # Each tile has 4 subtiles:
        # top left, top right, bottom left, bottom right
        quadrant = i % 4
        tile_x = i // 4  % tileset_size
        tile_y = i // 4 // tileset_size
        true_x = (tile_x * 2 + quadrant  % 2) * subtile_size
        true_y = (tile_y * 2 + quadrant // 2) * subtile_size

        p, r, x, y = subtile
        im = colored_im[p].copy(x * subtile_size, y * subtile_size, subtile_size, subtile_size)
        painter.drawImage(true_x, true_y, im.mirrored(r % 2, r // 2))
    painter.end()
    return new_pix

class TileSetModel(ResourceCollectionModel):
    def __init__(self, data, window):
        super().__init__(data, window)
        for tileset in self._data:
            tileset.set_pixmap(QPixmap(tileset.full_path))

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole or role == Qt.EditRole:
            tileset = self._data[index.row()]
            text = tileset.nid
            return text
        elif role == Qt.DecorationRole:
            tileset = self._data[index.row()]
            pixmap = tileset.pixmap
            pix = pixmap.scaled(96, 96)
            # pix = pixmap
            return QIcon(pix)
        return None

    def create_new(self):
        settings = MainSettingsController()
        starting_path = settings.get_last_open_path()
        fns, ok = QFileDialog.getOpenFileNames(self.window, "Choose new Tileset", starting_path, "PNG Files (*.png);;Config Files (*.mapchip_config);;All Files(*)")
        new_tileset = None
        if ok:
            if len(fns) == 1 and fns[0].endswith('.mapchip_config'):
                mapchip_config = fns[0]
                parent_dir = os.path.split(fns[0])[0]
                settings.set_last_open_path(parent_dir)
                starting_path = settings.get_last_open_path()
                fn, pok = QFileDialog.getOpenFileName(self.window, "Choose Object Palette", starting_path, "PNG Files (*.png);;All Files(*)")
                if pok:
                    if fn.endswith('.png'):
                        object_palette = fn
                        nid = os.path.split(mapchip_config)[-1][:-15]
                        nid = str_utils.get_next_name(nid, RESOURCES.tilesets.keys())

                        current_proj = settings.get_current_project()
                        if not current_proj:
                            QMessageBox.critical(self.window, "Error!", "Cannot load new tilesets without having saved the project")
                            return

                        mapchip = read_mapchip_file(mapchip_config)
                        if not mapchip:
                            QMessageBox.critical(self.window, "Error!", "Mapchip files must not be empty!")
                            return

                        palette = read_palette_file(object_palette)
                        if not palette:
                            QMessageBox.critical(self.window, "Error!", "PLTE chunk not found. Choose 8-bit PNG files only!")
                            return

                        palette_image = QImage(object_palette)
                        pix = draw_tileset_from_mapchip(mapchip, palette, palette_image)
                        full_path = os.path.join(current_proj, 'resources', 'tilesets', '%s.png' % nid)
                        pix.save(full_path)
                        new_tileset = TileSet(nid, full_path)
                        new_tileset.set_pixmap(pix)
                        RESOURCES.tilesets.append(new_tileset)
                    else:
                        QMessageBox.critical(self.window, "File Type Error!", "Object Palette must be PNG format!")
                    parent_dir = os.path.split(fns[0])[0]
                    settings.set_last_open_path(parent_dir)
                return new_tileset

            for fn in fns:
                if fn.endswith('.png'):
                    nid = os.path.split(fn)[-1][:-4]
                    pix = QPixmap(fn)
                    nid = str_utils.get_next_name(nid, RESOURCES.tilesets.keys())
                    if pix.width() % TILEWIDTH != 0:
                        QMessageBox.critical(self.window, 'Error', "Image width must be exactly divisible by %d pixels!" % TILEWIDTH)
                        continue
                    elif pix.height() % TILEHEIGHT != 0:
                        QMessageBox.critical(self.window, 'Error', "Image height must be exactly divisible by %d pixels!" % TILEHEIGHT)
                        continue
                    new_tileset = TileSet(nid, fn)
                    new_tileset.set_pixmap(pix)
                    RESOURCES.tilesets.append(new_tileset)
                else:
                    QMessageBox.critical(self.window, "File Type Error!", "Tileset must be PNG format!")
            parent_dir = os.path.split(fns[-1])[0]
            settings.set_last_open_path(parent_dir)
        return new_tileset

    def delete(self, idx):
        # Check to see what is using me?
        res = self._data[idx]
        nid = res.nid
        affected_tilemaps = [tilemap for tilemap in RESOURCES.tilemaps if nid in tilemap.tilesets]
        if affected_tilemaps:
            model = TileMapModel
            msg = "Deleting Tileset <b>%s</b> would affect these tilemaps." % nid
            deletion_tab = DeletionTab(affected_tilemaps, model, msg, "Tilemaps")
            ok = DeletionDialog.inform([deletion_tab], self.window)
            if ok:
                self.delete_tileset_from_tilemaps(nid)
            else:
                return
        super().delete(idx)

    def delete_tileset_from_tilemaps(self, tileset_nid):
        # What uses tilesets
        # Tilemaps use tilesets
        for tilemap in RESOURCES.tilemaps:
            if tileset_nid in tilemap.tilesets:
                tilemap.tilesets.remove(tileset_nid)
            for layer in tilemap.layers:
                for coord, tile_sprite in list(layer.sprite_grid.items()):
                    if tile_sprite.tileset_nid == tileset_nid:
                        # Delete all places that tileset is used
                        del layer.sprite_grid[coord]

    def on_nid_changed(self, old_nid, new_nid):
        # What uses tilesets
        # Tilemaps use tilesets
        for tilemap in RESOURCES.tilemaps:
            for idx, nid in enumerate(tilemap.tilesets):
                if nid == old_nid:
                    tilemap.tilesets[idx] = new_nid
            for layer in tilemap.layers:
                for coord, tile_sprite in layer.sprite_grid.items():
                    if tile_sprite.tileset_nid == old_nid:
                        tile_sprite.tileset_nid = new_nid

def create_tilemap_pixmap(tilemap):
    base_layer = tilemap.layers.get('base')
    image = QImage(tilemap.width * TILEWIDTH,
                   tilemap.height * TILEHEIGHT,
                   QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 255))

    painter = QPainter()
    painter.begin(image)
    for coord, tile_sprite in base_layer.sprite_grid.items():
        tileset = RESOURCES.tilesets.get(tile_sprite.tileset_nid)
        if not tileset:
            continue
        if not tileset.pixmap:
            tileset.set_pixmap(QPixmap(tileset.full_path))
        pix = tileset.get_pixmap(tile_sprite.tileset_position)
        if pix:
            painter.drawImage(coord[0] * TILEWIDTH,
                              coord[1] * TILEHEIGHT,
                              pix.toImage())
    painter.end()
    tilemap.pixmap = QPixmap.fromImage(image)
    return tilemap.pixmap

class TileMapModel(ResourceCollectionModel):
    def __init__(self, data, window):
        super().__init__(data, window)
        for tilemap in self._data:
            create_tilemap_pixmap(tilemap)

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole or role == Qt.EditRole:
            tilemap = self._data[index.row()]
            text = tilemap.nid
            return text
        elif role == Qt.DecorationRole:
            tilemap = self._data[index.row()]
            pixmap = tilemap.pixmap
            if pixmap:
                pix = pixmap.scaled(96, 96)
                return QIcon(pix)
        return None

    def create_new(self):
        new_nid = str_utils.get_next_name('New Tilemap', self._data.keys())
        new_tilemap = TileMapPrefab(new_nid)
        map_editor = MapEditor(self.window, new_tilemap)
        map_editor.exec_()
        create_tilemap_pixmap(new_tilemap)
        RESOURCES.tilemaps.append(new_tilemap)
        self.layoutChanged.emit()

    def delete(self, idx):
        # Check to see what is using me?
        res = self._data[idx]
        nid = res.nid
        affected_levels = [level for level in DB.levels if level.tilemap == nid]
        if affected_levels:
            from app.editor.global_editor.level_menu import LevelModel
            model = LevelModel
            msg = "Deleting Tilemap <b>%s</b> would affect these levels." % nid
            deletion_tab = DeletionTab(affected_levels, model, msg, "Levels")
            ok = DeletionDialog.inform([deletion_tab], self.window)
            if ok:
                pass
            else:
                return
        super().delete(idx)

    def on_nid_changed(self, old_nid, new_nid):
        # What uses tilemaps
        # Levels use tilemaps
        for level in DB.levels:
            if level.tilemap == old_nid:
                level.tilemap = new_nid

    def duplicate(self, tilemap):
        idx = self._data.index(tilemap.nid)
        new_nid = str_utils.get_next_name(tilemap.nid, self._data.keys())
        # Duplicate by serializing and then deserializing
        ser_tilemap = tilemap.save()
        new_tilemap = TileMapPrefab.restore(ser_tilemap)
        new_tilemap.nid = new_nid
        self._data.insert(idx + 1, new_tilemap)
        create_tilemap_pixmap(new_tilemap)
        self.layoutChanged.emit()
