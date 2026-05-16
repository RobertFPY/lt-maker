"""
Reusable preference components for building configuration UIs.
"""
from PyQt5 import QtGui
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QCheckBox, QSpinBox, QDoubleSpinBox, QPushButton,
                              QFontComboBox, QSizePolicy, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal

from app.extensions.custom_gui import ComboBox


class PreferenceWidget(QWidget):
    """Base class for all preference widgets."""

    valueChanged = pyqtSignal(object)  # Emitted when value changes

    def __init__(self, label: str, tooltip: str = None, parent=None):
        super().__init__(parent)
        self.label_text = label
        self._setup_ui()
        if tooltip:
            self.setToolTip(tooltip)

    def _setup_ui(self):
        """Override in subclasses to set up the UI."""
        raise NotImplementedError

    def get_value(self):
        """Override to return the current value."""
        raise NotImplementedError

    def set_value(self, value):
        """Override to set the current value."""
        raise NotImplementedError


class BooleanPreference(PreferenceWidget):
    """Checkbox preference for boolean values."""

    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.checkbox = QCheckBox(self.label_text, self)
        self.checkbox.stateChanged.connect(lambda: self.valueChanged.emit(self.get_value()))
        layout.addWidget(self.checkbox)
        layout.addStretch()

    def get_value(self) -> bool:
        return self.checkbox.isChecked()

    def set_value(self, value: bool):
        self.checkbox.setChecked(bool(value))


class IntegerPreference(PreferenceWidget):
    """Spinbox preference for integer values."""

    def __init__(self, label: str, min_val: int = 0, max_val: int = 100,
                 tooltip: str = None, parent=None):
        self.min_val = min_val
        self.max_val = max_val
        super().__init__(label, tooltip, parent)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        self.label = QLabel(self.label_text, self)
        self.label.setAlignment(Qt.AlignBottom)

        self.spinbox = QSpinBox(self)
        self.spinbox.setRange(self.min_val, self.max_val)
        self.spinbox.valueChanged.connect(lambda: self.valueChanged.emit(self.get_value()))

        layout.addWidget(self.label)
        layout.addWidget(self.spinbox)

    def get_value(self) -> int:
        return self.spinbox.value()

    def set_value(self, value: int):
        self.spinbox.setValue(int(value))


class DoublePreference(PreferenceWidget):
    """Spinbox preference for floating point values."""

    def __init__(self, label: str, min_val: float = 0.0, max_val: float = 100.0,
                 decimals: int = 2, tooltip: str = None, parent=None):
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals
        super().__init__(label, tooltip, parent)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        self.label = QLabel(self.label_text, self)
        self.label.setAlignment(Qt.AlignBottom)

        self.spinbox = QDoubleSpinBox(self)
        self.spinbox.setRange(self.min_val, self.max_val)
        self.spinbox.setDecimals(self.decimals)
        self.spinbox.valueChanged.connect(lambda: self.valueChanged.emit(self.get_value()))

        layout.addWidget(self.label)
        layout.addWidget(self.spinbox)

    def get_value(self) -> float:
        return self.spinbox.value()

    def set_value(self, value: float):
        self.spinbox.setValue(float(value))


class ChoicePreference(PreferenceWidget):
    """Combobox preference for selecting from multiple options."""

    def __init__(self, label: str, options: list = None, tooltip: str = None, parent=None):
        self.options = options or []
        super().__init__(label, tooltip, parent)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        self.label = QLabel(self.label_text, self)
        self.label.setAlignment(Qt.AlignBottom)

        self.combobox = ComboBox(self)
        for option in self.options:
            self.combobox.addItem(option)
        self.combobox.currentIndexChanged.connect(lambda: self.valueChanged.emit(self.get_value()))

        layout.addWidget(self.label)
        layout.addWidget(self.combobox)

    def add_options(self, options: list):
        """Add options to the combobox."""
        for option in options:
            self.combobox.addItem(option)

    def get_value(self) -> str:
        return self.combobox.currentText()

    def get_index(self) -> int:
        return self.combobox.currentIndex()

    def set_value(self, value: str):
        self.combobox.setValue(value)

    def set_index(self, index: int):
        self.combobox.setCurrentIndex(index)


class FontPreference(PreferenceWidget):
    """Font selection preference."""

    def __init__(self, label: str, monospace_only: bool = False,
                 tooltip: str = None, parent=None):
        self.monospace_only = monospace_only
        super().__init__(label, tooltip, parent)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        self.label = QLabel(self.label_text, self)
        self.label.setAlignment(Qt.AlignBottom)

        self.font_combo = QFontComboBox(self)
        if self.monospace_only:
            self.font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        self.font_combo.currentFontChanged.connect(lambda: self.valueChanged.emit(self.get_value()))

        layout.addWidget(self.label)
        layout.addWidget(self.font_combo)

    def get_value(self) -> str:
        return self.font_combo.currentText()

    def set_value(self, font_name: str):
        self.font_combo.setCurrentFont(QtGui.QFont(font_name))


class KeybindingPreference(PreferenceWidget):
    """Preference for binding keyboard shortcuts."""

    def __init__(self, label: str, tooltip: str = None, parent=None):
        self.current_key = None
        self.awaiting_key = False
        super().__init__(label, tooltip, parent)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        self.label = QLabel(self.label_text, self)
        self.label.setAlignment(Qt.AlignBottom)

        button_layout = QHBoxLayout()

        self.bind_button = QPushButton("None", self)
        self.bind_button.clicked.connect(self.start_binding)
        sp = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sp.setHorizontalStretch(4)
        self.bind_button.setSizePolicy(sp)

        self.unbind_button = QPushButton("Unbind", self)
        self.unbind_button.clicked.connect(self.unbind)
        sp1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sp1.setHorizontalStretch(1)
        self.unbind_button.setSizePolicy(sp1)

        button_layout.addWidget(self.bind_button)
        button_layout.addWidget(self.unbind_button)

        layout.addWidget(self.label)
        layout.addLayout(button_layout)

    def start_binding(self):
        """Start waiting for a key press."""
        self.bind_button.setText("Press any key...")
        self.awaiting_key = True
        self.setFocus()

    def bind_key(self, key: Qt.Key):
        """Bind a specific key."""
        from app.editor import utilities
        self.current_key = key
        self.bind_button.setText(utilities.qtkey_to_string(key))
        self.awaiting_key = False
        self.valueChanged.emit(self.get_value())

    def unbind(self):
        """Remove the current binding."""
        self.current_key = None
        self.bind_button.setText("None")
        self.awaiting_key = False
        self.valueChanged.emit(self.get_value())

    def event(self, event):
        """Override event to capture Tab and Enter keys."""
        if self.awaiting_key and event.type() == event.KeyPress:
            self.bind_key(event.key())
            return True
        return super().event(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Handle key press events when awaiting binding."""
        if self.awaiting_key:
            self.bind_key(event.key())
            event.accept()
        else:
            super().keyPressEvent(event)

    def get_value(self):
        return self.current_key

    def set_value(self, key):
        from app.editor import utilities
        self.current_key = key
        if key is not None:
            self.bind_button.setText(utilities.qtkey_to_string(key))
        else:
            self.bind_button.setText("None")

    def is_awaiting_key(self) -> bool:
        """Check if this widget is waiting for a key press."""
        return self.awaiting_key


class MousebindingPreference(PreferenceWidget):
    """Preference for selecting mouse buttons from a dropdown."""

    def __init__(self, label: str, tooltip: str = None, parent=None):
        super().__init__(label, tooltip, parent)

    def _setup_ui(self):
        from app.editor.settings.preference_definitions import name_to_button

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        self.label = QLabel(self.label_text, self)
        self.label.setAlignment(Qt.AlignBottom)

        self.combobox = ComboBox(self)
        # Populate with button names from preference_definitions
        for button_name in name_to_button.keys():
            self.combobox.addItem(button_name)
        self.combobox.currentIndexChanged.connect(lambda: self.valueChanged.emit(self.get_value()))

        layout.addWidget(self.label)
        layout.addWidget(self.combobox)

    def get_value(self) -> str:
        return self.combobox.currentText()

    def set_value(self, value: str):
        self.combobox.setValue(value)


class PreferenceSection(QFrame):
    """A section grouping related preferences together."""

    def __init__(self, title: str = None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        if title:
            title_label = QLabel(f"<b>{title}</b>")
            self.main_layout.addWidget(title_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(8)
        self.main_layout.addLayout(self.content_layout)

    def add_preference(self, widget: PreferenceWidget):
        """Add a preference widget to this section."""
        self.content_layout.addWidget(widget)

    def add_widget(self, widget: QWidget):
        """Add any widget to this section."""
        self.content_layout.addWidget(widget)

    def add_stretch(self):
        """Add stretch to push content to the top."""
        self.content_layout.addStretch()
