"""Main window smoke tests."""

from __future__ import annotations

import sys
import time
from statistics import median

import pytest
from PyQt6.QtWidgets import QApplication

from ankismart.core.config import AppConfig
from ankismart.core.task_models import TaskStatus, build_default_task_run
from ankismart.core.task_store import JsonTaskStore
from ankismart.ui import app as app_module
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


def test_main_window_startup_smoke_budget(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    warmup = MainWindow(config=AppConfig(language="zh", theme="light"))
    warmup.close()
    app.processEvents()

    samples_ms: list[float] = []
    for _ in range(3):
        started = time.perf_counter()
        window = MainWindow(config=AppConfig(language="zh", theme="light"))
        samples_ms.append((time.perf_counter() - started) * 1000)
        window.close()
        app.processEvents()

    # Qt + qfluentwidgets startup cost on Windows CI is noisy; keep a budget
    # that still catches large regressions without making the smoke test flaky.
    assert median(samples_ms) < 650


def test_main_window_keeps_sidebar_back_action(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    window = MainWindow(config=AppConfig(language="zh", theme="light"))
    window.show()
    app.processEvents()

    back_buttons = [
        button
        for button in window.navigationInterface.findChildren(object)
        if hasattr(button, "toolTip")
        and callable(button.toolTip)
        and button.toolTip() == "Back"
    ]

    assert any(button.isVisible() for button in back_buttons if hasattr(button, "isVisible"))
    window.close()
    app.processEvents()


def test_main_window_title_bar_uses_default_compact_size(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    window = MainWindow(config=AppConfig(language="zh", theme="light"))
    window.show()
    app.processEvents()

    assert window.titleBar.height() == 36
    assert getattr(window, "_title_bar_label", None) is None
    assert getattr(window, "_title_bar_icon_label", None) is None

    window.close()
    app.processEvents()


def test_main_window_loads_resumable_tasks(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)
    tasks_path = tmp_path / "tasks.json"
    monkeypatch.setattr("ankismart.ui.main_window.TASKS_PATH", tasks_path)
    task = build_default_task_run(flow="full_pipeline", task_id="task-r1")
    task.status = TaskStatus.FAILED
    task.resume_from_stage = "generate"
    JsonTaskStore(tasks_path).save(task)

    window = MainWindow(config=AppConfig(language="zh", theme="light"))

    assert [item.task_id for item in window.resumable_tasks] == ["task-r1"]
    assert "task-r1" in window.task_center_panel._task_widgets
    assert window.task_center_panel.isVisible() is False
    window.close()


def test_main_window_does_not_resave_loaded_resumable_tasks(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)
    tasks_path = tmp_path / "tasks.json"
    monkeypatch.setattr("ankismart.ui.main_window.TASKS_PATH", tasks_path)
    task = build_default_task_run(flow="full_pipeline", task_id="task-r2")
    task.status = TaskStatus.FAILED
    task.resume_from_stage = "push"
    JsonTaskStore(tasks_path).save(task)

    save_calls: list[str] = []
    monkeypatch.setattr(
        "ankismart.ui.task_runtime.JsonTaskStore.save",
        lambda self, item: save_calls.append(item.task_id),
    )

    window = MainWindow(config=AppConfig(language="zh", theme="light"))

    assert save_calls == []
    window.close()


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


def test_startup_timing_helpers_record_stage_costs(monkeypatch) -> None:
    app_module._STARTUP_TS.clear()
    samples = iter([10.0, 10.125])
    monkeypatch.setattr(app_module.time, "perf_counter", lambda: next(samples))

    app_module._mark_startup("main.enter")
    app_module._mark_startup("window.shown")

    assert app_module._startup_cost_ms("main.enter", "window.shown") == 125.0


def test_log_startup_timing_emits_expected_summary(monkeypatch) -> None:
    app_module._STARTUP_TS.clear()
    app_module._STARTUP_TS.update(
        {
            "main.enter": 1.0,
            "qapp.created": 1.01,
            "config.loaded": 1.03,
            "theme.applied": 1.05,
            "window.created": 1.10,
            "window.shown": 1.12,
        }
    )
    calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(
        app_module.logger,
        "info",
        lambda message, extra=None: calls.append((message, extra or {})),
    )

    app_module._log_startup_timing()

    assert calls == [
        (
            "startup timing",
            {
                "event": "app.startup.timing",
                "qapp_ms": 10.0,
                "config_ms": 20.0,
                "theme_ms": 20.0,
                "window_ms": 50.0,
                "show_ms": 20.0,
                "total_ms": 120.0,
            },
        )
    ]


def test_app_module_keeps_httpx_off_startup_import_path() -> None:
    assert "httpx" not in app_module.__dict__


def test_app_module_keeps_main_window_off_startup_import_path() -> None:
    assert "MainWindow" not in app_module.__dict__
