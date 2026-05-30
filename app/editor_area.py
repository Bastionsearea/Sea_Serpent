"""
Code editor widget with syntax highlighting, line numbers, and minimap.

Provides the reusable CodeEditor, LineNumberArea, and Minimap classes
that are embedded into the dock system by dock_editor_manager.py.
"""

from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import (
    QFont, QFontDatabase, QTextOption, QColor, QPainter,
    QWheelEvent, QTextFormat, QFontMetrics,
)
from pygments import lex
from PySide6.QtWidgets import (
    QPlainTextEdit, QTextEdit, QFrame, QWidget,
)

from .theme import Colors
from .syntax_highlighter import SyntaxHighlighter, _token_format


class LineNumberArea(QWidget):
    """Gutter area that paints line numbers beside the editor content."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return self._editor._line_number_area_size()

    def paintEvent(self, event):
        self._editor._line_number_area_paint(event)


class CodeEditor(QPlainTextEdit):
    """VSCode-style code editor with line numbers and syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CodeEditor")
        self.setFrameShape(QFrame.NoFrame)
        self.setTabStopDistance(40)

        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setFamilies(["Cascadia Code", "Fira Code", "Consolas",
                           "Courier New", "monospace"])
        font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Line number area
        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_number_area_width()

        # Syntax highlighter (lazy-init on file open)
        self._highlighter = SyntaxHighlighter(self.document())

        # Highlight current line
        self._highlight_current_line()

        # Text wrapping options
        doc = self.document()
        opt = doc.defaultTextOption()
        doc.setDefaultTextOption(opt)

        self._whitespace_visible = False

    def set_syntax_language(self, filename: str):
        """Enable syntax highlighting for the given filename."""
        self._highlighter.set_language_by_filename(filename)

    def clear_syntax(self):
        """Remove all syntax highlighting."""
        self._highlighter.set_language("")

    def toggle_whitespace_visibility(self):
        """Toggle the display of tab/space invisible characters."""
        self._whitespace_visible = not self._whitespace_visible
        doc = self.document()
        opt = doc.defaultTextOption()
        if self._whitespace_visible:
            opt.setFlags(opt.flags() | QTextOption.Flag.ShowTabsAndSpaces)
        else:
            opt.setFlags(opt.flags() & ~QTextOption.Flag.ShowTabsAndSpaces)
        doc.setDefaultTextOption(opt)

    def whitespace_visible(self) -> bool:
        return self._whitespace_visible

    def _line_number_area_size(self):
        digits = len(str(max(1, self.blockCount())))
        char_w = max(1, self.fontMetrics().horizontalAdvance('0'))
        padding = int(3 * char_w)
        return QSize(padding * 2 + int(digits * char_w), 0)

    def _update_line_number_area_width(self):
        self.setViewportMargins(self._line_number_area_size().width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(),
                                          self._line_number_area.width(),
                                          rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def _highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            line_color = QColor("#2a2d2e")
            sel.format.setBackground(line_color)
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra_selections.append(sel)
        self.setExtraSelections(extra_selections)

    def _line_number_area_paint(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(Colors.EDITOR_BG))

        char_w = max(1, self.fontMetrics().horizontalAdvance('0'))
        left_pad = int(3 * char_w)
        right_pad = int(3 * char_w)
        area_w = self._line_number_area.width()
        text_w = area_w - left_pad - right_pad
        line_h = self.fontMetrics().height()

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        current_line = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                if block_number == current_line:
                    painter.setPen(QColor(Colors.LINE_NUMBER_ACTIVE))
                else:
                    painter.setPen(QColor(Colors.LINE_NUMBER))
                painter.drawText(left_pad, top, text_w, line_h,
                                 Qt.AlignRight | Qt.AlignVCenter, number)

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            cr.left(), cr.top(),
            self._line_number_area_size().width(), cr.height()
        )

    def wheelEvent(self, event: QWheelEvent):
        """Support Ctrl+Scroll for zoom."""
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoomIn(1)
            else:
                self.zoomOut(1)
            event.accept()
            return
        super().wheelEvent(event)


class Minimap(QWidget):
    """VSCode-style minimap — renders syntax-highlighted code at tiny scale."""

    LINE_HEIGHT = 3          # pixels per line in the minimap
    CHARS_PER_LINE = 60      # max visible characters per minimap line

    def __init__(self, parent=None, editor: CodeEditor = None):
        super().__init__(parent)
        self.setObjectName("Minimap")
        self.setFixedWidth(100)
        self._editor = editor
        self.setCursor(Qt.PointingHandCursor)
        self._content_height = 0
        self._dragging = False

        self._font = QFont("Consolas", 2)
        self._font.setStyleHint(QFont.Monospace)
        self._char_w = 0

    def _ensure_char_width(self, painter: QPainter):
        if self._char_w <= 0:
            fm = QFontMetrics(self._font)
            self._char_w = max(1.5, fm.horizontalAdvance('x'))

    def set_editor(self, editor: CodeEditor):
        self._editor = editor

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(Colors.MINIMAP_BG))
        painter.setFont(self._font)
        self._ensure_char_width(painter)

        if not self._editor:
            return

        doc = self._editor.document()
        total_blocks = doc.blockCount()
        if total_blocks == 0:
            return

        content_height = total_blocks * self.LINE_HEIGHT
        self._content_height = content_height

        sb = self._editor.verticalScrollBar()
        scroll_offset = 0
        if sb and sb.maximum() > 0:
            scroll_offset = (sb.value() / sb.maximum()) * max(0, content_height - self.height())

        lexer = None
        if hasattr(self._editor, '_highlighter') and self._editor._highlighter:
            lexer = self._editor._highlighter._lexer

        first_visible = max(0, int(scroll_offset / self.LINE_HEIGHT))
        visible_count = int(self.height() / self.LINE_HEIGHT) + 2

        block = doc.findBlockByNumber(first_visible)
        y = float(first_visible * self.LINE_HEIGHT - scroll_offset + 2)
        char_w = self._char_w
        margin = 2
        max_chars = int((self.width() - margin * 2) / char_w)
        max_chars = min(max_chars, self.CHARS_PER_LINE)
        drawn = 0
        max_draw = min(total_blocks - first_visible, 5000)

        while block.isValid() and y < self.height() and drawn < max_draw:
            text = block.text()
            if text:
                truncated = text[:max_chars]
                if lexer:
                    x = float(margin)
                    try:
                        for ttype, value in lex(truncated, lexer):
                            if not value or x > self.width():
                                break
                            fmt = _token_format(ttype)
                            painter.setPen(fmt.foreground().color())
                            w = len(value) * char_w
                            painter.drawText(QRectF(x, y, w + 1, self.LINE_HEIGHT),
                                           Qt.AlignLeft | Qt.AlignTop, value)
                            x += w
                    except Exception:
                        painter.setPen(QColor(Colors.TEXT_DISABLED))
                        painter.drawText(QRectF(margin, y, self.width() - margin, self.LINE_HEIGHT),
                                       Qt.AlignLeft | Qt.AlignTop, truncated[:50])
                else:
                    painter.setPen(QColor(Colors.TEXT_DISABLED))
                    painter.drawText(QRectF(margin, y, self.width() - margin, self.LINE_HEIGHT),
                                   Qt.AlignLeft | Qt.AlignTop, truncated[:max_chars])

            y += self.LINE_HEIGHT
            block = block.next()
            drawn += 1

        # Slider overlay
        if content_height > self.height():
            slider_h = max(20, self.height() * self.height() // max(1, content_height))
            slider_y = min(self.height() - slider_h,
                          int(scroll_offset * self.height() / max(1, content_height)))
            painter.fillRect(0, slider_y, self.width(), slider_h,
                           QColor(255, 255, 255, 12))
            painter.setPen(QColor(Colors.ACCENT))
            painter.drawRect(0, slider_y, self.width() - 1, slider_h - 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._editor:
            self._dragging = True
            self._scroll_to_y(event.position().y())

    def mouseMoveEvent(self, event):
        if self._dragging and self._editor:
            self._scroll_to_y(event.position().y())

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def _scroll_to_y(self, y: float):
        sb = self._editor.verticalScrollBar()
        if sb and sb.maximum() > 0:
            ratio = max(0, min(1, y / self.height()))
            sb.setValue(int(ratio * sb.maximum()))

    def update_minimap(self):
        self.update()
