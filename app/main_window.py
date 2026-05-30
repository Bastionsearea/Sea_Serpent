"""
Main window – assembles all components into the final VSCode-like layout.

Layout structure:
┌────────────────────────────────────────────────────────────────────┐
│                  Title Bar                                         │
├────┬────────┬──────────────────────────────────────┬──────┬────────┤
│    │        │                                      │      │        │
│ Act│ Sidebar│                     Editor Area      │Mini- │ (Panel)│
│ivit│        │                                      │map   │        │
│y   │        │                                      │      │        │
│ Bar│        │                                      │      │        │
│    │        │                                      │      │        │
│    │        ├──────────────────────────────────────┴──────┴────────┤
│    │        │ Panel (Terminal / Problems / Output / Debug)         │
└────┴────────┴──────────────────────────────────────────────────────┘
"""

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QApplication, QMessageBox, QFrame
)

from .theme import Colors, get_global_stylesheet
from .title_bar import TitleBar
from .activity_bar import ActivityBar
from .sidebar import Sidebar, RightSidebar
from .dock_editor_manager import DockEditorManager
from .panel import Panel
# Note: minimap is integrated inside dock editor widgets


class VSCodiumWindow(QMainWindow):
    """Main application window that integrates all VSCode-like components."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sea Serpent")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(800, 500)

        # Default geometry — centered on screen
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 1400, 900
        self.setGeometry((screen.width() - w) // 2, (screen.height() - h) // 2, w, h)

        # Apply global theme
        self.setStyleSheet(get_global_stylesheet())

        # Central widget
        central = QWidget()
        central.setAutoFillBackground(True)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 1. Title Bar ────────────────────────────────────────────────────
        self.title_bar = TitleBar(self)
        self.title_bar.window_minimized.connect(self.showMinimized)
        self.title_bar.window_maximized.connect(self._do_maximize)
        self.title_bar.window_restored.connect(self._do_restore)
        self.title_bar.window_closed.connect(self.close)
        main_layout.addWidget(self.title_bar)

        # Title bar bottom separator (1px light gray line)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedHeight(1)
        separator.setStyleSheet("QFrame { color: #555555; }")
        main_layout.addWidget(separator)

        # ── 2. Main Content (Activity Bar + Splitter) ───────────────────────
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Activity Bar
        self.activity_bar = ActivityBar()
        self.activity_bar.view_changed.connect(self._on_view_changed)
        self.activity_bar.sidebar_toggle_requested.connect(self._toggle_sidebar)
        content_layout.addWidget(self.activity_bar)

        # Activity bar right separator (1px light gray line)
        ab_separator = QFrame()
        ab_separator.setFrameShape(QFrame.VLine)
        ab_separator.setFrameShadow(QFrame.Plain)
        ab_separator.setFixedWidth(1)
        ab_separator.setStyleSheet("QFrame { color: #555555; }")
        content_layout.addWidget(ab_separator)

        # Editor area (includes minimap integrated)
        self.editor_area = DockEditorManager()
        self.editor_area.file_closed.connect(self._on_file_closed)
        self.editor_area.tabs_changed.connect(self._update_title_tabs)
        self.title_bar.tab_selected.connect(self.editor_area.activate_tab)

        # Panel (hidden by default, controlled via View → Toggle Panel)
        self.panel = Panel()
        self.panel.panel_closed.connect(self._hide_panel)
        self.panel.maximize_toggled.connect(self._toggle_panel_maximize)
        self.panel.setVisible(False)

        # Vertical splitter: Editor | Panel
        self.editor_panel_splitter = QSplitter(Qt.Vertical)
        self.editor_panel_splitter.setChildrenCollapsible(False)
        self.editor_panel_splitter.setHandleWidth(1)
        self.editor_panel_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Colors.BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.FOCUS_BORDER};
            }}
        """)
        self.editor_panel_splitter.addWidget(self.editor_area)
        self.editor_panel_splitter.addWidget(self.panel)
        self.editor_panel_splitter.setSizes([700, 0])

        # Main splitter: Sidebar | Editor Column
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(1)
        self.main_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Colors.BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.FOCUS_BORDER};
            }}
        """)

        # Sidebar (left)
        self.sidebar = Sidebar()
        self.sidebar.file_selected.connect(self._on_file_selected)
        self.main_splitter.addWidget(self.sidebar)

        self.main_splitter.addWidget(self.editor_panel_splitter)

        # Right sidebar
        self.right_sidebar = RightSidebar()
        self.right_sidebar.setVisible(False)
        self.right_sidebar.close_requested.connect(self._hide_right_sidebar)
        self.main_splitter.addWidget(self.right_sidebar)

        # Set initial sizes: sidebar ~260px, editor takes the rest, right sidebar hidden
        self.main_splitter.setSizes([260, 1140, 0])

        content_layout.addWidget(self.main_splitter)

        main_layout.addWidget(content, 1)  # stretch factor = 1

        # ── Keyboard shortcuts ─────────────────────────────────────────────
        self._setup_shortcuts()

        # ── State ──────────────────────────────────────────────────────────
        self._panel_visible = False
        self._panel_maximized = False
        self._panel_normal_sizes = None  # saved splitter sizes when panel is not maximized
        self._right_sidebar_visible = False
        self._normal_geometry = None  # saved geometry for restoring from maximized

    # ── Event Overrides ──────────────────────────────────────────────────────

    def changeEvent(self, event):
        """Handle window state changes to sync title bar buttons."""
        if event.type() == QEvent.WindowStateChange:
            self.title_bar.set_maximized_state(self.isMaximized())
        super().changeEvent(event)

    def closeEvent(self, event):
        """Confirm close — uses non-blocking approach to avoid event loop issues."""
        reply = QMessageBox.question(
            self, "Exit",
            "Do you want to exit Sea Serpent?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
        super().closeEvent(event)

    # ── Window Maximize / Restore ────────────────────────────────────────────

    def _do_maximize(self):
        """Maximize using manual geometry — reliable for frameless windows.

        Qt's showMaximized() is unreliable with FramelessWindowHint on Windows:
        it sometimes fails to transition, causing the internal _is_maximized
        flag to desync and requiring two clicks to restore.
        """
        self._normal_geometry = self.geometry()
        screen = self.screen().availableGeometry()
        self.setGeometry(screen)
        self.title_bar.set_maximized_state(True)

    def _do_restore(self):
        """Restore to pre-maximized geometry — reliable for frameless windows."""
        if self._normal_geometry is not None:
            self.setGeometry(self._normal_geometry)
        else:
            # Fallback: centre a default-sized window on the current screen
            screen = self.screen().availableGeometry()
            w, h = 1400, 900
            self.setGeometry(
                (screen.width() - w) // 2,
                (screen.height() - h) // 2,
                w, h,
            )
        self.title_bar.set_maximized_state(False)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_view_changed(self, view_id: str, view_title: str):
        """Handle activity bar view change."""
        if view_id == "terminal":
            self._show_panel()
            self.panel._switch_to("terminal")
            return

        if view_id == "agent":
            self._show_chat()
            return

        if self.sidebar.is_collapsed():
            self.sidebar.expand()
            saved = getattr(self, '_saved_sidebar_width', self.sidebar.DEFAULT_WIDTH)
            total = self.main_splitter.width()
            self.main_splitter.setSizes([saved, total - saved])
        self.sidebar.show_view(view_id, view_title)

    def _update_title_tabs(self):
        """Sync the title bar tab dropdown with currently open editor tabs."""
        tabs = self.editor_area.get_tab_list()
        self.title_bar.set_tab_list(tabs)

    def _on_file_selected(self, file_path: str):
        """Handle file selection from the sidebar explorer."""
        self.editor_area.open_file(file_path)

    def _on_file_closed(self, file_path: str):
        """Handle file tab closure."""
        self.editor_area.close_file(file_path)

    def _on_menu_action(self, action: str):
        """Handle title bar menu actions."""
        if action == "view:toggle_sidebar":
            self._toggle_sidebar()
        elif action == "view:toggle_panel":
            self._toggle_panel()
        elif action == "view:toggle_minimap":
            self.editor_area.toggle_minimap()
        elif action == "view:toggle_right_sidebar":
            self._toggle_right_sidebar()
        elif action == "view:command_palette":
            self._show_command_palette()
        elif action == "file:exit":
            self.close()
        elif action == "view:toggle_render_whitespace":
            self.editor_area.toggle_render_whitespace()
        elif action == "view:toggle_activity_bar_size":
            self._toggle_activity_bar_size()
        elif action == "help:about":
            QMessageBox.about(
                self, "About Sea Serpent",
                "Sea Serpent v1.0.0\n\n"
                "A VSCode-inspired GUI Desktop Client built with PySide6.\n\n"
                "Reference design: VSCodium"
            )

    # ── Panel Management ─────────────────────────────────────────────────────

    def _show_panel(self):
        """Make the bottom panel visible."""
        self.panel.setVisible(True)
        total = self.editor_panel_splitter.height()
        panel_h = getattr(self, '_saved_panel_height', 200)
        self.editor_panel_splitter.setSizes([total - panel_h, panel_h])
        self._panel_visible = True

    def _hide_panel(self):
        """Hide the bottom panel."""
        self._saved_panel_height = self.panel.height()
        self.panel.setVisible(False)
        self._panel_visible = False
        self._panel_maximized = False
        self.panel.maximize_btn.setToolTip("Maximize Panel")

    def _toggle_panel(self):
        """Toggle the bottom panel visibility."""
        if self._panel_visible:
            self._hide_panel()
        else:
            self._show_panel()

    def _toggle_panel_maximize(self):
        """Toggle the panel between normal size and maximized (covers editor)."""
        if self._panel_maximized:
            # Restore to normal sizes
            self.editor_panel_splitter.setChildrenCollapsible(False)
            if self._panel_normal_sizes is not None:
                self.editor_panel_splitter.setSizes(self._panel_normal_sizes)
            else:
                total = self.editor_panel_splitter.height()
                panel_h = getattr(self, '_saved_panel_height', 200)
                self.editor_panel_splitter.setSizes([total - panel_h, panel_h])
            self._panel_maximized = False
            self.panel.maximize_btn.setToolTip("Maximize Panel")
        else:
            # Save current sizes before maximizing
            self._panel_normal_sizes = self.editor_panel_splitter.sizes()
            # Temporarily allow the editor to collapse so the panel can fill the area
            self.editor_panel_splitter.setChildrenCollapsible(True)
            total = self.editor_panel_splitter.height()
            self.editor_panel_splitter.setSizes([0, total])
            self._panel_maximized = True
            self.panel.maximize_btn.setToolTip("Restore Panel Size")

    def _toggle_sidebar(self):
        """Toggle the sidebar visibility by collapsing/expanding it."""
        if self.sidebar.is_collapsed():
            self.sidebar.expand()
            saved = getattr(self, '_saved_sidebar_width', self.sidebar.DEFAULT_WIDTH)
            total = self.main_splitter.width()
            self.main_splitter.setSizes([saved, total - saved])
        else:
            self._saved_sidebar_width = self.sidebar.width()
            self.sidebar.collapse()

    def _toggle_activity_bar_size(self):
        """Toggle the activity bar between compact and large size."""
        compact = not self.activity_bar.is_compact()
        self.activity_bar.set_compact_mode(compact)

    def _show_chat(self):
        """Open the right sidebar and switch to the chat view."""
        if self._right_sidebar_visible:
            self.right_sidebar.show_chat()
        else:
            self.right_sidebar.expand()
            self.right_sidebar.setVisible(True)
            self.right_sidebar.show_chat()
            sizes = self.main_splitter.sizes()
            saved = getattr(self, '_saved_right_sidebar_width', self.right_sidebar.DEFAULT_WIDTH)
            center = sizes[1] - saved if sizes[1] > saved else sizes[1] - saved
            if center < 200:
                center = sizes[1] // 2
                saved = sizes[1] - center
            self.main_splitter.setSizes([sizes[0], center, saved])
            self._right_sidebar_visible = True

    def _hide_right_sidebar(self):
        """Hide the right sidebar (called by close button)."""
        if self._right_sidebar_visible:
            self._saved_right_sidebar_width = self.right_sidebar.width()
            self.right_sidebar.setVisible(False)
            self.right_sidebar.collapse()
            self._right_sidebar_visible = False

    def _toggle_right_sidebar(self):
        """Toggle the right sidebar visibility."""
        if self._right_sidebar_visible:
            self._hide_right_sidebar()
        else:
            self.right_sidebar.expand()
            self.right_sidebar.setVisible(True)
            saved = getattr(self, '_saved_right_sidebar_width', self.right_sidebar.DEFAULT_WIDTH)
            sizes = self.main_splitter.sizes()
            # sizes: [left_sidebar, center, right_sidebar]
            center = sizes[1] - saved
            self.main_splitter.setSizes([sizes[0], center, saved])
            self._right_sidebar_visible = True

    def _show_command_palette(self):
        """Show a command palette dialog — reuses a cached instance."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget
        if not hasattr(self, '_cmd_palette_dialog') or self._cmd_palette_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Command Palette")
            dialog.setFixedSize(500, 350)
            dialog.setStyleSheet(f"""
                QDialog {{
                    background-color: {Colors.DROPDOWN_BG};
                    border: 1px solid {Colors.BORDER};
                }}
            """)
            layout = QVBoxLayout(dialog)
            search = QLineEdit()
            search.setPlaceholderText("Type a command to search...")
            search.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Colors.INPUT_BG};
                    color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.FOCUS_BORDER};
                    padding: 6px 12px;
                    font-size: 13px;
                    border-radius: 0px;
                }}
            """)
            commands = QListWidget()
            commands.setStyleSheet(f"""
                QListWidget {{
                    background-color: {Colors.DROPDOWN_BG};
                    color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    font-size: 13px;
                    outline: none;
                }}
                QListWidget::item {{
                    padding: 6px 12px;
                }}
                QListWidget::item:hover {{
                    background-color: {Colors.LIST_HOVER};
                }}
                QListWidget::item:selected {{
                    background-color: {Colors.LIST_ACTIVE};
                }}
            """)
            commands.addItems([
                "> View: Toggle Sidebar",
                "> View: Toggle Panel",
                "> View: Toggle Minimap",
                "> File: Open File",
                "> Edit: Select All",
                "> Help: About",
            ])
            layout.addWidget(search)
            layout.addWidget(commands)
            dialog.finished.connect(dialog.deleteLater)
            self._cmd_palette_dialog = dialog
        self._cmd_palette_dialog.show()

    def _setup_shortcuts(self):
        """Set up global keyboard shortcuts."""
        # Ctrl+Shift+P / F1: Command Palette
        cmd_palette = QAction("Command Palette", self)
        cmd_palette.triggered.connect(self._show_command_palette)
        cmd_palette.setShortcut("Ctrl+Shift+P")
        self.addAction(cmd_palette)

        # Ctrl+B: Toggle Sidebar
        toggle_sidebar = QAction("Toggle Sidebar", self)
        toggle_sidebar.triggered.connect(self._toggle_sidebar)
        toggle_sidebar.setShortcut("Ctrl+B")
        self.addAction(toggle_sidebar)

        # Ctrl+J: Toggle Panel
        toggle_panel = QAction("Toggle Panel", self)
        toggle_panel.triggered.connect(self._toggle_panel)
        toggle_panel.setShortcut("Ctrl+J")
        self.addAction(toggle_panel)

        # Ctrl+W: Close current tab
        close_tab = QAction("Close Tab", self)
        close_tab.triggered.connect(self.editor_area.close_current_file)
        close_tab.setShortcut("Ctrl+W")
        self.addAction(close_tab)
