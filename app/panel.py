"""
Bottom panel – the area below the editor for terminals, problems, output, debug.

Mirrors VSCode's panel:
- Tab bar at the top (Terminal, Problems, Output, Debug Console)
- Stacked content area
- Resizeable
"""

from PySide6.QtCore import Qt, Signal, QByteArray
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QPlainTextEdit, QStackedWidget, QSizePolicy, QTreeWidget,
    QTreeWidgetItem, QFrame
)

from .theme import Colors, ICONS
from .terminal_widget import TerminalWidget


class PanelTab(QPushButton):
    """An individual panel tab button."""

    def __init__(self, title: str, panel_id: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("PanelTab")
        self.setCheckable(True)
        self.setFixedHeight(30)
        self._panel_id = panel_id
        self.setCursor(Qt.PointingHandCursor)


class Panel(QWidget):
    """Bottom panel with tabbed views (Terminal, Problems, Output, Debug)."""

    panel_closed = Signal()
    tab_changed = Signal(str)
    maximize_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setMinimumHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Tab Bar ─────────────────────────────────────────────────────────
        self.tab_bar = QWidget()
        self.tab_bar.setObjectName("PanelTabs")
        self.tab_bar.setFixedHeight(30)

        tab_layout = QHBoxLayout(self.tab_bar)
        tab_layout.setContentsMargins(0, 0, 4, 0)
        tab_layout.setSpacing(0)

        self._tabs_info = [
            ("TERMINAL", "terminal"),
            ("PROBLEMS", "problems"),
            ("OUTPUT", "output"),
            ("DEBUG CONSOLE", "debug_console"),
        ]

        self._tab_buttons: list[PanelTab] = []
        self._button_group = []

        for title, panel_id in self._tabs_info:
            btn = PanelTab(title, panel_id)
            btn.clicked.connect(lambda checked, pid=panel_id: self._switch_to(pid))
            self._tab_buttons.append(btn)
            tab_layout.addWidget(btn)

        # Spacer — pushes everything after to the right
        tab_layout.addStretch(1)

        # Panel label (shows status text)
        self.panel_label = QLabel("")
        self.panel_label.setStyleSheet(f"background: transparent; color: {Colors.TEXT_DISABLED}; font-size: 11px;")
        self.panel_label.setFixedHeight(30)
        tab_layout.addWidget(self.panel_label)

        # Maximize / restore button
        self.maximize_btn = QPushButton()
        self.maximize_btn.setFixedSize(28, 28)
        max_pixmap = QPixmap()
        max_pixmap.loadFromData(QByteArray(ICONS["panel_maximize"].encode("utf-8")))
        self.maximize_btn.setIcon(max_pixmap.scaled(12, 12, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.maximize_btn.setIconSize(max_pixmap.size())
        self.maximize_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
            }}
            QPushButton:hover {{
                background: transparent;
            }}
        """)
        self.maximize_btn.setToolTip("Maximize Panel")
        self.maximize_btn.clicked.connect(self._on_maximize_clicked)
        tab_layout.addWidget(self.maximize_btn)

        # Close button
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(28, 28)
        close_pixmap = QPixmap()
        close_pixmap.loadFromData(QByteArray(ICONS["close"].encode("utf-8")))
        self.close_btn.setIcon(close_pixmap.scaled(12, 12, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.close_btn.setIconSize(close_pixmap.size())
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
            }}
            QPushButton:hover {{
                background: transparent;
            }}
        """)
        self.close_btn.clicked.connect(self.panel_closed.emit)
        tab_layout.addWidget(self.close_btn)

        layout.addWidget(self.tab_bar)

        # ── Content Area ────────────────────────────────────────────────────
        self.stacked = QStackedWidget()

        # Page 0: Terminal — real shell via QProcess
        self.terminal_page = TerminalWidget()
        self.stacked.addWidget(self.terminal_page)

        # Page 1: Problems
        self.problems_page = QTreeWidget()
        self.problems_page.setObjectName("PanelProblems")
        self.problems_page.setHeaderLabels(["", "Description", "File", "Line"])
        self.problems_page.setColumnWidth(0, 20)
        self.problems_page.setColumnWidth(1, 400)
        self.problems_page.setColumnWidth(2, 200)
        self.problems_page.setColumnWidth(3, 60)
        self.problems_page.setRootIsDecorated(False)
        self.problems_page.setAlternatingRowColors(False)
        self.problems_page.setFrameShape(QFrame.NoFrame)
        self.problems_page.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {Colors.PANEL_BG};
                color: {Colors.TEXT_PRIMARY};
                border: none;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                padding: 2px 4px;
            }}
            QHeaderView::section {{
                background-color: {Colors.PANEL_TITLE_BG};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                padding: 4px;
                font-size: 11px;
                text-transform: uppercase;
            }}
        """)
        # Add a couple of sample problems
        self._add_sample_problems()
        self.stacked.addWidget(self.problems_page)

        # Page 2: Output
        self.output_page = QPlainTextEdit()
        self.output_page.setObjectName("PanelTextEdit")
        self.output_page.setReadOnly(True)
        self.output_page.setPlaceholderText("No output yet. Select an output channel.")
        self.stacked.addWidget(self.output_page)

        # Page 3: Debug Console
        self.debug_page = QPlainTextEdit()
        self.debug_page.setObjectName("PanelTextEdit")
        self.debug_page.setReadOnly(True)
        self.debug_page.setPlaceholderText("Debug console (simulated)")
        self.stacked.addWidget(self.debug_page)

        layout.addWidget(self.stacked)

        # Default selection
        self._current_id = "terminal"
        self._tab_buttons[0].setChecked(True)
        self.stacked.setCurrentIndex(0)

    def _switch_to(self, panel_id: str):
        """Switch to the given panel tab."""
        idx_map = {
            "terminal": 0, "problems": 1,
            "output": 2, "debug_console": 3
        }
        idx = idx_map.get(panel_id, 0)
        self.stacked.setCurrentIndex(idx)
        self._current_id = panel_id

        # Update tab button states
        for btn in self._tab_buttons:
            btn.setChecked(btn._panel_id == panel_id)

        self.tab_changed.emit(panel_id)

    def _on_maximize_clicked(self):
        """Emit signal so the main window can toggle panel maximized state."""
        self.maximize_toggled.emit()

    def _add_sample_problems(self):
        """Add sample problem items to problems panel."""
        problems = [
            ("warning", "Unused import: 'os'", "main.py", 1),
            ("warning", "Local variable 'x' is not used", "utils.py", 42),
            ("error", "Undefined name 'undefined_var'", "app.py", 15),
            ("info", "Line too long (89 > 79 characters)", "styles.py", 67),
        ]
        for ptype, desc, file, line in problems:
            icon = "⚠" if ptype == "warning" else "✕" if ptype == "error" else "ℹ"
            item = QTreeWidgetItem([icon, desc, file, str(line)])
            if ptype == "error":
                item.setForeground(0, Qt.red)
                item.setForeground(1, Qt.red)
            elif ptype == "warning":
                item.setForeground(0, QColor(Colors.ACCENT_YELLOW))
                item.setForeground(1, QColor(Colors.ACCENT_YELLOW))
            self.problems_page.addTopLevelItem(item)

    def append_output(self, text: str, panel: str = "terminal"):
        """Append text to one of the output panels."""
        if panel == "terminal":
            self.terminal_page.write_command(text)
        elif panel == "output":
            self.output_page.appendPlainText(text)
        elif panel == "debug":
            self.debug_page.appendPlainText(text)

    def set_panel_label(self, text: str):
        """Set the label text on the right side of the panel tab bar."""
        self.panel_label.setText(text)

    def current_panel(self) -> str:
        """Return the current panel id."""
        return self._current_id
