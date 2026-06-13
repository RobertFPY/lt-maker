from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, \
    QDialog, QAbstractItemView, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHeaderView
from app.data.resources.resources import RESOURCES
from app.extensions.custom_gui import ResourceTableView, MultiselectTableView
from app.editor.data_editor import SingleResourceEditor, MultiResourceEditor
from app.editor.sound_editor.sound_model import SFXModel, MusicModel
from app.editor import table_model
from app.editor.sound_editor.sound_player import SoundPlayer


class SoundTab(QWidget):
    def __init__(self, data, title, model, view, parent=None):
        super().__init__(parent)
        self.window = parent
        self._data = data
        self.title = title

        self.setWindowTitle(self.title)
        self.setStyleSheet("font: 10pt;")

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        self.setMinimumWidth(360)

        self.model = model(data, self)
        self.proxy_model = table_model.ProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.view = view(None, self)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setModel(self.proxy_model)
        self.view.setSortingEnabled(True)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.view.horizontalHeader().setMaximumSectionSize(250)
        # Remove edit on double click
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.display = self.view

        self.layout.addWidget(self.view)

        # Sound Player UI
        self.sound_player_widget = SoundPlayer(self.view, self.layout)

        # Add or Mofidy UI
        hboxItem = QHBoxLayout()

        self.button = QPushButton("Add Track (.ogg)")
        self.button.clicked.connect(self.append)
        hboxItem.addWidget(self.button)

        self.modify_button = QPushButton("Modify Track")
        self.modify_button.setEnabled(False)
        self.modify_button.clicked.connect(self.modify)
        hboxItem.addWidget(self.modify_button)

        self.layout.addLayout(hboxItem)

        selection_model = self.view.selectionModel()
        selection_model.selectionChanged.connect(self.on_select)

        # Stop audio player whenever closing SoundTab
        if self.window:
            self.window.finished.connect(self.sound_player_widget.stop_track_on_close_event)

    def append(self):
        last_index = self.model.append()
        if last_index:
            self.view.setCurrentIndex(last_index)

    def reset(self):
        pass

    def update_list(self):
        pass

    def get_selected(self):
        select = self.display.selectionModel()
        indices = select.selectedRows()
        return [self._data[self.proxy_model.mapToSource(index).row()] for index in indices]
    
    def modify(self, index):
        proxy_indices = self.display.selectionModel().selectedRows()
        if proxy_indices:
            real_indices = [self.proxy_model.mapToSource(index) for index in proxy_indices]
            self.model.modify(real_indices)

    def on_select(self):
        has_selection = self.view.selectionModel().hasSelection()
        self.modify_button.setEnabled(has_selection)
        
        selected_track = None
        selected_candidates = self.get_selected()

        if len(selected_candidates) > 0:
            selected_track = selected_candidates[0]

        self.sound_player_widget.handle_audio_player_on_select(has_selection, selected_track)
  
class SFXDatabase(SoundTab):
    @classmethod
    def create(cls, parent=None):
        data = RESOURCES.sfx
        title = "SFX"

        dialog = cls(data, title, SFXModel, MultiselectTableView, parent)
        return dialog

class MusicDatabase(SoundTab):
    @classmethod
    def create(cls, parent=None):
        data = RESOURCES.music
        title = "Music"

        dialog = cls(data, title, MusicModel, ResourceTableView, parent)
        return dialog

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autofill_button = QPushButton("Autofill Sound Room Number")
        self.autofill_button.clicked.connect(self.autofill)
        self.autofill_button.setToolTip('Assign consecutive, unique, positive values to all the Sound Room Numbers that are currently 0.')
        self.layout.addWidget(self.autofill_button)

    def autofill(self):
        self.model.autofill()

def get_sfx():
    window = SingleResourceEditor(SFXDatabase, ['sfx'])
    result = window.exec_()
    if result == QDialog.Accepted:
        selected_sfx = window.tab.get_selected()
        return selected_sfx, True
    else:
        return None, False

def get_music():
    window = SingleResourceEditor(MusicDatabase, ['music'])
    result = window.exec_()
    if result == QDialog.Accepted:
        selected_music = window.tab.get_selected()
        return selected_music, True
    else:
        return None, False

def get_full_editor(parent=None):
    return MultiResourceEditor((MusicDatabase, SFXDatabase),
                               ("music", "sfx"), parent)

# Testing
# Run "python -m app.editor.sound_editor.sound_tab"
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
    RESOURCES.load('default.ltproj', CURRENT_SERIALIZATION_VERSION)
    # DB.load('default.ltproj')
    window = MultiResourceEditor((MusicDatabase, SFXDatabase),
                                 ("music", "sfx"))
    # window = SingleResourceEditor(SFXDatabase, ['sfx'])
    window.show()
    app.exec_()
