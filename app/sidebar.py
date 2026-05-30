"""
Sidebar – the collapsible panel next to the activity bar.

Contains views like Explorer (file tree), Search, Source Control, etc.
Each view is a stacked widget page.
"""

import os

from PySide6.QtCore import Qt, Signal, QByteArray, QTimer
from PySide6.QtGui import (
    QIcon, QPixmap, QColor, QPalette, QStandardItem, QStandardItemModel,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTreeView, QStackedWidget, QFrame, QHeaderView,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle,
    QProxyStyle, QCommonStyle,
)

from .theme import Colors, ICONS
from .chat_widget import ChatWidget


class SidebarTreeDelegate(QStyledItemDelegate):
    """Custom delegate that suppresses focus rect and uses dark selection colors."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        # Remove focus state to prevent the white focus rectangle
        opt.state &= ~QStyle.State_HasFocus
        # Use a dark selection background that matches the theme
        if opt.state & QStyle.State_Selected:
            painter.fillRect(opt.rect, QColor(Colors.LIST_HOVER))
        super().paint(painter, opt, index)


class SidebarTreeStyle(QProxyStyle):
    """Custom style that draws VSCode chevron icons for tree branch indicators."""

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorBranch and option.state & QStyle.State_Children:
            icon_key = "chevron_down" if option.state & QStyle.State_Open else "chevron_right"
            svg_str = ICONS.get(icon_key, "")
            if svg_str:
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray(svg_str.encode("utf-8")))
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(12, 12, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    x = option.rect.x() + (option.rect.width() - pixmap.width()) // 2 + 5
                    y = option.rect.y() + (option.rect.height() - pixmap.height()) // 2
                    painter.drawPixmap(x, y, pixmap)
                    return
        super().drawPrimitive(element, option, painter, widget)


class Sidebar(QWidget):
    """Collapsible sidebar showing contextual views (Explorer, Search, etc.)."""

    file_selected = Signal(str)        # Emitted with file path when a file is clicked
    view_changed = Signal(str)         # Emitted when the active view changes

    DEFAULT_WIDTH = 260
    MIN_WIDTH = 120

    # 目录加载上限 — 超过此数量不再展开子目录，防止 UI 冻结
    MAX_DIR_ENTRIES = 500
    # 搜索输入去抖延迟 (毫秒)
    SEARCH_DEBOUNCE_MS = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setMinimumWidth(self.MIN_WIDTH)

        self._view_titles: dict[str, str] = {}

        self._build_ui()
        self._setup_search_debounce()
        self._populate_explorer()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Search Bar (hidden by default, shown in search view) ────────────
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("SearchBar")
        self.search_bar.setPlaceholderText("Search files by name...")
        self.search_bar.setFixedHeight(28)
        self.search_bar.setVisible(False)
        self.search_bar.textChanged.connect(self._on_search_text_changed)

        search_wrapper = QWidget()
        search_wrapper.setStyleSheet("background-color: transparent;")
        search_wrapper.setVisible(False)
        search_wrapper_layout = QVBoxLayout(search_wrapper)
        search_wrapper_layout.setContentsMargins(10, 10, 10, 10)
        search_wrapper_layout.addWidget(self.search_bar)
        self._search_wrapper = search_wrapper
        layout.addWidget(search_wrapper)

        # ── Stacked Views ───────────────────────────────────────────────────
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setContentsMargins(0, 0, 0, 0)

        # Page 0: Home (placeholder)
        self.home_page = QWidget()
        self.home_page.setStyleSheet("background-color: transparent;")
        home_layout = QVBoxLayout(self.home_page)
        home_layout.setContentsMargins(16, 16, 16, 16)
        home_layout.setAlignment(Qt.AlignTop)
        home_label = QLabel("Home view")
        home_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        home_label.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(home_label)
        self.stacked_widget.addWidget(self.home_page)

        # Page 1: Explorer (file tree)
        self.explorer_page = QWidget()
        self.explorer_page.setStyleSheet("background-color: transparent;")
        explorer_layout = QVBoxLayout(self.explorer_page)
        explorer_layout.setContentsMargins(0, 0, 0, 0)
        explorer_layout.setSpacing(0)

        # Title bar
        explorer_title = QWidget()
        explorer_title.setStyleSheet("background-color: transparent;")
        explorer_title_layout = QHBoxLayout(explorer_title)
        explorer_title_layout.setContentsMargins(12, 8, 12, 8)
        explorer_title_label = QLabel("EXPLORER")
        explorer_title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY}; font-size: 11px; font-weight: 600;
            background: transparent;
        """)
        explorer_title_layout.addWidget(explorer_title_label)
        explorer_title_layout.addStretch()
        explorer_layout.addWidget(explorer_title)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(16)
        self.tree_view.setFrameShape(QFrame.NoFrame)
        self.tree_view.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree_view.setSelectionMode(QTreeView.SingleSelection)
        self.tree_view.setFocusPolicy(Qt.NoFocus)
        self.tree_view.setExpandsOnDoubleClick(True)
        self.tree_view.setItemDelegate(SidebarTreeDelegate(self.tree_view))
        self.tree_view.setStyle(SidebarTreeStyle(self.tree_view.style()))

        # Set a dark palette to prevent system highlight colors bleeding through
        palette = self.tree_view.palette()
        palette.setColor(QPalette.Highlight, QColor(Colors.LIST_HOVER))
        palette.setColor(QPalette.HighlightedText, QColor(Colors.TEXT_PRIMARY))
        self.tree_view.setPalette(palette)

        self.tree_view.clicked.connect(self._on_tree_clicked)

        self._tree_model = QStandardItemModel()
        self.tree_view.setModel(self._tree_model)
        explorer_layout.addWidget(self.tree_view)
        self.stacked_widget.addWidget(self.explorer_page)

        # Page 2: Search results (placeholder)
        self.search_page = QWidget()
        self.search_page.setStyleSheet("background-color: transparent;")
        search_layout = QVBoxLayout(self.search_page)
        search_layout.setContentsMargins(16, 16, 16, 16)
        search_layout.setAlignment(Qt.AlignTop)
        search_label = QLabel("Search results will appear here")
        search_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        search_label.setAlignment(Qt.AlignCenter)
        search_layout.addWidget(search_label)
        self.stacked_widget.addWidget(self.search_page)

        # Page 3: Source Control (placeholder)
        self.sc_page = QWidget()
        self.sc_page.setStyleSheet("background-color: transparent;")
        sc_layout = QVBoxLayout(self.sc_page)
        sc_layout.setContentsMargins(16, 16, 16, 16)
        sc_layout.setAlignment(Qt.AlignTop)
        sc_label = QLabel("Source control view")
        sc_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        sc_label.setAlignment(Qt.AlignCenter)
        sc_layout.addWidget(sc_label)
        self.stacked_widget.addWidget(self.sc_page)

        # Page 4: Run (placeholder)
        self.run_page = QWidget()
        self.run_page.setStyleSheet("background-color: transparent;")
        run_layout = QVBoxLayout(self.run_page)
        run_layout.setContentsMargins(16, 16, 16, 16)
        run_layout.setAlignment(Qt.AlignTop)
        run_label = QLabel("Run and Debug view")
        run_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        run_label.setAlignment(Qt.AlignCenter)
        run_layout.addWidget(run_label)
        self.stacked_widget.addWidget(self.run_page)

        # Page 5: Testing (placeholder)
        self.testing_page = QWidget()
        self.testing_page.setStyleSheet("background-color: transparent;")
        testing_layout = QVBoxLayout(self.testing_page)
        testing_layout.setContentsMargins(16, 16, 16, 16)
        testing_layout.setAlignment(Qt.AlignTop)
        testing_label = QLabel("Testing view")
        testing_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        testing_label.setAlignment(Qt.AlignCenter)
        testing_layout.addWidget(testing_label)
        self.stacked_widget.addWidget(self.testing_page)

        # Page 6: Extensions (placeholder)
        self.ext_page = QWidget()
        self.ext_page.setStyleSheet("background-color: transparent;")
        ext_layout = QVBoxLayout(self.ext_page)
        ext_layout.setContentsMargins(16, 16, 16, 16)
        ext_layout.setAlignment(Qt.AlignTop)
        ext_label = QLabel("Extensions view")
        ext_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        ext_label.setAlignment(Qt.AlignCenter)
        ext_layout.addWidget(ext_label)
        self.stacked_widget.addWidget(self.ext_page)

        # Page 7: Database (placeholder)
        self.db_page = QWidget()
        self.db_page.setStyleSheet("background-color: transparent;")
        db_layout = QVBoxLayout(self.db_page)
        db_layout.setContentsMargins(16, 16, 16, 16)
        db_layout.setAlignment(Qt.AlignTop)
        db_label = QLabel("Database view")
        db_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        db_label.setAlignment(Qt.AlignCenter)
        db_layout.addWidget(db_label)
        self.stacked_widget.addWidget(self.db_page)

        # Page 8: Terminal (placeholder)
        self.terminal_page = QWidget()
        self.terminal_page.setStyleSheet("background-color: transparent;")
        terminal_layout = QVBoxLayout(self.terminal_page)
        terminal_layout.setContentsMargins(16, 16, 16, 16)
        terminal_layout.setAlignment(Qt.AlignTop)
        terminal_label = QLabel("Terminal view")
        terminal_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background-color: transparent;")
        terminal_label.setAlignment(Qt.AlignCenter)
        terminal_layout.addWidget(terminal_label)
        self.stacked_widget.addWidget(self.terminal_page)

        # Page 9: AI Agent / Chat
        self._agent_page = ChatWidget()
        self._agent_page.setStyleSheet("background-color: transparent;")
        self._agent_page.message_sent.connect(self._on_agent_message)
        self.stacked_widget.addWidget(self._agent_page)


        layout.addWidget(self.stacked_widget)

    def _setup_search_debounce(self):
        """设置搜索输入去抖定时器，避免每次按键都遍历整个树模型."""
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(self.SEARCH_DEBOUNCE_MS)
        self._search_debounce_timer.timeout.connect(self._apply_search_filter)

    def _on_search_text_changed(self, text: str):
        """搜索文本变更时启动去抖定时器."""
        self._pending_filter_text = text
        self._search_debounce_timer.start()

    def _apply_search_filter(self):
        """在去抖延迟后真正执行过滤."""
        self._filter_tree(getattr(self, '_pending_filter_text', ''))

    # ── View Switching ──────────────────────────────────────────────────────

    def show_view(self, view_id: str, view_title: str):
        """Switch the sidebar to the given view."""
        self._view_titles[view_id] = view_title
        page_map = {
            "home": 0,
            "files": 1,
            "search": 2,
            "source_control": 3,
            "run": 4,
            "testing": 5,
            "extensions": 6,
            "database": 7,
            "terminal": 8,
            "agent": 9,
        }
        idx = page_map.get(view_id, 0)
        self.stacked_widget.setCurrentIndex(idx)

        # Show search bar only for search view
        self.search_bar.setVisible(True)
        self._search_wrapper.setVisible(view_id == "search")
        if view_id == "search":
            self.search_bar.setFocus()
            self.search_bar.clear()

        self.view_changed.emit(view_id)

    # ── File Explorer ───────────────────────────────────────────────────────

    def _on_agent_message(self, text: str):
        """Handle messages sent from the agent chat in the sidebar."""
        # Could be used to trigger editor actions based on chat
        pass

    def _populate_explorer(self):
        """Populate the file tree from the project root."""
        self._tree_model.clear()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._add_directory(self._tree_model.invisibleRootItem(), project_root)

    def _add_directory(self, parent_item: QStandardItem, dir_path: str):
        """向树模型中添加文件/文件夹条目，带数量上限保护."""
        try:
            entries = sorted(os.listdir(dir_path))
        except OSError:
            return 0

        ignore = {".git", "__pycache__", ".mypy_cache", ".pytest_cache",
                   ".vscode", ".idea", "node_modules", ".DS_Store", ".svn"}

        count = 0
        for entry in entries:
            if entry in ignore:
                continue
            if count >= self.MAX_DIR_ENTRIES:
                overflow = QStandardItem(f"... ({len(entries) - count} more entries)")
                overflow.setEditable(False)
                parent_item.appendRow(overflow)
                break

            full_path = os.path.join(dir_path, entry)
            try:
                is_dir = os.path.isdir(full_path)
            except OSError:
                continue

            item = QStandardItem(self._file_icon(is_dir), entry)
            item.setData(full_path, Qt.UserRole)
            item.setEditable(False)

            if is_dir:
                dummy = QStandardItem("")
                item.appendRow(dummy)
            else:
                item.setData(entry, Qt.UserRole + 1)

            parent_item.appendRow(item)
            count += 1

        return count

    def _file_icon(self, is_dir: bool) -> QIcon:
        """Return a VSCode-style icon for file/directory."""
        svg = ICONS["folder"] if is_dir else ICONS["file"]
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(svg.encode("utf-8")))
        if pixmap.isNull():
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
        return QIcon(pixmap)

    def _on_tree_clicked(self, index):
        """Handle a click on a tree item."""
        item = self._tree_model.itemFromIndex(index)
        if item is None:
            return
        path = item.data(Qt.UserRole)
        if path and os.path.isfile(path):
            self.file_selected.emit(path)
        elif path and os.path.isdir(path):
            # If it's a dir with a dummy child, replace with real children
            if item.rowCount() == 1 and item.child(0).text() == "":
                item.removeRow(0)
                count = self._add_directory(item, path)
                # If no children were added (empty dir, all ignored), put dummy back
                if count == 0:
                    dummy = QStandardItem("")
                    item.appendRow(dummy)

    def _filter_tree(self, text: str):
        """Filter the tree view based on search text."""
        # Simple visibility filter for the tree
        for row in range(self._tree_model.rowCount()):
            item = self._tree_model.item(row)
            self._set_item_visible_recursive(item, text)

    def _set_item_visible_recursive(self, item: QStandardItem, filter_text: str):
        """Recursively set visibility of tree items based on filter."""
        text_lower = filter_text.lower()
        name = item.text().lower()
        visible = not filter_text or text_lower in name

        for row in range(item.rowCount()):
            child = item.child(row)
            child_visible = self._set_item_visible_recursive(child, filter_text)
            visible = visible or child_visible

        # We can't directly hide rows in QStandardItemModel easily,
        # so for now just highlight matching items.
        # A QSortFilterProxyModel would be better for production.
        return visible

    # ── Collapse ────────────────────────────────────────────────────────────

    def expand(self):
        """Remove fixed-width collapse so sidebar can be resized."""
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMaximumWidth(16777215)

    def collapse(self):
        """Collapse sidebar to zero width."""
        self.setFixedWidth(0)

    def is_collapsed(self) -> bool:
        """Return True if the sidebar is currently collapsed."""
        return self.width() <= 10

    def _toggle_collapse(self):
        """Toggle sidebar collapse state."""
        if self.is_collapsed():
            self.expand()
        else:
            self.collapse()

    def refresh_tree(self):
        """Reload the file tree from disk."""
        self._populate_explorer()



class SidebarContainer(QWidget):
    """Wrapper around Sidebar that adds a thin resize handle on the right edge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarContainer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar(self)
        layout.addWidget(self.sidebar)


class RightSidebar(QWidget):
    """Right-side panel with Outline and AI Chat views via stacked widget."""

    DEFAULT_WIDTH = 260
    MIN_WIDTH = 240

    PAGE_OUTLINE = 0
    PAGE_CHAT = 1

    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightSidebar")
        self.setMinimumWidth(self.MIN_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab switcher bar
        self.tab_bar = QWidget()
        self.tab_bar.setObjectName("RightSidebarTabBar")
        self.tab_bar.setStyleSheet(f"""
            QWidget#RightSidebarTabBar {{
                background-color: {Colors.EDITOR_BG};
                border: none;
            }}
        """)
        tab_layout = QHBoxLayout(self.tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        self.outline_tab = QPushButton("OUTLINE")
        self.outline_tab.setCheckable(True)
        self.outline_tab.setChecked(True)
        self.outline_tab.setStyleSheet(self._tab_style())
        self.outline_tab.clicked.connect(lambda: self._switch_page(self.PAGE_OUTLINE))
        tab_layout.addWidget(self.outline_tab)

        self.chat_tab = QPushButton("CHAT")
        self.chat_tab.setCheckable(True)
        self.chat_tab.setStyleSheet(self._tab_style())
        self.chat_tab.clicked.connect(lambda: self._switch_page(self.PAGE_CHAT))
        tab_layout.addWidget(self.chat_tab)

        tab_layout.addStretch()

        # Close button (Chrome-style)
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(28, 28)
        close_pixmap = QPixmap()
        close_pixmap.loadFromData(QByteArray(ICONS["close"].encode("utf-8")))
        self.close_btn.setIcon(close_pixmap.scaled(12, 12, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.close_btn.setIconSize(close_pixmap.size())
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
            }
            QPushButton:hover {
                background: transparent;
            }
        """)
        self.close_btn.clicked.connect(self.close_requested.emit)
        tab_layout.addWidget(self.close_btn)

        layout.addWidget(self.tab_bar)

        # Stacked widget
        self.stacked = QStackedWidget()

        # Page 0: Outline (placeholder)
        outline_page = QWidget()
        outline_page.setStyleSheet("background-color: transparent;")
        outline_layout = QVBoxLayout(outline_page)
        outline_layout.setAlignment(Qt.AlignCenter)
        hint = QLabel("No symbols found in document")
        hint.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; font-size: 12px;"
        )
        hint.setAlignment(Qt.AlignCenter)
        outline_layout.addWidget(hint)
        self.stacked.addWidget(outline_page)

        # Page 1: Chat
        self._chat_widget = ChatWidget()
        self._chat_widget.setStyleSheet("background-color: transparent;")
        self.stacked.addWidget(self._chat_widget)

        layout.addWidget(self.stacked, 1)

    def _tab_style(self) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 6px 14px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                color: {Colors.TEXT_PRIMARY};
                border-bottom: 2px solid {Colors.ACCENT};
            }}
        """

    def _switch_page(self, page: int):
        self.stacked.setCurrentIndex(page)
        self.outline_tab.setChecked(page == self.PAGE_OUTLINE)
        self.chat_tab.setChecked(page == self.PAGE_CHAT)

    def show_chat(self):
        """Switch to the chat page."""
        self._switch_page(self.PAGE_CHAT)

    def show_outline(self):
        """Switch to the outline page."""
        self._switch_page(self.PAGE_OUTLINE)

    def chat_widget(self) -> ChatWidget:
        """Return the embedded chat widget."""
        return self._chat_widget

    def collapse(self):
        self.setFixedWidth(0)

    def expand(self):
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMaximumWidth(16777215)

    def is_collapsed(self) -> bool:
        return self.width() <= 10
