#!/usr/bin/env python3
"""
Sea Serpent – A VSCode-inspired GUI Desktop Client.

This is the entry point for the application. Run it with:

    python main.py

Requires PySide6 (pip install PySide6).
"""

import sys
import os
import logging
import traceback

from PySide6.QtCore import Qt, QCoreApplication, qInstallMessageHandler, QtMsgType
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

# Ensure the project root is on the path for direct execution
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.WARNING,
    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s',
)
logger = logging.getLogger(__name__)


def _qt_message_handler(mode, context, message):
    if mode == QtMsgType.QtFatalMsg:
        logger.critical("Qt fatal: %s (file=%s, line=%d)",
                        message, context.file, context.line)


def main():
    """Initialize and run the Sea Serpent application."""

    qInstallMessageHandler(_qt_message_handler)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Sea Serpent")
    app.setOrganizationName("Sea Serpent")

    sys.excepthook = lambda exc_type, exc_value, exc_tb: (
        logger.critical("Unhandled exception:\n%s",
                        ''.join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    )

    # Default font
    font = QFont("-apple-system, BlinkMacSystemFont, 'Segoe WPC', 'Segoe UI', "
                 "'Helvetica Neue', sans-serif", 13)
    app.setFont(font)

    try:
        from app.main_window import VSCodiumWindow
        window = VSCodiumWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.exception("Fatal startup error")
        QMessageBox.critical(None, "Startup Error", f"Failed to start Sea Serpent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
