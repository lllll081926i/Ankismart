"""Main window smoke tests."""

from __future__ import annotations

import sys

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

    assert closed_pages == [
        "import",
        "preview",
        "card_preview",
        "result",
        "performance",
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


def test_performance_page_observability_cards_render_expected_text(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    window = MainWindow(config=AppConfig(language="zh", theme="light"))
    window.show()
    app.processEvents()

    window.config.ops_conversion_durations = [1.0, 2.0, 3.0]
    window.config.ops_generation_durations = [2.0, 4.0]
    window.config.ops_push_durations = [0.5, 1.0]
    window.config.ops_error_counters = {"generate:rate_limit": 3, "push:cancelled": 1}
    window.config.ops_cloud_pages_daily = [
        {"date": "2026-02-20", "pages": 10},
        {"date": "2026-02-21", "pages": 12},
    ]

    window.performance_page.refresh_statistics()

    assert "转换 P50/P95" in window.performance_page._latency_label.text()
    assert "generate:rate_limit: 3" in window.performance_page._error_heatmap_label.text()
    assert "2026-02-21: 12" in window.performance_page._cloud_trend_label.text()

    window.close()
    app.processEvents()


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
