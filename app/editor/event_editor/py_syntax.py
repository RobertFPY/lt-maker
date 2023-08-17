from __future__ import annotations

from dataclasses import dataclass
from PyQt5 import QtCore, QtGui
from app import dark_theme

# from https://wiki.python.org/moin/PyQt/Python%20syntax%20highlighting
# with some modification

def format(color: QtGui.QColor):
    """Return a QTextCharFormat with the given attributes.
    """
    _format = QtGui.QTextCharFormat()
    _format.setForeground(color)
    return _format

class PythonHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the Python language.
    """
    # keywords
    keywords = ['and', 'def', 'class', 'is', 'lambda', 'not', 'or',
                'None', 'True', 'False', 'self']
    # alt keywords
    alt_keywords = ['assert', 'break', 'continue', 'del',
                    'if', 'elif', 'else', 'except', 'raise',
                    'return', 'try', 'while', 'yield', 'finally',
                    'for', 'from', 'global', 'import', 'pass', 'in']

    # Python braces
    braces = [
        '\{', '\}', '\(', '\)', '\[', '\]',
    ]

    def __init__(self, parent: QtGui.QTextDocument) -> None:
        super().__init__(parent)
        theme = dark_theme.get_theme()
        styles = theme.python_syntax_highlighting()
        # Multi-line strings (expression, flag, style)
        self.tri_single = (QtCore.QRegExp("'''"), 1, format(styles.string2))
        self.tri_double = (QtCore.QRegExp('"""'), 2, format(styles.string2))

        rules = []

        # Keyword, operator, and brace rules
        rules += [(r'\b%s\b' % w, 0, format(styles.keyword))
            for w in PythonHighlighter.keywords]
        rules += [(r'\b%s\b' % w, 0, format(styles.alt_keyword))
            for w in PythonHighlighter.alt_keywords]
        rules += [(r'%s' % b, 0, format(styles.brace))
            for b in PythonHighlighter.braces]

        # All other rules
        rules += [
            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, format(styles.deffunc)),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, format(styles.defclass)),

            # Numeric literals
            (r'\b[+-]?[0-9]+[lL]?\b', 0, format(styles.numbers)),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, format(styles.numbers)),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, format(styles.numbers)),

            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, format(styles.string)),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, format(styles.string)),

            # From '#' until a newline
            (r'#[^\n]*', 0, format(styles.comment)),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt)
            for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """
        self.tripleQuoutesWithinStrings = []
        # Do other syntax formatting
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)
            if index >= 0:
                # if there is a string we check
                # if there are some triple quotes within the string
                # they will be ignored if they are matched again
                if expression.pattern() in [r'"[^"\\]*(\\.[^"\\]*)*"', r"'[^'\\]*(\\.[^'\\]*)*'"]:
                    innerIndex = self.tri_single[0].indexIn(text, index + 1)
                    if innerIndex == -1:
                        innerIndex = self.tri_double[0].indexIn(text, index + 1)

                    if innerIndex != -1:
                        tripleQuoteIndexes = range(innerIndex, innerIndex + 3)
                        self.tripleQuoutesWithinStrings.extend(tripleQuoteIndexes)

            while index >= 0:
                # skipping triple quotes within strings
                if index in self.tripleQuoutesWithinStrings:
                    index += 1
                    expression.indexIn(text, index)
                    continue

                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            in_multiline = self.match_multiline(text, *self.tri_double)

    def match_multiline(self, text, delimiter, in_state, style):
        """Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # skipping triple quotes within strings
            if start in self.tripleQuoutesWithinStrings:
                return False
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False otherwise
        if self.currentBlockState() == in_state:
            return True
        else:
            return False