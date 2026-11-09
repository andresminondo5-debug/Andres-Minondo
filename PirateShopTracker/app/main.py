"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from app import config
from app.engine import TrackerEngine
from app.storage import Storage
from app.ui.main_window import MainWindow
from app.ui.theme import STYLE


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_TITLE)
    app.setStyleSheet(STYLE)

    settings = config.load_settings()
    storage = Storage(config.data_dir() / "tracker.db")
    engine = TrackerEngine(settings, storage)

    window = MainWindow(settings, storage, engine)
    window.show()
    window.auto_start()

    code = app.exec()
    window.shutdown()
    return code
