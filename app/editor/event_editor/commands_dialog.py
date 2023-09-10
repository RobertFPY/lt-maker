from __future__ import annotations
from enum import Enum

import functools
import logging
import math
import os
import re

from PyQt5.QtCore import QRect, QSize, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt5.QtGui import (QFont, QFontMetrics, QIcon, QPainter, QPalette,
                         QTextCursor)
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QApplication,
                             QCheckBox, QCompleter, QDialog, QFrame,
                             QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QListView, QMenu, QMessageBox,
                             QPlainTextEdit, QPushButton, QSizePolicy,
                             QSpinBox, QSplitter, QStyle, QStyledItemDelegate,
                             QTextEdit, QToolBar, QVBoxLayout, QWidget)
from app.editor.event_editor.event_text_editor import EventTextEditor

import app.editor.game_actions.game_actions as GAME_ACTIONS
from app import dark_theme
from app.data.database.database import DB
from app.data.database.levels import LevelPrefab
from app.data.resources.resources import RESOURCES
from app.editor import table_model, timer
from app.editor.base_database_gui import CollectionModel
from app.editor.custom_widgets import TilemapBox
from app.editor.event_editor import event_autocompleter, find_and_replace
from app.editor.event_editor.event_highlighter import EventHighlighter
from app.editor.event_editor.py_syntax import PythonHighlighter
from app.editor.lib.components.validated_line_edit import \
    NoParentheticalLineEdit
from app.editor.map_view import SimpleMapView
from app.editor.settings import MainSettingsController
from app.events import event_commands, event_validators
from app.events.event_prefab import EventPrefab
from app.events.mock_event import IfStatementStrategy
from app.events.python_eventing.utils import FORBIDDEN_PYTHON_COMMAND_NIDS
from app.events.regions import RegionType
from app.events.triggers import ALL_TRIGGERS
from app.extensions.custom_gui import (ComboBox, PropertyBox, PropertyCheckBox,
                                       QHLine, TableView)
from app.extensions.markdown2 import Markdown
from app.utilities import str_utils

def bold(s: str):
    return f'**{s}**'

def italic(s: str):
    return f'_{s}_'

def python_help_text(command: event_commands.EventCommand):
    command_n = bold(command.nickname or command.nid)

    kwds = []
    kwds = command.keywords + [italic(opt) + '?' for opt in command.optional_keywords]
    if command.keyword_types:
        ktypes = command.keyword_types
        kwds = [f"{kwds[i]}={ktypes[i]}" for i in range(len(kwds))]
    args_str = ', '.join(kwds)

    flags_str = ''
    if command.flags:
        flags_str = '.FLAGS(%s[, flag])' % italic("flag")

    command_str = f'{command_n}({args_str}){flags_str}\n\n'

    optional_flags_str = ''
    if command.flags:
        flags_list = ', '.join(command.flags)
        optional_flags_str = f'{italic("Optional Flags")}: {flags_list}\n\n --- \n\n'

    text = command_str + optional_flags_str

    already = []
    for keyword in command.get_keyword_types():
        if keyword in already:
            continue
        else:
            already.append(keyword)
        validator = event_validators.get(keyword)
        if validator and validator().desc:
            text += '_%s_ %s\n\n' % (keyword, str(validator().desc))
        else:
            text += '_%s_ %s\n\n' % (keyword, "")
    if command.desc:
        text += " --- \n\n"
    text += str(command.desc)
    return text

def command_help_text(command: event_commands.EventCommand):
    # command name
    text = bold(command.nickname or command.nid)
    text += ';'

    # command keywords
    i = 0
    all_keywords = command.keywords + command.optional_keywords
    for i, kwyd in enumerate(all_keywords):
        next_text = kwyd
        if command.keyword_types:
            next_text = next_text + '=' + command.keyword_types[i]
        if not i < len(command.keywords): # it's an optional
            next_text = italic(next_text)
        next_text += ';'
        text += next_text
    if command.flags:
        text += '_flags_'
    else:
        if text[-1] == ';':
            text = text[:-1]
    text += '\n\n'
    if command.flags:
        text += '_Optional Flags:_ ' + ';'.join(command.flags) + '\n\n'
    text += " --- \n\n"
    already = []
    for keyword in command.get_keyword_types():
        if keyword in already:
            continue
        else:
            already.append(keyword)
        validator = event_validators.get(keyword)
        if validator and validator().desc:
            text += '_%s_ %s\n\n' % (keyword, str(validator().desc))
        else:
            text += '_%s_ %s\n\n' % (keyword, "")
    if command.desc:
        text += " --- \n\n"
    text += str(command.desc)
    return text

class ShowCommandsDialog(QDialog):
    def __init__(self, parent=None, is_python=False):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowTitle("Event Commands")
        self.window = parent
        self.is_python = is_python

        self.commands = event_commands.get_commands()
        if is_python:
            self.commands = [command for command in self.commands if command.nid not in FORBIDDEN_PYTHON_COMMAND_NIDS]
        self.categories = [category.value for category in event_commands.Tags]
        self._data = []
        for category in self.categories:
            # Ignore hidden category
            if category == event_commands.Tags.HIDDEN.value:
                continue
            self._data.append(category)
            commands = [command() for command in self.commands if command.tag.value == category]
            self._data += commands

        self.model = EventCommandModel(self._data, self.categories, self)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.view = QListView(self)
        self.view.setMinimumSize(256, 360)
        self.view.setModel(self.proxy_model)
        self.view.doubleClicked.connect(self.on_double_click)

        self.delegate = CommandDelegate(self._data, self, is_python)
        self.view.setItemDelegate(self.delegate)

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Enter search term here...")
        self.search_box.textChanged.connect(self.search)

        self.desc_box = QTextEdit(self)
        self.desc_box.setReadOnly(True)
        self.view.selectionModel().selectionChanged.connect(self.on_item_changed)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.search_box)
        left_layout.addWidget(self.view)
        left_frame = QFrame(self)
        left_frame.setLayout(left_layout)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle:horizontal {background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eee, stop:1 #ccc); border: 1px solid #777; width: 13px; margin-top: 2px; margin-bottom: 2px; border-radius: 4px;}")
        splitter.addWidget(left_frame)
        splitter.addWidget(self.desc_box)

        main_layout = QHBoxLayout()
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def search(self, text):
        self.proxy_model.setFilterRegularExpression(text.lower())

    def on_double_click(self, index):
        index = self.proxy_model.mapToSource(index)
        idx = index.row()
        command = self._data[idx]
        if command not in self.categories:
            self.window.insert_text_with_newline(command.nid)

    def on_item_changed(self, curr, prev):
        if curr.indexes():
            index = curr.indexes()[0]
            index = self.proxy_model.mapToSource(index)
            idx = index.row()
            command = self._data[idx]
            if command not in self.categories:
                if self.is_python:
                    text = python_help_text(command)
                else:
                    text = command_help_text(command)
                self.desc_box.setMarkdown(text)
            else:
                self.desc_box.setMarkdown(command + ' Section')
        else:
            self.desc_box.setMarkdown('')

class EventCommandModel(CollectionModel):
    def __init__(self, data, categories, window):
        super().__init__(data, window)
        self.categories = categories

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            command = self._data[index.row()]
            if command in self.categories:
                return command
            else:
                return command.nid

class CommandDelegate(QStyledItemDelegate):
    def __init__(self, data, parent=None, is_python=False):
        super().__init__(parent=None)
        self.window = parent
        self._data = data
        self.is_python = is_python

    def sizeHint(self, option, index):
        index = self.window.proxy_model.mapToSource(index)
        command = self._data[index.row()]
        if hasattr(command, 'nid'):
            return QSize(0, 24)
        else:
            return QSize(0, 32)

    def render_command_keywords(self, command: event_commands.EventCommand):
        optional_keywords = ["%s?" % kwd for kwd in command.optional_keywords]
        if self.is_python:
            kwds = ', '.join(command.keywords + optional_keywords)
            if kwds:
                return f'({kwds})'
        else:
            kwds = ';'.join(command.keywords + optional_keywords)
            if kwds:
                return ';' + kwds
        return ''

    def paint(self, painter, option, index):
        index = self.window.proxy_model.mapToSource(index)
        command = self._data[index.row()]
        rect = option.rect
        left = rect.left()
        right = rect.right()
        top = rect.top()
        bottom = rect.bottom()
        if option.state & QStyle.State_Selected:
            palette = QApplication.palette()
            color = palette.color(QPalette.Highlight)
            painter.fillRect(rect, color)
        font = painter.font()
        if hasattr(command, 'nid'):
            font.setBold(True)
            font_height = QFontMetrics(font).lineSpacing()
            painter.setFont(font)
            painter.drawText(left, top + font_height, command.nid)
            horiz_advance = QFontMetrics(font).horizontalAdvance(command.nid)
            font.setBold(False)
            painter.setFont(font)
            keywords = self.render_command_keywords(command)
            if keywords:
                painter.drawText(left + horiz_advance, top + font_height, keywords)
        else:
            prev_size = font.pointSize()
            font.setPointSize(prev_size + 4)
            font_height = QFontMetrics(font).lineSpacing()
            painter.setFont(font)
            painter.drawText(left, top + font_height, command)
            font.setPointSize(prev_size)
            painter.setFont(font)
            painter.drawLine(left, top + 1.25 * font_height, right, top + 1.25 * font_height)
