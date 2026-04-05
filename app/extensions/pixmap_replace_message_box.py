from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QDialogButtonBox, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from app.editor.icon_editor.icon_view import IconView
from app.extensions.custom_gui import PropertyBox

class PixmapReplaceMessageBox(QDialog):
    def __init__(self, title: str, text: str, caption1: str, caption2: str, pix1: QPixmap, pix2: QPixmap,
                 alert_level: QMessageBox.Icon = QMessageBox.Warning, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout()

        self.icon_label = QLabel(self)
        self.icon_label.setPixmap(QMessageBox().standardIcon(alert_level))

        self.text_label = QLabel(text, self)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.icon_label)
        hlayout.addWidget(self.text_label)
        layout.addLayout(hlayout)

        pix_section = QHBoxLayout()
        self.pix1 = pix1
        self.pix2 = pix2

        old_pix = PropertyBox(caption1, IconView, self)
        old_pix.edit.set_image(self.pix1)
        old_pix.edit.show_image()

        new_pix = PropertyBox(caption2, IconView, self)
        new_pix.edit.set_image(self.pix2)
        new_pix.edit.show_image()

        pix_section.addWidget(old_pix)
        pix_section.addWidget(new_pix)
        layout.addLayout(pix_section)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        layout.addWidget(self.buttonbox)

        self.setLayout(layout)
        self.final_pix = self.pix1
    
    def exec_(self) -> QPixmap:
        super().exec_()
        return self.final_pix
    
    def accept(self):
        self.final_pix = self.pix2
        super().accept()
    
    def reject(self):
        self.final_pix = self.pix1
        super().reject()