import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from app.data.database.database import Database
from app.editor.file_manager import project_file_backend
from app.editor.file_manager.project_file_backend import ProjectFileBackend
from app.utilities import serialization


def _access_denied(source: Path, destination: Path) -> PermissionError:
    error = PermissionError(5, "Access is denied", str(source))
    error.filename2 = str(destination)
    return error


class SaveJsonRetryTests(unittest.TestCase):
    def test_save_json_retries_a_transient_replace_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "overworlds.json"
            path.write_text(json.dumps({"version": "old"}), encoding="utf-8")
            real_replace = os.replace

            attempts = 0

            def fail_once(source, destination):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise _access_denied(Path(source), Path(destination))
                real_replace(source, destination)

            with mock.patch.object(
                serialization.os,
                "replace",
                side_effect=fail_once,
            ) as replace, mock.patch.object(serialization.time, "sleep") as sleep:
                serialization.save_json(path, {"version": "new"})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"version": "new"})
            self.assertEqual(replace.call_count, 2)
            sleep.assert_called_once_with(serialization.REPLACE_RETRY_DELAYS[0])

    def test_save_json_keeps_the_previous_file_after_a_persistent_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "overworlds.json"
            temporary_path = path.with_suffix(".json.tmp")
            path.write_text(json.dumps({"version": "old"}), encoding="utf-8")

            with mock.patch.object(
                serialization.os,
                "replace",
                side_effect=_access_denied(temporary_path, path),
            ) as replace, mock.patch.object(serialization.time, "sleep"):
                with self.assertRaises(PermissionError) as raised:
                    serialization.save_json(path, {"version": "new"})

            self.assertEqual(raised.exception.filename2, str(path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"version": "old"})
            self.assertEqual(
                json.loads(temporary_path.read_text(encoding="utf-8")),
                {"version": "new"},
            )
            self.assertEqual(replace.call_count, len(serialization.REPLACE_RETRY_DELAYS) + 1)


class DatabaseWriteGameDataTests(unittest.TestCase):
    def test_writer_supports_chunked_staging_and_legacy_serialize_returns_bool(self):
        database = Database()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project.ltproj"
            staged_data_dir = Path(temp_dir) / "staged-game_data"
            payload = {"items": [{"nid": "Iron Sword"}]}

            with mock.patch.object(database, "save", return_value=payload):
                database.write_game_data(staged_data_dir, as_chunks=True)

            self.assertEqual(
                json.loads((staged_data_dir / "items" / "Iron_Sword.json").read_text(encoding="utf-8")),
                [{"nid": "Iron Sword"}],
            )
            self.assertEqual(
                json.loads((staged_data_dir / "items" / ".orderkeys").read_text(encoding="utf-8")),
                ["Iron_Sword"],
            )

            with mock.patch.object(
                database,
                "write_game_data",
                side_effect=_access_denied(staged_data_dir, project_dir / "game_data"),
            ):
                self.assertFalse(database.serialize(project_dir, as_chunks=True))


class ProjectFileBackendTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name) / "project.ltproj"
        self.project_dir.mkdir()
        game_data = self.project_dir / "game_data"
        game_data.mkdir()
        (game_data / "marker.json").write_text('{"version": "old"}', encoding="utf-8")
        (self.project_dir / "metadata.json").write_text('{"version": "old"}', encoding="utf-8")

        self.backend = object.__new__(ProjectFileBackend)
        self.backend.current_proj = str(self.project_dir)
        self.backend.parent = mock.Mock()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _begin_save_backup(self) -> serialization.ProjectBackupMergeTransaction:
        transaction = serialization.ProjectBackupMergeTransaction(self.project_dir)
        transaction.begin_backup()
        return transaction

    def test_autosave_recovery_is_noninteractive_and_keeps_previous_snapshot(self):
        transaction = serialization.ProjectSaveTransaction(self.project_dir)
        transaction.stage(
            lambda data_dir: (data_dir / "marker.json").write_text(
                '{"version": "new"}',
                encoding="utf-8",
            ),
            {"version": "new"},
        )
        # A pending journal from a previous process has no live file lock.
        transaction._release_lock()

        self.assertEqual(
            self.backend._recover_pending_project_save(self.project_dir, interactive=False),
            "restored",
        )
        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse(transaction.journal_path.exists())

    def test_interactive_recovery_offers_completion_after_partial_install(self):
        transaction = serialization.ProjectSaveTransaction(self.project_dir)
        transaction.stage(
            lambda data_dir: (data_dir / "marker.json").write_text(
                '{"version": "new"}',
                encoding="utf-8",
            ),
            {"version": "new"},
        )
        transaction._write_journal("committing")
        transaction._move_current_to_backups()
        serialization.replace_with_retry(
            transaction.staged_game_data,
            transaction.game_data_path,
        )
        transaction._release_lock()

        pending = serialization.ProjectSaveTransaction.load_pending(self.project_dir)
        self.assertIsNotNone(pending)
        self.assertTrue(pending.can_complete)
        self.assertFalse(pending.is_installed)
        with mock.patch.object(
            self.backend,
            "_choose_pending_save_recovery",
            return_value="complete",
        ):
            self.assertEqual(
                self.backend._recover_pending_project_save(self.project_dir, interactive=True),
                "completed",
            )

        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )

    def test_noninteractive_recovery_keeps_new_data_after_committed_journal_write_fails(self):
        transaction = serialization.ProjectSaveTransaction(self.project_dir)
        transaction.stage(
            lambda data_dir: (data_dir / "marker.json").write_text(
                '{"version": "new"}',
                encoding="utf-8",
            ),
            {"version": "new"},
        )
        real_write_journal = transaction._write_journal

        def fail_committed_journal(state: str) -> None:
            if state == "committed":
                transaction.state = state
                raise _access_denied(
                    transaction.journal_path.with_name(transaction.journal_path.name + ".tmp"),
                    transaction.journal_path,
                )
            real_write_journal(state)

        with mock.patch.object(transaction, "_write_journal", side_effect=fail_committed_journal):
            transaction.commit()

        pending = serialization.ProjectSaveTransaction.load_pending(self.project_dir)
        self.assertIsNotNone(pending)
        self.assertEqual("committing", pending.state)
        self.assertTrue(pending.is_installed)
        self.assertTrue(pending.commit_marker.is_file())
        self.assertEqual(
            self.backend._recover_pending_project_save(self.project_dir, interactive=False),
            "finalized",
        )
        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertFalse(pending.journal_path.exists())
        self.assertFalse(pending.commit_marker.exists())

    def test_an_active_save_is_not_recovered_by_another_editor_instance(self):
        transaction = serialization.ProjectSaveTransaction(self.project_dir)
        transaction.stage(
            lambda data_dir: (data_dir / "marker.json").write_text(
                '{"version": "new"}',
                encoding="utf-8",
            ),
            {"version": "new"},
        )
        try:
            self.assertTrue(serialization.ProjectSaveTransaction.is_active(self.project_dir))
            self.assertEqual(
                self.backend._recover_pending_project_save(self.project_dir, interactive=False),
                "failed",
            )
            self.assertTrue(transaction.journal_path.exists())
            self.assertTrue(transaction.staged_game_data.exists())
        finally:
            transaction._release_lock()
            serialization.ProjectSaveTransaction.recover(self.project_dir, "restore")

    def test_save_backup_restoration_replaces_partial_project_with_backup(self):
        backup_path = Path(str(self.project_dir) + ".lttmp")
        backup_path.mkdir()
        backup_game_data = backup_path / "game_data"
        backup_game_data.mkdir()
        (backup_game_data / "marker.json").write_text('{"version": "backup"}', encoding="utf-8")
        (backup_path / "metadata.json").write_text('{"version": "backup"}', encoding="utf-8")

        (self.project_dir / "game_data" / "marker.json").write_text(
            '{"version": "partial"}',
            encoding="utf-8",
        )
        self.backend._restore_project_backup(backup_path)

        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "backup"},
        )
        self.assertFalse(backup_path.exists())

    def test_save_backup_merge_rolls_back_on_a_locked_new_file(self):
        backup_path = Path(str(self.project_dir) + ".lttmp")
        backup_game_data = backup_path / "game_data"
        backup_game_data.mkdir(parents=True)
        (backup_game_data / "marker.json").write_text('{"version": "old"}', encoding="utf-8")
        (backup_path / "metadata.json").write_text('{"version": "old"}', encoding="utf-8")
        (self.project_dir / "game_data" / "marker.json").write_text(
            '{"version": "new"}',
            encoding="utf-8",
        )
        (self.project_dir / "metadata.json").write_text('{"version": "new"}', encoding="utf-8")
        real_replace = serialization.replace_with_retry

        def lock_new_marker(source: Path, destination: Path, **kwargs) -> None:
            if Path(source) == self.project_dir / "game_data" / "marker.json":
                raise _access_denied(Path(source), Path(destination))
            real_replace(source, destination, **kwargs)

        with mock.patch.object(
            serialization,
            "replace_with_retry",
            side_effect=lock_new_marker,
        ):
            with self.assertRaises(PermissionError):
                self.backend._merge_project_backup(backup_path)

        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse(backup_path.exists())

    def test_save_backup_merge_recovers_the_old_project_after_an_interrupt(self):
        backup_path = Path(str(self.project_dir) + ".lttmp")
        backup_game_data = backup_path / "game_data"
        backup_game_data.mkdir(parents=True)
        (backup_game_data / "marker.json").write_text('{"version": "old"}', encoding="utf-8")
        (backup_path / "metadata.json").write_text('{"version": "old"}', encoding="utf-8")
        (self.project_dir / "game_data" / "marker.json").write_text(
            '{"version": "new"}',
            encoding="utf-8",
        )
        (self.project_dir / "metadata.json").write_text('{"version": "new"}', encoding="utf-8")
        real_replace = serialization.replace_with_retry

        def interrupt_before_new_marker(source: Path, destination: Path, **kwargs) -> None:
            if Path(source) == self.project_dir / "game_data" / "marker.json":
                raise KeyboardInterrupt
            real_replace(source, destination, **kwargs)

        with mock.patch.object(
            serialization,
            "replace_with_retry",
            side_effect=interrupt_before_new_marker,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.backend._merge_project_backup(backup_path)

        self.assertTrue(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))
        self.assertEqual(
            self.backend._recover_pending_project_save(self.project_dir, interactive=False),
            "restored",
        )
        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))

    def test_save_backup_merge_finishes_a_complete_snapshot_after_an_interrupt(self):
        backup_path = Path(str(self.project_dir) + ".lttmp")
        backup_game_data = backup_path / "game_data"
        backup_game_data.mkdir(parents=True)
        (backup_game_data / "marker.json").write_text('{"version": "old"}', encoding="utf-8")
        (backup_path / "metadata.json").write_text('{"version": "old"}', encoding="utf-8")
        (self.project_dir / "game_data" / "marker.json").write_text(
            '{"version": "new"}',
            encoding="utf-8",
        )
        (self.project_dir / "metadata.json").write_text('{"version": "new"}', encoding="utf-8")

        with mock.patch.object(
            serialization.ProjectBackupMergeTransaction,
            "_finish_install",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.backend._merge_project_backup(backup_path)

        self.assertEqual(
            self.backend._recover_pending_project_save(self.project_dir, interactive=False),
            "finalized",
        )
        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertFalse(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))

    def test_active_save_backup_merge_is_not_recovered_by_another_editor(self):
        backup_path = Path(str(self.project_dir) + ".lttmp")
        backup_game_data = backup_path / "game_data"
        backup_game_data.mkdir(parents=True)
        (backup_game_data / "marker.json").write_text('{"version": "backup"}', encoding="utf-8")
        (backup_path / "metadata.json").write_text('{"version": "backup"}', encoding="utf-8")
        transaction = serialization.ProjectBackupMergeTransaction(self.project_dir)
        transaction._acquire_lock()
        transaction._create_journal("merging")
        try:
            self.assertTrue(serialization.ProjectBackupMergeTransaction.is_active(self.project_dir))
            self.assertEqual(
                self.backend._recover_pending_project_save(self.project_dir, interactive=False),
                "failed",
            )
            self.assertTrue(transaction.journal_path.exists())
        finally:
            transaction._release_lock()
            serialization.ProjectBackupMergeTransaction.recover(self.project_dir)

    def test_save_backup_journal_and_lock_start_before_resources_are_written(self):
        transaction = self._begin_save_backup()
        try:
            self.assertTrue(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))
            self.assertTrue(serialization.ProjectBackupMergeTransaction.is_active(self.project_dir))
            self.assertFalse(self.project_dir.exists())
            self.assertEqual(
                json.loads(
                    (transaction.backup_path / "game_data" / "marker.json").read_text(
                        encoding="utf-8"
                    )
                ),
                {"version": "old"},
            )
        finally:
            transaction.abort()

        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))

    def test_save_backup_recovers_the_old_project_after_a_resources_phase_crash(self):
        transaction = self._begin_save_backup()
        self.project_dir.mkdir()
        (self.project_dir / "resources").mkdir()
        (self.project_dir / "resources" / "partial.txt").write_text("new", encoding="utf-8")
        transaction._release_lock()

        self.assertEqual(
            self.backend._recover_pending_project_save(self.project_dir, interactive=False),
            "restored",
        )
        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse((self.project_dir / "resources" / "partial.txt").exists())

    def test_save_backup_finishes_restore_after_interruption_between_root_renames(self):
        transaction = self._begin_save_backup()
        self.project_dir.mkdir()
        game_data = self.project_dir / "game_data"
        game_data.mkdir()
        (game_data / "marker.json").write_text('{"version": "new"}', encoding="utf-8")
        (self.project_dir / "metadata.json").write_text('{"version": "new"}', encoding="utf-8")
        transaction.mark_resources_saved()
        transaction.mark_database_committed()
        real_replace = serialization.replace_with_retry

        def interrupt_final_restore(source: Path, destination: Path, **kwargs) -> None:
            if Path(source) == transaction.backup_path and Path(destination) == self.project_dir:
                raise KeyboardInterrupt
            real_replace(source, destination, **kwargs)

        with mock.patch.object(
            serialization,
            "replace_with_retry",
            side_effect=interrupt_final_restore,
        ):
            with self.assertRaises(KeyboardInterrupt):
                transaction._restore_previous_project()
        transaction._release_lock()

        self.assertFalse(self.project_dir.exists())
        self.assertTrue(transaction.backup_path.exists())
        self.assertEqual(
            self.backend._recover_pending_project_save(self.project_dir, interactive=False),
            "restored",
        )
        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )

    def test_save_backup_finishes_a_database_committed_snapshot_after_a_crash(self):
        transaction = self._begin_save_backup()
        self.project_dir.mkdir()
        game_data = self.project_dir / "game_data"
        game_data.mkdir()
        (game_data / "marker.json").write_text('{"version": "new"}', encoding="utf-8")
        (self.project_dir / "metadata.json").write_text('{"version": "new"}', encoding="utf-8")
        transaction.mark_resources_saved()
        transaction.mark_database_committed()
        transaction._release_lock()

        self.assertEqual(
            self.backend._recover_pending_project_save(self.project_dir, interactive=False),
            "finalized",
        )
        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertFalse(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))

    def test_rejects_an_unsafe_save_backup_merge_journal_path(self):
        outside_path = self.project_dir.parent / "must-not-be-touched.json"
        outside_path.write_text('{"version": "safe"}', encoding="utf-8")
        transaction = serialization.ProjectBackupMergeTransaction(self.project_dir)
        journal = {
            "version": serialization.ProjectBackupMergeTransaction.JOURNAL_VERSION,
            "transaction_id": transaction.transaction_id,
            "state": "merging",
            "old_moves": ["../must-not-be-touched.json"],
            "new_moves": [],
        }
        transaction.journal_path.write_text(json.dumps(journal), encoding="utf-8")

        with self.assertRaises(RuntimeError):
            serialization.ProjectBackupMergeTransaction.load_pending(self.project_dir)

        self.assertEqual(
            json.loads(outside_path.read_text(encoding="utf-8")),
            {"version": "safe"},
        )

    def test_save_does_not_overwrite_a_snapshot_selected_for_recovery(self):
        self.backend.settings = mock.Mock()
        self.backend._recover_pending_project_save = mock.Mock(return_value="restored")
        self.backend.load = mock.Mock(return_value=True)

        checker = mock.Mock()
        checker.validate_for_errors.return_value = []
        with mock.patch.object(project_file_backend, "DBChecker", return_value=checker), \
                mock.patch.object(project_file_backend.RESOURCES, "save") as resources_save:
            result = ProjectFileBackend.save.__wrapped__(self.backend)

        self.assertFalse(result)
        self.backend.load.assert_called_once_with()
        resources_save.assert_not_called()

    def test_autosave_skips_the_current_tick_after_recovery(self):
        self.backend.settings = mock.Mock()
        self.backend.autosave_progress = mock.Mock()
        self.backend._recover_pending_project_save = mock.Mock(return_value="restored")
        temporary_autosave = str(Path(self.temp_dir.name) / "autosave.ltproj")

        with mock.patch.object(project_file_backend, "DB") as database, \
                mock.patch.object(project_file_backend, "RESOURCES") as resources, \
                mock.patch.object(project_file_backend.os.path, "abspath", return_value=temporary_autosave), \
                mock.patch.object(project_file_backend.os.path, "isdir", return_value=True):
            database.constants.value.return_value = "Test Game"
            ProjectFileBackend.autosave.__wrapped__(self.backend)

        resources.autosave.assert_not_called()

    def test_load_checks_for_a_pending_recovery_before_rejecting_a_missing_directory(self):
        self.backend._recover_pending_project_save = mock.Mock(return_value="failed")
        shutil.rmtree(self.project_dir)

        self.assertFalse(ProjectFileBackend.load(self.backend))
        self.backend._recover_pending_project_save.assert_called_once_with(
            self.project_dir,
            interactive=True,
        )

    def test_auto_open_accepts_a_missing_project_when_a_backup_journal_exists(self):
        self.backend.settings = mock.Mock()
        self.backend.load = mock.Mock(return_value=True)
        shutil.rmtree(self.project_dir)

        with mock.patch.object(
            serialization.ProjectBackupMergeTransaction,
            "has_pending",
            return_value=True,
        ):
            self.assertTrue(self.backend.auto_open(str(self.project_dir)))

        self.backend.load.assert_called_once_with()

    def test_save_backup_keeps_an_outer_journal_through_a_successful_editor_save(self):
        self.backend.settings = mock.Mock()
        self.backend.save_progress = mock.Mock()
        self.backend.display_fatal_errors = mock.Mock()
        self.backend.settings.get_preference.side_effect = (
            lambda preference: preference == project_file_backend.Preference.SAVE_BACKUP
        )
        self.backend._recover_pending_project_save = mock.Mock(return_value="none")

        def write_resources(project_path: str, progress) -> bool:
            resource_path = Path(project_path) / "resources"
            resource_path.mkdir(parents=True)
            (resource_path / "new-resource.txt").write_text("new", encoding="utf-8")
            return True

        def write_database(project_path: str, has_fatal_errors: bool, as_chunks: bool) -> None:
            game_data = Path(project_path) / "game_data"
            game_data.mkdir()
            (game_data / "marker.json").write_text('{"version": "new"}', encoding="utf-8")
            (Path(project_path) / "metadata.json").write_text('{"version": "new"}', encoding="utf-8")

        checker = mock.Mock()
        checker.validate_for_errors.return_value = []
        self.backend._save_database_transaction = mock.Mock(side_effect=write_database)
        with mock.patch.object(project_file_backend, "DBChecker", return_value=checker), \
                mock.patch.object(project_file_backend, "RESOURCES") as resources, \
                mock.patch.object(project_file_backend, "DB") as database:
            resources.save.side_effect = write_resources
            database.constants.value.return_value = "Test Game"

            self.assertTrue(ProjectFileBackend.save.__wrapped__(self.backend))

        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertTrue((self.project_dir / "resources" / "new-resource.txt").is_file())
        self.assertFalse(Path(str(self.project_dir) + ".lttmp").exists())
        self.assertFalse(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))

    def test_save_backup_restores_the_old_project_when_resource_save_fails(self):
        self.backend.settings = mock.Mock()
        self.backend.save_progress = mock.Mock()
        self.backend.settings.get_preference.side_effect = (
            lambda preference: preference == project_file_backend.Preference.SAVE_BACKUP
        )
        self.backend._recover_pending_project_save = mock.Mock(return_value="none")
        self.backend._display_save_error = mock.Mock()
        checker = mock.Mock()
        checker.validate_for_errors.return_value = []

        with mock.patch.object(project_file_backend, "DBChecker", return_value=checker), \
                mock.patch.object(project_file_backend, "RESOURCES") as resources:
            resources.save.return_value = False
            self.assertFalse(ProjectFileBackend.save.__wrapped__(self.backend))

        self.assertEqual(
            json.loads((self.project_dir / "game_data" / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse(Path(str(self.project_dir) + ".lttmp").exists())
        self.assertFalse(serialization.ProjectBackupMergeTransaction.has_pending(self.project_dir))


class ProjectSaveTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name) / "project.ltproj"
        self.project_dir.mkdir()
        self.game_data = self.project_dir / "game_data"
        self.game_data.mkdir()
        (self.game_data / "marker.json").write_text('{"version": "old"}', encoding="utf-8")
        (self.project_dir / "metadata.json").write_text('{"version": "old"}', encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _write_new_game_data(data_dir: Path) -> None:
        (data_dir / "marker.json").write_text('{"version": "new"}', encoding="utf-8")

    def _stage(self) -> serialization.ProjectSaveTransaction:
        transaction = serialization.ProjectSaveTransaction(self.project_dir)
        transaction.stage(self._write_new_game_data, {"version": "new"})
        return transaction

    def test_commit_replaces_game_data_and_metadata_together(self):
        transaction = self._stage()

        transaction.commit()

        self.assertEqual(
            json.loads((self.game_data / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertFalse(transaction.journal_path.exists())
        self.assertFalse(transaction.staged_game_data.exists())

    def test_commit_preserves_old_project_and_journal_when_game_data_is_locked(self):
        transaction = self._stage()
        real_replace = serialization.replace_with_retry

        def lock_game_data(source: Path, destination: Path, **kwargs) -> None:
            if Path(source) == self.game_data:
                raise _access_denied(Path(source), Path(destination))
            real_replace(source, destination, **kwargs)

        with mock.patch.object(
            serialization,
            "replace_with_retry",
            side_effect=lock_game_data,
        ), mock.patch.object(serialization.time, "sleep"):
            with self.assertRaises(PermissionError):
                transaction.commit()

        self.assertEqual(
            json.loads((self.game_data / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertTrue(transaction.journal_path.exists())
        self.assertTrue(transaction.staged_game_data.exists())

    def test_recovery_can_finish_a_staged_save_after_a_failed_commit(self):
        transaction = self._stage()
        real_replace = serialization.replace_with_retry

        def fail_staged_game_data(source: Path, destination: Path, **kwargs) -> None:
            if Path(source) == transaction.staged_game_data:
                raise _access_denied(Path(source), Path(destination))
            real_replace(source, destination, **kwargs)

        with mock.patch.object(
            serialization,
            "replace_with_retry",
            side_effect=fail_staged_game_data,
        ), mock.patch.object(serialization.time, "sleep"):
            with self.assertRaises(PermissionError):
                transaction.commit()

        serialization.ProjectSaveTransaction.recover(self.project_dir, "complete")

        self.assertEqual(
            json.loads((self.game_data / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertFalse(transaction.journal_path.exists())

    def test_recovery_finishes_a_save_interrupted_after_game_data_install(self):
        transaction = self._stage()
        transaction._write_journal("committing")
        transaction._move_current_to_backups()
        serialization.replace_with_retry(
            transaction.staged_game_data,
            transaction.game_data_path,
        )
        transaction._release_lock()

        serialization.ProjectSaveTransaction.recover(self.project_dir, "complete")

        self.assertEqual(
            json.loads((self.game_data / "marker.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "new"},
        )
        self.assertFalse(transaction.journal_path.exists())

    def test_recovery_restores_old_project_after_game_data_install(self):
        transaction = self._stage()
        transaction._write_journal("committing")
        transaction._move_current_to_backups()
        serialization.replace_with_retry(
            transaction.staged_game_data,
            transaction.game_data_path,
        )
        transaction._release_lock()

        serialization.ProjectSaveTransaction.recover(self.project_dir, "restore")

        self.assertEqual(
            json.loads((self.game_data / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse(transaction.journal_path.exists())

    def test_committing_journal_with_both_new_targets_preserves_restore_choice(self):
        transaction = self._stage()
        transaction._write_journal("committing")
        transaction._move_current_to_backups()
        transaction._install_staged_project()

        pending = serialization.ProjectSaveTransaction.load_pending(self.project_dir)
        self.assertIsNotNone(pending)
        self.assertTrue(pending.can_complete)
        self.assertFalse(pending.is_installed)

        transaction._release_lock()
        serialization.ProjectSaveTransaction.recover(self.project_dir, "restore")

        self.assertEqual(
            json.loads((self.game_data / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )

    def test_recovery_can_discard_a_staged_save_and_keep_the_old_project(self):
        transaction = self._stage()
        transaction._release_lock()

        serialization.ProjectSaveTransaction.recover(self.project_dir, "restore")

        self.assertEqual(
            json.loads((self.game_data / "marker.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertEqual(
            json.loads((self.project_dir / "metadata.json").read_text(encoding="utf-8")),
            {"version": "old"},
        )
        self.assertFalse(transaction.journal_path.exists())

    def test_rejects_a_journal_with_an_untrusted_transaction_identifier(self):
        outside_path = self.project_dir.parent / "must-not-be-touched.json"
        outside_path.write_text('{"version": "safe"}', encoding="utf-8")
        journal = {
            "version": serialization.ProjectSaveTransaction.JOURNAL_VERSION,
            "transaction_id": "../../must-not-be-touched",
            "state": "ready",
            "had_game_data": True,
            "had_metadata": True,
        }
        (self.project_dir / serialization.ProjectSaveTransaction.JOURNAL_FILENAME).write_text(
            json.dumps(journal),
            encoding="utf-8",
        )

        with self.assertRaises(RuntimeError):
            serialization.ProjectSaveTransaction.load_pending(self.project_dir)

        self.assertEqual(
            json.loads(outside_path.read_text(encoding="utf-8")),
            {"version": "safe"},
        )

    def test_stage_rejects_a_second_writer_with_an_existing_journal(self):
        first = self._stage()
        second = serialization.ProjectSaveTransaction(self.project_dir)

        with self.assertRaises(FileExistsError):
            second.stage(self._write_new_game_data, {"version": "newer"})

        try:
            self.assertTrue(first.journal_path.exists())
            self.assertEqual(
                json.loads((first.staged_game_data / "marker.json").read_text(encoding="utf-8")),
                {"version": "new"},
            )
        finally:
            first._release_lock()


if __name__ == "__main__":
    unittest.main()
