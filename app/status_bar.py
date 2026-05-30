"""
Status bar – the horizontal strip at the bottom of the window.

Mirrors VSCode's status bar with left/right sections for:
- Branch name, file position, encoding, language, indentation
- Errors/warnings, notifications, and toggles
"""

from PySide6.QtCore import Qt, Signal, QByteArray
from PySide6.QtGui import QFont, QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)

from .theme import Colors, ICONS


def _make_icon(icon_name: str, size: int = 14) -> QIcon:
    """Build a QIcon from a named SVG in the ICONS dict."""
    svg = ICONS.get(icon_name, "")
    if not svg:
        return QIcon()
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray(svg.encode("utf-8")))
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
    return QIcon(pixmap)


class StatusBarItem(QPushButton):
    """An individual clickable item in the status bar."""

    def __init__(self, text: str = "", icon_name: str = "", tooltip: str = "",
                 parent=None):
        super().__init__(parent)
        self.setObjectName("StatusItem")
        if icon_name:
            self.setIcon(_make_icon(icon_name, 16))
            self.setIconSize(QPixmap(16, 16).size())
        self.setText(text)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)


class StatusLabel(QLabel):
    """Non-interactive label used in the status bar."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("StatusLabel")


class StatusBar(QWidget):
    """Bottom status bar with left and right sections."""

    item_clicked = Signal(str)  # Emitted with item id when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFixedHeight(22)

        self._items: dict[str, StatusBarItem] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        # ── Left Section ────────────────────────────────────────────────────
        self.left_section = QHBoxLayout()
        self.left_section.setContentsMargins(0, 0, 0, 0)
        self.left_section.setSpacing(0)

        # Remote indicator
        self._add_left_item("branch", "", "remote",
                            "Open a Remote Window")

        # Error/Warning counts
        self._add_left_item("errors", "0", "error",
                            "No problems detected")
        self._add_left_item("warnings", "0", "warning",
                            "No warnings")

        layout.addLayout(self.left_section)
        layout.addStretch(1)

        # ── Right Section ───────────────────────────────────────────────────
        self.right_section = QHBoxLayout()
        self.right_section.setContentsMargins(0, 0, 0, 0)
        self.right_section.setSpacing(0)

        # Encoding
        self._add_right_item("encoding", "UTF-8", "", "File Encoding")

        # Line ending
        self._add_right_item("line_ending", "LF", "", "Line Ending")

        # Language
        self._add_right_item("language", "Python", "", "Select Language Mode")

        # Indentation
        self._add_right_item("indent", "Spaces: 4", "", "Indentation")

        # Line/Column
        self._add_right_item("position", "Ln 1, Col 1", "", "Go to Line/Column")

        # Notifications
        self._add_right_item("notifications", "", "bell", "Notifications")

        layout.addLayout(self.right_section)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _add_left_item(self, item_id: str, text: str, icon_name: str = "",
                       tooltip: str = "") -> StatusBarItem:
        return self._add_item(item_id, text, icon_name, tooltip, self.left_section)

    def _add_right_item(self, item_id: str, text: str, icon_name: str = "",
                        tooltip: str = "") -> StatusBarItem:
        return self._add_item(item_id, text, icon_name, tooltip, self.right_section)

    def _add_item(self, item_id: str, text: str, icon_name: str,
                  tooltip: str, section: QHBoxLayout) -> StatusBarItem:
        item = StatusBarItem(text, icon_name, tooltip)
        item.clicked.connect(lambda: self.item_clicked.emit(item_id))
        self._items[item_id] = item
        section.addWidget(item)
        return item

    def update_item(self, item_id: str, text: str, tooltip: str = None):
        """Update the text (and optionally tooltip) of a status bar item."""
        item = self._items.get(item_id)
        if item:
            item.setText(text)
            if tooltip:
                item.setToolTip(tooltip)

    def set_errors(self, count: int):
        """Update the error count display."""
        self.update_item("errors", str(count),
                         f"{count} problems" if count else "No problems detected")
        item = self._items.get("errors")
        if item and count > 0:
            item.setStyleSheet(
                f"QPushButton#StatusItem {{ color: {Colors.ACCENT_RED}; }}"
            )

    def set_position(self, line: int, col: int):
        """Update the cursor position display."""
        self.update_item("position", f"Ln {line}, Col {col}")

    def set_language(self, language: str):
        """Update the displayed language."""
        self.update_item("language", language)

    def set_branch(self, branch: str):
        """Update the remote/branch display."""
        self.update_item("branch", branch)
