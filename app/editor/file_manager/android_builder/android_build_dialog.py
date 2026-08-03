from __future__ import annotations

from html import escape
from pathlib import Path
import threading
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.data.database.database import DB
from app.editor.file_manager.android_builder.android_build_config import (
    AndroidEditorBuildConfig,
    config_path,
    load_config,
    validate_config,
)
from app.editor.file_manager.android_builder.android_build_controller import (
    AndroidBuildController,
    PrerequisiteStatus,
    check_prerequisites,
)
from app.utilities import file_utils


class AndroidBuildDialog(QDialog):
    prerequisite_checked = pyqtSignal(object)

    def __init__(self, project_backend, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project_backend = project_backend
        self.controller = AndroidBuildController(project_backend, self)
        self.controller.output_received.connect(self._append_output)
        self.controller.stage_changed.connect(self._set_stage)
        self.controller.build_finished.connect(self._build_finished)
        self._project_path = Path(project_backend.current_proj).resolve()
        self._artifact_dir = ""
        self._apk_path = ""
        self._log_path = ""
        self._prerequisites_ready = False
        self._loaded_package_id = ""
        self._has_saved_config = False
        self._close_after_cancel = False
        self._prerequisite_generation = 0

        self.setWindowTitle("Build Android APK")
        self.resize(820, 700)
        self.setWindowModality(Qt.WindowModal)
        self._create_ui()
        self._load_fields()
        self.prerequisite_checked.connect(self._prerequisite_result)
        QTimer.singleShot(0, self.refresh_prerequisites)

    def _create_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            "Build an ARM64 APK using the verified Buildozer/python-for-android "
            "pipeline. Optimized Release builds are development-signed for testing."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.package_id = QLineEdit(self)
        self.package_id.setToolTip(
            "Keep this ID unchanged between versions so Android upgrades the "
            "existing app and preserves its persistent player data."
        )
        form.addRow("Package ID:", self.package_id)
        self.app_name = QLineEdit(self)
        form.addRow("App name:", self.app_name)

        version_row = QHBoxLayout()
        self.version_name = QLineEdit(self)
        self.version_name.setPlaceholderText("1.0.0")
        self.version_code = QSpinBox(self)
        self.version_code.setRange(1, 2_100_000_000)
        version_row.addWidget(QLabel("Name"))
        version_row.addWidget(self.version_name, 1)
        version_row.addWidget(QLabel("Code"))
        version_row.addWidget(self.version_code)
        form.addRow("Version:", version_row)

        self.icon_path = QLineEdit(self)
        icon_button = QPushButton("Browse…", self)
        icon_button.clicked.connect(self._browse_icon)
        form.addRow("Icon PNG:", self._path_row(self.icon_path, icon_button))

        self.abi = QComboBox(self)
        self.abi.addItem("ARM64 (arm64-v8a)", "arm64-v8a")
        form.addRow("ABI:", self.abi)

        self.mode = QComboBox(self)
        self.mode.addItem("Debug signed", "debug")
        self.mode.addItem("Release optimized — development signed", "release")
        self.mode.setToolTip(
            "Release disables the p4a/NDK debug native build and is signed with "
            "the established development certificate. It is not for Play Store."
        )
        form.addRow("Build mode:", self.mode)

        self.runtime_debugger = QCheckBox("Enable in-game debugger", self)
        self.runtime_debugger.setToolTip(
            "Developer-only tools. Android opens them inside the game instead "
            "of launching a web browser."
        )
        form.addRow("Developer tools:", self.runtime_debugger)

        self.output_path = QLineEdit(self)
        output_button = QPushButton("Browse…", self)
        output_button.clicked.connect(self._browse_output)
        form.addRow(
            "Output directory:",
            self._path_row(self.output_path, output_button),
        )

        self.distro = QLineEdit(self)
        self.distro.setPlaceholderText("Ubuntu-24.04")
        self.distro.textChanged.connect(self._invalidate_prerequisites)
        form.addRow("WSL distro:", self.distro)
        root.addLayout(form)

        prerequisite_grid = QGridLayout()
        self.prerequisite_status = QLabel("Checking prerequisites…", self)
        self.prerequisite_status.setWordWrap(True)
        refresh_button = QPushButton("Check again", self)
        refresh_button.clicked.connect(self.refresh_prerequisites)
        prerequisite_grid.addWidget(self.prerequisite_status, 0, 0)
        prerequisite_grid.addWidget(refresh_button, 0, 1)
        root.addLayout(prerequisite_grid)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.stage_label = QLabel("Ready", self)
        root.addWidget(self.stage_label)
        root.addWidget(self.progress)

        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Buildozer verbose output can exceed 15 MiB. Preserve the complete
        # editor-side log while keeping only the recent UI tail responsive.
        self.output.setMaximumBlockCount(5000)
        root.addWidget(self.output, 1)

        path_grid = QGridLayout()
        self.apk_label = QLabel("APK: not built", self)
        self.apk_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.log_label = QLabel("Log: not created", self)
        self.log_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_grid.addWidget(self.apk_label, 0, 0, 1, 3)
        path_grid.addWidget(self.log_label, 1, 0, 1, 3)
        root.addLayout(path_grid)

        buttons = QHBoxLayout()
        self.build_button = QPushButton("Build APK", self)
        self.build_button.clicked.connect(self.start_build)
        self.cancel_button = QPushButton("Cancel build", self)
        self.cancel_button.clicked.connect(self.controller.cancel)
        self.cancel_button.setEnabled(False)
        self.open_output_button = QPushButton("Open output", self)
        self.open_output_button.clicked.connect(self._open_output)
        self.open_output_button.setEnabled(False)
        self.open_log_button = QPushButton("Open log", self)
        self.open_log_button.clicked.connect(self._open_log)
        self.open_log_button.setEnabled(False)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.reject)
        buttons.addWidget(self.build_button)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(self.open_output_button)
        buttons.addWidget(self.open_log_button)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    @staticmethod
    def _path_row(line_edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return widget

    def _load_fields(self) -> None:
        title = DB.constants.value("title") or self._project_path.stem
        config, warning = load_config(self._project_path, str(title))
        self._loaded_package_id = config.package_id
        self._has_saved_config = config_path(self._project_path).is_file()
        self.package_id.setText(config.package_id)
        self.app_name.setText(config.app_name)
        self.version_name.setText(config.version_name)
        self.version_code.setValue(config.version_code)
        self.icon_path.setText(config.icon or "")
        self.output_path.setText(config.output_directory)
        self.distro.setText(config.distro)
        self._select_combo_value(self.abi, config.arch)
        self._select_combo_value(self.mode, config.mode)
        self.runtime_debugger.setChecked(config.runtime_debugger)
        if warning:
            self._append_output(f"Warning: {warning}\n")

    @staticmethod
    def _select_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _browse_icon(self) -> None:
        starting = self.icon_path.text() or str(
            self._project_path / "resources" / "system"
        )
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Android icon",
            starting,
            "PNG Images (*.png);;All Files (*)",
        )
        if filename:
            self.icon_path.setText(filename)

    def _browse_output(self) -> None:
        starting = self.output_path.text() or str(self._project_path.parent)
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Android build output directory",
            starting,
        )
        if directory:
            self.output_path.setText(directory)

    def _config_from_fields(self) -> AndroidEditorBuildConfig:
        return AndroidEditorBuildConfig(
            package_id=self.package_id.text().strip(),
            app_name=self.app_name.text().strip(),
            version_name=self.version_name.text().strip(),
            version_code=self.version_code.value(),
            icon=self.icon_path.text().strip() or None,
            arch=str(self.abi.currentData()),
            mode=str(self.mode.currentData()),
            runtime_debugger=self.runtime_debugger.isChecked(),
            output_directory=self.output_path.text().strip(),
            distro=self.distro.text().strip(),
        )

    def refresh_prerequisites(self) -> None:
        self.prerequisite_status.setText("Checking prerequisites…")
        self.build_button.setEnabled(False)
        self._prerequisite_generation += 1
        generation = self._prerequisite_generation
        distro = self.distro.text().strip() or "Ubuntu-24.04"
        thread = threading.Thread(
            target=self._run_prerequisite_check,
            args=(generation, distro),
            daemon=True,
        )
        thread.start()

    def _invalidate_prerequisites(self) -> None:
        self._prerequisites_ready = False
        self.build_button.setEnabled(False)
        self.prerequisite_status.setText(
            "WSL distro changed. Click Check again."
        )

    def _run_prerequisite_check(self, generation: int, distro: str) -> None:
        status = check_prerequisites(distro)
        self.prerequisite_checked.emit((generation, status))

    def _prerequisite_result(self, result) -> None:
        generation, status = result
        if generation != self._prerequisite_generation:
            return
        self._show_prerequisite_status(status)

    def _show_prerequisite_status(self, status: PrerequisiteStatus) -> None:
        self._prerequisites_ready = status.passed
        color = "#2e8b57" if status.passed else "#b22222"
        details = "\n".join(f"• {line}" for line in status.details)
        self.prerequisite_status.setText(
            f"<b style='color:{color}'>{escape(status.summary)}</b><br>"
            + "<br>".join(f"• {escape(line)}" for line in status.details)
        )
        self.prerequisite_status.setToolTip(details)
        self.build_button.setEnabled(status.passed)

    def start_build(self) -> None:
        if not self._prerequisites_ready:
            QMessageBox.warning(
                self,
                "Android prerequisites missing",
                "Resolve the prerequisite errors and click Check again.",
            )
            return
        config = self._config_from_fields()
        errors = validate_config(config)
        try:
            Path(config.output_directory).resolve().relative_to(
                self._project_path.resolve()
            )
        except ValueError:
            pass
        else:
            errors.append(
                "Output directory cannot be inside the source .ltproj folder."
            )
        if errors:
            QMessageBox.warning(
                self,
                "Invalid Android build configuration",
                "\n".join(f"• {error}" for error in errors),
            )
            return
        if (
            self._has_saved_config
            and self._loaded_package_id
            and config.package_id != self._loaded_package_id
        ):
            answer = QMessageBox.warning(
                self,
                "Change Android package ID?",
                "Changing the package ID makes Android treat this as a "
                "different app. Existing installations and persistent player "
                "data will not be upgraded.\n\nContinue with the new package ID?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        project_path, error = self.controller.prepare_project()
        if error or project_path is None:
            QMessageBox.warning(self, "Cannot build Android APK", error or "")
            return
        self._project_path = project_path
        self._set_running(True)
        self._artifact_dir = ""
        self._apk_path = ""
        self._log_path = ""
        self.open_output_button.setEnabled(False)
        self.open_log_button.setEnabled(False)
        self.output.clear()
        self.progress.setValue(0)
        self.apk_label.setText("APK: building…")
        self.log_label.setText("Log: creating…")
        try:
            self.controller.start(project_path, config)
            self._loaded_package_id = config.package_id
            self._has_saved_config = True
            self._log_path = self.controller.editor_log_path
            self.log_label.setText(f"Log: {self._log_path}")
            self.open_log_button.setEnabled(True)
            self.open_output_button.setEnabled(True)
        except (OSError, RuntimeError, ValueError) as exc:
            self._set_running(False)
            QMessageBox.critical(
                self,
                "Could not start Android build",
                str(exc),
            )

    def _set_running(self, running: bool) -> None:
        self.build_button.setEnabled(not running and self._prerequisites_ready)
        self.cancel_button.setEnabled(running)

    def _append_output(self, text: str) -> None:
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _set_stage(self, progress: int, description: str) -> None:
        self.progress.setValue(progress)
        self.stage_label.setText(description)

    def _build_finished(
        self,
        success: bool,
        artifact_dir: str,
        apk_path: str,
        log_path: str,
        error: str,
    ) -> None:
        self._set_running(False)
        self._artifact_dir = artifact_dir
        self._apk_path = apk_path
        self._log_path = log_path
        self.apk_label.setText(f"APK: {apk_path or 'not produced'}")
        self.log_label.setText(f"Log: {log_path or 'not available'}")
        self.open_output_button.setEnabled(
            bool(artifact_dir or self.output_path.text().strip())
        )
        self.open_log_button.setEnabled(bool(log_path))
        if success:
            QMessageBox.information(
                self,
                "Android APK completed",
                f"APK created and verified successfully:\n{apk_path}",
            )
        elif not self._close_after_cancel:
            self.stage_label.setText("Android APK build failed")
            QMessageBox.critical(
                self,
                "Android APK build failed",
                f"{error}\n\nLog:\n{log_path}",
            )
        if self._close_after_cancel:
            QDialog.reject(self)

    def _open_output(self) -> None:
        path = self._artifact_dir or self.output_path.text().strip()
        if path:
            file_utils.startfile(path)

    def _open_log(self) -> None:
        if self._log_path:
            file_utils.startfile(self._log_path)

    def reject(self) -> None:
        if self.controller.running:
            answer = QMessageBox.question(
                self,
                "Cancel Android build?",
                "The Android build is still running. Cancel it and close?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            self._close_after_cancel = True
            self.stage_label.setText("Cancelling Android build…")
            self.controller.cancel()
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self.controller.running:
            event.ignore()
            self.reject()
            return
        event.accept()
