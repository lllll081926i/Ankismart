from __future__ import annotations

from pathlib import Path

from ankismart.core.models import BatchConvertResult, ConvertedDocument, MarkdownResult
from ankismart.ui.import_page import ImportPage


class _DummyCombo:
    def __init__(self, value: str) -> None:
        self._value = value

    def currentData(self) -> str:
        return self._value

    def currentText(self) -> str:
        return self._value


class _DummyLineEdit:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _DummyMain:
    class _Config:
        openai_api_key = "test-key"
        openai_model = "gpt-4o"
        anki_connect_url = "http://127.0.0.1:8765"
        anki_connect_key = ""

    config = _Config()
    batch_result = None
    _switched_to_preview = False
    _loaded_batch_result = None

    def switch_to_preview(self):
        self._switched_to_preview = True

    def load_preview_documents(self, result):
        self._loaded_batch_result = result


def _make_page():
    page = ImportPage.__new__(ImportPage)
    page._main = _DummyMain()
    page._file_paths = []
    page._worker = None
    page._type_combo = _DummyCombo("basic")
    page._deck_combo = _DummyCombo("Default")
    page._tags_input = _DummyLineEdit("tag1, tag2")
    page._status_label = type(
        "_Label", (), {"setText": lambda self, text: None}
    )()
    page._progress = type(
        "_Progress",
        (),
        {
            "hide": lambda self: None,
            "show": lambda self: None,
            "setRange": lambda self, a, b: None,
            "setValue": lambda self, v: None,
        },
    )()
    page._btn_convert = type(
        "_Btn", (), {"setEnabled": lambda self, v: None}
    )()
    return page


def test_batch_convert_done_sets_result_and_switches(monkeypatch):
    page = _make_page()

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

    # Monkeypatch QMessageBox to avoid GUI
    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type("_MB", (), {"warning": staticmethod(lambda *a, **k: None)}),
    )

    ImportPage._on_batch_convert_done(page, result)

    assert page._main.batch_result is result
    assert page._main._switched_to_preview is True


def test_switch_to_preview_loads_documents_when_supported(monkeypatch):
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

    def _fake_switch(index):
        switched_to["index"] = index

    window._switch_page = _fake_switch

    MainWindow.switch_to_preview(window)

    assert switched_to["index"] == 1
    assert window._preview_page.loaded is window._batch_result


def test_batch_convert_done_shows_errors(monkeypatch):
    page = _make_page()
    warnings_shown = []

    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type(
            "_MB",
            (),
            {
                "warning": staticmethod(
                    lambda parent, title, msg: warnings_shown.append(msg)
                )
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

    assert len(warnings_shown) == 1
    assert "b.pdf" in warnings_shown[0]
    assert page._main.batch_result is result


def test_batch_convert_done_no_documents(monkeypatch):
    page = _make_page()
    status_texts = []
    page._status_label = type(
        "_Label", (), {"setText": lambda self, t: status_texts.append(t)}
    )()

    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type("_MB", (), {"warning": staticmethod(lambda *a, **k: None)}),
    )

    result = BatchConvertResult(documents=[], errors=["all failed"])

    ImportPage._on_batch_convert_done(page, result)

    assert page._main._switched_to_preview is False
    assert any("没有" in t for t in status_texts)


def test_start_convert_uses_batch_worker(monkeypatch):
    captured = {}

    class _FakeBatchWorker:
        def __init__(self, file_paths, config=None):
            captured["file_paths"] = file_paths
            self.file_progress = type(
                "_Sig", (), {"connect": lambda self, fn: None}
            )()
            self.finished = type(
                "_Sig", (), {"connect": lambda self, fn: None}
            )()
            self.error = type(
                "_Sig", (), {"connect": lambda self, fn: None}
            )()

        def start(self):
            pass

    monkeypatch.setattr(
        "ankismart.ui.import_page.BatchConvertWorker", _FakeBatchWorker
    )

    page = _make_page()
    page._file_paths = [Path("a.md"), Path("b.docx")]

    ImportPage._start_convert(page)

    assert len(captured["file_paths"]) == 2
    assert captured["file_paths"][0] == Path("a.md")
