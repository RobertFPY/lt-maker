from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtGui import QFont, QFontMetrics
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

        self.textChanged.connect(self._clamp_scroll)
        self._clamp_scroll() # just to be sure

    def _get_max_width(self):
        metrics = QFontMetrics(self.font())
        # easier on the eyes with +5
        return (metrics.horizontalAdvance(self.toPlainText()) + 5) if self.toPlainText() else 0

    def _clamp_scroll(self):
        """ Dynamically adjusts the horizontal scroll range while preserving cursor position. """
        max_width = self._get_max_width()
        scroll_bar = self.horizontalScrollBar()
        current_value = scroll_bar.value()

        # adjust max but preserve relative position
        scroll_bar.setMaximum(max(0, max_width - self.viewport().width()))

        # shift scroll only if user is at the end? ugh
        if current_value >= scroll_bar.maximum() - 5:  
            scroll_bar.setValue(scroll_bar.maximum())
        
    def scrollContentsBy(self, dx, dy):
        self.verticalScrollBar().setValue(0)
        super().scrollContentsBy(dx, 0) # explicitly no vertical scrolling

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            return
        super().keyPressEvent(event)