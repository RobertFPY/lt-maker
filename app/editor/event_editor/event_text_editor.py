from __future__ import annotations

import math
import os
from typing import TYPE_CHECKING, Optional, Tuple, Type

from PyQt5.QtCore import QRect, QSize, Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QFontMetrics, QPainter, QPalette, QTextCursor
from PyQt5.QtWidgets import QCompleter, QLabel, QPlainTextEdit, QWidget, QAction

from app import dark_theme
from app.editor.event_editor import event_autocompleter, event_formatter
from app.editor.event_editor.utils import EditorLanguageMode
from app.editor.settings import MainSettingsController
from app.utilities import str_utils

if TYPE_CHECKING:
    from app.editor.event_editor.event_properties import EventProperties

class LineNumberArea(QWidget):
    def __init__(self, parent: EventTextEditor):
        super().__init__(parent)
        self.editor = parent

    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)

class EventTextEditor(QPlainTextEdit):
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        return super().mouseReleaseEvent(event)

    def __init__(self, parent):
        super().__init__(parent)
        self.event_properties: EventProperties = parent
        self.line_number_area = LineNumberArea(self)

        self.settings = MainSettingsController()
        theme = dark_theme.get_theme()
        self.line_number_color = theme.event_syntax_highlighting().line_number_color

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.line_number_area.update)

        self.updateLineNumberAreaWidth(0)
        # Set tab to four spaces
        fm = QFontMetrics(self.font())
        self.setTabStopWidth(4 * fm.width(' '))

        self.completer: Optional[QCompleter] = None
        self.function_hinter: Optional[Type[event_autocompleter.EventScriptFunctionHinter]] = None
        # completer
        self.textChanged.connect(self.complete)
        self.prev_keyboard_press = None
        
        self.format_action = QAction("Format...", self, shortcut="Ctrl+Alt+F", triggered=self.autoformat)
        self.addAction(self.format_action)

        self.function_annotator: QLabel = QLabel(self)
        if bool(self.settings.get_event_autocomplete()):
            # function helper
            self.textChanged.connect(self.display_function_hint)
            self.clicked.connect(self.display_function_hint)
            self.cursorPositionChanged.connect(self.display_function_hint)
            self.function_annotator.setTextFormat(Qt.RichText)
            self.function_annotator.setWordWrap(True)
            with open(os.path.join(os.path.dirname(__file__),'event_styles.css'), 'r') as stylecss:
                self.function_annotator.setStyleSheet(stylecss.read())

    def autoformat(self):
        if self.event_properties.language_mode == EditorLanguageMode.EVENT:
            text = self.document().toRawText()
            text = str_utils.convert_raw_text_newlines(text)
            formatted = event_formatter.format_event_script(text)
            self.document().setPlainText(formatted)
        else:
            pass

    def set_completer(self, completer):
        if not completer:
            self.completer = None
            return
        completer.setWidget(self)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer = completer
        self.completer.insertText.connect(self.insert_completion)

    def set_function_hinter(self, function_hinter: Type[event_autocompleter.EventScriptFunctionHinter]):
        self.function_hinter = function_hinter

    def insert_completion(self, completion):
        tc = self.textCursor()
        for i in range(len(self.completer.completionPrefix())):
            tc.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
        tc.removeSelectedText()
        tc.insertText(completion)
        self.setTextCursor(tc)

    def display_function_hint(self):
        if not self.should_show_function_hint():
            self.hide_function_hint()
            return
        tc = self.textCursor()
        line = tc.block().text()
        cursor_pos = tc.positionInBlock()

        hint_text = self.function_hinter.generate_hint_for_line(line, cursor_pos)
        if not hint_text:
            self.hide_function_hint()
            return
        self.function_annotator.setText(hint_text)
        self.function_annotator.setWordWrap(True)
        self.function_annotator.adjustSize()

        # offset the position and display
        tc_top_right = self.mapTo(self.parent(), self.cursorRect(tc).topRight())
        height = self.function_annotator.height()

        top, left = tc_top_right.y() - height - 5, min(tc_top_right.x() + 15, self.width() - self.function_annotator.width())
        if top < 0:
            if self.completer and self.completer.popup().isVisible():
                top = tc_top_right.y() + self.completer.popup().height() + 6
                left = min(tc_top_right.x(), self.width() - self.function_annotator.width())
            else:
                top = tc_top_right.y() + 5
        tc_top_right.setY(top)
        tc_top_right.setX(left)
        self.function_annotator.move(tc_top_right)
        self.function_annotator.show()

    def get_event_command_context(self) -> Tuple[str, int]: # returns code line, and position in line
        if self.event_properties.language_mode == EditorLanguageMode.EVENT:
            return self.textCursor().block().text(), self.textCursor().positionInBlock()
        elif self.event_properties.language_mode == EditorLanguageMode.PYTHON:
            curr_pos = self.textCursor().position()
            terminal_pos = curr_pos
            while terminal_pos > 0 and self.document().characterAt(terminal_pos) != '$':
                terminal_pos -= 1
            return self.document().toRawText()[terminal_pos:curr_pos], curr_pos - terminal_pos
        else:
            return None

    def complete(self):
        if not self.should_show_completion_box():
            self.hide_completion_box()
            return
        line, cursor_pos = self.get_event_command_context()
        if not self.completer.setTextToComplete(line, cursor_pos, self.event_properties.current.level_nid):
            return
        cr = self.cursorRect()
        cr.setWidth(
            self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.line_number_area)
        bg_color = self.palette().color(QPalette.Base)
        painter.fillRect(event.rect(), bg_color)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while (block.isValid() and top <= event.rect().bottom()):
            if (block.isVisible() and bottom >= event.rect().top()):
                number = str(block_number + 1)
                if self.textCursor().blockNumber() == block_number:
                    color = self.palette().color(QPalette.Window)
                    painter.fillRect(0, top, self.line_number_area.width(), self.fontMetrics().height(), color)
                painter.setPen(self.line_number_color)
                painter.drawText(0, top, self.line_number_area.width() - 2, self.fontMetrics().height(), Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def lineNumberAreaWidth(self) -> int:
        num_blocks = max(1, self.blockCount())
        digits = math.ceil(math.log(num_blocks, 10))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits

        return space

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def updateLineNumberAreaWidth(self, newBlockCount: int):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy: int):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def createMimeDataFromSelection(self):
        mimedata = QMimeData()
        mimedata.setText(self.textCursor().selectedText())
        return mimedata

    def should_show_completion_box(self):
        if not self.completer or not bool(self.settings.get_event_autocomplete()):
            return False
        if not self.document().toPlainText():
            return False
        if self.prev_keyboard_press in (Qt.Key_Backspace, Qt.Key_Return, Qt.Key_Tab): # don't do autocomplete on backspace
            return False
        tc = self.textCursor()
        line = tc.block().text()
        cursor_pos = tc.positionInBlock()
        if len(line) != cursor_pos: # Only do autocomplete on end of line
            return False
        if tc.blockNumber() <= 0 and cursor_pos <= 0:
            return False
        return True

    def hide_completion_box(self):
        try:
            if self.completer and self.completer.popup().isVisible():
                self.completer.popup().hide()
        except:
            pass

    def should_show_function_hint(self):
        if not bool(self.settings.get_event_autocomplete()):
            return False
        if not self.function_hinter:
            return False
        if not self.document().toPlainText():
            return False
        if self.prev_keyboard_press == Qt.Key_Return: # don't do hint on newline
            return False
        tc = self.textCursor()
        cursor_pos = tc.positionInBlock()
        if tc.blockNumber() <= 0 and cursor_pos <= 0:
            return False
        return True

    def hide_function_hint(self):
        if self.function_annotator.isVisible():
            self.function_annotator.hide()

    def keyPressEvent(self, event):
        self.prev_keyboard_press = event.key()
        # Shift + Tab is not the same as catching a shift modifier + tab key
        # Shift + Tab is a Backtab
        if self.completer:  # let the autocomplete handle the event first
            stop_handling = self.completer.handleKeyPressEvent(event)
            if stop_handling:
                return
        # autocomplete didn't handle the event, or doesn't consume it
        # let the textbox handle
        if event.key() == Qt.Key_Tab:
            cur = self.textCursor()
            cur.insertText("    ")
        elif event.key() == Qt.Key_Backspace:
            # autofill functionality, hides autofill windows
            self.hide_function_hint()
            self.hide_completion_box()
            return super().keyPressEvent(event)
        elif event.key() == Qt.Key_Return:
            self.hide_function_hint()
            self.hide_completion_box()
            return super().keyPressEvent(event)
        elif event.key() == Qt.Key_Backtab:
            cur = self.textCursor()
            # Copy the current selection
            pos = cur.position()  # Where a selection ends
            anchor = cur.anchor()  # Where a selection starts (can be the same as above)
            cur.setPosition(pos)
            # Move the position back one, selecting the character prior to the original position
            cur.setPosition(pos - 1, QTextCursor.KeepAnchor)

            if str(cur.selectedText()) == "\t":
                # The prior character is a tab, so delete the selection
                cur.removeSelectedText()
                # Reposition the cursor
                cur.setPosition(anchor - 1)
                cur.setPosition(pos - 1, QTextCursor.KeepAnchor)
            elif str(cur.selectedText()) == " ":
                # Remove up to four spaces
                counter = 0
                while counter < 4 and all(c == " " for c in str(cur.selectedText())):
                    counter += 1
                    cur.setPosition(pos - 1 - counter, QTextCursor.KeepAnchor)
                cur.setPosition(pos - counter, QTextCursor.KeepAnchor)
                cur.removeSelectedText()
                # Reposition the cursor
                cur.setPosition(anchor)
                cur.setPosition(pos, QTextCursor.KeepAnchor)
            else:
                # Try all of the above, looking before the anchor
                cur.setPosition(anchor)
                cur.setPosition(anchor - 1, QTextCursor.KeepAnchor)
                if str(cur.selectedText()) == "\t":
                    cur.removeSelectedText()
                    cur.setPosition(anchor - 1)
                    cur.setPosition(pos - 1, QTextCursor.KeepAnchor)
                else:
                    # It's not a tab, so reset the selection to what it was
                    cur.setPosition(anchor)
                    cur.setPosition(pos, QTextCursor.KeepAnchor)
        elif event.key() == Qt.Key_Escape:
            # autofill functionality, hides autofill windows
            self.hide_function_hint()
            self.hide_completion_box()
        else:
            return super().keyPressEvent(event)
