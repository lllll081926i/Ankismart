from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from ankismart.core.config import load_config
from ankismart.core.logging import setup_logging
from ankismart.ui.main_window import MainWindow
from ankismart.ui.styles import get_stylesheet
from ankismart.ui.workers import ConnectionCheckWorker


def main() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    setup_logging()
    config = load_config()

    app = QApplication(sys.argv)
    app.setApplicationName("AnkiSmart")
    app.setStyleSheet(get_stylesheet())

    window = MainWindow(config)

    # Import pages lazily to avoid circular imports
    from ankismart.ui.import_page import ImportPage
    from ankismart.ui.preview_page import PreviewPage
    from ankismart.ui.result_page import ResultPage
    from ankismart.ui.settings_page import SettingsPage

    import_page = ImportPage(window)
    preview_page = PreviewPage(window)
    result_page = ResultPage(window)
    settings_page = SettingsPage(window)

    window.add_page(import_page)
    window.add_preview_page(preview_page)
    window.add_page(result_page)
    window.add_page(settings_page)
    window.set_import_page(import_page)

    # Check AnkiConnect on startup
    checker = ConnectionCheckWorker(config.anki_connect_url, config.anki_connect_key)
    checker.finished.connect(window.set_connection_status)
    checker.start()
    # Keep reference to prevent GC
    window._connection_checker = checker

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
