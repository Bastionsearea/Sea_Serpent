"""
Activity bar – the narrow vertical strip of icon buttons on the far left.

Mirrors VSCode's activity bar: each button toggles a sidebar view.
"""

import time

from PySide6.QtCore import Qt, QSize, Signal, QByteArray
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QButtonGroup

from .theme import Colors, ICONS


def _svg_to_icon(svg_string: str) -> QIcon:
    """Convert an SVG string to a QIcon (16x16 base, scales automatically)."""
    pixmap = QPixmap()
    ba = QByteArray(svg_string.encode("utf-8"))
    pixmap.loadFromData(ba)
    if pixmap.isNull():
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
    return QIcon(pixmap)


class ActivityBar(QWidget):
    """Left-side icon bar. Emits view_changed when an icon is selected."""

    # (view_id, view_title)
    view_changed = Signal(str, str)
    sidebar_toggle_requested = Signal()

    _DOUBLE_CLICK_INTERVAL = 0.4  # seconds

    LARGE_WIDTH = 48
    COMPACT_WIDTH = 34
    LARGE_BTN = 48
    COMPACT_BTN = 34
    LARGE_ICON = 28
    COMPACT_ICON = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        self._compact = True
        self.setFixedWidth(self.COMPACT_WIDTH)

        self._views: list[dict] = [
            {"id": "home",          "title": "Home",              "icon": "home"},
            {"id": "files",         "title": "Explorer",          "icon": "files"},
            {"id": "search",        "title": "Search",            "icon": "search"},
            {"id": "source_control","title": "Source Control",    "icon": "source_control"},
            {"id": "run",           "title": "Run and Debug",     "icon": "run"},
            {"id": "play",          "title": "Play",              "icon": "play"},
            {"id": "testing",       "title": "Testing",           "icon": "beaker"},
            {"id": "extensions",    "title": "Extensions",        "icon": "extensions"},
            {"id": "database",      "title": "Database",          "icon": "database"},
            {"id": "terminal",      "title": "Terminal",          "icon": "terminal"},
            {"id": "agent",         "title": "Chat",              "icon": "copilot"},
        ]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top button group ────────────────────────────────────────────────
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        for view in self._views:
            btn = QPushButton(self)
            btn.setObjectName("ActivityButton")
            btn.setCheckable(True)
            btn.setFixedSize(self.COMPACT_BTN, self.COMPACT_BTN)
            btn.setIcon(_svg_to_icon(ICONS.get(view["icon"], "")))
            btn.setIconSize(QSize(self.COMPACT_ICON, self.COMPACT_ICON))
            btn.setToolTip(view["title"])
            btn.clicked.connect(lambda checked, v=view: self._on_button_clicked(v))
            self._button_group.addButton(btn)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        # ── Bottom buttons (settings, accounts) ─────────────────────────────
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 4)
        bottom_layout.setSpacing(0)

        self.accounts_btn = QPushButton(self)
        self.accounts_btn.setObjectName("ActivityButton")
        self.accounts_btn.setFixedSize(self.COMPACT_BTN, self.COMPACT_BTN)
        self.accounts_btn.setIcon(_svg_to_icon(ICONS.get("accounts", "")))
        self.accounts_btn.setIconSize(QSize(self.COMPACT_ICON, self.COMPACT_ICON))
        self.accounts_btn.setToolTip("Accounts")
        bottom_layout.addWidget(self.accounts_btn)

        self.settings_btn = QPushButton(self)
        self.settings_btn.setObjectName("ActivityButton")
        self.settings_btn.setFixedSize(self.COMPACT_BTN, self.COMPACT_BTN)
        self.settings_btn.setIcon(_svg_to_icon(ICONS.get("settings", "")))
        self.settings_btn.setIconSize(QSize(self.COMPACT_ICON, self.COMPACT_ICON))
        self.settings_btn.setToolTip("Settings")
        bottom_layout.addWidget(self.settings_btn)

        layout.addLayout(bottom_layout)

        # Default selection (Home)
        self._buttons[0].setChecked(True)
        self._current_view = self._views[0]

        # Double-click detection
        self._last_click_time = 0.0
        self._last_clicked_view_id = ""

    def _on_button_clicked(self, view: dict):
        now = time.time()
        is_same_view = (view["id"] == self._current_view["id"])
        is_double_click = (
            is_same_view and
            view["id"] == self._last_clicked_view_id and
            (now - self._last_click_time) < self._DOUBLE_CLICK_INTERVAL
        )

        self._last_click_time = now
        self._last_clicked_view_id = view["id"]

        if is_double_click:
            self.sidebar_toggle_requested.emit()
            return

        self._current_view = view
        self.view_changed.emit(view["id"], view["title"])

    def current_view(self) -> str:
        """Return the currently active view id."""
        return self._current_view["id"]

    def select_view(self, view_id: str):
        """Programmatically select a view by its id."""
        for i, view in enumerate(self._views):
            if view["id"] == view_id:
                self._buttons[i].setChecked(True)
                self._current_view = view
                self.view_changed.emit(view["id"], view["title"])
                break

    def add_custom_view(self, view_id: str, title: str, icon_svg: str):
        """Dynamically add a new view button to the activity bar."""
        view = {"id": view_id, "title": title, "icon": icon_svg}
        # Insert before the spacer
        last_idx = self.layout().count() - 2  # before stretch + bottom_layout
        btn_size = self.COMPACT_BTN if self._compact else self.LARGE_BTN
        icon_size = self.COMPACT_ICON if self._compact else self.LARGE_ICON
        btn = QPushButton(self)
        btn.setObjectName("ActivityButton")
        btn.setCheckable(True)
        btn.setFixedSize(btn_size, btn_size)
        btn.setIconSize(QSize(icon_size, icon_size))
        btn.setIcon(_svg_to_icon(icon_svg))
        btn.setToolTip(title)
        btn.clicked.connect(lambda checked, v=view: self._on_button_clicked(v))
        self._button_group.addButton(btn)
        self._buttons.insert(len(self._views), btn)
        self._views.append(view)
        self.layout().insertWidget(last_idx, btn)

    def mouseDoubleClickEvent(self, event):
        """Toggle between compact and large mode on double-click."""
        if event.button() == Qt.LeftButton:
            self.set_compact_mode(not self._compact)
        super().mouseDoubleClickEvent(event)

    def set_compact_mode(self, enabled: bool):
        """Switch between compact (34px) and large (48px) mode."""
        if self._compact == enabled:
            return
        self._compact = enabled
        w = self.COMPACT_WIDTH if enabled else self.LARGE_WIDTH
        btn_size = self.COMPACT_BTN if enabled else self.LARGE_BTN
        icon_sz = QSize(self.COMPACT_ICON, self.COMPACT_ICON) if enabled else QSize(self.LARGE_ICON, self.LARGE_ICON)
        self.setFixedWidth(w)
        for btn in self._buttons:
            btn.setFixedSize(btn_size, btn_size)
            btn.setIconSize(icon_sz)
        self.accounts_btn.setFixedSize(btn_size, btn_size)
        self.accounts_btn.setIconSize(icon_sz)
        self.settings_btn.setFixedSize(btn_size, btn_size)
        self.settings_btn.setIconSize(icon_sz)

    def is_compact(self) -> bool:
        """Return True if the activity bar is in compact mode."""
        return self._compact
