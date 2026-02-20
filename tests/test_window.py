"""Main window smoke tests."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from ankismart.core.config import AppConfig
from ankismart.ui.main_window import MainWindow

_APP = QApplication.instance() or QApplication([])


def _get_app() -> QApplication:
    return _APP


def test_main_window_smoke(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    window = MainWindow(config=AppConfig(language="zh", theme="light"))
    window.show()
    app.processEvents()

    assert window.windowTitle() == "Ankismart"
    assert window.import_page is not None
    assert window.preview_page is not None
    assert window.card_preview_page is not None
    assert window.result_page is not None
    assert window.settings_page is not None

    window.close()
    app.processEvents()


def test_shutdown_pages_closes_all_child_pages(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    window = MainWindow(config=AppConfig(language="zh", theme="light"))
    window.show()
    app.processEvents()

    closed_pages: list[str] = []

    def _mark(name: str):
        return lambda: closed_pages.append(name)

    window.import_page.close = _mark("import")
    window.preview_page.close = _mark("preview")
    window.card_preview_page.close = _mark("card_preview")
    window.result_page.close = _mark("result")
    window.performance_page.close = _mark("performance")
    window.settings_page.close = _mark("settings")

    window._shutdown_pages()

    assert closed_pages == ["import", "preview", "card_preview", "result", "performance", "settings"]
    window.close()
    app.processEvents()


def test_close_event_invokes_shutdown_pages(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    window = MainWindow(config=AppConfig(language="zh", theme="light"))
    window.show()
    app.processEvents()

    calls: list[str] = []
    monkeypatch.setattr(window, "_shutdown_pages", lambda: calls.append("called"))

    window.close()
    app.processEvents()

    assert calls == ["called"]
