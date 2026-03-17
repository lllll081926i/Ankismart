"""Main window smoke tests."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from ankismart.core.config import AppConfig
from ankismart.ui.main_window import MainWindow
from tests.e2e.conftest import _configure_test_qapp, _teardown_test_window

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
    assert "performance" not in window._deferred_page_queue

    with pytest.raises(AttributeError):
        _ = window.performance_page

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
    window.settings_page.close = _mark("settings")

    window._shutdown_pages()

    assert closed_pages == [
        "import",
        "preview",
        "card_preview",
        "result",
        "settings",
    ]
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

def test_app_write_crash_report_creates_log(tmp_path, monkeypatch) -> None:
    from ankismart.ui import app as app_module

    monkeypatch.setattr(app_module, "CONFIG_DIR", tmp_path)

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    path = app_module._write_crash_report(exc_type, exc_value, exc_tb)
    content = path.read_text(encoding="utf-8")

    assert path.exists()
    assert "RuntimeError: boom" in content
    assert "Traceback:" in content


def test_e2e_qapp_configuration_disables_quit_on_last_window_closed() -> None:
    app = _get_app()

    _configure_test_qapp(app)

    assert app.quitOnLastWindowClosed() is False


def test_e2e_window_teardown_closes_window_cleanly(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    _configure_test_qapp(app)
    window = MainWindow(config=AppConfig(language="zh", theme="light"))
    window.show()
    app.processEvents()

    _teardown_test_window(window, app)

    assert window.isVisible() is False
