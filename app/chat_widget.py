"""
Chat widget — Copilot-style AI agent chat panel for the right sidebar.

Layout mirrors the VS Code Copilot Chat structure (from microsoft/vscode):
  src/vs/workbench/contrib/chat/browser/widget/chatWidget.ts
  src/vs/workbench/contrib/chat/browser/widget/input/chatInputPart.ts

CSS class hierarchy reference:
  .interactive-input-part
    .chat-input-container
      .chat-editor-container   (text input)
      .chat-input-toolbars
        .chat-execute-toolbar   (mode selector + model picker + send)
    .chat-attachments-container (context chips)
"""

from PySide6.QtCore import Qt, Signal, QByteArray, QTimer, QEvent
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QScrollArea, QFrame,
    QTextEdit, QApplication, QStackedWidget,
)

from .theme import Colors, ICONS


def _svg_icon(key: str, color: str = "#cccccc", size: int = 16) -> QIcon:
    """Build a QIcon from the ICONS dict, tinted to the given color."""
    svg = ICONS.get(key, "")
    if not svg:
        return QIcon()
    tinted = svg.replace('fill="#cccccc"', f'fill="{color}"')
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray(tinted.encode("utf-8")))
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
    return QIcon(pixmap)


# ── Compact SVG icons for chat toolbar buttons ─────────────────────────────

ICON_ATTACH = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M9.14645 1.14645C9.34171 0.951184 9.65829 0.951184 9.85355 1.14645L13.8536 '
    '5.14645C14.0488 5.34171 14.0488 5.65829 13.8536 5.85355L5.85355 13.8536C5.53857 '
    '14.1685 5.03857 14.1685 4.72355 13.8536L2.14645 11.2764C1.83147 10.9614 1.83147 '
    '10.4614 2.14645 10.1464L10.1464 2.14645C10.3201 1.97288 10.5904 1.95362 10.7866 '
    '2.0883L10.8536 2.14645C11.0488 2.34171 11.0488 2.65829 10.8536 2.85355L3.20711 '
    '10.5L5.5 12.7929L13.1464 5.14645L10.5 2.5L9.14645 3.85355C8.95118 4.04882 8.63462 '
    '4.04882 8.43934 3.85355C8.24408 3.65829 8.24408 3.34171 8.43934 3.14645L9.14645 '
    '1.14645Z" fill="#cccccc"/>'
    '</svg>'
)

ICON_SEND = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M15.854 8.354L1.854 15.354C1.658 15.452 1.428 15.42 1.268 15.268C1.108 15.116 '
    '1.06 14.888 1.146 14.688L3.5 9.5L1.146 4.312C1.06 4.112 1.108 3.884 1.268 3.732C1.428 '
    '3.58 1.658 3.548 1.854 3.646L15.854 10.646C16.042 10.74 16.146 10.936 16.146 11.146C16.146 '
    '11.356 16.042 11.552 15.854 11.646L15.854 8.354ZM14.646 10.5L4.5 9.5L14.646 10.5ZM4.5 '
    '10.5L2.646 14.146L14.646 10.5H4.5ZM14.646 4.5L2.646 0.854L4.5 4.5H14.646Z" fill="#cccccc"/>'
    '</svg>'
)

# Codicons: add, hubot (agent), settings-gear
ICON_ADD = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M8 1.5C8 1.22386 7.77614 1 7.5 1C7.22386 1 7 1.22386 7 1.5V7H1.5C1.22386 7 1 '
    '7.22386 1 7.5C1 7.77614 1.22386 8 1.5 8H7V13.5C7 13.7761 7.22386 14 7.5 14C7.77614 14 8 '
    '13.7761 8 13.5V8H13.5C13.7761 8 14 7.77614 14 7.5C14 7.22386 13.7761 7 13.5 7H8V1.5Z" '
    'fill="#cccccc"/>'
    '</svg>'
)

ICON_AGENT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M5.10198 3C4.92335 3 4.75829 3.0953 4.66897 3.25L2.07089 7.75C1.98158 7.9047 1.98158 '
    '8.0953 2.07089 8.25L4.5746 12.5866C4.72231 12.8424 4.99529 13 5.29071 13C5.65144 13 5.97055 '
    '12.7662 6.0792 12.4222L8.96823 3.27622C9.20821 2.51649 9.913 2 10.7097 2C11.3622 2 11.9651 '
    '2.34809 12.2914 2.91316L14.7953 7.25C15.0632 7.7141 15.0632 8.2859 14.7953 8.75L12.1972 '
    '13.25C11.9292 13.7141 11.434 14 10.8981 14H8.50155C8.22541 14 8.00155 13.7761 8.00155 '
    '13.5C8.00155 13.2239 8.22541 13 8.50155 13H10.8981C11.0768 13 11.2418 12.9047 11.3311 '
    '12.75L13.9292 8.25C14.0185 8.0953 14.0185 7.9047 13.9292 7.75L11.4254 3.41316C11.2777 '
    '3.1575 11.005 3 10.7097 3C10.3493 3 10.0304 3.23369 9.92179 3.57743L7.03276 12.7234C6.7927 '
    '13.4834 6.08769 14 5.29071 14C4.63803 14 4.03492 13.6518 3.70858 13.0866L1.20487 8.75C0.936918 '
    '8.2859 0.936919 7.7141 1.20487 7.25L3.80295 2.75C4.07089 2.2859 4.56609 2 5.10198 2H7.50155C7.77769 '
    '2 8.00155 2.22386 8.00155 2.5C8.00155 2.77614 7.77769 3 7.50155 3H5.10198Z" fill="#cccccc"/>'
    '</svg>'
)

ICON_NEW_CHAT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M14.56 7.44049C14.28 7.16049 13.9 7.00049 13.5 7.00049H13V4.00049C13 2.90049 12.1 '
    '2.00049 11 2.00049H3C1.9 2.00049 1 2.90049 1 4.00049V9.00049C1 10.1005 1.9 11.0005 3 '
    '11.0005V12.0005C3 12.8205 3.93 13.2905 4.59 12.8105L7 11.0505V11.5005C7 11.9005 7.16 '
    '12.2805 7.44 12.5605C7.72 12.8405 8.1 13.0005 8.5 13.0005H10.29L12.15 14.8505C12.19 '
    '14.9005 12.25 14.9405 12.31 14.9605C12.37 14.9905 12.43 15.0005 12.5 15.0005C12.57 '
    '15.0005 12.63 14.9905 12.69 14.9605C12.78 14.9205 12.86 14.8605 12.92 14.7805C12.97 '
    '14.7005 13 14.6005 13 14.5005V13.0005H13.5C13.9 13.0005 14.28 12.8405 14.56 12.5605C14.84 '
    '12.2805 15 11.9005 15 11.5005V8.50049C15 8.10049 14.84 7.72049 14.56 7.44049ZM6.75 '
    '10.0005L4 12.0005V10.0005H3C2.45 10.0005 2 9.55049 2 9.00049V4.00049C2 3.45049 2.45 '
    '3.00049 3 3.00049H11C11.55 3.00049 12 3.45049 12 4.00049V7.00049H8.5C8.1 7.00049 7.72 '
    '7.16049 7.44 7.44049C7.16 7.72049 7 8.10049 7 8.50049V10.0005H6.75ZM14 11.5005C14 11.6305 '
    '13.95 11.7605 13.85 11.8505C13.76 11.9505 13.63 12.0005 13.5 12.0005H12.5C12.37 12.0005 '
    '12.24 12.0505 12.15 12.1505C12.05 12.2405 12 12.3705 12 12.5005V13.2905L10.85 12.1505C10.81 '
    '12.1005 10.75 12.0605 10.69 12.0405C10.63 12.0105 10.57 12.0005 10.5 12.0005H8.5C8.37 '
    '12.0005 8.24 11.9505 8.15 11.8505C8.05 11.7605 8 11.6305 8 11.5005V8.50049C8 8.37049 '
    '8.05 8.24049 8.15 8.15049C8.24 8.05049 8.37 8.00049 8.5 8.00049H13.5C13.63 8.00049 13.76 '
    '8.05049 13.85 8.15049C13.95 8.24049 14 8.37049 14 8.50049V11.5005Z" fill="#cccccc"/>'
    '</svg>'
)

ICON_HISTORY = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M2 8C2 4.68629 4.68629 2 8 2C11.3137 2 14 4.68629 14 8C14 11.3137 11.3137 14 8 '
    '14C4.68629 14 2 11.3137 2 8ZM8 1C4.13401 1 1 4.13401 1 8C1 11.866 4.13401 15 8 15C11.866 '
    '15 15 11.866 15 8C15 4.13401 11.866 1 8 1ZM8 4.5C8 4.22386 7.77614 4 7.5 4C7.22386 4 7 '
    '4.22386 7 4.5V8.5C7 8.77614 7.22386 9 7.5 9H10.5C10.7761 9 11 8.77614 11 8.5C11 8.22386 '
    '10.7761 8 10.5 8H8V4.5Z" fill="#cccccc"/>'
    '</svg>'
)

ICON_SETTINGS = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M6 9.5C6.93191 9.5 7.71496 10.1374 7.93699 11L13.5 11C13.7761 11 14 11.2239 14 '
    '11.5C14 11.7455 13.8231 11.9496 13.5899 11.9919L13.5 12L7.93673 12.001C7.71435 12.8631 '
    '6.93155 13.5 6 13.5C5.06845 13.5 4.28565 12.8631 4.06327 12.001L2.5 12C2.22386 12 2 11.7761 '
    '2 11.5C2 11.2545 2.17688 11.0504 2.41012 11.0081L2.5 11L4.06301 11C4.28504 10.1374 5.06809 '
    '9.5 6 9.5ZM6 10.5C5.44772 10.5 5 10.9477 5 11.5C5 12.0523 5.44772 12.5 6 12.5C6.55228 '
    '12.5 7 12.0523 7 11.5C7 10.9477 6.55228 10.5 6 10.5ZM10 2.5C10.9319 2.5 11.715 3.13738 '
    '11.937 3.99998L13.5 4C13.7761 4 14 4.22386 14 4.5C14 4.74546 13.8231 4.94961 13.5899 '
    '4.99194L13.5 5L11.9367 5.00102C11.7144 5.86312 10.9316 6.5 10 6.5C9.06845 6.5 8.28565 '
    '5.86312 8.06327 5.00102L2.5 5C2.22386 5 2 4.77614 2 4.5C2 4.25454 2.17688 4.05039 2.41012 '
    '4.00806L2.5 4L8.06301 3.99998C8.28504 3.13738 9.06809 2.5 10 2.5ZM10 3.5C9.44772 3.5 9 '
    '3.94772 9 4.5C9 5.05228 9.44772 5.5 10 5.5C10.5523 5.5 11 5.05228 11 4.5C11 3.94772 '
    '10.5523 3.5 10 3.5Z" fill="#cccccc"/>'
    '</svg>'
)

ICON_ARROW_UP = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M13.854 7.14576L8.85401 2.14576C8.65901 1.95076 8.34201 1.95076 8.14701 2.14576L3.14601 '
    '7.14576C2.95101 7.34076 2.95101 7.65776 3.14601 7.85276C3.34101 8.04776 3.65801 8.04776 '
    '3.85301 7.85276L7.99901 3.70676V13.4998C7.99901 13.7758 8.22301 13.9998 8.49901 13.9998C8.77501 '
    '13.9998 8.99901 13.7758 8.99901 13.4998V3.70676L13.145 7.85276C13.243 7.95076 13.371 7.99876 '
    '13.499 7.99876C13.627 7.99876 13.755 7.94976 13.853 7.85276C14.048 7.65776 14.048 7.34076 '
    '13.853 7.14576H13.854Z" fill="#cccccc"/>'
    '</svg>'
)

ICON_CLOSE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M2.58859 2.71569L2.64645 2.64645C2.82001 2.47288 3.08944 2.4536 3.28431 '
    '2.58859L3.35355 2.64645L8 7.293L12.6464 2.64645C12.8417 2.45118 13.1583 2.45118 '
    '13.3536 2.64645C13.5488 2.84171 13.5488 3.15829 13.3536 3.35355L8.707 8L13.3536 '
    '12.6464C13.5271 12.82 13.5464 13.0894 13.4114 13.2843L13.3536 13.3536C13.18 13.5271 '
    '12.9106 13.5464 12.7157 13.4114L12.6464 13.3536L8 8.707L3.35355 13.3536C3.15829 '
    '13.5488 2.84171 13.5488 2.64645 13.3536C2.45118 13.1583 2.45118 12.8417 2.64645 '
    '12.6464L7.293 8L2.64645 3.35355C2.47288 3.17999 2.4536 2.91056 2.58859 2.71569L2.64645 '
    '2.64645L2.58859 2.71569Z" fill="#cccccc"/>'
    '</svg>'
)

ICON_AT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    '<path d="M8 1C4.134 1 1 4.134 1 8C1 11.866 4.134 15 8 15C8.27614 15 8.5 14.7761 8.5 '
    '14.5C8.5 14.2239 8.27614 14 8 14C4.691 14 2 11.309 2 8C2 4.691 4.691 2 8 2C11.309 '
    '2 14 4.691 14 8V8.5C14 9.052 13.552 9.5 13 9.5C12.448 9.5 12 9.052 12 8.5V8C12 5.791 '
    '10.209 4 8 4C5.791 4 4 5.791 4 8C4 10.209 5.791 12 8 12C9.104 12 10.104 11.552 10.828 '
    '10.828C11.24 11.24 11.81 11.5 12.45 11.5C13.856 11.5 15 10.356 15 8.9V8C15 4.134 11.866 '
    '1 8 1ZM8 11C6.343 11 5 9.657 5 8C5 6.343 6.343 5 8 5C9.657 5 11 6.343 11 8C11 9.657 '
    '9.657 11 8 11Z" fill="#cccccc"/>'
    '</svg>'
)


# ── Chat message widget ────────────────────────────────────────────────────

class ChatMessageWidget(QFrame):
    """A single chat bubble — either user or assistant."""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatMessage")
        self._role = role
        self.setFrameShape(QFrame.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)

        # Role label
        role_label = QLabel("You" if role == "user" else "Copilot")
        role_font = QFont()
        role_font.setPointSize(10)
        role_font.setBold(True)
        role_label.setFont(role_font)
        if role == "user":
            role_label.setStyleSheet(f"color: {Colors.ACCENT_BLUE}; background: transparent;")
        else:
            role_label.setStyleSheet(f"color: {Colors.ACCENT_GREEN}; background: transparent;")
        layout.addWidget(role_label)

        # Content
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.PlainText)
        content_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; background: transparent; font-size: 12px;"
        )
        layout.addWidget(content_label)

        if role == "user":
            self.setStyleSheet(
                f"QFrame#ChatMessage {{ background-color: {Colors.EDITOR_BG}; "
                f"border-left: 2px solid {Colors.ACCENT_BLUE}; margin: 2px 0px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#ChatMessage {{ background-color: {Colors.EDITOR_BG}; "
                f"border-left: 2px solid {Colors.ACCENT_GREEN}; margin: 2px 0px; }}"
            )

    def role(self) -> str:
        return self._role


# ── Context chip widget ────────────────────────────────────────────────────

class ContextChip(QFrame):
    """A pill-shaped chip showing an @-mentioned resource with a remove button."""

    removed = Signal(object)

    def __init__(self, text: str, icon_key: str = "file", parent=None):
        super().__init__(parent)
        self.setObjectName("ContextChip")
        self.setFrameShape(QFrame.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)

        # Icon
        icon_label = QLabel()
        icon_label.setPixmap(_svg_icon(icon_key, Colors.TEXT_SECONDARY, 12).pixmap(12, 12))
        icon_label.setFixedSize(12, 12)
        layout.addWidget(icon_label)

        # Text
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; background: transparent; font-size: 11px;"
        )
        layout.addWidget(label)

        # Remove button
        remove_btn = QPushButton()
        remove_btn.setIcon(_svg_icon("close", Colors.TEXT_SECONDARY, 10))
        remove_btn.setIconSize(QPixmap(10, 10).size())
        remove_btn.setFixedSize(14, 14)
        remove_btn.setFlat(True)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 2px; }"
        )
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)

        self.setStyleSheet(
            f"QFrame#ContextChip {{ "
            f"background-color: {Colors.INPUT_BG}; "
            f"border: 1px solid {Colors.BORDER}; "
            f"border-radius: 10px; "
            f"}}"
        )
        self.setFixedHeight(24)

    def text(self) -> str:
        return self._text if hasattr(self, '_text') else ""


# ── Main chat widget ───────────────────────────────────────────────────────

class ChatWidget(QWidget):
    """Copilot-style AI chat panel with conversation history and input box."""

    message_sent = Signal(str)  # User typed message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatWidget")

        self._context_files: list[str] = []
        self._chips: list[ContextChip] = []

        self._build_ui()
        self._add_welcome_message()

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Title bar (matches VS Code chat view header) ───────────────────
        title_bar = QWidget()
        title_bar.setObjectName("ChatTitleBar")
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet(f"""
            QWidget#ChatTitleBar {{
                background-color: {Colors.EDITOR_BG};
                border: none;
            }}
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 8, 0)
        title_layout.setSpacing(4)

        title_layout.addStretch()
        layout.addWidget(title_bar)

        # ── Stacked: Welcome / Conversation (fills all available space) ───
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {Colors.EDITOR_BG};")

        # Page 0: Welcome (vertically centered)
        self._welcome_page = QWidget()
        self._welcome_page.setStyleSheet("background: transparent;")
        self._welcome_layout = QVBoxLayout(self._welcome_page)
        self._welcome_layout.setContentsMargins(0, 0, 0, 0)
        self._welcome_layout.setSpacing(0)
        self._stack.addWidget(self._welcome_page)

        # Page 1: Conversation scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.EDITOR_BG}; border: none; }}"
        )
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._conv_container = QWidget()
        self._conv_container.setStyleSheet(f"background-color: {Colors.EDITOR_BG};")
        self._conv_layout = QVBoxLayout(self._conv_container)
        self._conv_layout.setContentsMargins(0, 0, 0, 0)
        self._conv_layout.setSpacing(0)
        self._conv_layout.addStretch(1)

        scroll_area.setWidget(self._conv_container)
        self._scroll_area = scroll_area
        self._stack.addWidget(scroll_area)

        # Start on welcome page
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, 1)

        # ── Input container (matches .interactive-input-part) ──────────────
        input_container = QWidget()
        input_container.setObjectName("ChatInputContainer")
        input_container.setStyleSheet(f"""
            QWidget#ChatInputContainer {{
                background-color: {Colors.EDITOR_BG};
                border: none;
            }}
        """)
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(12, 12, 12, 12)
        input_layout.setSpacing(6)

        # Context chips (.chat-attachments-container)
        self.chips_area = QWidget()
        self.chips_area.setVisible(False)
        chips_layout = QHBoxLayout(self.chips_area)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(4)
        chips_layout.addStretch()
        self._chips_layout = chips_layout
        input_layout.addWidget(self.chips_area)

        # ── Bordered input frame (wraps text input + toolbar) ──────────────
        self._input_frame = QFrame()
        self._input_frame.setObjectName("ChatInputFrame")
        self._input_frame.setStyleSheet(f"""
            QFrame#ChatInputFrame {{
                background-color: {Colors.EDITOR_BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        frame_layout = QVBoxLayout(self._input_frame)
        frame_layout.setContentsMargins(4, 4, 4, 4)
        frame_layout.setSpacing(2)

        # Text input (.chat-editor-container)
        self.text_input = QPlainTextEdit()
        self.text_input.setObjectName("ChatInput")
        self.text_input.setPlaceholderText("Write a message...")
        self.text_input.setMinimumHeight(38)
        self.text_input.setMaximumHeight(200)
        self.text_input.setFixedHeight(38)
        self.text_input.setStyleSheet(f"""
            QPlainTextEdit#ChatInput {{
                background-color: {Colors.EDITOR_BG};
                color: {Colors.TEXT_PRIMARY};
                border: none;
                padding: 4px 8px;
                font-size: 13px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
        """)
        self.text_input.textChanged.connect(self._on_text_changed)
        self.text_input.installEventFilter(self)
        frame_layout.addWidget(self.text_input)

        # ── Bottom toolbar: [add] [agent] [new-chat] [history] [settings] --- [arrow-up] ──
        action_bar = QWidget()
        action_bar.setStyleSheet("background: transparent;")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(4, 0, 4, 2)
        action_layout.setSpacing(4)

        # Add button
        add_btn = QPushButton()
        add_btn.setIcon(self._codicon_icon(ICON_ADD))
        add_btn.setIconSize(QPixmap(16, 16).size())
        add_btn.setToolTip("Add")
        add_btn.setFixedSize(26, 26)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFlat(True)
        add_btn.setStyleSheet(self._toolbar_btn_style())
        action_layout.addWidget(add_btn)

        # Agent button
        agent_btn = QPushButton()
        agent_btn.setIcon(self._codicon_icon(ICON_AGENT))
        agent_btn.setIconSize(QPixmap(16, 16).size())
        agent_btn.setToolTip("Agent")
        agent_btn.setFixedSize(26, 26)
        agent_btn.setCursor(Qt.PointingHandCursor)
        agent_btn.setFlat(True)
        agent_btn.setStyleSheet(self._toolbar_btn_style())
        action_layout.addWidget(agent_btn)

        # New Chat button
        new_chat_btn = QPushButton()
        new_chat_btn.setIcon(self._codicon_icon(ICON_NEW_CHAT))
        new_chat_btn.setIconSize(QPixmap(16, 16).size())
        new_chat_btn.setToolTip("New Chat")
        new_chat_btn.setFixedSize(26, 26)
        new_chat_btn.setCursor(Qt.PointingHandCursor)
        new_chat_btn.setFlat(True)
        new_chat_btn.setStyleSheet(self._toolbar_btn_style())
        new_chat_btn.clicked.connect(self._clear_chat)
        action_layout.addWidget(new_chat_btn)

        # Chat History button
        history_btn = QPushButton()
        history_btn.setIcon(self._codicon_icon(ICON_HISTORY))
        history_btn.setIconSize(QPixmap(16, 16).size())
        history_btn.setToolTip("Chat History")
        history_btn.setFixedSize(26, 26)
        history_btn.setCursor(Qt.PointingHandCursor)
        history_btn.setFlat(True)
        history_btn.setStyleSheet(self._toolbar_btn_style())
        action_layout.addWidget(history_btn)

        # Settings button
        settings_btn = QPushButton()
        settings_btn.setIcon(self._codicon_icon(ICON_SETTINGS))
        settings_btn.setIconSize(QPixmap(16, 16).size())
        settings_btn.setToolTip("Settings")
        settings_btn.setFixedSize(26, 26)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setFlat(True)
        settings_btn.setStyleSheet(self._toolbar_btn_style())
        action_layout.addWidget(settings_btn)

        action_layout.addStretch()

        # Arrow up (send) button — right aligned
        self.send_btn = QPushButton()
        self.send_btn.setIcon(self._codicon_icon(ICON_ARROW_UP))
        self.send_btn.setIconSize(QPixmap(16, 16).size())
        self.send_btn.setToolTip("Send (Enter)")
        self.send_btn.setFixedSize(26, 26)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setFlat(True)
        self.send_btn.setStyleSheet(self._toolbar_btn_style())
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._send_message)
        action_layout.addWidget(self.send_btn)

        frame_layout.addWidget(action_bar)
        input_layout.addWidget(self._input_frame)
        layout.addWidget(input_container)

    # ── Title bar button helper ────────────────────────────────────────────

    def _make_title_btn(self, svg: str, tooltip: str) -> QPushButton:
        btn = QPushButton()
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(svg.encode("utf-8")))
        btn.setIcon(QIcon(pixmap))
        btn.setIconSize(QPixmap(14, 14).size())
        btn.setFixedSize(24, 24)
        btn.setFlat(True)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
        )
        return btn

    def _codicon_icon(self, svg: str) -> QIcon:
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(svg.encode("utf-8")))
        return QIcon(pixmap)

    def _toolbar_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Colors.LIST_HOVER};
            }}
        """

    # ── Combo box style ────────────────────────────────────────────────────

    def _combo_style(self) -> str:
        """VS Code-style toolbar dropdown — compact, subtle border, dark theme."""
        return f"""
            QComboBox {{
                background-color: transparent;
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 3px 20px 3px 8px;
                font-size: 11px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                background-color: {Colors.LIST_HOVER};
                border-color: {Colors.BORDER};
            }}
            QComboBox:pressed {{
                background-color: {Colors.LIST_ACTIVE};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 16px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.DROPDOWN_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 4px 0px;
                selection-background-color: {Colors.LIST_ACTIVE};
                selection-color: {Colors.TEXT_PRIMARY};
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 12px;
                min-height: 22px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {Colors.LIST_HOVER};
            }}
        """

    # ── Message handling ───────────────────────────────────────────────────

    def _on_text_changed(self):
        text = self.text_input.toPlainText().strip()

        # Auto-resize height between 38px and 200px max.
        # When empty, force 38px — document size can be unreliable during init.
        if text:
            doc_height = int(self.text_input.document().size().height()) + 16
            new_height = max(38, min(doc_height, 200))
        else:
            new_height = 38
        if new_height != self.text_input.height():
            self.text_input.setFixedHeight(new_height)

        self.send_btn.setEnabled(len(text) > 0)

    def eventFilter(self, obj, event):
        """Enter to send (without Shift), Shift+Enter for newline."""
        if obj is self.text_input:
            if event.type() == QKeyEvent.KeyPress:
                key = event.key()
                modifiers = event.modifiers()
                if key == Qt.Key_Return or key == Qt.Key_Enter:
                    if not (modifiers & Qt.ShiftModifier):
                        self._send_message()
                        return True
            elif event.type() == QEvent.FocusIn:
                self._input_frame.setStyleSheet(f"""
                    QFrame#ChatInputFrame {{
                        background-color: {Colors.EDITOR_BG};
                        border: 1px solid {Colors.ACCENT};
                        border-radius: 8px;
                    }}
                """)
            elif event.type() == QEvent.FocusOut:
                self._input_frame.setStyleSheet(f"""
                    QFrame#ChatInputFrame {{
                        background-color: {Colors.EDITOR_BG};
                        border: 1px solid {Colors.BORDER};
                        border-radius: 8px;
                    }}
                """)
        return super().eventFilter(obj, event)

    def _send_message(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            return

        self.message_sent.emit(text)

        # Switch from welcome to conversation on first message
        self._switch_to_conversation()

        # Add user message
        self._add_message("user", text)

        # Clear input
        self.text_input.clear()
        self.text_input.setFixedHeight(38)

        # Simulate AI response
        QTimer.singleShot(600, lambda: self._simulate_response(text))

    def _simulate_response(self, user_text: str):
        """Demo: simulate a brief assistant response."""
        import random
        responses = [
            "I see you're asking about `{}`. How can I help with that?",
            "Let me help you with `{}`. What would you like me to do?",
            "I can assist with `{}`. Could you provide more details?",
            "Good question! Regarding `{}`, here's what I can do: I can help you write, refactor, explain, or debug code.",
        ]
        resp = random.choice(responses).format(user_text[:40])
        self._add_message("assistant", resp)

    def _add_message(self, role: str, content: str):
        msg = ChatMessageWidget(role, content)
        # Insert before the stretch
        self._conv_layout.insertWidget(self._conv_layout.count() - 1, msg)
        # Scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        vs = self._scroll_area.verticalScrollBar()
        vs.setValue(vs.maximum())

    def _add_welcome_message(self):
        """Clear all welcome page content."""
        while self._welcome_layout.count():
            item = self._welcome_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_chat(self):
        """Remove all messages and show the welcome again."""
        while self._conv_layout.count() > 1:
            item = self._conv_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_welcome_message()
        self._stack.setCurrentIndex(0)

    def _switch_to_conversation(self):
        """Switch from welcome page to conversation view."""
        self._stack.setCurrentIndex(1)

    # ── Context chips ──────────────────────────────────────────────────────

    def add_context(self, label: str, icon_key: str = "file"):
        """Add a context chip (e.g., file, folder)."""
        self._context_files.append(label)
        chip = ContextChip(label, icon_key)
        chip.removed.connect(self._remove_chip)
        self._chips.append(chip)
        # Insert before the stretch spacer
        self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
        self.chips_area.setVisible(True)

    def _remove_chip(self, chip: ContextChip):
        self._chips.remove(chip)
        chip.deleteLater()
        if not self._chips:
            self.chips_area.setVisible(False)

    def _add_context_demo(self):
        """Demo: simulate adding a file as context."""
        import os
        demo_files = ["app/main_window.py", "app/chat_widget.py", "app/theme.py", "app/sidebar.py"]
        for f in demo_files[:1]:  # Add just one for demo
            if f not in self._context_files:
                self.add_context(f, "file")
                break


# ── Thin wrapper to match existing RightSidebar API ────────────────────────

class ChatSidebarContainer(QWidget):
    """Container that holds the ChatWidget inside the right sidebar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatSidebarContainer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.chat = ChatWidget()
        layout.addWidget(self.chat)
