import os
import shutil

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon, QImage, QColor, QPainter

from app.data.resources.portraits import PortraitPrefab, GBA_PORTRAIT_WIDTH, GBA_PORTRAIT_HEIGHT
from app.data.resources.resources import RESOURCES

from app.utilities.data import Data
from app.data.database.database import DB

from app.extensions.custom_gui import DeletionTab, DeletionDialog
from app.editor.base_database_gui import ResourceCollectionModel
from app.editor.settings import MainSettingsController
from app.utilities import str_utils, utils
from app.utilities.typing import NID

import app.editor.utilities as editor_utilities

def get_chibi(portrait_nid):
    res = RESOURCES.portraits.get(portrait_nid)
    if not res:
        return None
    if not res.pixmap:
        res.pixmap = QPixmap(res.full_path)
    pixmap = res.pixmap.copy(*res.get_minimug())
    pixmap = QPixmap.fromImage(editor_utilities.convert_colorkey(pixmap.toImage()))
    return pixmap

def auto_frame_portrait(portrait: PortraitPrefab, progress_dialog: QProgressDialog = None):
    def test_similarity(im1: QImage, im2: QImage, size: tuple) -> int:
        diff = 0
        for x, y in utils.itergrid(*size):
            color1 = im1.pixel(x, y)  # Returns QRgb
            color2 = im2.pixel(x, y)
            # If pixel is transparent then pixel is matching
            if color1 != editor_utilities.qCOLORKEY:
                diff += color1 ^ color2
        return diff

    if progress_dialog:
        progress_dialog.setValue(1)
        if progress_dialog.wasCanceled():
            return
    if not portrait.pixmap:
        portrait.pixmap = QPixmap(portrait.full_path)
    pixmap = portrait.pixmap
    blink_frame1 = QImage(pixmap.copy(*portrait.get_blink_frame(0)))
    mouth_frame1 = QImage(pixmap.copy(*portrait.get_mouth_frame(0)))
    main_frame = QImage(pixmap.copy(*portrait.get_face_frame()))
    best_blink_similarity = portrait.blink_size[0] * portrait.blink_size[1] * 128**3
    best_mouth_similarity = portrait.mouth_size[0] * portrait.mouth_size[1] * 128**3
    best_blink_pos = [0, 0]
    best_mouth_pos = [0, 0]

    if progress_dialog:
        progress_dialog.setLabelText("Auto-guessing Blink Frame Offset...")
        progress_dialog.setValue(10)
        if progress_dialog.wasCanceled():
            return
    for x, y in utils.itergrid(*utils.tuple_sub(portrait.face_size, portrait.blink_size)):
        sub_frame = main_frame.copy(x, y, *portrait.blink_size)
        blink_similarity = test_similarity(blink_frame1, sub_frame, portrait.blink_size)
        if blink_similarity < best_blink_similarity:
            best_blink_similarity = blink_similarity
            best_blink_pos = (x, y)

    if progress_dialog:
        progress_dialog.setLabelText("Auto-guessing Mouth Frame Offset...")
        progress_dialog.setValue(50)
        if progress_dialog.wasCanceled():
            return
    for x, y in utils.itergrid(*utils.tuple_sub(portrait.face_size, portrait.mouth_size)):
        sub_frame = main_frame.copy(x, y, *portrait.mouth_size)
        mouth_similarity = test_similarity(mouth_frame1, sub_frame, portrait.mouth_size)
        if mouth_similarity < best_mouth_similarity:
            best_mouth_similarity = mouth_similarity
            best_mouth_pos = (x, y)

    portrait.blinking_offset = best_blink_pos
    portrait.smiling_offset = best_mouth_pos
    if progress_dialog:
        progress_dialog.setValue(100)

def auto_colorkey(portrait: PortraitPrefab):
    if not portrait.pixmap:
        portrait.pixmap = QPixmap(portrait.full_path)
    im = portrait.pixmap.toImage()
    if im.pixel(0, 0) != editor_utilities.qCOLORKEY:
        im = editor_utilities.color_convert(im, {im.pixel(0, 0): editor_utilities.qCOLORKEY})
        # since we're messing with data, let's try to be atomic
        try:
            shutil.copyfile(portrait.full_path, portrait.full_path + '.bak')
        except:
            raise IOError("failed to create backup, aborting auto-colorkey")
        os.remove(portrait.full_path)
        try:
            im.save(portrait.full_path)
            portrait.pixmap = QPixmap(portrait.full_path)
            portrait.image = None # reset this so the engine will know to reload
        except:
            shutil.move(portrait.full_path + '.bak', portrait.full_path)
            raise IOError("some file operation failed, aborting auto-colorkey")
        os.remove(portrait.full_path + '.bak')

def import_gba_portrait(portrait: PortraitPrefab) -> None:
    if not portrait.pixmap:
        portrait.pixmap = QPixmap(portrait.full_path)
    gba_pix = portrait.pixmap
    minimug = gba_pix.copy(96, 16, 32, 32)
    face_frame = gba_pix.copy(0, 0, 96, 80)
    blink_frames = gba_pix.copy(96, 48, 32, 32)
    mouth_frames = gba_pix.copy(0, 80, 128, 32)

    new_pix = QPixmap(160, 112)
    new_pix.fill(QColor(editor_utilities.qCOLORKEY))
    painter = QPainter()
    painter.begin(new_pix)
    painter.drawPixmap(128, 80, minimug)
    painter.drawPixmap(  0, 80, mouth_frames)
    painter.drawPixmap(128, 48, blink_frames)
    painter.drawPixmap( 32,  0, face_frame)
    painter.end()

    try:
        tokens = portrait.full_path.split('.')
        new_path = '%s_lt.%s' % ('.'.join(tokens[:-1]), tokens[-1])
        new_pix.save(new_path)
        portrait.pixmap = QPixmap(new_path)
        portrait.full_path = new_path
        portrait.image = None # reset this so the engine will know to reload
    except:
        raise IOError("some file operation failed, aborted")

def create_new(window):
    settings = MainSettingsController()
    starting_path = settings.get_last_open_path()
    fns, ok = QFileDialog.getOpenFileNames(window, "Select Portraits", starting_path, "PNG Files (*.png);;All Files(*)")
    new_portraits = []
    if ok:
        for fn in fns:
            if fn.endswith('.png'):
                nid = os.path.split(fn)[-1][:-4]
                pix = QPixmap(fn)
                existing_nids = [d.nid for d in RESOURCES.portraits] + [p.nid for p in new_portraits]
                nid = str_utils.get_next_name(nid, existing_nids)
                if pix.width() >= GBA_PORTRAIT_WIDTH and pix.height() >= GBA_PORTRAIT_HEIGHT:
                    new_portrait = PortraitPrefab(nid, fn, pix)
                    if pix.width() == GBA_PORTRAIT_WIDTH and pix.height() == GBA_PORTRAIT_HEIGHT:   # must be GBA format then
                        # Swap to use colorkey color if it's not
                        auto_colorkey(new_portrait)
                        import_gba_portrait(new_portrait)
                        auto_frame_portrait(new_portrait)
                    else:   # new LT format, which must be at least 160x112px
                        new_portrait.full_size = (pix.width(), pix.height())
                        new_portrait.face_size = (pix.width() - new_portrait.blink_size[0],
                                                  pix.height() - new_portrait.mouth_size[1]*2)
                        new_portrait.chibi_coord = utils.tuple_sub(new_portrait.full_size, (32, 32))
                    new_portraits.append(new_portrait)
                else:
                    QMessageBox.critical(window, "Error", "Image is not correct size (at least 128x112 px)")
            else:
                QMessageBox.critical(window, "File Type Error!", "Portrait must be PNG format!")
        parent_dir = os.path.split(fns[-1])[0]
        settings.set_last_open_path(parent_dir)
    return new_portraits

def check_delete(nid: NID, window) -> bool:
    # Check to see what is using me?
    affected_units = [unit for unit in DB.units if unit.portrait_nid == nid]
    if affected_units:
        from app.editor.unit_editor.unit_model import UnitModel
        model = UnitModel
        msg = "Deleting Portrait <b>%s</b> would affect these units." % nid
        deletion_tab = DeletionTab(affected_units, model, msg, "Units")
        return DeletionDialog.inform([deletion_tab], window)
    return True

def on_delete(nid: NID):
    # What uses portraits
    # Units
    for unit in DB.units:
        if unit.portrait_nid == nid:
            unit.portrait_nid = None

def on_nid_changed(old_nid, new_nid):
    # What uses portraits
    # Units (Later Dialogues)
    for unit in DB.units:
        if unit.portrait_nid == old_nid:
            unit.portrait_nid = new_nid

class PortraitModel(ResourceCollectionModel):
    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            portrait = self._data[index.row()]
            text = portrait.nid
            return text
        elif role == Qt.DecorationRole:
            portrait = self._data[index.row()]
            if not portrait.pixmap:
                portrait.pixmap = QPixmap(portrait.full_path)
            pixmap = portrait.pixmap
            chibi = pixmap.copy(*portrait.get_minimug())
            chibi = QPixmap.fromImage(editor_utilities.convert_colorkey(chibi.toImage()))
            return QIcon(chibi)
        elif role == Qt.EditRole:
            portrait = self._data[index.row()]
            text = portrait.nid
            return text
        return None