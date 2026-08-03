from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QLabel, QVBoxLayout, QWidget)

from app.data.database.levels import LevelPrefab
from app.utilities.typing import NID


class EventTestContextDialog(QDialog):
    """Choose the live level units exposed to an editor Event Test."""

    def __init__(
            self,
            level: LevelPrefab,
            unit_required: bool = False,
            parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Event Test Context")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        description = QLabel(
            "Choose the trigger units for this preview. "
            "unit is also available as unit1; unit2 is also available as "
            "target. position follows unit (or unit2 when unit is None).",
            self,
        )
        description.setWordWrap(True)

        self.unit_box = QComboBox(self)
        self.unit2_box = QComboBox(self)
        self._populate_unit_box(self.unit_box, level, not unit_required)
        self._populate_unit_box(self.unit2_box, level, True)

        form = QFormLayout()
        form.addRow("unit / unit1", self.unit_box)
        form.addRow("unit2 / target", self.unit2_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        if unit_required and not level.units:
            buttons.button(QDialogButtonBox.Ok).setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(description)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _populate_unit_box(
            combo_box: QComboBox,
            level: LevelPrefab,
            allow_none: bool) -> None:
        if allow_none:
            combo_box.addItem("None", None)
        for unit in level.units:
            combo_box.addItem(f"{unit.nid} ({unit.team})", unit.nid)

    @property
    def unit_nid(self) -> Optional[NID]:
        return self.unit_box.currentData()

    @property
    def unit2_nid(self) -> Optional[NID]:
        return self.unit2_box.currentData()
