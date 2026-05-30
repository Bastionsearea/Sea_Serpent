"""
VS Code-style breadcrumb navigation bar for the editor area.

Shows the file path as clickable segments separated by chevrons,
e.g.:  src > app > main_window.py
"""

import os

from PySide6.QtCore import Qt, Signal, QEvent, QByteArray
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from .theme import Colors

CHEVRON_SVG = (
    '<svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="#cccccc">'
    '<path d="M6.14601 3.14579C5.95101 3.34079 5.95101 3.65779 6.14601 3.85279L10.292 '
    '7.99879L6.14601 12.1448C5.95101 12.3398 5.95101 12.6568 6.14601 12.8518C6.34101 '
    '13.0468 6.65801 13.0468 6.85301 12.8518L11.353 8.35179C11.548 8.15679 11.548 '
    '7.83979 11.353 7.64478L6.85301 3.14479C6.65801 2.94979 6.34101 2.95079 6.14601 3.14579Z"/>'
    '</svg>'
)


class BreadcrumbBar(QWidget):
    """Horizontal breadcrumb showing file path segments above the editor."""

    segment_clicked = Signal(str)
    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BreadcrumbBar")
        self.setFixedHeight(22)
        self.setStyleSheet(f"""
            QWidget#BreadcrumbBar {{
                background-color: {Colors.EDITOR_BG};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 0, 4, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._file_path = ""

    def set_file_path(self, file_path: str, workspace_root: str = ""):
        """Set the file path to display, building breadcrumb segments."""
        self._file_path = file_path

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not file_path:
            return

        if workspace_root and file_path.startswith(workspace_root):
            relative = os.path.relpath(file_path, workspace_root)
        else:
            relative = file_path

        parts = relative.replace("\\", "/").split("/")

        for part in parts[:-1]:
            self._add_segment(part, is_last=False)
            self._add_chevron()

        if parts:
            self._add_segment(parts[-1], is_last=True)

        self._layout.addStretch(1)

    def _add_segment(self, text: str, is_last: bool = False):
        btn = QPushButton(text)
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        weight = "600" if is_last else "400"
        color = Colors.TEXT_PRIMARY if is_last else Colors.TEXT_SECONDARY
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {color};
                font-size: 13px;
                font-weight: {weight};
                padding: 0px 6px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {Colors.TAB_HOVER_BG};
            }}
        """)
        btn.installEventFilter(self)
        self._layout.addWidget(btn)

    def _add_chevron(self):
        lbl = QLabel()
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(CHEVRON_SVG.encode("utf-8")))
        lbl.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lbl.setStyleSheet("background: transparent; border: none; padding: 0px;")
        lbl.installEventFilter(self)
        self._layout.addWidget(lbl)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonDblClick:
            self.double_clicked.emit()
            return True
        return super().eventFilter(watched, event)
