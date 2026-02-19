from __future__ import annotations

from PyQt6.QtWidgets import QApplication


class BasePageObject:
    def __init__(self, window) -> None:
        self.window = window

    @property
    def app(self) -> QApplication:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication is not initialized")
        return app

    def process_events(self) -> None:
        self.app.processEvents()
