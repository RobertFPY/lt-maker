from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QLabel,
                             QPlainTextEdit, QSplitter, QVBoxLayout, QWidget)

from app.events.event_converter import ConversionResult, convert_event_script
from app.events.event_version import EventVersion


class EventConverterDialog(QDialog):
    def __init__(
        self,
        source: str,
        source_version: EventVersion,
        code_font: QFont,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.result: ConversionResult = convert_event_script(source, source_version)

        self.setWindowTitle("Convert Event")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.resize(1100, 700)

        direction = (
            "Classic Event  ->  Python Event"
            if source_version == EventVersion.EVENT
            else "Python Event  ->  Classic Event"
        )
        direction_label = QLabel(direction, self)

        self.source_box = QPlainTextEdit(self)
        self.source_box.setPlainText(source)
        self.source_box.setReadOnly(True)
        self.source_box.setFont(code_font)

        self.preview_box = QPlainTextEdit(self)
        self.preview_box.setPlainText(self.result.text)
        self.preview_box.setReadOnly(True)
        self.preview_box.setFont(code_font)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.source_box)
        splitter.addWidget(self.preview_box)
        splitter.setSizes([550, 550])

        self.status_box = QPlainTextEdit(self)
        self.status_box.setReadOnly(True)
        self.status_box.setMaximumHeight(130)
        if self.result.issues:
            self.status_box.setPlainText(
                "Conversion cannot be applied until these issues are fixed:\n"
                + "\n".join(str(issue) for issue in self.result.issues)
            )
        else:
            self.status_box.setPlainText(
                "Ready. Review the preview, then choose Apply Conversion. "
                "The original event is unchanged until you apply."
            )

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, parent=self)
        self.apply_button = buttons.addButton(
            "Apply Conversion", QDialogButtonBox.AcceptRole
        )
        self.apply_button.setEnabled(self.result.can_apply)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(direction_label)
        layout.addWidget(splitter, stretch=1)
        layout.addWidget(self.status_box)
        layout.addWidget(buttons)

    @property
    def converted_text(self) -> str:
        return self.result.text
