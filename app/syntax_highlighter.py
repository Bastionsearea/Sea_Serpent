"""
Syntax highlighting via Pygments + QSyntaxHighlighter.

Supports Python, JavaScript, TypeScript, HTML, CSS, JSON, C/C++, Rust,
Go, Java, Ruby, Shell, YAML, XML, Markdown, and more — every
language Pygments knows about.
"""

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter
from pygments import lex
from pygments.lexers import (
    get_lexer_for_filename,
    get_lexer_by_name,
    guess_lexer,
)
from pygments.token import Token

from .theme import Colors

# ── VS Code Dark+ (Default Dark) exact syntax colours ────────────────────
# Sourced from the VS Code source: extensions/theme-defaults/themes/dark_plus.json

_VSCODE = {
    # Base
    "foreground":  "#D4D4D4",
    "comment":     "#6A9955",
    "keyword":     "#569CD6",
    "string":      "#CE9178",
    "number":      "#B5CEA8",
    "type":        "#4EC9B0",
    "function":    "#DCDCAA",
    "variable":    "#9CDCFE",
    "constant":    "#4FC1FF",
    "parameter":   "#9CDCFE",
    "operator":    "#D4D4D4",
    "punctuation": "#D4D4D4",
    "tag":         "#569CD6",
    "attribute":   "#9CDCFE",
    "decorator":   "#C586C0",
    "regex":       "#D16969",
    "escape":      "#D7BA7D",
    "error":       "#F44747",
    "heading":     "#569CD6",
    "bold":        "#DCDCAA",
    "deleted":     "#F44747",
    "inserted":    "#6A9955",
}

# Pygments token → VS Code colour + style flags
# In VS Code Dark+, only comments are italic; nothing is bold by default.
_TOKEN_DEFS: list[tuple[object, str, bool]] = [
    # (token_type, color_key, italic)

    # Comments
    (Token.Comment,                "comment",     True),
    (Token.Comment.Single,         "comment",     True),
    (Token.Comment.Multiline,      "comment",     True),
    (Token.Comment.Special,        "comment",     True),

    # Keywords (control flow, storage modifiers)
    (Token.Keyword,                "keyword",     False),
    (Token.Keyword.Constant,       "keyword",     False),
    (Token.Keyword.Declaration,    "keyword",     False),
    (Token.Keyword.Namespace,      "keyword",     False),
    (Token.Keyword.Reserved,       "keyword",     False),
    (Token.Keyword.Type,           "type",        False),

    # Strings
    (Token.String,                 "string",      False),
    (Token.String.Doc,             "comment",     True),
    (Token.String.Interpol,        "string",      False),
    (Token.String.Escape,          "escape",      False),
    (Token.String.Regex,           "regex",       False),
    (Token.String.Single,          "string",      False),
    (Token.String.Double,          "string",      False),
    (Token.String.Backtick,        "string",      False),
    (Token.Literal.String,         "string",      False),

    # Numbers
    (Token.Number,                 "number",      False),
    (Token.Number.Integer,         "number",      False),
    (Token.Number.Float,           "number",      False),
    (Token.Number.Hex,             "number",      False),
    (Token.Number.Oct,             "number",      False),
    (Token.Number.Bin,             "number",      False),

    # Names — functions, classes, builtins, decorators, variables
    (Token.Name.Function,          "function",    False),
    (Token.Name.Class,             "type",        False),
    (Token.Name.Builtin,           "function",    False),
    (Token.Name.Decorator,         "decorator",   False),
    (Token.Name.Exception,         "type",        False),
    (Token.Name.Variable,          "variable",    False),
    (Token.Name.Other,             "foreground",  False),
    (Token.Name.Attribute,         "attribute",   False),
    (Token.Name.Tag,               "tag",         False),
    (Token.Name.Label,             "decorator",   False),
    (Token.Name,                   "foreground",  False),

    # Constants
    (Token.Name.Builtin.Pseudo,    "constant",    False),
    (Token.Literal.Number,         "number",      False),

    # Operators & punctuation
    (Token.Operator,               "operator",    False),
    (Token.Operator.Word,          "keyword",     False),
    (Token.Punctuation,            "punctuation", False),

    # Markdown, diffs etc.
    (Token.Generic.Heading,        "heading",     False),
    (Token.Generic.Subheading,     "heading",     False),
    (Token.Generic.Emph,           "foreground",  True),
    (Token.Generic.Strong,         "bold",        False),
    (Token.Generic.Deleted,        "deleted",     False),
    (Token.Generic.Inserted,       "inserted",    False),
    (Token.Generic.Error,          "error",       False),
    (Token.Error,                  "error",       False),
]

# Build format table once at import time
_formats: dict[int, QTextCharFormat] = {}


def _build_formats() -> dict[int, QTextCharFormat]:
    fmts: dict[int, QTextCharFormat] = {}
    for token_type, color_key, italic in _TOKEN_DEFS:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(_VSCODE[color_key]))
        if italic:
            fmt.setFontItalic(True)
        fmts[token_type] = fmt
    # Default fallback
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(_VSCODE["foreground"]))
    fmts[Token.Text] = fmt
    return fmts


_FORMATS = _build_formats()


_FORMATS = _build_formats()


def _token_format(token_type: int) -> QTextCharFormat:
    """Return the closest-matching format for a Pygments token type."""
    t = token_type
    while t not in _FORMATS:
        parent = t.parent
        if parent == t:          # reached the root (Token)
            return _FORMATS[Token.Text]
        t = parent
    return _FORMATS[t]


# Language name → Pygments lexer alias / short-name mapping for
# extensions that Pygments's get_lexer_for_filename doesn't map to the
# display name we want.
_LANG_ALIASES = {
    "c": "c",
    "cpp": "cpp",
    "html": "html",
    "css": "css",
    "javascript": "js",
    "json": "json",
    "python": "python",
    "typescript": "ts",
    "rust": "rust",
    "go": "go",
    "java": "java",
    "ruby": "ruby",
    "shell": "bash",
    "yaml": "yaml",
    "xml": "xml",
    "markdown": "markdown",
    "sql": "sql",
    "kotlin": "kotlin",
    "swift": "swift",
    "php": "php",
    "scala": "scala",
    "perl": "perl",
    "lua": "lua",
    "dart": "dart",
    "r": "r",
}


class SyntaxHighlighter(QSyntaxHighlighter):
    """Pygments-powered syntax highlighter for any PySide6 QTextDocument."""

    def __init__(self, document, language: str = ""):
        super().__init__(document)
        self._lexer = None
        if language:
            self.set_language(language)

    def set_language(self, language: str):
        """Set the highlighting language by name or filename."""
        # Try by filename (e.g. "test.py") so get_lexer_for_filename can
        # match the extension; otherwise try by short alias.
        alias = _LANG_ALIASES.get(language.lower(), language.lower())
        try:
            self._lexer = get_lexer_by_name(alias, stripall=True)
        except Exception:
            try:
                self._lexer = get_lexer_for_filename(language)
            except Exception:
                self._lexer = None
        if self._lexer is not None:
            self.rehighlight()

    def set_language_by_filename(self, filename: str):
        """Detect language from a filename and apply highlighting."""
        try:
            self._lexer = get_lexer_for_filename(filename, stripall=True)
        except Exception:
            self._lexer = None
        if self._lexer is not None:
            self.rehighlight()

    def highlightBlock(self, text: str):
        if not text or self._lexer is None:
            return

        text_to_highlight = text[:8000]

        try:
            tokens = list(lex(text_to_highlight, self._lexer))
        except Exception:
            return

        if not tokens:
            return

        # Accumulate same-format runs to reduce setFormat calls.
        run_start = 0
        run_fmt = _token_format(tokens[0][0])
        pos = 0

        for token_type, token_value in tokens:
            fmt = _token_format(token_type)
            length = len(token_value)
            if length == 0:
                continue

            if fmt != run_fmt:
                self.setFormat(run_start, pos - run_start, run_fmt)
                run_start = pos
                run_fmt = fmt

            pos += length

        if pos > run_start:
            self.setFormat(run_start, pos - run_start, run_fmt)
