from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import QObject, QProcess, QTimer, pyqtSignal

from app.editor import timer
from app.editor.file_manager.android_builder.android_build_config import (
    AndroidEditorBuildConfig,
    parse_build_output_line,
    powershell_arguments,
    save_config,
)
from app.editor.file_manager.project_file_backend import DEFAULT_PROJECT

if TYPE_CHECKING:
    from app.editor.file_manager.project_file_backend import ProjectFileBackend


REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ROOT = REPO_ROOT / "utilities" / "build_tools" / "android_runtime"
BUILD_SCRIPT = RUNTIME_ROOT / "build_runtime.ps1"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class PrerequisiteStatus:
    passed: bool
    summary: str
    details: tuple[str, ...]


def _decode_windows_output(raw: bytes) -> str:
    if b"\x00" in raw:
        return raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
    return raw.decode("utf-8", errors="replace")


def _powershell_path() -> Optional[str]:
    discovered = shutil.which("powershell.exe") or shutil.which("powershell")
    if discovered:
        return discovered
    fallback = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    return str(fallback) if fallback.is_file() else None


def check_prerequisites(distro: str) -> PrerequisiteStatus:
    details: list[str] = []
    failures: list[str] = []
    if os.name != "nt":
        failures.append("Android editor builds currently require Windows + WSL2.")
    if not BUILD_SCRIPT.is_file():
        failures.append(f"Missing Android build script: {BUILD_SCRIPT}")

    powershell = _powershell_path()
    if powershell:
        details.append(f"PowerShell: {powershell}")
    else:
        failures.append("PowerShell was not found.")

    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    if not wsl:
        failures.append("WSL was not found.")
    else:
        try:
            listed = subprocess.run(
                [wsl, "--list", "--quiet"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=15,
                creationflags=CREATE_NO_WINDOW,
            )
            distro_names = tuple(
                line.strip()
                for line in _decode_windows_output(listed.stdout).splitlines()
                if line.strip()
            )
            if listed.returncode:
                failures.append("WSL is installed but not initialized.")
            elif distro not in distro_names:
                available = ", ".join(distro_names) or "none"
                failures.append(
                    f"WSL distro {distro!r} was not found (available: {available})."
                )
            else:
                details.append(f"WSL distro: {distro}")
                command_check = (
                    'export PATH="$HOME/.venvs/lt-android-probe/bin:'
                    '$HOME/.local/bin:$PATH"; '
                    "missing=''; "
                    "for c in python3 buildozer java javac sha256sum tar unzip flock; "
                    'do command -v "$c" >/dev/null 2>&1 || missing="$missing $c"; '
                    "done; "
                    'if [ -n "$missing" ]; then echo "Missing:$missing"; exit 2; fi; '
                    'echo "Android build toolchain ready"'
                )
                checked = subprocess.run(
                    [wsl, "-d", distro, "--", "bash", "-lc", command_check],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                    creationflags=CREATE_NO_WINDOW,
                )
                output = _decode_windows_output(checked.stdout).strip()
                if checked.returncode:
                    failures.append(output or "Android tools are missing inside WSL.")
                else:
                    details.append(output)
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(f"Could not check WSL prerequisites: {exc}")

    if failures:
        return PrerequisiteStatus(
            False,
            "Android prerequisites are incomplete.",
            tuple(failures + details),
        )
    return PrerequisiteStatus(
        True,
        "Android prerequisites are ready.",
        tuple(details),
    )


class AndroidBuildController(QObject):
    output_received = pyqtSignal(str)
    stage_changed = pyqtSignal(int, str)
    build_finished = pyqtSignal(
        bool, str, str, str, str
    )  # success, artifact_dir, apk, log, error

    def __init__(
        self,
        project_backend: "ProjectFileBackend",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.project_backend = project_backend
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self._buffer = ""
        self._artifact_dir = ""
        self._apk_path = ""
        self._editor_log_path = ""
        self._failure_message = ""
        self._output_directory = Path()
        self._autosave_paused = False
        self._completion_emitted = False

    @property
    def running(self) -> bool:
        return self.process.state() != QProcess.NotRunning

    @property
    def editor_log_path(self) -> str:
        return self._editor_log_path

    def prepare_project(self) -> tuple[Optional[Path], Optional[str]]:
        if not self.project_backend.save(new=False, as_chunks=False):
            return None, "The project must be saved before building an APK."
        parent = self.project_backend.parent
        if hasattr(parent, "_save"):
            parent._save()

        project_path = Path(self.project_backend.current_proj).resolve()
        if project_path.name == DEFAULT_PROJECT:
            return None, "Save the default project under a new name before building."
        metadata_path = project_path / "metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"Could not read saved project metadata: {exc}"
        if metadata.get("has_fatal_errors"):
            return (
                None,
                "The saved project has fatal validation errors. "
                "Fix them before building an APK.",
            )
        return project_path, None

    def start(
        self,
        project_path: Path,
        config: AndroidEditorBuildConfig,
    ) -> None:
        if self.running:
            raise RuntimeError("An Android build is already running")
        self._output_directory = Path(config.output_directory).resolve()
        normalized_icon = (
            str(Path(config.icon).resolve()) if config.icon else None
        )
        config = replace(
            config,
            output_directory=str(self._output_directory),
            icon=normalized_icon,
        )
        save_config(project_path, config)
        self._output_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._editor_log_path = str(
            self._output_directory / f"android-editor-{timestamp}.log"
        )
        self._artifact_dir = ""
        self._apk_path = ""
        self._failure_message = ""
        self._buffer = ""
        self._completion_emitted = False

        powershell = _powershell_path()
        if not powershell:
            raise FileNotFoundError("PowerShell was not found")
        self.process.setProgram(powershell)
        self.process.setArguments(
            powershell_arguments(BUILD_SCRIPT, project_path, config)
        )
        self.stage_changed.emit(5, "Launching PowerShell and WSL")
        self._append_editor_log(
            f"LT Maker Android build\nProject: {project_path}\n"
            f"Output: {self._output_directory}\n\n"
        )
        timer.get_timer().autosave_timer.stop()
        self._autosave_paused = True
        self.process.start()

    def cancel(self) -> None:
        if not self.running:
            return
        self.output_received.emit("\nCancellation requested...\n")
        self.process.terminate()
        QTimer.singleShot(3000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.running:
            self.process.kill()

    def _append_editor_log(self, text: str) -> None:
        if not self._editor_log_path:
            return
        with open(
            self._editor_log_path,
            "a",
            encoding="utf-8",
            errors="replace",
        ) as output:
            output.write(text)

    def _read_output(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if not text:
            return
        self._append_editor_log(text)
        self.output_received.emit(text)
        self._buffer += text
        lines = self._buffer.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            self._buffer = lines.pop()
        else:
            self._buffer = ""
        for raw_line in lines:
            self._handle_line(raw_line.strip())

    def _handle_line(self, line: str) -> None:
        update = parse_build_output_line(
            line,
            self._output_directory,
            self._artifact_dir,
        )
        if update.progress is not None:
            self.stage_changed.emit(update.progress, update.description)
        if update.artifact_dir:
            self._artifact_dir = update.artifact_dir
        if update.apk_path:
            self._apk_path = update.apk_path

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        self._failure_message = self.process.errorString()
        if (
            _error == QProcess.FailedToStart
            and self.process.state() == QProcess.NotRunning
        ):
            self._complete(-1)

    def _process_finished(
        self,
        exit_code: int,
        _exit_status: QProcess.ExitStatus,
    ) -> None:
        self._complete(exit_code)

    def _complete(self, exit_code: int) -> None:
        if self._completion_emitted:
            return
        self._completion_emitted = True
        self._read_output()
        if self._buffer:
            self._handle_line(self._buffer.strip())
            self._buffer = ""
        if self._autosave_paused:
            timer.get_timer().autosave_timer.start()
            self._autosave_paused = False
        success = exit_code == 0 and bool(self._apk_path)
        if success:
            self.stage_changed.emit(100, "Android APK build completed")
            published_log = str(Path(self._artifact_dir) / "build.log")
            log_path = (
                published_log
                if Path(published_log).is_file()
                else self._editor_log_path
            )
            error = ""
        else:
            log_path = self._editor_log_path
            error = self._failure_message or (
                f"Android build failed with exit code {exit_code}."
            )
        self.build_finished.emit(
            success,
            self._artifact_dir,
            self._apk_path,
            log_path,
            error,
        )
