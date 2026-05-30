"""
Dock-based editor manager.

Each open file lives in its own dock widget, all placed in the center area.
Only the active file's content is shown (via setCurrentDockWidget).
Dragging a file's title bar floats only that file.
"""

import os
import PySide6QtAds as QtAds

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QApplication,
    QTabBar,
)

from .theme import Colors
from .editor_area import CodeEditor, Minimap
from .breadcrumb import BreadcrumbBar

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class DockEditorManager(QWidget):
    """Manages a QStackedWidget containing a welcome page and a CDockManager.

    All open files coexist as tabs in the center dock area; the tab bar is
    hidden to show only the active file. Switching calls setCurrentDockWidget.
    """

    file_closed = Signal(str)
    tabs_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DockEditorManager")

        QtAds.CDockManager.setConfigFlag(
            QtAds.CDockManager.eConfigFlag.HideSingleCentralWidgetTitleBar, False
        )
        QtAds.CDockManager.setConfigFlag(
            QtAds.CDockManager.eConfigFlag.DockAreaHasCloseButton, False
        )
        QtAds.CDockManager.setConfigFlag(
            QtAds.CDockManager.eConfigFlag.DockAreaHasTabsMenuButton, False
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName("EditorStack")
        self._stack.setStyleSheet(
            f"QStackedWidget#EditorStack {{ background-color: {Colors.EDITOR_BG}; }}"
        )
        layout.addWidget(self._stack)

        # Page 0: Welcome
        self._welcome_page = self._create_welcome_page()
        self._stack.addWidget(self._welcome_page)

        # Page 1: Dock manager
        self._dock_manager = QtAds.CDockManager(self._stack)
        self._dock_manager.setStyleSheet(
            f"background-color: {Colors.EDITOR_BG};"
        )
        self._stack.addWidget(self._dock_manager)

        # file_path -> (dock, editor, minimap)
        self._open_files: dict[str, tuple] = {}
        self._active_file: str | None = None
        self._minimap_visible = True

        self._stack.setCurrentIndex(0)

    # ── Public API ────────────────────────────────────────────────────────────

    def open_file(self, file_path: str):
        """Open a file in its own dock area. Focus it if already open."""
        if not os.path.isfile(file_path):
            return

        if file_path in self._open_files:
            self._activate(file_path)
            return

        content = self._load_content(file_path)
        relative_path = self._make_relative_path(file_path)

        editor_widget = QWidget()
        main_layout = QVBoxLayout(editor_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        breadcrumb = BreadcrumbBar()
        workspace_root = os.getcwd()
        breadcrumb.set_file_path(file_path, workspace_root)
        breadcrumb.setCursor(Qt.PointingHandCursor)

        editor_layout = QHBoxLayout()
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        editor = CodeEditor()
        editor.setPlainText(content)
        editor.set_syntax_language(file_path)

        minimap = Minimap(editor=editor)
        minimap.setVisible(self._minimap_visible)
        minimap.setFixedWidth(100)

        editor.verticalScrollBar().valueChanged.connect(minimap.update_minimap)
        editor.textChanged.connect(minimap.update_minimap)

        editor_layout.addWidget(editor, 1)
        editor_layout.addWidget(minimap)

        main_layout.addWidget(breadcrumb)
        main_layout.addLayout(editor_layout, 1)

        dock = QtAds.CDockWidget(relative_path)
        dock.setWidget(editor_widget)
        dock.setFeature(QtAds.CDockWidget.CustomCloseHandling, True)
        dock.setFeature(QtAds.CDockWidget.DockWidgetClosable, True)
        dock.setFeature(QtAds.CDockWidget.DockWidgetMovable, True)
        dock.setFeature(QtAds.CDockWidget.DockWidgetFloatable, True)
        dock.setProperty("_file_path", file_path)
        dock.closeRequested.connect(lambda: self._on_dock_close_requested(dock))
        dock.topLevelChanged.connect(
            lambda floating, fp=file_path: self._on_dock_top_level_changed(fp, floating)
        )
        breadcrumb.double_clicked.connect(
            lambda d=dock, mgr=self._dock_manager: (
                d.setFloating() if not d.isFloating()
                else mgr.addDockWidget(QtAds.DockWidgetArea.CenterDockWidgetArea, d)
            )
        )

        self._open_files[file_path] = (dock, editor, minimap)

        if self._stack.currentIndex() == 0:
            self._stack.setCurrentIndex(1)
            QApplication.processEvents()

        self._dock_manager.addDockWidget(
            QtAds.DockWidgetArea.CenterDockWidgetArea, dock
        )

        self._switch_to(file_path)
        self._active_file = file_path
        editor.setFocus()
        self._hide_title_bars()
        self.tabs_changed.emit()

    def close_file(self, file_path: str):
        """Close a file and remove its dock."""
        entry = self._open_files.pop(file_path, None)
        if entry is None:
            return
        dock, _editor, _minimap = entry
        dock.closeDockWidget()
        dock.deleteLater()

        if not self._open_files:
            self._active_file = None
            self._stack.setCurrentIndex(0)
        elif file_path == self._active_file:
            self._active_file = None
            next_file = next(iter(self._open_files.keys()))
            self._activate(next_file)
        self.tabs_changed.emit()

    def close_current_file(self):
        if self._active_file and self._active_file in self._open_files:
            self._on_dock_close_requested(self._open_files[self._active_file][0])

    def toggle_minimap(self, visible: bool = None):
        if visible is None:
            visible = not self._minimap_visible
        self._minimap_visible = visible
        for _dock, _editor, minimap in self._open_files.values():
            minimap.setVisible(visible)

    def toggle_render_whitespace(self):
        if self._active_file and self._active_file in self._open_files:
            self._open_files[self._active_file][1].toggle_whitespace_visibility()

    def whitespace_visible(self) -> bool:
        if self._active_file and self._active_file in self._open_files:
            return self._open_files[self._active_file][1].whitespace_visible()
        return False

    def current_editor(self) -> CodeEditor | None:
        if self._active_file and self._active_file in self._open_files:
            return self._open_files[self._active_file][1]
        return None

    def get_tab_list(self) -> list[tuple]:
        result = []
        for file_path, (_dock, _editor, _minimap) in self._open_files.items():
            file_name = os.path.basename(file_path)
            is_active = (file_path == self._active_file)
            result.append((file_path, file_name, is_active))
        return result

    def activate_tab(self, file_path: str):
        if file_path in self._open_files and file_path != self._active_file:
            self._activate(file_path)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _switch_to(self, file_path: str):
        """Make *file_path* the current tab in the center dock area."""
        dock, _editor, _minimap = self._open_files[file_path]
        # Ensure every non-floating dock is visible (no toggleView(False)).
        for _fp, (_dock, _ed, _mm) in self._open_files.items():
            if not _dock.isFloating():
                _dock.toggleView(True)
        # Switch the active tab.
        area = dock.dockAreaWidget()
        if area is not None:
            area.setCurrentDockWidget(dock)
            # Hide tab bar and title bar — breadcrumb serves as the header.
            tb = area.findChild(QTabBar)
            if tb is not None:
                tb.hide()
            title_bar = area.titleBar()
            if title_bar is not None:
                title_bar.hide()

    def _activate(self, file_path: str):
        """Bring the given file to the front."""
        if file_path not in self._open_files:
            return
        self._switch_to(file_path)
        self._active_file = file_path
        _dock, editor, _minimap = self._open_files[file_path]
        editor.setFocus()
        self._hide_title_bars()
        self.tabs_changed.emit()

    def _load_content(self, file_path: str) -> str:
        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                if file_size > MAX_FILE_SIZE:
                    content = f.read(MAX_FILE_SIZE)
                    content += (
                        f"\n\n... [File truncated: "
                        f"{file_size / (1024 * 1024):.1f} MB total]"
                    )
                    return content
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    def _on_dock_top_level_changed(self, file_path: str, floating: bool):
        if floating:
            if file_path == self._active_file:
                self._active_file = None
                remaining = [fp for fp in self._open_files if fp != file_path]
                if remaining:
                    self._activate(remaining[0])
                else:
                    self._stack.setCurrentIndex(0)
        else:
            # Re-docked
            self._activate(file_path)

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {Colors.EDITOR_BG};")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Sea Serpent")
        title.setStyleSheet(f"""
            font-size: 32px; font-weight: 300; color: {Colors.TEXT_SECONDARY};
            background: transparent;
        """)
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "PySide6 Desktop Client\n\n"
            "Open a file from the Explorer to start editing"
        )
        subtitle.setStyleSheet(f"""
            font-size: 14px; color: {Colors.TEXT_DISABLED};
            background: transparent;
        """)
        subtitle.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(subtitle)
        return page

    def _hide_title_bars(self):
        for _dock, _editor, _minimap in self._open_files.values():
            area = _dock.dockAreaWidget()
            if area is not None:
                tb = area.titleBar()
                if tb is not None and tb.isVisible():
                    tb.hide()

    def _make_relative_path(self, file_path: str) -> str:
        try:
            cwd = os.getcwd()
            if file_path.startswith(cwd):
                return os.path.relpath(file_path, cwd)
        except Exception:
            pass
        return file_path

    def _on_dock_close_requested(self, dock: QtAds.CDockWidget):
        file_path = dock.property("_file_path")
        if file_path:
            self.file_closed.emit(file_path)
