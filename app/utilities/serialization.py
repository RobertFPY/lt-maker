from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import logging
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Any, BinaryIO, Literal, Optional
from uuid import uuid4


# A short retry window absorbs transient Windows locks from antivirus, indexing,
# and sync clients without making a failed Save appear to hang indefinitely.
REPLACE_RETRY_DELAYS = (
    0.05,
    0.10,
    0.20,
    0.40,
    0.50,
    0.50,
    0.50,
    0.50,
    0.50,
    0.50,
    0.50,
    0.50,
    0.25,
)


def _clear_readonly_and_retry(func, path, _exc):
    """rmtree error handler: clear the read-only bit and retry.

    The most common cause of WinError 5 (access denied) when deleting a
    save directory on Windows is a read-only file. Make it writable and
    retry the failing operation once; if it still fails, let it raise.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree_robust(path):
    """shutil.rmtree that recovers from read-only files across Python versions."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_readonly_and_retry)
    else:
        # onerror gets (func, path, exc_info); adapt to our handler
        shutil.rmtree(path, onerror=lambda f, p, ei: _clear_readonly_and_retry(f, p, ei[1]))


def load_json(path: Path):
    if not path.exists():
       raise Exception("Path %s does not exist" % str(path))
    with path.open() as source:
        try:
            loaded = json.load(source)
        except Exception as e:
            raise Exception("Could not read %s" % str(path)) from e
        return loaded


def replace_with_retry(
    source: Path | str,
    destination: Path | str,
    *,
    retry_delays: tuple[float, ...] = REPLACE_RETRY_DELAYS,
) -> None:
    """Atomically replace *destination*, retrying only transient access locks."""
    source_path = Path(source)
    destination_path = Path(destination)
    for delay in (*retry_delays, None):
        try:
            os.replace(source_path, destination_path)
            return
        except PermissionError:
            if delay is None:
                raise
            logging.warning(
                "Save target is temporarily locked; retrying %s -> %s in %.2f seconds.",
                source_path,
                destination_path,
                delay,
            )
            time.sleep(delay)


def save_json(path: Path, value: Any, *, fsync: bool = False):
    """Atomically serialize JSON, optionally flushing it to disk first."""
    temp_save_loc = path.parent / (path.name + ".tmp")
    with open(temp_save_loc, 'w', encoding='utf-8') as serialize_file:
        json.dump(value, serialize_file, indent=4)
        serialize_file.flush()
        if fsync:
            os.fsync(serialize_file.fileno())
    replace_with_retry(temp_save_loc, path)


class ProjectSaveTransaction:
    """Commit ``game_data`` and ``metadata.json`` as one recoverable unit.

    Directory replacement is not one operating-system operation on Windows, so
    the journal records enough state to either restore the previous project or
    finish the staged Save after a crash or a persistent external file lock.
    """

    JOURNAL_FILENAME = ".lt-maker-save-transaction.json"
    LOCK_FILENAME = ".lt-maker-save-transaction.lock"
    JOURNAL_VERSION = 1
    _TRANSACTION_ID_RE = re.compile(r"[0-9a-f]{32}")
    _STATES = {"staging", "ready", "committing", "committed"}

    def __init__(self, project_dir: Path | str, transaction_id: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.transaction_id = transaction_id or uuid4().hex
        if not self._TRANSACTION_ID_RE.fullmatch(self.transaction_id):
            raise ValueError("Invalid project save transaction identifier")
        prefix = f".lt-save-{self.transaction_id}"
        self.game_data_path = self.project_dir / "game_data"
        self.metadata_path = self.project_dir / "metadata.json"
        self.staged_game_data = self.project_dir / f"{prefix}.game_data"
        self.staged_metadata = self.project_dir / f"{prefix}.metadata.json"
        self.backup_game_data = self.project_dir / f"{prefix}.backup-game_data"
        self.backup_metadata = self.project_dir / f"{prefix}.backup-metadata.json"
        self.commit_marker = self.project_dir / f"{prefix}.commit-installed"
        self.journal_path = self.project_dir / self.JOURNAL_FILENAME
        self.lock_path = self.project_dir / self.LOCK_FILENAME
        self._transaction_lock: Optional[BinaryIO] = None
        self.had_game_data = False
        self.had_metadata = False
        self.state = "staging"

    @classmethod
    def load_pending(cls, project_dir: Path | str) -> Optional[ProjectSaveTransaction]:
        project_path = Path(project_dir)
        journal_path = project_path / cls.JOURNAL_FILENAME
        if not journal_path.exists():
            return None
        try:
            with journal_path.open(encoding="utf-8") as journal_file:
                journal = json.load(journal_file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Cannot read the pending project save journal at {journal_path}"
            ) from error

        if not isinstance(journal, dict) or journal.get("version") != cls.JOURNAL_VERSION:
            raise RuntimeError(f"Unsupported project save journal at {journal_path}")
        transaction_id = journal.get("transaction_id")
        state = journal.get("state")
        had_game_data = journal.get("had_game_data")
        had_metadata = journal.get("had_metadata")
        if (
            not isinstance(transaction_id, str)
            or state not in cls._STATES
            or not isinstance(had_game_data, bool)
            or not isinstance(had_metadata, bool)
        ):
            raise RuntimeError(f"Invalid project save journal at {journal_path}")

        try:
            transaction = cls(project_path, transaction_id)
        except ValueError as error:
            raise RuntimeError(f"Invalid project save journal at {journal_path}") from error
        transaction.state = state
        transaction.had_game_data = had_game_data
        transaction.had_metadata = had_metadata
        return transaction

    @property
    def can_complete(self) -> bool:
        return (
            self._new_game_data_is_available()
            and self._new_metadata_is_available()
        )

    @property
    def is_installed(self) -> bool:
        return (
            (self.state == "committed" or self.commit_marker.is_file())
            and self.game_data_path.is_dir()
            and self.metadata_path.is_file()
            and not self.staged_game_data.exists()
            and not self.staged_metadata.exists()
        )

    @classmethod
    def has_pending(cls, project_dir: Path | str) -> bool:
        return (Path(project_dir) / cls.JOURNAL_FILENAME).exists()

    @classmethod
    def is_active(cls, project_dir: Path | str) -> bool:
        """Whether another process currently owns this project's save lock."""
        project_path = Path(project_dir)
        project_path.mkdir(parents=True, exist_ok=True)
        lock_path = project_path / cls.LOCK_FILENAME
        lock_stream = lock_path.open("a+b")
        try:
            cls._lock_stream(lock_stream)
        except OSError:
            lock_stream.close()
            return True
        cls._unlock_stream(lock_stream)
        return False

    def stage(
        self,
        write_game_data: Callable[[Path], None],
        metadata: Mapping[str, Any],
    ) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.had_game_data = self.game_data_path.exists()
        self.had_metadata = self.metadata_path.exists()
        self._acquire_lock()
        stage_completed = False
        try:
            self._create_journal("staging")
            self.staged_game_data.mkdir()
            write_game_data(self.staged_game_data)
            save_json(self.staged_metadata, dict(metadata))
            self._write_journal("ready")
            stage_completed = True
        except Exception:
            try:
                self._discard_workspace()
                self._remove_journal()
            except OSError:
                logging.exception(
                    "Could not clean incomplete project save staging at %s",
                    self.project_dir,
                )
            raise
        finally:
            if not stage_completed:
                self._release_lock()

    def commit(self) -> None:
        self._acquire_lock()
        try:
            if not self.can_complete:
                raise RuntimeError(
                    "Cannot commit a project save before game data and metadata are staged"
                )
            self._write_journal("committing")
            try:
                self._move_current_to_backups()
                self._install_staged_project()
            except Exception:
                try:
                    self._restore_old_project_preserving_staged_data()
                    self._write_journal("ready")
                except Exception:
                    logging.exception(
                        "Project save rollback failed; recovery journal remains at %s",
                        self.journal_path,
                    )
                raise

            try:
                self._write_commit_marker()
            except (OSError, RuntimeError):
                # Without a durable completion marker, recovery must preserve
                # both choices instead of silently presenting this new project
                # as an acknowledged successful Save.
                logging.exception(
                    "Project save installed but could not create its completion marker at %s",
                    self.commit_marker,
                )
                try:
                    self._restore_old_project_preserving_staged_data()
                    self._write_journal("ready")
                except Exception:
                    logging.exception(
                        "Project save marker rollback failed; recovery journal remains at %s",
                        self.journal_path,
                    )
                raise

            try:
                self._write_journal("committed")
            except OSError:
                # The new project is complete. Leaving the journal lets the next
                # launch safely finish cleanup instead of treating this as a failed
                # Save and rolling back good data.
                logging.exception(
                    "Project save committed but could not update journal at %s",
                    self.journal_path,
                )
                return
            self._finalize_committed_save()
        finally:
            self._release_lock()

    @classmethod
    def recover(
        cls,
        project_dir: Path | str,
        action: Literal["complete", "restore"],
    ) -> bool:
        transaction = cls.load_pending(project_dir)
        if transaction is None:
            return False

        transaction._acquire_lock()
        try:
            if transaction.is_installed:
                transaction._finalize_committed_save()
                return False

            if action == "complete":
                # A crash may leave one old target in its backup while the other
                # target is already installed. Normalize that mixed state before
                # attempting the all-or-nothing commit again.
                transaction._restore_old_project_preserving_staged_data()
                if not transaction.can_complete:
                    raise RuntimeError(
                        "Cannot complete the pending project save because its staged files are incomplete"
                    )
                transaction.commit()
            elif action == "restore":
                transaction._restore_old_project_preserving_staged_data()
                transaction._discard_workspace()
                transaction._remove_journal()
            else:
                raise ValueError(f"Unsupported project save recovery action: {action}")
            return True
        finally:
            transaction._release_lock()

    def _write_journal(self, state: str) -> None:
        if state not in self._STATES:
            raise ValueError(f"Unsupported project save state: {state}")
        self.state = state
        save_json(
            self.journal_path,
            self._journal_payload(state),
            fsync=True,
        )

    def _create_journal(self, state: str) -> None:
        """Create the transaction journal exactly once across writer processes."""
        if state not in self._STATES:
            raise ValueError(f"Unsupported project save state: {state}")
        try:
            with self.journal_path.open("x", encoding="utf-8") as journal_file:
                json.dump(self._journal_payload(state), journal_file, indent=4)
                journal_file.flush()
                os.fsync(journal_file.fileno())
        except FileExistsError as error:
            raise FileExistsError(
                f"A pending project save already exists at {self.journal_path}"
            ) from error
        self.state = state

    def _journal_payload(self, state: str) -> dict[str, Any]:
        return {
            "version": self.JOURNAL_VERSION,
            "transaction_id": self.transaction_id,
            "state": state,
            "had_game_data": self.had_game_data,
            "had_metadata": self.had_metadata,
        }

    def _write_commit_marker(self) -> None:
        """Durably acknowledge that both live targets are the new snapshot."""
        try:
            with self.commit_marker.open("xb") as marker_file:
                marker_file.write(b"1")
                marker_file.flush()
                os.fsync(marker_file.fileno())
        except FileExistsError as error:
            raise RuntimeError(
                f"Unexpected project save completion marker already exists: {self.commit_marker}"
            ) from error

    def _acquire_lock(self) -> None:
        if self._transaction_lock is not None:
            return
        self.project_dir.mkdir(parents=True, exist_ok=True)
        lock_stream = self.lock_path.open("a+b")
        try:
            self._lock_stream(lock_stream)
        except OSError as error:
            lock_stream.close()
            raise FileExistsError(
                f"Another LT Maker process is saving this project: {self.project_dir}"
            ) from error
        self._transaction_lock = lock_stream

    def _release_lock(self) -> None:
        if self._transaction_lock is None:
            return
        lock_stream = self._transaction_lock
        self._transaction_lock = None
        self._unlock_stream(lock_stream)

    @staticmethod
    def _lock_stream(lock_stream: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            lock_stream.seek(0)
            if not lock_stream.read(1):
                lock_stream.seek(0)
                lock_stream.write(b"0")
                lock_stream.flush()
            lock_stream.seek(0)
            msvcrt.locking(lock_stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock_stream(lock_stream: BinaryIO) -> None:
        try:
            if os.name == "nt":
                import msvcrt

                lock_stream.seek(0)
                msvcrt.locking(lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)
        finally:
            lock_stream.close()

    def _new_game_data_is_available(self) -> bool:
        return self._new_target_is_available(
            self.game_data_path,
            self.staged_game_data,
            self.backup_game_data,
            self.had_game_data,
            is_directory=True,
        )

    def _new_metadata_is_available(self) -> bool:
        return self._new_target_is_available(
            self.metadata_path,
            self.staged_metadata,
            self.backup_metadata,
            self.had_metadata,
            is_directory=False,
        )

    @staticmethod
    def _new_target_is_available(
        target: Path,
        staged: Path,
        backup: Path,
        existed_before: bool,
        *,
        is_directory: bool,
    ) -> bool:
        expected = Path.is_dir if is_directory else Path.is_file
        if expected(staged):
            return True
        # Once the old target has moved to its backup, a target at the live
        # location is the new staged candidate, even if the process crashed
        # before the second target was installed.
        return expected(target) and (backup.exists() or not existed_before)

    def _move_current_to_backups(self) -> None:
        self._move_to_backup(
            self.game_data_path,
            self.backup_game_data,
            self.had_game_data,
        )
        self._move_to_backup(
            self.metadata_path,
            self.backup_metadata,
            self.had_metadata,
        )

    @staticmethod
    def _move_to_backup(target: Path, backup: Path, existed_before: bool) -> None:
        if backup.exists():
            raise RuntimeError(f"Unexpected project save backup already exists: {backup}")
        if target.exists():
            if not existed_before:
                raise RuntimeError(
                    f"Project save target unexpectedly appeared during staging: {target}"
                )
            replace_with_retry(target, backup)
        elif existed_before:
            raise FileNotFoundError(f"Project save target disappeared: {target}")

    def _install_staged_project(self) -> None:
        replace_with_retry(self.staged_game_data, self.game_data_path)
        replace_with_retry(self.staged_metadata, self.metadata_path)

    def _restore_old_project_preserving_staged_data(self) -> None:
        self._restore_target(
            self.game_data_path,
            self.backup_game_data,
            self.staged_game_data,
            self.had_game_data,
        )
        self._restore_target(
            self.metadata_path,
            self.backup_metadata,
            self.staged_metadata,
            self.had_metadata,
        )

    @staticmethod
    def _restore_target(
        target: Path,
        backup: Path,
        staged: Path,
        existed_before: bool,
    ) -> None:
        if backup.exists():
            if target.exists():
                if staged.exists():
                    raise RuntimeError(
                        f"Cannot safely restore project save target with two candidates: {target}"
                    )
                replace_with_retry(target, staged)
            replace_with_retry(backup, target)
        elif not existed_before and target.exists() and not staged.exists():
            replace_with_retry(target, staged)
        elif existed_before and not target.exists():
            raise FileNotFoundError(f"Previous project save target is missing: {target}")

    def _finalize_committed_save(self) -> None:
        try:
            self._discard_backups()
            self._remove_journal()
        except Exception:
            logging.exception(
                "Project save is complete but cleanup is pending at %s",
                self.project_dir,
            )
            return
        try:
            self._remove_path(self.commit_marker)
        except Exception:
            # No journal remains, so a stale marker is only cleanup debris;
            # never let deleting it reinterpret a committed Save as incomplete.
            logging.exception(
                "Project save is complete but completion-marker cleanup is pending at %s",
                self.commit_marker,
            )

    def _discard_workspace(self) -> None:
        self._remove_path(self.staged_game_data)
        self._remove_path(self.staged_metadata)
        self._discard_backups()
        self._remove_path(self.commit_marker)

    def _discard_backups(self) -> None:
        self._remove_path(self.backup_game_data)
        self._remove_path(self.backup_metadata)

    def _remove_journal(self) -> None:
        if self.journal_path.exists():
            self.journal_path.unlink()

    @staticmethod
    def _remove_path(path: Path) -> None:
        if not path.exists():
            return
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            rmtree_robust(path)
        else:
            raise RuntimeError(f"Unexpected project save path type: {path}")


class ProjectBackupMergeTransaction:
    """Keep the complete ``SAVE_BACKUP`` workflow recoverable.

    The legacy backup workflow first moves the old project to ``.lttmp`` and
    writes a new project at the original path.  Merging the two directories is
    necessarily many renames, not one atomic operation.  This transaction
    begins *before* that first move and journals each later rename. An
    interrupted Save can therefore either finish a complete new project or
    restore the old ``.lttmp`` snapshot.
    """

    JOURNAL_VERSION = 1
    _STATES = {
        "preparing",
        "backup_moved",
        "resources_saved",
        "database_committed",
        "merging",
        "ready_to_finalize",
        "installed",
        "restoring",
        "restored",
    }

    def __init__(self, project_dir: Path | str, transaction_id: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.transaction_id = transaction_id or uuid4().hex
        if not ProjectSaveTransaction._TRANSACTION_ID_RE.fullmatch(self.transaction_id):
            raise ValueError("Invalid SAVE_BACKUP merge transaction identifier")
        self.backup_path = self.project_dir.parent / (self.project_dir.name + ".lttmp")
        name_prefix = f".{self.project_dir.name}.save-backup-merge"
        self.journal_path = self.project_dir.parent / (name_prefix + ".json")
        self.lock_path = self.project_dir.parent / (name_prefix + ".lock")
        self.shadow_root = self.project_dir.parent / (
            f"{name_prefix}-{self.transaction_id}.rollback"
        )
        self.state = "preparing"
        self.old_moves: list[Path] = []
        self.new_moves: list[Path] = []
        self._transaction_lock: Optional[BinaryIO] = None

    @classmethod
    def has_pending(cls, project_dir: Path | str) -> bool:
        project_path = Path(project_dir)
        journal_name = f".{project_path.name}.save-backup-merge.json"
        return (project_path.parent / journal_name).exists()

    @classmethod
    def is_active(cls, project_dir: Path | str) -> bool:
        """Whether another process currently owns this merge's file lock."""
        transaction = cls(project_dir)
        transaction.project_dir.parent.mkdir(parents=True, exist_ok=True)
        lock_stream = transaction.lock_path.open("a+b")
        try:
            ProjectSaveTransaction._lock_stream(lock_stream)
        except OSError:
            lock_stream.close()
            return True
        ProjectSaveTransaction._unlock_stream(lock_stream)
        return False

    @classmethod
    def load_pending(
        cls,
        project_dir: Path | str,
    ) -> Optional[ProjectBackupMergeTransaction]:
        project_path = Path(project_dir)
        journal_path = project_path.parent / (
            f".{project_path.name}.save-backup-merge.json"
        )
        if not journal_path.exists():
            return None
        try:
            with journal_path.open(encoding="utf-8") as journal_file:
                journal = json.load(journal_file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Cannot read the pending SAVE_BACKUP merge journal at {journal_path}"
            ) from error

        if not isinstance(journal, dict) or journal.get("version") != cls.JOURNAL_VERSION:
            raise RuntimeError(f"Unsupported SAVE_BACKUP merge journal at {journal_path}")
        transaction_id = journal.get("transaction_id")
        state = journal.get("state")
        old_moves = journal.get("old_moves")
        new_moves = journal.get("new_moves")
        if (
            not isinstance(transaction_id, str)
            or state not in cls._STATES
            or not isinstance(old_moves, list)
            or not isinstance(new_moves, list)
        ):
            raise RuntimeError(f"Invalid SAVE_BACKUP merge journal at {journal_path}")

        try:
            transaction = cls(project_path, transaction_id)
            transaction.old_moves = [
                transaction._parse_relative_path(relative)
                for relative in old_moves
            ]
            transaction.new_moves = [
                transaction._parse_relative_path(relative)
                for relative in new_moves
            ]
        except (TypeError, ValueError) as error:
            raise RuntimeError(f"Invalid SAVE_BACKUP merge journal at {journal_path}") from error
        if (
            len(set(transaction.old_moves)) != len(transaction.old_moves)
            or len(set(transaction.new_moves)) != len(transaction.new_moves)
        ):
            raise RuntimeError(f"Invalid SAVE_BACKUP merge journal at {journal_path}")
        transaction.state = state
        return transaction

    def begin_backup(self) -> None:
        """Move the old project to ``.lttmp`` while retaining the outer lock."""
        if not self.project_dir.is_dir():
            raise RuntimeError("SAVE_BACKUP requires an existing project directory")
        if self.backup_path.exists():
            raise RuntimeError(f"SAVE_BACKUP backup already exists: {self.backup_path}")

        self._acquire_lock()
        journal_created = False
        try:
            self._create_journal("preparing")
            journal_created = True
            replace_with_retry(self.project_dir, self.backup_path)
            self._write_journal("backup_moved")
        except Exception:
            if journal_created:
                try:
                    self._restore_previous_project()
                except Exception:
                    logging.exception(
                        "SAVE_BACKUP setup rollback failed; recovery journal remains at %s",
                        self.journal_path,
                    )
            self._release_lock()
            raise

    def mark_resources_saved(self) -> None:
        if self.state != "backup_moved":
            raise RuntimeError("SAVE_BACKUP resources were saved in an unexpected state")
        self._write_journal("resources_saved")

    def mark_database_committed(self) -> None:
        if self.state != "resources_saved":
            raise RuntimeError("SAVE_BACKUP database committed in an unexpected state")
        self._write_journal("database_committed")

    def abort(self) -> None:
        """Restore the old project after a caught resources/database error."""
        self._acquire_lock()
        try:
            self._restore_previous_project()
        finally:
            self._release_lock()

    def merge(self) -> None:
        """Merge the completed new project into the old backup directory."""
        if not self.project_dir.is_dir() or not self.backup_path.is_dir():
            raise RuntimeError("SAVE_BACKUP merge requires both project candidates")

        self._acquire_lock()
        installed = False
        try:
            if not self.journal_path.exists():
                # Supports callers upgrading from the legacy final-merge path.
                self._create_journal("database_committed")
            elif self.state == "preparing":
                raise RuntimeError(
                    "SAVE_BACKUP merge must use its active backup transaction"
                )
            if self.state != "database_committed":
                raise RuntimeError("SAVE_BACKUP merge started in an unexpected state")
            self._write_journal("merging")
            self._move_removed_json_to_shadow()
            self._move_new_files_into_backup()
            self._write_journal("ready_to_finalize")
            self._finish_install()
            installed = True
            try:
                self._write_journal("installed")
            except OSError:
                # The new project is already complete.  Keep the journal and
                # let the next launch finish cleanup instead of rolling it back.
                logging.exception(
                    "SAVE_BACKUP merge installed but could not update journal at %s",
                    self.journal_path,
                )
                return
            self._finalize_installed()
        except Exception:
            if self.journal_path.exists() and not installed:
                try:
                    self._restore_previous_project()
                except Exception:
                    logging.exception(
                        "SAVE_BACKUP merge rollback failed; recovery journal remains at %s",
                        self.journal_path,
                    )
            raise
        finally:
            self._release_lock()

    @classmethod
    def recover(
        cls,
        project_dir: Path | str,
    ) -> Literal["none", "finalized", "restored"]:
        """Recover an interrupted SAVE_BACKUP transaction."""
        transaction = cls.load_pending(project_dir)
        if transaction is None:
            return "none"

        transaction._acquire_lock()
        try:
            if transaction.state == "preparing":
                if transaction.project_dir.is_dir() and not transaction.backup_path.exists():
                    # Nothing was moved before the process stopped.
                    transaction._finalize_unmoved_preparation()
                    return "none"
                transaction._restore_previous_project()
                return "restored"

            if transaction.state in {"backup_moved", "resources_saved", "merging"}:
                # Resources or individual file moves alone do not make a
                # complete project. Preserve the old snapshot in these states.
                transaction._restore_previous_project()
                return "restored"

            if transaction.state == "database_committed":
                if transaction.project_dir.is_dir() and transaction.backup_path.is_dir():
                    # Both resources and database metadata are complete. Resume
                    # the preserving merge rather than discarding old loose
                    # resource files.
                    transaction.merge()
                    return "finalized"
                raise RuntimeError(
                    "SAVE_BACKUP recovery cannot find both complete project candidates"
                )

            if transaction.state in {"installed", "ready_to_finalize"}:
                if not transaction.backup_path.exists() and transaction.project_dir.is_dir():
                    # The backup directory has already become the live new
                    # project.  Only cleanup was interrupted.
                    transaction._finalize_installed()
                    return "finalized"
                if (
                    transaction.backup_path.is_dir()
                    and transaction._can_finish_install()
                ):
                    transaction._finish_install()
                    try:
                        transaction._write_journal("installed")
                    except OSError:
                        logging.exception(
                            "SAVE_BACKUP merge recovery installed but could not update journal at %s",
                            transaction.journal_path,
                        )
                        return "finalized"
                    transaction._finalize_installed()
                    return "finalized"

            if transaction.state in {"restoring", "restored"}:
                if transaction.backup_path.is_dir() and not transaction.project_dir.exists():
                    transaction._complete_restored_root()
                    return "restored"
                if not transaction.backup_path.exists() and transaction.project_dir.is_dir():
                    transaction._finalize_restored()
                    return "restored"

            raise RuntimeError(
                f"Unsupported SAVE_BACKUP recovery state: {transaction.state}"
            )
        finally:
            transaction._release_lock()

    @staticmethod
    def _parse_relative_path(value: object) -> Path:
        if not isinstance(value, str) or not value:
            raise ValueError("Invalid relative path")
        relative = Path(value)
        if (
            relative.is_absolute()
            or relative.drive
            or relative.root
            or not relative.parts
            or any(part in ("", ".", "..") for part in relative.parts)
        ):
            raise ValueError("Unsafe relative path")
        return relative

    @staticmethod
    def _serialize_relative_path(relative: Path) -> str:
        ProjectBackupMergeTransaction._parse_relative_path(str(relative))
        return relative.as_posix()

    def _move_removed_json_to_shadow(self) -> None:
        for old_directory, _dirs, files in list(os.walk(self.backup_path)):
            old_dir = Path(old_directory)
            relative_dir = old_dir.relative_to(self.backup_path)
            if relative_dir.parts[:1] == ("build",):
                continue
            for filename in files:
                old_file = old_dir / filename
                relative_path = relative_dir / filename
                new_file = self.project_dir / relative_path
                if filename.endswith(".json") and not new_file.exists():
                    self._record_old_move(relative_path)
                    self._move_file(old_file, self.shadow_root / relative_path)

    def _move_new_files_into_backup(self) -> None:
        for source_directory, _dirs, files in list(os.walk(self.project_dir)):
            source_dir = Path(source_directory)
            relative_dir = source_dir.relative_to(self.project_dir)
            for filename in files:
                source_file = source_dir / filename
                relative_path = relative_dir / filename
                destination_file = self.backup_path / relative_path
                if destination_file.exists():
                    self._record_old_move(relative_path)
                    self._move_file(destination_file, self.shadow_root / relative_path)
                self._record_new_move(relative_path)
                self._move_file(source_file, destination_file)

    def _record_old_move(self, relative_path: Path) -> None:
        if relative_path in self.old_moves:
            raise RuntimeError(
                f"SAVE_BACKUP merge tried to move one old file twice: {relative_path}"
            )
        self.old_moves.append(relative_path)
        self._write_journal("merging")

    def _record_new_move(self, relative_path: Path) -> None:
        if relative_path in self.new_moves:
            raise RuntimeError(
                f"SAVE_BACKUP merge tried to move one new file twice: {relative_path}"
            )
        self.new_moves.append(relative_path)
        self._write_journal("merging")

    def _can_finish_install(self) -> bool:
        for relative_path in self.old_moves:
            if not (self.shadow_root / relative_path).is_file():
                return False
        for relative_path in self.new_moves:
            if not (self.backup_path / relative_path).is_file():
                return False
            if (self.project_dir / relative_path).exists():
                return False
        return True

    def _finish_install(self) -> None:
        if not self.backup_path.is_dir():
            raise RuntimeError("SAVE_BACKUP merge lost the merged backup directory")
        if self.project_dir.exists():
            rmtree_robust(self.project_dir)
        replace_with_retry(self.backup_path, self.project_dir)

    def _restore_previous_project(self) -> None:
        # If the process stopped after clearing the temporary new project, the
        # old backup is already complete and must be renamed back directly.
        # Replaying file moves here would fail because their temporary targets
        # were deliberately removed just before that root rename.
        if (
            self.state in {"restoring", "restored"}
            and self.backup_path.is_dir()
            and not self.project_dir.exists()
        ):
            self._complete_restored_root()
            return

        # A crash before the first directory replacement leaves the original
        # project untouched. Do not needlessly round-trip it through .lttmp.
        if (
            self.state == "preparing"
            and self.project_dir.is_dir()
            and not self.backup_path.exists()
            and not self.old_moves
            and not self.new_moves
        ):
            self._finalize_unmoved_preparation()
            return

        # A crash after the final directory rename leaves the complete new
        # project at its normal path.  Normalize it back to the backup path
        # before reversing the recorded per-file moves.
        if not self.backup_path.exists():
            if not self.project_dir.is_dir():
                raise RuntimeError("SAVE_BACKUP recovery cannot find either project candidate")
            replace_with_retry(self.project_dir, self.backup_path)

        for relative_path in reversed(self.new_moves):
            self._undo_move(
                self.backup_path / relative_path,
                self.project_dir / relative_path,
            )
        for relative_path in reversed(self.old_moves):
            self._undo_move(
                self.shadow_root / relative_path,
                self.backup_path / relative_path,
            )

        self._write_journal("restoring")
        if self.project_dir.exists():
            rmtree_robust(self.project_dir)
        self._complete_restored_root()

    def _complete_restored_root(self) -> None:
        if self.project_dir.exists():
            raise RuntimeError(
                "SAVE_BACKUP recovery cannot restore the old project over an existing directory"
            )
        if not self.backup_path.is_dir():
            raise RuntimeError("SAVE_BACKUP recovery lost the previous project backup")
        replace_with_retry(self.backup_path, self.project_dir)
        try:
            self._write_journal("restored")
        except OSError:
            logging.exception(
                "SAVE_BACKUP project was restored but cleanup journal could not be updated at %s",
                self.journal_path,
            )
            return
        self._finalize_restored()

    def _finalize_unmoved_preparation(self) -> None:
        try:
            if self.journal_path.exists():
                self.journal_path.unlink()
        except OSError:
            logging.warning(
                "SAVE_BACKUP had not moved the project but cleanup remains at %s",
                self.journal_path,
                exc_info=True,
            )

    @staticmethod
    def _undo_move(source: Path, destination: Path) -> None:
        source_exists = source.exists()
        destination_exists = destination.exists()
        if source_exists and destination_exists:
            raise RuntimeError(
                f"SAVE_BACKUP recovery found two candidates for {destination}"
            )
        if source_exists:
            ProjectBackupMergeTransaction._move_file(source, destination)
        elif not destination_exists:
            raise RuntimeError(
                f"SAVE_BACKUP recovery lost both candidates for {destination}"
            )

    @staticmethod
    def _move_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        replace_with_retry(source, destination)

    def _create_journal(self, state: str) -> None:
        try:
            with self.journal_path.open("x", encoding="utf-8") as journal_file:
                json.dump(self._journal_payload(state), journal_file, indent=4)
                journal_file.flush()
                os.fsync(journal_file.fileno())
        except FileExistsError as error:
            raise FileExistsError(
                f"A pending SAVE_BACKUP merge already exists at {self.journal_path}"
            ) from error
        self.state = state

    def _write_journal(self, state: str) -> None:
        if state not in self._STATES:
            raise ValueError(f"Unsupported SAVE_BACKUP merge state: {state}")
        self.state = state
        save_json(self.journal_path, self._journal_payload(state), fsync=True)

    def _journal_payload(self, state: str) -> dict[str, Any]:
        return {
            "version": self.JOURNAL_VERSION,
            "transaction_id": self.transaction_id,
            "state": state,
            "old_moves": [
                self._serialize_relative_path(relative)
                for relative in self.old_moves
            ],
            "new_moves": [
                self._serialize_relative_path(relative)
                for relative in self.new_moves
            ],
        }

    def _acquire_lock(self) -> None:
        if self._transaction_lock is not None:
            return
        self.project_dir.parent.mkdir(parents=True, exist_ok=True)
        lock_stream = self.lock_path.open("a+b")
        try:
            ProjectSaveTransaction._lock_stream(lock_stream)
        except OSError as error:
            lock_stream.close()
            raise FileExistsError(
                f"Another LT Maker process is merging SAVE_BACKUP for {self.project_dir}"
            ) from error
        self._transaction_lock = lock_stream

    def _release_lock(self) -> None:
        if self._transaction_lock is None:
            return
        lock_stream = self._transaction_lock
        self._transaction_lock = None
        ProjectSaveTransaction._unlock_stream(lock_stream)

    def _finalize_installed(self) -> None:
        self._finalize_cleanup("installed")

    def _finalize_restored(self) -> None:
        self._finalize_cleanup("restored")

    def _finalize_cleanup(self, expected_state: str) -> None:
        try:
            if self.shadow_root.exists():
                ProjectSaveTransaction._remove_path(self.shadow_root)
            if self.journal_path.exists():
                self.journal_path.unlink()
        except Exception:
            logging.warning(
                "SAVE_BACKUP merge is %s but cleanup remains at %s",
                expected_state,
                self.journal_path,
                exc_info=True,
            )
