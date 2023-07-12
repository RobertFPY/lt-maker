from PyQt5.QtGui import QIcon, QPixmap, QColor
from PyQt5.QtCore import Qt

from app.data.database.database import DB

from app.editor.base_database_gui import DragDropCollectionModel

class TerrainModel(DragDropCollectionModel):
    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            terrain = self._data[index.row()]
            text = terrain.nid + " : " + terrain.name
            return text
        elif role == Qt.DecorationRole:
            terrain = self._data[index.row()]
            color = terrain.color
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(color[0], color[1], color[2]))
            return QIcon(pixmap)
        return None

    def create_new(self):
        new_terrain = DB.terrain.create_new(DB)
        return new_terrain
