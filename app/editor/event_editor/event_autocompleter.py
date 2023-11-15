from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher as SM
from typing import List, Optional, Type

from PyQt5.QtCore import (QAbstractListModel, QLocale, QModelIndex, QSize, Qt,
                          pyqtSignal)
from PyQt5.QtWidgets import (QCompleter, QStyledItemDelegate,
                             QStyleOptionViewItem)
from PyQt5.QtGui import QPalette, QColor
from app import dark_theme

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.editor.settings import MainSettingsController
from app.events import event_commands, event_validators
from app.events.event_prefab import EventVersion
from app.events.event_structs import ParseMode
from app.events.python_eventing.swscomp.swscompv1 import SWSCompilerV1
from app.utilities.typing import NID


@dataclass
class CompletionToInsert():
    text: str                   # text to insert
    position: int               # location to insert at
    replace: int                # chars to delete before insertion (e.g. for autocompleting half a word)

@dataclass
class CompletionEntry():
    name: str                   # what the completion actually shows
    match_text: str             # what the completer matches against
    value: str                  # what the completer inserts

@dataclass
class CompletionLocation():
    word_to_complete: str       # word to complete
    word_to_match: str          # word to match against. can differ from above (e.g. completing `"Eir` but only matching against `Eir`)
    index: int                  # index of the word to complete

COMPLETION_DATA_ROLE = 100

def _fuzzy_match(text: str, completion: CompletionEntry) -> float:
    start_bonus = 0.5 if completion.match_text.startswith(text) else 0
    return SM(None, text.lower(), completion.match_text).ratio() + start_bonus

class EventScriptCompleter(QCompleter):
    insertText = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = MainSettingsController()
        self.setFilterMode(Qt.MatchContains)
        self.activated[QModelIndex].connect(self.do_complete)
        self.completion_location: Optional[CompletionLocation] = None
        self.version = EventVersion.EVENT

    def set_version(self, version: EventVersion):
        self.version = version

    def do_complete(self, completion_index: QModelIndex):
        completion: CompletionEntry = completion_index.data(COMPLETION_DATA_ROLE)
        self.insertText.emit([CompletionToInsert(completion.value, self.completion_location.index, len(self.completion_location.word_to_complete))])
        self.popup().hide()

    def handleKeyPressEvent(self, event) -> bool:
        # If completer is up, Tab/Enter can auto-complete
        if event.key() == self.settings.get_autocomplete_button(Qt.Key_Tab):
            if self.popup().isVisible() and len(self.popup().selectedIndexes()) > 0:
                self.do_complete(self.popup().selectedIndexes()[0])
                return True  # should not enter a tab
        elif event.key() == Qt.Key_Backspace:
            self.popup().hide()
        elif event.key() == Qt.Key_Escape:
            self.popup().hide()
        return False

    def setTextToComplete(self, line: str, end_idx: int, level_nid: NID):
        completions = generate_completions(line, level_nid, self.version)
        if not completions:
            self.setModel(self.ESInternalModel([], self))
            return
        self.completion_location = get_arg_info(line, end_idx)
        # sort completions based on similarity
        completions = sorted(completions, key=lambda compl: _fuzzy_match(self.completion_location.word_to_match, compl), reverse=True)
        self.setModel(self.ESInternalModel(completions, self))
        self.popup().setItemDelegate(self.ESInternalDelegate(self))
        self.setCompletionPrefix(self.completion_location.word_to_match)
        self.popup().setCurrentIndex(self.completionModel().index(0, 0))
        return True

    class ESInternalDelegate(QStyledItemDelegate):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.settings = MainSettingsController()
            theme = dark_theme.get_theme()
            self.syntax_colors = theme.event_syntax_highlighting()

        def displayText(self, value: CompletionEntry, locale: QLocale) -> str:
            return value.name

        def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
            completion: CompletionEntry = index.data(COMPLETION_DATA_ROLE)
            return QSize(len(completion.name) * 8 + 8, 20)

        def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:
            super().initStyleOption(option, index)
            option.font.setFamily(self.settings.get_code_font())
            option.font.setBold(True)
            completion: CompletionEntry = index.data(COMPLETION_DATA_ROLE)
            if completion.name.startswith('{') and completion.name.endswith('}'):
                option.palette.setBrush(QPalette.ColorRole.Text, QColor(self.syntax_colors.special_text_color))
                option.palette.setBrush(QPalette.ColorRole.HighlightedText, QColor(self.syntax_colors.special_text_color))

    class ESInternalModel(QAbstractListModel):
        def __init__(self, data: List[CompletionEntry], parent: EventScriptCompleter):
            super().__init__(parent)
            self._data = data

        def rowCount(self, parent=None) -> int:
            return len(self._data)

        def data(self, index: QModelIndex, role: int):
            if not index.isValid():
                return None
            # completer uses this field to match against
            elif role == Qt.ItemDataRole.EditRole:
                return self._data[index.row()].match_text
            # what the completer ultimately returns
            elif role == COMPLETION_DATA_ROLE:
                return self._data[index.row()]
            # delegate uses this to decide what to display
            elif role == Qt.ItemDataRole.DisplayRole:
                return self._data[index.row()]
            else:
                return None

def generate_completions(line: str, level_nid: NID, version: EventVersion) -> List[CompletionEntry]:
    if version == EventVersion.EVENT:
        return generate_event_completions(line, level_nid)
    elif version == EventVersion.PYEV1:
        return generate_pyev1_completions(line, level_nid)
    return []

def generate_event_completions(line: str, level_nid: NID) -> List[CompletionEntry]:
    as_tokens = event_commands.parse_event_line(line)
    arg = as_tokens.tokens[-1]

    def create_completion(nid, name):
        nid_or_name = nid
        if name and nid != name:
            nid_or_name = "%s (%s)" % (name, nid)
        return CompletionEntry(nid_or_name, nid_or_name, nid)

    if as_tokens.mode() == ParseMode.COMMAND:
        commands = event_validators.EventFunction().valid_entries()
        completions = [create_completion(nid, name) for name, nid in commands]
        return completions

    command_t = event_commands.ALL_EVENT_COMMANDS.get(as_tokens.command(), None)
    if not command_t:
        return []

    completions = []
    if as_tokens.mode() == ParseMode.ARGS:
        arg_name = get_arg_name(command_t, arg, len(as_tokens.tokens) - 2)
        arg_validator = event_validators.get(command_t.get_validator_from_keyword(arg_name))
        if arg_validator:
            valids = arg_validator(DB, RESOURCES).valid_entries(level_nid, arg)
            completions = [create_completion(nid, name) for name, nid in valids]
        flag_cmpls = []
        if arg_name in command_t.optional_keywords:
            # add flags when we're done with required
            flags = command_t().flags
            flag_key = "FLAG(%s)"
            flag_cmpls = [CompletionEntry(flag_key % flag, flag, flag) for flag in flags]
        return completions + flag_cmpls

    elif as_tokens.mode() == ParseMode.FLAGS:
        flags = command_t().flags
        flag_key = "FLAG(%s)"
        completions = [CompletionEntry(flag_key % flag, flag, flag) for flag in flags]
        return completions
    return []

def generate_pyev1_completions(line: str, level_nid: NID) -> List[CompletionEntry]:
    as_tokens = SWSCompilerV1.parse_line(line)
    if not as_tokens:
        return []

    arg = as_tokens.tokens[-1]

    def create_completion(nid, name, is_command: bool=False):
        nid_or_name = nid
        if name and nid != name:
            nid_or_name = "%s (%s)" % (name, nid)
        if not is_command:
            nid = '"%s"' % nid
        return CompletionEntry(nid_or_name, nid_or_name, nid)

    if as_tokens.mode() == ParseMode.COMMAND:
        commands = event_validators.EventFunction().valid_entries()
        completions = [create_completion(nid, name, True) for name, nid in commands]
        return completions

    command_t = event_commands.ALL_EVENT_COMMANDS.get(as_tokens.command(), None)
    if not command_t:
        return []

    if as_tokens.mode() == ParseMode.ARGS:
        arg_name = get_arg_name(command_t, arg, len(as_tokens.tokens) - 2)
        arg_validator = event_validators.get(command_t.get_validator_from_keyword(arg_name))
        if arg_validator:
            valids = arg_validator(DB, RESOURCES).valid_entries(level_nid)
            completions = [create_completion(nid, name) for name, nid in valids]
            return completions

    elif as_tokens.mode() == ParseMode.FLAGS:
        flags = command_t().flags
        flag_key = "FLAG(%s)"
        completions = [CompletionEntry(flag_key % flag, flag, flag) for flag in flags]
        return completions

def get_arg_info(line: str, end_idx: int) -> CompletionLocation:
    """Returns the arg at the end of line, as well as its starting index in the document"""
    as_tokens = event_commands.parse_event_line(line)
    full_arg = as_tokens.tokens[-1]
    arg_to_match = trim_arg_match(full_arg)
    arg_to_replace = trim_arg_text(full_arg)
    return CompletionLocation(arg_to_replace, arg_to_match, end_idx - len(arg_to_replace))

def get_arg_name(command_t: Type[event_commands.EventCommand], arg_text: str, arg_idx: int) -> Optional[str]:
    # is this a keyword arg?
    if '=' in arg_text:
        maybe_keyword, _ = arg_text.split('=', 1)
        if command_t.get_validator_from_keyword(maybe_keyword):
            return maybe_keyword

    # not a keyword arg
    if not arg_idx < len(command_t.get_keywords()):
        return None
    return command_t.get_keywords()[arg_idx]

def trim_arg_match(arg_text: str) -> str:
    return re.split('[^a-zA-Z0-9_]', arg_text)[-1]

def trim_arg_text(arg_text: str) -> str:
    return re.split('[^a-zA-Z0-9_"\'\{]', arg_text)[-1]
