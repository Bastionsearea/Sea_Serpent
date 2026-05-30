"""
Custom frameless title bar mimicking VSCode's native-style title bar.

Provides window controls (minimize, maximize/restore, close),
application title, and menu integration.
"""

import os

from PySide6.QtCore import Qt, Signal, QPoint, QByteArray
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QApplication, QToolButton, QMenu,
)
from .theme import Colors, ICONS


def _svg_to_pixmap(svg_string: str, size: int = 16, color: str = None) -> QPixmap:
    """Convert an SVG string to a QPixmap of given size, optionally changing color."""
    if color:
        svg_string = svg_string.replace('#cccccc', color)
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray(svg_string.encode('utf-8')))
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class TitleBar(QWidget):
    """Custom frameless title bar with window controls and menu."""

    window_minimized = Signal()
    window_maximized = Signal()
    window_restored = Signal()
    window_closed = Signal()
    tab_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self._is_maximized = False
        self._drag_start_pos = None
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("TitleBar")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo ───────────────────────────────────────────────────────────
        self.logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "app", "images", "logo.png")
        logo_pm = QPixmap()
        if logo_pm.load(logo_path) and not logo_pm.isNull():
            logo_pm = logo_pm.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(logo_pm)
            self.logo_label.setFixedSize(logo_pm.width() + 8, 34)
            self.logo_label.setAlignment(Qt.AlignCenter)
            self.logo_label.setStyleSheet("background: transparent; margin-left: 8px;")
        layout.addWidget(self.logo_label)

        # ── Title ─────────────────────────────────────────────────────────────
        self.title_label = QLabel("Sea Serpent")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                margin-left: 8px;
            }}
        """)
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        # ── Tab Switcher Dropdown ─────────────────────────────────────────
        self.tab_dropdown_btn = QToolButton()
        self.tab_dropdown_btn.setObjectName("TabDropdownButton")
        self.tab_dropdown_btn.setToolTip("Open Editors")
        self.tab_dropdown_btn.setFixedSize(46, 30)
        self.tab_dropdown_btn.setIcon(self._pixmap_for_icon("ellipsis", 16))
        self.tab_dropdown_btn.setStyleSheet(f"""
            QToolButton#TabDropdownButton {{
                background: transparent;
                border: none;
                padding: 0px;
                margin-right: 8px;
            }}
        """)
        self._tab_menu = QMenu(self.tab_dropdown_btn)
        self._tab_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Colors.DROPDOWN_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 5px 28px 5px 12px;
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.LIST_ACTIVE};
            }}
        """)
        self.tab_dropdown_btn.clicked.connect(self._show_tab_menu)
        self.tab_dropdown_btn.setVisible(False)  # hidden until files are opened
        layout.addWidget(self.tab_dropdown_btn)

        # ── Window Controls ─────────────────────────────────────────────────
        self.min_btn = QPushButton()
        self.min_btn.setObjectName("WindowButton")
        self.min_btn.setIcon(self._pixmap_for_icon("minimize", 16))
        self.min_btn.setFixedSize(46, 30)
        self.min_btn.clicked.connect(self.window_minimized.emit)
        self.min_btn.setToolTip("Minimize")

        self.max_btn = QPushButton()
        self.max_btn.setObjectName("WindowButton")
        self.max_btn.setIcon(self._pixmap_for_icon("maximize", 16))
        self.max_btn.setFixedSize(46, 30)
        self.max_btn.clicked.connect(self._toggle_maximize)
        self.max_btn.setToolTip("Maximize")

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setIcon(self._pixmap_for_icon("close", 16))
        self.close_btn.setFixedSize(46, 30)
        self.close_btn.clicked.connect(self.window_closed.emit)
        self.close_btn.setToolTip("Close")

        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)

    def _do_drag(self, event):
        """Perform window drag based on mouse movement."""
        if self._parent is None or self._drag_start_pos is None:
            return
        if self._is_maximized:
            self._is_maximized = False
            self._update_maximize_icon()
            self.window_restored.emit()
        delta = event.globalPosition().toPoint() - self._drag_start_pos
        try:
            self._parent.move(self._parent.x() + delta.x(),
                              self._parent.y() + delta.y())
        except Exception:
            pass
        self._drag_start_pos = event.globalPosition().toPoint()

    def _pixmap_for_icon(self, icon_name: str, size: int = 12) -> QPixmap:
        return _svg_to_pixmap(ICONS.get(icon_name, ""), size)

    def _toggle_maximize(self):
        """Toggle between maximized and normal window state.

        Updates internal state immediately rather than relying on the async
        changeEvent callback, preventing the "need to click twice" issue
        when the event loop delays the WindowStateChange event.
        """
        if self._is_maximized:
            self._is_maximized = False
            self._update_maximize_icon()
            self.window_restored.emit()
        else:
            self._is_maximized = True
            self._update_maximize_icon()
            self.window_maximized.emit()

    def _update_maximize_icon(self):
        name = "restore" if self._is_maximized else "maximize"
        self.max_btn.setIcon(self._pixmap_for_icon(name, 16))
        tip = "Restore Down" if self._is_maximized else "Maximize"
        self.max_btn.setToolTip(tip)

    def set_maximized_state(self, maximized: bool):
        """Sync the internal state after an external maximize/restore."""
        self._is_maximized = maximized
        self._update_maximize_icon()

    def _show_tab_menu(self):
        """Show the tab list menu below the dropdown button."""
        self._tab_menu.popup(
            self.tab_dropdown_btn.mapToGlobal(
                self.tab_dropdown_btn.rect().bottomLeft()
            )
        )

    def set_tab_list(self, tabs: list[tuple]):
        """Update the tab dropdown menu.

        Args:
            tabs: List of (file_path, file_name, is_active) tuples.
        """
        self._tab_menu.clear()
        self.tab_dropdown_btn.setVisible(len(tabs) > 0)
        if not tabs:
            return
        for file_path, file_name, is_active in tabs:
            label = f"  ●  {file_name}" if is_active else f"     {file_name}"
            action = QAction(label, self._tab_menu)
            action.setData(file_path)
            if is_active:
                font = action.font()
                font.setBold(True)
                action.setFont(font)
            action.triggered.connect(
                lambda checked=False, fp=file_path: self.tab_selected.emit(fp)
            )
            self._tab_menu.addAction(action)

    # ── Mouse dragging for window movement ──────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_start_pos:
            self._do_drag(event)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = None
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()
            event.accept()
