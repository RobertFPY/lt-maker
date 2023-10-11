import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget, QPushButton
from app.data.database.database import DB
from app.data.resources.resources import RESOURCES

from app.data.validation.db_validation import validate_events

MAX_NUM_CHARS = 100000

def generate_header(title: str):
    bars = '=' * len(title)
    return f"{bars}\n{title}\n{bars}"

class ErrorViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Error report")
        self.resize(800,800)

        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setFont(QFont('Consolas', 10))
        self.textEdit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.textEdit.setLineWrapMode(QTextEdit.NoWrap)

        self.refresh_errors_button = QPushButton("Regenerate Error Report")
        self.refresh_errors_button.clicked.connect(self.regenerate_errors)

        layout = QVBoxLayout()
        layout.addWidget(self.textEdit)
        layout.addWidget(self.refresh_errors_button)
        self.setLayout(layout)

        self.regenerate_errors()

    def regenerate_errors(self):
        text_body = ""
        
        event_errors = validate_events(DB, RESOURCES)
        if event_errors:
            event_errors_as_str = '\n'.join(str(error) for error in event_errors)
            text_body += generate_header("EVENT ERRORS")
            text_body += event_errors_as_str

        if not text_body:
            text_body = generate_header("No errors in project!")
        self.textEdit.setText(text_body)

def show_error_report():
    dlg = ErrorViewer()
    dlg.show()
    return dlg

# python -m app.editor.error_viewer
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = ErrorViewer()
    win.show()
    sys.exit(app.exec_())