from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtGui import QFont
from app.editor.settings import MainSettingsController
from app.editor.event_editor.py_syntax import PythonHighlighter

class CodeLineEdit(QPlainTextEdit):
    """
        A widget used for code liners in the editor.
        Behaves similar to a QLineEdit widget, but subclasses a QPlainTextEdit widget.
        It has the following features:
            - No line wrapping.
            - Horizontal and vertical scroll bars are always off.
            - Default fixed height of 25 pixels, to approximate a QLineEdit.
            - In-built Python syntax highlighting.
            - Adapts its font to the user's settings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.highlighter = PythonHighlighter(self.document())
        
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(25)
        
        settings = MainSettingsController()
        if settings.get_code_font_in_boxes():
            self.setFont(QFont(settings.get_code_font()))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            return
        super().keyPressEvent(event)