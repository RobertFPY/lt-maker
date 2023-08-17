from __future__ import annotations

import math
import os

from PyQt5.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFontMetrics, QPainter, QPalette, QTextCursor
from PyQt5.QtWidgets import QCompleter, QLabel, QPlainTextEdit, QWidget

from app import dark_theme
from app.editor.event_editor import event_autocompleter
from app.editor.settings import MainSettingsController
from app.events import event_commands, event_validators
from app.extensions.markdown2 import Markdown


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
        self.window = parent
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

        self.completer: QCompleter = None
        self.function_annotator: QLabel = QLabel(self)
        self.markdown_converter: Markdown = Markdown()

        if not bool(self.settings.get_event_autocomplete()):
            return  # Event auto completer is turned off
        else:
            # completer
            self.setCompleter(event_autocompleter.EventScriptCompleter(parent=self))
            self.textChanged.connect(self.complete)
            self.textChanged.connect(self.display_function_hint)
            self.clicked.connect(self.display_function_hint)
            self.cursorPositionChanged.connect(self.display_function_hint)
            self.prev_keyboard_press = None

            # function helper
            self.function_annotator.setTextFormat(Qt.RichText)
            self.function_annotator.setWordWrap(True)
            with open(os.path.join(os.path.dirname(__file__),'event_styles.css'), 'r') as stylecss:
                self.function_annotator.setStyleSheet(stylecss.read())

    def setCompleter(self, completer):
        if not completer:
            return
        completer.setWidget(self)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer = completer
        self.completer.insertText.connect(self.insertCompletion)

    def insertCompletion(self, completion):
        tc = self.textCursor()
        while not tc.atBlockEnd():
            tc.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            if tc.selectedText() in ";,":
                break
            tc.clearSelection()
        end = tc.position()
        while not tc.atBlockStart():
            tc.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
            if tc.selectedText() in ';,':
                break
            tc.clearSelection()
        start = tc.position()
        for i in range(start, end):
            tc.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        tc.removeSelectedText()
        tc.insertText(completion)
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def display_function_hint(self):
        if not bool(self.settings.get_event_autocomplete()):
            return  # Event auto completer is turned off
        tc = self.textCursor()
        line = tc.block().text()
        cursor_pos = tc.positionInBlock()
        if len(line) != cursor_pos and line[cursor_pos - 1] != ';':
            self.function_annotator.hide()
            return  # Only do function hint on end of line or when clicking at the beginning of a field
        if tc.blockNumber() <= 0 and cursor_pos <= 0:  # don't do hint if cursor is at the very top left of event
            self.function_annotator.hide()
            return
        if self.prev_keyboard_press == Qt.Key_Return: # don't do hint on newline
            self.function_annotator.hide()
            return

        if len(line) > 0 and line[cursor_pos - 1] == ';':
            self.function_annotator.show()

        # determine which command and validator is under the cursor
        command = event_autocompleter.detect_command_under_cursor(line)
        validator, flags = event_autocompleter.detect_type_under_cursor(line, cursor_pos, None)

        if not command or command == event_commands.Comment:
            return

        hint_words = []
        hint_words.append(command.nid)
        all_keywords = command.keywords + command.optional_keywords
        for idx, keyword in enumerate(all_keywords):
            if command.keyword_types:
                keyword_type = command.keyword_types[idx]
                hint_str = "%s=%s" % (keyword, keyword_type)
                if validator and event_validators.get(keyword_type) == validator:
                    hint_str = "<b>%s</b>" % hint_str
                hint_words.append(hint_str)
            else:
                hint_str = keyword
                if validator and event_validators.get(keyword) == validator:
                    hint_str = "<b>%s</b>" % hint_str
                hint_words.append(hint_str)
        if command.flags:
            hint_words.append('FLAGS')
        hint_cmd = ""
        hint_desc = ""

        if validator == event_validators.EventFunction:
            self.function_annotator.hide()
            return
        else:
            try:
                arg_idx = line.count(';', 0, cursor_pos)
                if arg_idx != len(hint_words) - 1:
                    hint_desc = validator.__name__ + ' ' + str(validator().desc)
                elif cursor_pos > 0 and command.flags:
                    hint_desc = 'Must be one of (`' + str.join('`,`', flags) + '`)'
            except:
                if cursor_pos > 0 and command.flags:
                    hint_words[-1] = '<b>' + hint_words[-1] + '</b>'
                    hint_desc = 'Must be one of (`' + str.join('`,`', flags) + '`)'

        hint_cmd = str.join(';\u200b', hint_words)
        # style both components
        hint_cmd = '<div class="command_text">' + hint_cmd + '</div>'
        hint_desc = '<div class="desc_text">' + hint_desc + '</div>'
        hint_command_desc = '<div class="desc_text">' + self.markdown_converter.convert('\n'.join(command.desc.split('\n')[:3])) + '</div>'

        style = """
            <style>
                .command_text {font-family: 'Courier New', Courier, monospace;}
                .desc_text {font-family: Arial, Helvetica, sans-serif;}
            </style>
        """

        hint_text = style + hint_cmd + '<hr>' + hint_desc
        if self.settings.get_event_autocomplete_desc():
            hint_text += '<hr>' + hint_command_desc
        self.function_annotator.setText(hint_text)
        self.function_annotator.setWordWrap(True)
        self.function_annotator.adjustSize()

        # offset the position and display
        tc_top_right = self.mapTo(self.parent(), self.cursorRect(tc).topRight())
        height = self.function_annotator.height()

        top, left = tc_top_right.y() - height - 5, min(tc_top_right.x() + 15, self.width() - self.function_annotator.width())
        if top < 0:
            if self.completer.popup().isVisible():
                top = tc_top_right.y() + self.completer.popup().height() + 6
                left = min(tc_top_right.x(), self.width() - self.function_annotator.width())
            else:
                top = tc_top_right.y() + 5
        tc_top_right.setY(top)
        tc_top_right.setX(left)
        self.function_annotator.move(tc_top_right)

    def complete(self):
        if not self.completer or not bool(self.settings.get_event_autocomplete()):
            return  # Event auto completer is turned off
        tc = self.textCursor()
        line = tc.block().text()
        cursor_pos = tc.positionInBlock()
        if len(line) != cursor_pos:
            return  # Only do autocomplete on end of line
        if tc.blockNumber() <= 0 and cursor_pos <= 0:  # Remove if cursor is at the very top left of event
            return
        if self.prev_keyboard_press in (Qt.Key_Backspace, Qt.Key_Return, Qt.Key_Tab): # don't do autocomplete on backspace
            try:
                if self.completer.popup().isVisible():
                    self.completer.popup().hide()
            except: # popup doesn't exist?
                pass
            return

        if not self.completer.setTextToComplete(line, cursor_pos, self.window.current.level_nid):
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
            if self.function_annotator.isVisible():
                self.function_annotator.hide()
            return super().keyPressEvent(event)
        elif event.key() == Qt.Key_Return:
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
            if self.function_annotator.isVisible():
                self.function_annotator.hide()
        else:
            return super().keyPressEvent(event)
