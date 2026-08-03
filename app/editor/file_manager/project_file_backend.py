from __future__ import annotations
import functools

import logging
import os
from pathlib import Path
import shutil
from datetime import datetime
import traceback
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QVBoxLayout, QLabel, QDialogButtonBox, QCheckBox

from app.constants import VERSION
from app.data.database.database import DB, Database
from app.data.resources.resources import RESOURCES, Resources
from app.data.serialization.dataclass_serialization import dataclass_from_dict
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.data.validation.db_validation import DBChecker
from app.editor import timer
from app.editor.error_viewer import show_error_report
from app.editor.settings.preference_definitions import Preference
from app.extensions.message_box import show_warning_message
from app.utilities.file_manager import FileManager
from app.utilities.serialization import (
    ProjectBackupMergeTransaction,
    ProjectSaveTransaction,
    replace_with_retry,
    save_json,
)
from app.data.metadata import Metadata
from app.editor.file_manager.project_initializer import ProjectInitializer
from app.editor.lib.csv import csv_data_exporter, text_data_exporter
from app.editor.recent_project_dialog import choose_recent_project
from app.editor.settings import MainSettingsController
from app.extensions.custom_gui import SimpleDialog
from app.utilities import exceptions
import app.utilities.platformdirs as appdirs

if TYPE_CHECKING:
    from app.editor.main_editor import MainEditor


RESERVED_PROJECT_PATHS = ("default.ltproj", 'autosave.ltproj', 'autosave', 'default')
DEFAULT_PROJECT = "default.ltproj"
RecoveryResult = Literal["none", "finalized", "completed", "restored", "cancelled", "failed"]

class FatalErrorDialog(SimpleDialog):
    def __init__(self, main_window_reference: MainEditor, on_accept_do_not_show_callback):
        super().__init__()
        self.setWindowTitle("Validation Errors Detected")
        self.main_window_ref = main_window_reference

        layout = QVBoxLayout()
        self.setLayout(layout)

        message_label = QLabel('Fatal errors detected in game. Please fix all errors detected.'
                               '<br><br>Error report can be viewed in the <a href="#view_errors"><span style=" text-decoration: underline; color:#7777ff;">Error Viewer</span></a>')
        message_label.linkActivated.connect(self.open_error_viewer)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)

        self.on_accept_do_not_show_callback = on_accept_do_not_show_callback
        self.do_not_show_again = QCheckBox("Don't show for several minutes")

        layout.addWidget(message_label)
        layout.addWidget(self.do_not_show_again)
        layout.addWidget(button_box)
        self.setMinimumWidth(300)

    def accept(self):
        self.on_accept_do_not_show_callback(self.do_not_show_again.isChecked())
        self.close()

    def open_error_viewer(self):
        self.main_window_ref._error_window_ref = show_error_report()
        self.close()

class ProjectFileBackend():
    def __init__(self, parent, app_state_manager):
        self.parent = parent
        self.app_state_manager = app_state_manager
        self.settings = MainSettingsController()
        self.current_proj = self.settings.get_current_project()
        self.file_manager = FileManager(self.current_proj)
        self.is_saving = False
        # Metadata is loaded by ``load`` only after it has recovered any
        # interrupted project-save transaction.
        self.metadata = Metadata()

        self.save_progress = QProgressDialog(
            "Saving project to %s" % self.current_proj, None, 0, 100, self.parent)
        self.save_progress.setAutoClose(True)
        self.save_progress.setWindowTitle("Saving Project")
        self.save_progress.setWindowModality(Qt.WindowModal)
        self.save_progress.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.save_progress.reset()

        project_nid = DB.constants.value('game_nid').replace(' ', '_')
        autosave_path = os.path.abspath('autosave_%s.ltproj' % project_nid)
        self.autosave_progress = QProgressDialog(
            "Autosaving project to %s" % autosave_path, None, 0, 100, self.parent)
        self.autosave_progress.setAutoClose(True)
        self.autosave_progress.setWindowTitle("Autosaving Project")
        self.autosave_progress.setWindowModality(Qt.WindowModal)
        self.autosave_progress.setWindowFlag(
            Qt.WindowContextHelpButtonHint, False)
        self.autosave_progress.reset()

        timer.get_timer().autosave_timer.timeout.connect(self.autosave)

        self._do_not_show_fatal_errors = False
        timer.get_timer().autosave_timer.timeout.connect(self.refresh_do_not_show)

    def refresh_do_not_show(self):
        self._do_not_show_fatal_errors = False

    def display_fatal_errors(self):
        if self._do_not_show_fatal_errors:
            return
        def set_do_not_show_again(do_not_show_again):
            if self._do_not_show_fatal_errors:
                return
            self._do_not_show_fatal_errors = do_not_show_again
        dlg = FatalErrorDialog(self.parent, set_do_not_show_again)
        dlg.exec_()

    def maybe_save(self):
        # if not self.undo_stack.isClean():
        if True:  # For now, since undo stack is not being used
            ret = QMessageBox.warning(self.parent, "Main Editor", "The current project may have been modified.\n"
                                      "Do you want to save your changes?",
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if ret == QMessageBox.Save:
                return self.save()
            elif ret == QMessageBox.Cancel:
                return False
        return True

    def save_mutex(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # If we're currently saving, we don't want to save again! So gate operations in the save mutex!
            if not self.is_saving:
                # If we're saving the game, we want to ensure autosave doesn't show up and mess with our stuff! Stop it.
                timer.get_timer().autosave_timer.stop()
                self.is_saving = True

                # ... Then, actually save.
                result = func(self, *args, **kwargs)
                self.is_saving = False

                # ... Then start it again! Problem solved! (except this resets the timer, but close enough)
                timer.get_timer().autosave_timer.start()
                return result
        return wrapper

    def _build_metadata_payload(self, has_fatal_errors: bool, as_chunks: bool) -> dict[str, Any]:
        updated_metadata: dict[str, Any] = {
            'date': str(datetime.now()),
            'engine_version': VERSION,
            # Always use the current version. It is required to select the
            # deserializer when the project is loaded.
            'serialization_version': CURRENT_SERIALIZATION_VERSION,
            'project': DB.constants.get('game_nid').value,
            'has_fatal_errors': has_fatal_errors,
            'as_chunks': as_chunks,
        }
        return self.metadata.update(updated_metadata)

    def _save_database_transaction(
        self,
        save_dir: Path | str,
        has_fatal_errors: bool,
        as_chunks: bool,
    ) -> None:
        transaction = ProjectSaveTransaction(save_dir)
        transaction.stage(
            lambda data_dir: DB.write_game_data(data_dir, as_chunks=as_chunks),
            self._build_metadata_payload(has_fatal_errors, as_chunks),
        )
        transaction.commit()

    def _choose_pending_save_recovery(self, project_dir: Path) -> Optional[str]:
        dialog = QMessageBox(self.parent)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("Interrupted Project Save")
        dialog.setText("An interrupted Save was found for this project.")
        dialog.setInformativeText(
            "Choose which complete snapshot to keep. The resources folder is unchanged.\n\n"
            "Project: %s" % project_dir
        )
        finish_button = dialog.addButton("Finish Pending Save", QMessageBox.AcceptRole)
        restore_button = dialog.addButton("Restore Previous Project", QMessageBox.DestructiveRole)
        cancel_button = dialog.addButton(QMessageBox.Cancel)
        dialog.exec_()
        if dialog.clickedButton() is finish_button:
            return "complete"
        if dialog.clickedButton() is restore_button:
            return "restore"
        if dialog.clickedButton() is cancel_button:
            return None
        return None

    def _recover_pending_project_save(
        self,
        project_dir: Path | str,
        interactive: bool,
    ) -> RecoveryResult:
        project_path = Path(project_dir)
        try:
            # SAVE_BACKUP has its own series of file renames. Recover that
            # outer operation first, before looking for a nested database
            # transaction inside the project directory.
            if ProjectBackupMergeTransaction.has_pending(project_path):
                if ProjectBackupMergeTransaction.is_active(project_path):
                    error = RuntimeError(
                        "Another LT Maker process is still merging this project's backup"
                    )
                    logging.warning("%s: %s", error, project_path)
                    if interactive:
                        QMessageBox.warning(
                            self.parent,
                            "Project Save In Progress",
                            "Another LT Maker instance is still finishing this project's "
                            "backup. Wait for it to finish before opening, saving, or "
                            "recovering it.\n\nProject: %s" % project_path,
                        )
                    return "failed"
                backup_result = ProjectBackupMergeTransaction.recover(project_path)
                if backup_result == "restored":
                    logging.warning(
                        "Recovered the previous SAVE_BACKUP project snapshot at %s",
                        project_path,
                    )
                    return "restored"
                if backup_result == "finalized":
                    logging.info(
                        "Finalized the completed SAVE_BACKUP project snapshot at %s",
                        project_path,
                    )
                    return "finalized"

            # A journal alone is not proof that its owner crashed.  Do not let
            # another editor instance discard or complete staging while the
            # writer still holds the OS-level transaction lock.
            if (
                ProjectSaveTransaction.has_pending(project_path)
                and ProjectSaveTransaction.is_active(project_path)
            ):
                error = RuntimeError(
                    "Another LT Maker process is still saving this project"
                )
                logging.warning("%s: %s", error, project_path)
                if interactive:
                    QMessageBox.warning(
                        self.parent,
                        "Project Save In Progress",
                        "Another LT Maker instance is still saving this project. "
                        "Wait for it to finish before opening, saving, or recovering it.\n\n"
                        "Project: %s" % project_path,
                    )
                return "failed"

            transaction = ProjectSaveTransaction.load_pending(project_path)
            if transaction is None:
                return "none"

            if transaction.is_installed:
                ProjectSaveTransaction.recover(project_path, "complete")
                return "finalized"

            if not transaction.can_complete:
                logging.warning(
                    "Discarding incomplete project-save staging at %s and keeping the old project.",
                    project_path,
                )
                ProjectSaveTransaction.recover(project_path, "restore")
                return "restored"

            if not interactive:
                logging.warning(
                    "Autosave found a recoverable transaction at %s; keeping its previous database and metadata.",
                    project_path,
                )
                ProjectSaveTransaction.recover(project_path, "restore")
                return "restored"

            action = self._choose_pending_save_recovery(project_path)
            if action is None:
                return "cancelled"
            if action == "complete":
                ProjectSaveTransaction.recover(project_path, "complete")
                return "completed"
            ProjectSaveTransaction.recover(project_path, "restore")
            return "restored"
        except (OSError, RuntimeError) as error:
            logging.exception("Could not recover pending project save at %s", project_path)
            if interactive:
                QMessageBox.critical(
                    self.parent,
                    "Project Save Recovery Failed",
                    "LT Maker could not safely recover the interrupted Save.\n\n"
                    "Project: %s\n\nDetails: %s" % (project_path, error),
                )
            return "failed"

    def _restore_project_backup(self, backup_path: Path | str) -> None:
        project_path = Path(self.current_proj)
        backup_path = Path(backup_path)
        expected_backup_name = project_path.name + '.lttmp'
        if (
            backup_path.parent != project_path.parent
            or backup_path.name != expected_backup_name
            or not backup_path.is_dir()
        ):
            raise RuntimeError("Refusing to restore an unexpected project backup path")
        if project_path.exists():
            shutil.rmtree(project_path)
        replace_with_retry(backup_path, project_path)

    def _restore_project_backup_after_failure(
        self,
        backup_path: Optional[Path],
        transaction: Optional[ProjectBackupMergeTransaction] = None,
    ) -> bool:
        if backup_path is None:
            return True
        try:
            if transaction is not None:
                transaction.abort()
            else:
                self._restore_project_backup(backup_path)
            return True
        except (OSError, RuntimeError):
            logging.exception("Could not restore project backup at %s", backup_path)
            return False

    def _merge_project_backup(
        self,
        backup_path: Path,
        transaction: Optional[ProjectBackupMergeTransaction] = None,
    ) -> None:
        transaction = transaction or ProjectBackupMergeTransaction(self.current_proj)
        if Path(backup_path) != transaction.backup_path:
            raise RuntimeError("Refusing to merge an unexpected project backup path")
        transaction.merge()

    def _display_save_error(self, section: str, error: Optional[BaseException] = None) -> None:
        self.save_progress.setValue(100)
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Critical)
        error_msg.setWindowTitle("Serialization Error")
        if isinstance(error, PermissionError):
            source_path = error.filename or self.current_proj
            destination_path = error.filename2
            path_details = source_path
            if destination_path:
                path_details = "%s\n\u2192 %s" % (source_path, destination_path)
            error_msg.setText(
                "LT Maker could not replace this file or folder:\n%s\n\n"
                "Windows reports that one of these paths is in use or access is denied. Close any editor, "
                "sync client, or antivirus scan using it, then try Save again. The previous "
                "game data and metadata were kept for recovery.\n\nDetails: %s"
                % (path_details, error)
            )
        elif error is not None:
            error_msg.setText(
                "LT Maker could not save your project's %s.\n\n"
                "The previous game data and metadata were kept when possible.\n\nDetails: %s"
                % (section, error)
            )
        else:
            error_msg.setText(
                "LT Maker could not save your project's %s. Check disk space and folder permissions, "
                "then try again. For detailed logs, use View Logs in the Extra menu."
                % section
            )
        error_msg.exec_()

    @save_mutex
    def save(self, new:bool=False, as_chunks:Optional[bool]=None) -> bool:
        # make sure no errors in DB exist
        # if we make a mistake in validation,
        # we should allow the save so
        # the user can make a game
        try:
            checker = DBChecker(DB, RESOURCES)
            checker.repair()
            any_errors = checker.validate_for_errors()
            has_fatal_errors = bool(any_errors)
        except Exception as e:
            QMessageBox.warning(self.parent, "Validation warning", "Validation failed with error. Please send this message to the devs.\nYour save will continue as normal.\nException:\n" + traceback.format_exc())
            has_fatal_errors = False

        # Returns whether we successfully saved
        # check if we're editing default, if so, prompt to save as
        if new or not self.current_proj or os.path.basename(self.current_proj) == DEFAULT_PROJECT:
            if os.path.basename(self.current_proj) == DEFAULT_PROJECT:
                starting_path = appdirs.user_documents_dir()
            else:
                starting_path = Path(self.current_proj or QDir.currentPath()).parent
            fn, ok = QFileDialog.getSaveFileName(self.parent, "Save Project", str(starting_path),
                                                 "All Files (*)")
            if ok:
                # Make sure you can't save as "autosave" or "default"
                if os.path.split(fn)[-1] in RESERVED_PROJECT_PATHS:
                    QMessageBox.critical(
                        self.parent, "Save Error", "You cannot save project as <b>%s</b> or <b>autosave.ltproj</b>!\nChoose another name." % DEFAULT_PROJECT)
                    return False
                if fn.endswith('.ltproj'):
                    self.current_proj = fn
                else:
                    self.current_proj = fn + '.ltproj'
                self.settings.set_current_project(self.current_proj)
            else:
                return False
            new = True

        if new:
            if os.path.exists(self.current_proj):
                ret = QMessageBox.warning(self.parent, "Save Project", "The file already exists.\nDo you want to overwrite it?",
                                          QMessageBox.Save | QMessageBox.Cancel)
                if ret == QMessageBox.Save:
                    pass
                else:
                    return False

        recovery_result = self._recover_pending_project_save(self.current_proj, interactive=True)
        if recovery_result != "none":
            if recovery_result not in ("cancelled", "failed"):
                # The selected snapshot is now on disk. Reload it instead of
                # applying the current in-memory edits over the user's choice.
                self.load()
            return False

        backup_path: Optional[Path] = None
        backup_transaction: Optional[ProjectBackupMergeTransaction] = None
        # Make directory for saving if it doesn't already exist
        if not new and self.settings.get_preference(Preference.SAVE_BACKUP):
            # we will copy the existing save (whichever is more recent)
            # as a backup
            self.tmp_proj = self.current_proj + '.lttmp'
            backup_path = Path(self.tmp_proj)
            self.save_progress.setLabelText(
                "Making backup to %s" % self.tmp_proj)
            self.save_progress.setValue(1)
            try:
                if os.path.exists(self.tmp_proj):
                    shutil.rmtree(self.tmp_proj)

                backup_transaction = ProjectBackupMergeTransaction(self.current_proj)
                backup_transaction.begin_backup()
                backup_path = backup_transaction.backup_path
            except (OSError, RuntimeError) as error:
                self._display_save_error("backup", error)
                return False
        self.save_progress.setLabelText(
            "Saving project to %s" % self.current_proj)
        self.save_progress.setValue(10)

        success = RESOURCES.save(self.current_proj, progress=self.save_progress)
        if not success:
            self._restore_project_backup_after_failure(backup_path, backup_transaction)
            self._display_save_error("resources")
            return False
        try:
            if backup_transaction is not None:
                backup_transaction.mark_resources_saved()
        except (OSError, RuntimeError) as error:
            self._restore_project_backup_after_failure(backup_path, backup_transaction)
            self._display_save_error("resources", error)
            return False
        self.save_progress.setValue(75)

        if as_chunks is None:
            as_chunks = self.settings.get_preference(Preference.SAVE_CHUNKS)

        try:
            self._save_database_transaction(self.current_proj, has_fatal_errors, as_chunks)
            if backup_transaction is not None:
                backup_transaction.mark_database_committed()
        except (OSError, RuntimeError) as error:
            self._restore_project_backup_after_failure(backup_path, backup_transaction)
            self._display_save_error("database", error)
            return False
        self.save_progress.setValue(85)

        self.save_progress.setValue(87)
        if backup_path is not None:
            try:
                self._merge_project_backup(backup_path, backup_transaction)
            except (OSError, RuntimeError) as error:
                logging.exception("Could not finalize SAVE_BACKUP merge at %s", backup_path)
                self._display_save_error("backup merge", error)
                return False
        self.save_progress.setValue(100)

        self.settings.append_or_bump_project(DB.constants.value('title') or os.path.basename(self.current_proj), self.current_proj)

        if has_fatal_errors:
            self.display_fatal_errors()

        return True

    def new(self):
        if not self.maybe_save():
            return False
        project_initializer = ProjectInitializer()
        result = project_initializer.full_create_new_project()
        if result:
            _, _, path = result
            self.current_proj = path
            self.settings.set_current_project(path)
        self.load()
        return result

    def open(self) -> bool:
        if self.maybe_save():
            # Go up one directory when starting
            fn = choose_recent_project(load_only=True)
            if fn:
                if not fn.endswith('.ltproj'):
                    QMessageBox.warning(self.parent, "Incorrect directory type",
                                        "%s is not an .ltproj." % fn)
                    return False
                self.current_proj = fn
                self.settings.set_current_project(self.current_proj)
                logging.info("Opening project %s" % self.current_proj)
                return self.load()
            else:
                return False
        return False

    def auto_open(self, project_path: Optional[str] = None):
        path = project_path or self.settings.get_current_project()
        logging.info("Auto Open: %s" % path)
        if path and (
            os.path.exists(path)
            or ProjectBackupMergeTransaction.has_pending(path)
            or ProjectSaveTransaction.has_pending(path)
        ):
            try:
                self.current_proj = path
                self.settings.set_current_project(self.current_proj)
                return self.load()
            except exceptions.CustomComponentsException as e:
                logging.exception(e)
                logging.error("Failed to load project at %s due to syntax error. Likely there's a problem in your Custom Components file, located at %s. See error above." % (
                    path, RESOURCES.get_custom_components_path()))
                QMessageBox.warning(self.parent, "Load of project failed",
                                    "Failed to load project at %s due to syntax error. Likely there's a problem in your Custom Components file, located at %s. Exception:\n%s." % (path, RESOURCES.get_custom_components_path(), e))
                return False
            except Exception as e:
                logging.exception(e)
                logging.warning(
                    "Failed to load project at %s.", path)
                show_warning_message("Project load failed", "Failed to load project at %s" % path, detailed_text=str(e))
                return False
        logging.warning(
            "path %s not found. Falling back to %s" % (path, DEFAULT_PROJECT))
        QMessageBox.warning(self.parent, "Load of project failed",
                            "Failed to load project at %s - path doesn't exist" % path)
        return False

    def load(self) -> bool:
        curr_proj_path = Path(self.current_proj)
        recovery_result = self._recover_pending_project_save(curr_proj_path, interactive=True)
        if recovery_result in ("cancelled", "failed"):
            return False
        if not curr_proj_path.exists():
            return False
        self.file_manager = FileManager(curr_proj_path)
        try:
            self.metadata = dataclass_from_dict(Metadata, self.file_manager.load_json(Path('metadata.json')))
        except Exception:
            self.metadata = Metadata()

        if self.metadata.serialization_version < CURRENT_SERIALIZATION_VERSION:
            ret = QMessageBox.warning(self.parent, "Main Editor",
                                        "Project serialization version %d is outdated. The engine requires serialization version %d.\n"
                                        "Apply updates?" % (self.metadata.serialization_version, CURRENT_SERIALIZATION_VERSION),
                                        QMessageBox.Ok | QMessageBox.Cancel)
            if ret == QMessageBox.Ok:
                pass
            elif ret == QMessageBox.Cancel:
                return False

        RESOURCES.load(self.current_proj, self.metadata.serialization_version)
        DB.load(curr_proj_path, self.metadata.serialization_version)

        if self.metadata.serialization_version < CURRENT_SERIALIZATION_VERSION:
            self.save()     # To ensure updates from migration are saved

        self.settings.append_or_bump_project(
            DB.constants.value('title') or os.path.basename(self.current_proj), self.current_proj)
        return True

    @save_mutex
    def autosave(self):
        project_nid = DB.constants.value('game_nid').replace(' ', '_')
        autosave_path = os.path.abspath('autosave_%s.ltproj' % project_nid)
        self.autosave_progress.setLabelText(
            "Autosaving project to %s" % autosave_path)
        autosave_dir = os.path.abspath(autosave_path)
        # Make directory for saving if it doesn't already exist
        if not os.path.isdir(autosave_dir):
            os.mkdir(autosave_dir)
        recovery_result = self._recover_pending_project_save(autosave_dir, interactive=False)
        if recovery_result != "none":
            if recovery_result == "failed":
                logging.error("Autosave recovery failed at %s; the previous autosave was left unchanged.", autosave_dir)
            else:
                logging.info("Autosave recovery completed at %s; skipping this autosave tick.", autosave_dir)
            self.autosave_progress.setValue(100)
            return
        self.autosave_progress.setValue(1)

        try:
            self.parent.status_bar.showMessage(
                'Autosaving project to %s...' % autosave_dir)
        except Exception:
            pass

        # Actually save project
        logging.info("Autosaving project to %s..." % autosave_dir)
        RESOURCES.autosave(self.current_proj, autosave_dir,
                           self.autosave_progress)
        self.autosave_progress.setValue(75)
        as_chunks = self.settings.get_preference(Preference.SAVE_CHUNKS)
        try:
            self._save_database_transaction(
                autosave_dir,
                self.metadata.has_fatal_errors,
                as_chunks,
            )
        except (OSError, RuntimeError):
            logging.exception(
                "Autosave database transaction failed at %s; the previous database and metadata were kept.",
                autosave_dir,
            )
            try:
                self.parent.status_bar.showMessage(
                    'Autosave could not finish; the previous autosave was kept.')
            except Exception:
                pass
            self.autosave_progress.setValue(100)
            return
        self.autosave_progress.setValue(99)

        try:
            self.parent.status_bar.showMessage(
                'Autosave to %s complete!' % autosave_dir)
        except Exception:
            pass
        self.autosave_progress.setValue(100)

    def save_metadata(self, save_dir: Path, has_fatal_errors: bool, as_chunks: bool) -> None:
        save_json(
            Path(save_dir) / 'metadata.json',
            self._build_metadata_payload(has_fatal_errors, as_chunks),
        )

    def get_unused_files(self) -> Dict[str, List[str]]:
        return RESOURCES.get_unused_files(self.current_proj)

    def clean(self, unused_files: Dict[str, List[str]]):
        RESOURCES.clean(unused_files)

    def dump_csv(self, db: Database):
        starting_path = self.current_proj or QDir.currentPath()
        fn = QFileDialog.getExistingDirectory(
            self.parent, "Choose dump location", starting_path)
        if fn:
            csv_direc = fn
            for ttype, tstr in csv_data_exporter.dump_as_csv(db, RESOURCES):
                with open(os.path.join(csv_direc, ttype + '.csv'), 'w') as f:
                    f.write(tstr)
        else:
            return False

    def dump_script(self, db: Database, single_block=True):
        starting_path = self.current_proj or QDir.currentPath()
        fn = QFileDialog.getExistingDirectory(
            self.parent, "Choose dump location", starting_path)
        if fn:
            script_direc = os.path.join(fn, 'script')
            if not os.path.exists(script_direc):
                os.mkdir(script_direc)
            else:
                shutil.rmtree(script_direc)
                os.mkdir(script_direc)
            if single_block:
                with open(os.path.join(script_direc, "script.txt"), 'w') as f:
                    for level_nid, event_dict in text_data_exporter.dump_script(db.events, db.levels).items():
                        for event_nid, event_script in event_dict.items():
                            f.write(event_script + "\n")
            else:
                for level_nid, event_dict in text_data_exporter.dump_script(db.events, db.levels).items():
                    level_direc = os.path.join(script_direc, level_nid)
                    if not os.path.exists(level_direc):
                        os.mkdir(level_direc)
                    else:
                        shutil.rmtree(level_direc)
                        os.mkdir(level_direc)
                    for event_nid, event_script in event_dict.items():
                        with open(os.path.join(level_direc, event_nid + '.txt'), 'w') as f:
                            f.write(event_script)
        else:
            return False
