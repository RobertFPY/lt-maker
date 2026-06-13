from app.data.database.database import DB

from app.extensions.list_dialogs import MultiAttrListDialog
from app.extensions.list_models import MultiAttrListModel

from app.editor.base_database_gui import find_filter_keyword

from PyQt5.QtWidgets import QGridLayout, QLineEdit, QPushButton, QDialogButtonBox
from PyQt5.QtCore import Qt, pyqtSignal

class TranslationMultiModel(MultiAttrListModel):
    def create_new(self):
        return self._data.add_new_default(DB)

    def on_attr_changed(self, data, attr, old_value, new_value):
        if attr == 'nid':
            self._data.update_nid(data, new_value)

    def append(self):
        new_index = super().append()
        try:
            self.window.view.setRowHidden(new_index.row(), new_index, False)
        except Exception as e:
            print(e)

    def new(self, idx):
        new_index = super().new(idx)
        try:
            self.window.view.setRowHidden(new_index.row(), new_index, False)
        except Exception as e:
            print(e)

class TranslationDialog(MultiAttrListDialog):
    @classmethod
    def create(cls):
        dlg = cls(DB.translations, "Translation", ("nid", "text"),
                  TranslationMultiModel, (None, None, None), set())
        return dlg

    def placement(self, title):
        layout = QGridLayout(self)
        layout.addWidget(self.view, 1, 0, 1, 2)
        self.setLayout(layout)

        self.filter_field = QLineEdit()
        self.filter_field.setPlaceholderText('Filter by keyword, or by "nid"')
        self.filter_field.textChanged.connect(self.on_filter_changed)
        layout.addWidget(self.filter_field, 0, 0)

        self.add_button = QPushButton("Add %s" % title)
        self.add_button.clicked.connect(self.model.append)
        layout.addWidget(self.add_button, 2, 0, alignment=Qt.AlignLeft)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok, Qt.Horizontal, self)
        layout.addWidget(self.buttonbox, 2, 1)
        self.buttonbox.accepted.connect(self.accept)

        self.model.layoutChanged.connect(self.on_filter_changed)

    def on_filter_changed(self, text: str = None):
        text = self.filter_field.text().replace(' ', '')
        if not text:
            for i in range(self.model.rowCount()):
                self.view.setRowHidden(i, self.model.index(i), False)
            return

        try:
            for i in range(self.model.rowCount()):
                index = self.model.index(i)
                self.view.setRowHidden(i, index, False)
                if not find_filter_keyword(text, self.model, index):
                    self.view.setRowHidden(i, index, True)
        except Exception as e:
            print(e)
