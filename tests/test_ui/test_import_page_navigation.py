from __future__ import annotations

from types import SimpleNamespace

from qfluentwidgets import FluentIcon

from ankismart.core.models import BatchConvertResult, ConvertedDocument, MarkdownResult
from ankismart.ui.import_page import ImportPage

from .import_page_test_utils import (
    DummyListItem,
    DummyListWidget,
    make_page,
    patch_infobar,
)


class _ThreadLikeWorker:
    def __init__(self, *, running: bool) -> None:
        self._running = running
        self.wait_calls: list[int] = []
        self.cancel_called = False
        self.deleted = False

    def isRunning(self) -> bool:  # noqa: N802
        return self._running

    def wait(self, timeout: int) -> None:
        self.wait_calls.append(timeout)

    def cancel(self) -> None:
        self.cancel_called = True

    def deleteLater(self) -> None:  # noqa: N802
        self.deleted = True


def test_batch_convert_done_sets_result_and_switches(monkeypatch):
    page = make_page()

    result = BatchConvertResult(
        documents=[
            ConvertedDocument(
                result=MarkdownResult(
                    content="# title",
                    source_path="demo.md",
                    source_format="markdown",
                    trace_id="trace-xyz",
                ),
                file_name="demo.md",
            )
        ],
        errors=[],
    )

    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type("_MB", (), {"warning": staticmethod(lambda *a, **k: None)}),
    )

    ImportPage._on_batch_convert_done(page, result)

    assert page._main.batch_result is result
    assert page._main._switched_to_preview is True


def test_switch_to_preview_loads_documents_when_supported():
    from ankismart.ui.main_window import MainWindow

    class _PreviewPage:
        def __init__(self):
            self.loaded = None

        def load_documents(self, result):
            self.loaded = result

    window = MainWindow.__new__(MainWindow)
    window._preview_page = _PreviewPage()
    window._batch_result = BatchConvertResult(
        documents=[
            ConvertedDocument(
                result=MarkdownResult(
                    content="# title",
                    source_path="demo.md",
                    source_format="markdown",
                    trace_id="trace-xyz",
                ),
                file_name="demo.md",
            )
        ],
        errors=[],
    )

    switched_to = {}
    window._switch_page = lambda index: switched_to.setdefault("index", index)

    MainWindow.switch_to_preview(window)

    assert switched_to["index"] == 1
    assert window._preview_page.loaded is window._batch_result


def test_sidebar_theme_icon_mapping() -> None:
    from ankismart.ui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)

    window.config = SimpleNamespace(theme="light")
    assert MainWindow._get_theme_button_icon(window) == FluentIcon.BRIGHTNESS

    window.config = SimpleNamespace(theme="dark")
    assert MainWindow._get_theme_button_icon(window) == FluentIcon.QUIET_HOURS

    window.config = SimpleNamespace(theme="auto")
    assert MainWindow._get_theme_button_icon(window) == FluentIcon.IOT


def test_update_theme_refreshes_file_item_colors(monkeypatch) -> None:
    page = make_page()
    pending_item = DummyListItem("pending.md")
    completed_item = DummyListItem("done.md")
    page._file_list = DummyListWidget([pending_item, completed_item])
    page._file_status = {"pending.md": "pending", "done.md": "completed"}

    monkeypatch.setattr("ankismart.ui.import_page.isDarkTheme", lambda: True)

    ImportPage.update_theme(page)

    assert pending_item.color_name == "#a0a0a0"
    assert completed_item.color_name == "#ffffff"


def test_switch_to_result_targets_result_page() -> None:
    from ankismart.ui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    switched_to = {}
    window._switch_page = lambda index: switched_to.setdefault("index", index)

    MainWindow.switch_to_result(window)

    assert switched_to["index"] == 3


def test_batch_convert_done_shows_errors(monkeypatch):
    page = make_page()
    warnings_shown = []
    infobar_calls = patch_infobar(monkeypatch)

    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type(
            "_MB",
            (),
            {
                "warning": staticmethod(lambda parent, title, msg: warnings_shown.append(msg))
            },
        ),
    )

    result = BatchConvertResult(
        documents=[
            ConvertedDocument(
                result=MarkdownResult(
                    content="ok",
                    source_path="a.md",
                    source_format="markdown",
                    trace_id="t1",
                ),
                file_name="a.md",
            )
        ],
        errors=["b.pdf: conversion failed"],
    )

    ImportPage._on_batch_convert_done(page, result)

    assert len(warnings_shown) == 0
    assert len(infobar_calls["warning"]) == 1
    assert "b.pdf" in infobar_calls["warning"][0]["content"]
    assert page._main.batch_result is result


def test_batch_convert_done_no_documents(monkeypatch):
    page = make_page()
    status_texts = []
    patch_infobar(monkeypatch)
    page._status_label = type("_Label", (), {"setText": lambda self, t: status_texts.append(t)})()

    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type("_MB", (), {"warning": staticmethod(lambda *a, **k: None)}),
    )

    result = BatchConvertResult(documents=[], errors=["all failed"])

    ImportPage._on_batch_convert_done(page, result)

    assert page._main._switched_to_preview is False
    assert any("没有" in t for t in status_texts)


def test_cleanup_batch_worker_keeps_reference_when_running():
    page = make_page()
    worker = _ThreadLikeWorker(running=True)
    page._worker = worker

    ImportPage._cleanup_batch_worker(page)

    assert page._worker is worker
    assert worker.cancel_called is True
    assert worker.wait_calls == [200]
    assert worker.deleted is False


def test_cleanup_batch_worker_releases_finished_worker():
    page = make_page()
    worker = _ThreadLikeWorker(running=False)
    page._worker = worker

    ImportPage._cleanup_batch_worker(page)

    assert page._worker is None
    assert worker.deleted is True


def test_cleanup_ocr_download_worker_keeps_reference_when_running():
    page = make_page()
    worker = _ThreadLikeWorker(running=True)
    page._ocr_download_worker = worker

    ImportPage._cleanup_ocr_download_worker(page)

    assert page._ocr_download_worker is worker
    assert worker.wait_calls == [200]
    assert worker.deleted is False


def test_cleanup_ocr_download_worker_releases_finished_worker():
    page = make_page()
    worker = _ThreadLikeWorker(running=False)
    page._ocr_download_worker = worker

    ImportPage._cleanup_ocr_download_worker(page)

    assert page._ocr_download_worker is None
    assert worker.deleted is True


def test_cleanup_deck_loader_keeps_reference_when_running():
    page = make_page()
    worker = _ThreadLikeWorker(running=True)
    page._deck_loader = worker

    ImportPage._cleanup_deck_loader_worker(page)

    assert page._deck_loader is worker
    assert worker.wait_calls == [200]
    assert worker.deleted is False


def test_cleanup_deck_loader_releases_finished_worker():
    page = make_page()
    worker = _ThreadLikeWorker(running=False)
    page._deck_loader = worker

    ImportPage._cleanup_deck_loader_worker(page)

    assert page._deck_loader is None
    assert worker.deleted is True
