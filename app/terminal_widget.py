"""
Real terminal widget using PySide6 QProcess.

Spawns an actual shell process (cmd.exe on Windows, bash on Unix)
and connects stdin/stdout/stderr to an editable QPlainTextEdit for a
genuine interactive terminal experience — no external dependencies.
"""

import locale
import os
import re
import sys

from PySide6.QtCore import Qt, QProcess, QByteArray, Signal
from PySide6.QtGui import QFont, QTextCursor, QKeyEvent, QColor, QTextCharFormat
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit

from .theme import Colors

# ANSI escape sequence pattern
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

_ANSI_COLORS = {
    30: QColor(Colors.TEXT_PRIMARY),
    31: QColor(255, 100, 100),
    32: QColor(100, 255, 100),
    33: QColor(255, 255, 100),
    34: QColor(100, 150, 255),
    35: QColor(255, 100, 255),
    36: QColor(100, 255, 255),
    37: QColor(255, 255, 255),
    90: QColor(150, 150, 150),
    91: QColor(255, 130, 130),
    92: QColor(130, 255, 130),
    93: QColor(255, 255, 130),
    94: QColor(130, 170, 255),
    95: QColor(255, 130, 255),
    96: QColor(130, 255, 255),
    97: QColor(255, 255, 255),
}


def _ansi_256_color(n: int) -> QColor:
    if n < 16:
        std = [0x00, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
               0xC0, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        r = 0xFF if (n & 1) else (std[n] if (n & 2) else 0x00)
        g = 0xFF if (n & 1) else (std[n] if (n & 4) else 0x00)
        b = 0xFF if (n & 1) else (std[n] if (n & 8) else 0x00)
        return QColor(r, g, b)
    elif n < 232:
        n -= 16
        return QColor((n // 36) * 51, ((n % 36) // 6) * 51, (n % 6) * 51)
    else:
        gray = (n - 232) * 10 + 8
        return QColor(gray, gray, gray)


def _detect_encoding() -> str:
    """Detect the best encoding for the system shell output."""
    if sys.platform == 'win32':
        try:
            loc = locale.getdefaultlocale()
            if loc and loc[1]:
                return loc[1]
        except Exception:
            pass
        return sys.stdout.encoding or 'gbk'
    return sys.stdout.encoding or 'utf-8'


class TerminalView(QPlainTextEdit):
    """Editable terminal display area with ANSI support.

    The user can only type at the end (input zone). Process output
    is append-only and protected from editing.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(False)
        self.setObjectName("TerminalView")
        self.setFrameStyle(0)
        self.setCursorWidth(2)

        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Colors.EDITOR_BG};
                color: {Colors.TEXT_PRIMARY};
                border: none;
                padding: 4px 8px;
                selection-background-color: #3a3d41;
            }}
        """)

        # Everything before this position is read-only output
        self._input_start = 0

    def append_ansi(self, text: str):
        """Append ANSI-parsed output at end of document."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        default_fmt = QTextCharFormat()
        default_fmt.setForeground(QColor(Colors.TEXT_PRIMARY))

        pos = 0
        current_fmt = default_fmt

        for match in _ANSI_RE.finditer(text):
            if match.start() > pos:
                cursor.insertText(text[pos:match.start()], current_fmt)
            code_str = match.group()[2:-1]
            final_byte = match.group()[-1]
            if final_byte == 'm':
                current_fmt = self._parse_sgr(code_str, current_fmt)
            pos = match.end()

        if pos < len(text):
            cursor.insertText(text[pos:], current_fmt)

        self._input_start = self.textCursor().position()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_error(self, text: str):
        """Append stderr text in red."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(255, 100, 100))
        cursor.insertText(text, fmt)
        self._input_start = cursor.position()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_plain(self, text: str):
        """Append plain text (no ANSI)."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self._input_start = cursor.position()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def get_input_text(self) -> str:
        """Return the text the user has typed in the input zone."""
        return self.toPlainText()[self._input_start:]

    def clear_input(self):
        """Remove the current input text."""
        cursor = self.textCursor()
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)

    # ── Key event handling ────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()
        cursor = self.textCursor()

        # Ensure cursor never sits in the protected output zone
        if cursor.position() < self._input_start or cursor.anchor() < self._input_start:
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                        Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown):
                return

        if key == Qt.Key_Return or key == Qt.Key_Enter:
            event.ignore()
            return
        elif key == Qt.Key_Backspace:
            if cursor.position() <= self._input_start:
                return
        elif key == Qt.Key_Home:
            cursor.setPosition(self._input_start)
            self.setTextCursor(cursor)
            return
        elif key == Qt.Key_Left:
            if cursor.position() <= self._input_start:
                return
        elif key == Qt.Key_Up or key == Qt.Key_PageUp:
            return
        elif key == Qt.Key_C and modifiers == Qt.ControlModifier:
            # Let Ctrl+C be handled externally; insert ^C marker
            self.append_plain("^C")
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        cursor = self.textCursor()
        if cursor.position() < self._input_start or cursor.anchor() < self._input_start:
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        cursor = self.textCursor()
        if cursor.position() < self._input_start or cursor.anchor() < self._input_start:
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)

    # ── ANSI parsing ──────────────────────────────────────────────────────

    def _parse_sgr(self, code_str: str, current_fmt: QTextCharFormat) -> QTextCharFormat:
        fmt = QTextCharFormat(current_fmt)
        if not code_str:
            fmt.setForeground(QColor(Colors.TEXT_PRIMARY))
            fmt.setBackground(QColor(Colors.EDITOR_BG))
            fmt.setFontWeight(QFont.Normal)
            return fmt

        parts = code_str.split(';')
        i = 0
        while i < len(parts):
            try:
                code = int(parts[i])
            except ValueError:
                i += 1
                continue

            if code == 0:
                fmt.setForeground(QColor(Colors.TEXT_PRIMARY))
                fmt.setBackground(QColor(Colors.EDITOR_BG))
                fmt.setFontWeight(QFont.Normal)
            elif code == 1:
                fmt.setFontWeight(QFont.Bold)
            elif code == 22:
                fmt.setFontWeight(QFont.Normal)
            elif 30 <= code <= 37 or 90 <= code <= 97:
                color = _ANSI_COLORS.get(code)
                if color:
                    fmt.setForeground(color)
            elif 40 <= code <= 47:
                color = _ANSI_COLORS.get(code - 10)
                if color:
                    fmt.setBackground(color)
            elif code in (38, 48):
                if i + 2 < len(parts) and parts[i + 1] == '5':
                    try:
                        n = int(parts[i + 2])
                        c = _ansi_256_color(n)
                        if code == 38:
                            fmt.setForeground(c)
                        else:
                            fmt.setBackground(c)
                    except (ValueError, IndexError):
                        pass
                    i += 2
            i += 1

        return fmt


class TerminalWidget(QWidget):
    """A real terminal widget running an actual shell via QProcess."""

    process_finished = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TerminalWidget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._view = TerminalView()
        self._view.installEventFilter(self)
        layout.addWidget(self._view)

        self._process: QProcess | None = None
        self._encoding = _detect_encoding()

        self._start_shell()

    # ── Shell lifecycle ───────────────────────────────────────────────────

    def _start_shell(self):
        if self._process is not None:
            self._process.kill()
            self._process = None

        self._view.clear()
        self._view._input_start = 0

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        if sys.platform == 'win32':
            self._process.start('cmd.exe', [])
        else:
            shell = os.environ.get('SHELL', '/bin/bash')
            self._process.start(shell, [])

    # ── Process I/O ───────────────────────────────────────────────────────

    def _on_stdout(self):
        data = bytes(self._process.readAllStandardOutput())
        text = data.decode(self._encoding, errors='replace')
        self._view.append_ansi(text)

    def _on_stderr(self):
        data = bytes(self._process.readAllStandardError())
        text = data.decode(self._encoding, errors='replace')
        self._view.append_error(text)

    def _on_finished(self, exit_code, exit_status):
        self._view.append_plain(f"\n[Process exited with code {exit_code}]")
        self.process_finished.emit(exit_code)

    # ── Event filter — intercept Enter to send commands ───────────────────

    def eventFilter(self, obj, event):
        if obj is self._view and event.type() == event.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if key == Qt.Key_Return or key == Qt.Key_Enter:
                self._send_input()
                return True
            elif key == Qt.Key_C and modifiers == Qt.ControlModifier:
                self._view.append_plain("^C")
                if self._process and self._process.state() == QProcess.Running:
                    self._process.write(b'\x03')
                self._view._input_start = self._view.textCursor().position()
                return True

        return super().eventFilter(obj, event)

    def _send_input(self):
        if self._process is None or self._process.state() != QProcess.Running:
            return

        # Read the user's current input and clear it from the view
        input_text = self._view.get_input_text()
        self._view.clear_input()

        # Append a newline visually
        self._view.append_plain('\n')

        # Send to the shell
        cmd = (input_text + '\r\n').encode(self._encoding, errors='replace')
        self._process.write(QByteArray(cmd))

    # ── Public API ────────────────────────────────────────────────────────

    def write_command(self, command: str):
        """Programmatically send a command to the running shell."""
        if self._process and self._process.state() == QProcess.Running:
            cmd = (command + '\r\n').encode(self._encoding, errors='replace')
            self._process.write(QByteArray(cmd))

    def restart(self):
        self._start_shell()

    def terminate(self):
        if self._process is not None:
            self._process.kill()
            self._process = None
