from __future__ import annotations

from pathlib import Path

from types import SimpleNamespace

from qfluentwidgets import FluentIcon

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.core.models import BatchConvertResult, ConvertedDocument, MarkdownResult
from ankismart.ui.import_page import ImportPage


class _DummyCombo:
    def __init__(self, value: str) -> None:
        self._value = value
        self._items: list[str] = [value] if value else []

    def currentData(self) -> str:
        return self._value

    def currentText(self) -> str:
        return self._value

    def setCurrentText(self, value: str) -> None:
        self._value = value

    def clear(self) -> None:
        self._items = []

    def addItem(self, value: str) -> None:
        self._items.append(value)


class _DummyLineEdit:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:
        self._text = text


class _DummyMain:
    def __init__(self) -> None:
        self.config = AppConfig(
            llm_providers=[
                LLMProviderConfig(
                    id="test",
                    name="OpenAI",
                    api_key="test-key",
                    base_url="https://api.openai.com/v1",
                    model="gpt-4o",
                )
            ],
            active_provider_id="test",
        )
        self.batch_result = None
        self._switched_to_preview = False
        self._loaded_batch_result = None

    def switch_to_preview(self):
        self._switched_to_preview = True

    def load_preview_documents(self, result):
        self._loaded_batch_result = result


class _DummyModeCombo:
    def __init__(self, value: str) -> None:
        self._value = value

    def currentData(self) -> str:
        return self._value


class _DummySlider:
    def __init__(self, value: int) -> None:
        self._value = value

    def value(self) -> int:
        return self._value


class _DummyCheck:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


def _make_page():
    page = ImportPage.__new__(ImportPage)
    page._main = _DummyMain()
    page._file_paths = []
    page._worker = None
    page._strategy_sliders = [
        ("basic", _DummySlider(100), None),
    ]
    page._total_count_input = _DummyLineEdit("20")
    page._total_count_mode_combo = _DummyModeCombo("custom")
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
    page._progress_ring = type("_Ring", (), {"show": lambda self: None, "hide": lambda self: None})()
    page._progress_bar = type(
        "_Bar", (), {"show": lambda self: None, "hide": lambda self: None, "setValue": lambda self, value: None}
    )()
    page._btn_cancel = type(
        "_Btn",
        (),
        {
            "show": lambda self: None,
            "hide": lambda self: None,
            "setEnabled": lambda self, value: None,
        },
    )()
    return page


def _make_warning_box_collector(collected: list[tuple[str, str]]):
    return type(
        "_MB",
        (),
        {
            "warning": staticmethod(
                lambda _parent, title, msg: collected.append((title, msg))
            )
        },
    )


def test_build_generation_config_single_mode() -> None:
    page = _make_page()

    config = ImportPage.build_generation_config(page)

    assert config["mode"] == "mixed"
    assert config["target_total"] == 20
    assert config["strategy_mix"] == [{"strategy": "basic", "ratio": 100}]


def test_build_generation_config_mixed_mode() -> None:
    page = _make_page()
    page._total_count_input = _DummyLineEdit("30")
    page._total_count_mode_combo = _DummyModeCombo("custom")
    page._strategy_sliders = [
        ("basic", _DummySlider(50), None),
        ("cloze", _DummySlider(30), None),
        ("single_choice", _DummySlider(0), None),
    ]

    config = ImportPage.build_generation_config(page)

    assert config["mode"] == "mixed"
    assert config["target_total"] == 30
    assert config["strategy_mix"] == [
        {"strategy": "basic", "ratio": 50},
        {"strategy": "cloze", "ratio": 30},
    ]


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


def test_sidebar_theme_icon_mapping() -> None:
    from ankismart.ui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)

    window.config = SimpleNamespace(theme="light")
    assert MainWindow._get_theme_button_icon(window) == FluentIcon.BRIGHTNESS

    window.config = SimpleNamespace(theme="dark")
    assert MainWindow._get_theme_button_icon(window) == FluentIcon.QUIET_HOURS

    window.config = SimpleNamespace(theme="auto")
    assert MainWindow._get_theme_button_icon(window) == FluentIcon.IOT


def test_switch_to_result_targets_result_page() -> None:
    from ankismart.ui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    switched_to = {}
    window._switch_page = lambda index: switched_to.setdefault("index", index)

    MainWindow.switch_to_result(window)

    assert switched_to["index"] == 3


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
            self.page_progress = type(
                "_Sig", (), {"connect": lambda self, fn: None}
            )()
            self.finished = type(
                "_Sig", (), {"connect": lambda self, fn: None}
            )()
            self.error = type(
                "_Sig", (), {"connect": lambda self, fn: None}
            )()
            self.cancelled = type(
                "_Sig", (), {"connect": lambda self, fn: None}
            )()

        def start(self):
            pass

    monkeypatch.setattr(
        "ankismart.ui.import_page.BatchConvertWorker", _FakeBatchWorker
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.save_config", lambda cfg: None
    )

    page = _make_page()
    page._file_paths = [Path("a.md"), Path("b.docx")]

    ImportPage._start_convert(page)

    assert len(captured["file_paths"]) == 2
    assert captured["file_paths"][0] == Path("a.md")


def test_start_convert_skips_ocr_checks_for_non_ocr_files(monkeypatch):
    page = _make_page()
    page._file_paths = [Path("a.md"), Path("b.docx")]

    prepare_called = {"value": False}
    ensure_called = {"value": False}
    started = {"value": False}

    monkeypatch.setattr(ImportPage, "_prepare_local_ocr_runtime", lambda self: prepare_called.update(value=True) or True)
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: ensure_called.update(value=True) or True)
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)

    class _FakeBatchWorker:
        def __init__(self, file_paths, config=None):
            self.file_progress = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.page_progress = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.finished = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.error = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.cancelled = type("_Sig", (), {"connect": lambda self, fn: None})()

        def start(self):
            started["value"] = True

    monkeypatch.setattr("ankismart.ui.import_page.BatchConvertWorker", _FakeBatchWorker)

    ImportPage._start_convert(page)

    assert prepare_called["value"] is False
    assert ensure_called["value"] is False
    assert started["value"] is True


def test_start_convert_checks_ocr_for_pdf(monkeypatch):
    page = _make_page()
    page._file_paths = [Path("a.pdf")]

    calls = {"prepare": 0, "ensure": 0}
    monkeypatch.setattr(ImportPage, "_prepare_local_ocr_runtime", lambda self: calls.__setitem__("prepare", calls["prepare"] + 1) or True)
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: calls.__setitem__("ensure", calls["ensure"] + 1) or False)

    ImportPage._start_convert(page)

    assert calls["prepare"] == 1
    assert calls["ensure"] == 1


def test_apply_cuda_strategy_upgrades_lite_once(monkeypatch):
    page = _make_page()
    page._main.config.ocr_model_tier = "lite"
    page._main.config.ocr_auto_cuda_upgrade = True
    page._main.config.ocr_model_locked_by_user = False
    page._main.config.ocr_cuda_checked_once = False

    monkeypatch.setattr("ankismart.ui.import_page.is_cuda_available", lambda: True)
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)
    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type("_MB", (), {"information": staticmethod(lambda *a, **k: None)}),
    )

    ImportPage._apply_cuda_strategy_once(page)

    assert page._main.config.ocr_model_tier == "standard"
    assert page._main.config.ocr_cuda_checked_once is True


def test_start_convert_rejects_empty_api_key_for_non_ollama(monkeypatch):
    page = _make_page()
    page._file_paths = [Path("a.md")]
    page._main.config = AppConfig(
        llm_providers=[
            LLMProviderConfig(id="p1", name="OpenAI", api_key="", model="gpt-4o")
        ],
        active_provider_id="p1",
    )

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr("ankismart.ui.import_page.QMessageBox", _make_warning_box_collector(warnings))
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert len(warnings) == 1
    assert "API" in warnings[0][1]


def test_start_convert_allows_empty_api_key_for_ollama(monkeypatch):
    page = _make_page()
    page._file_paths = [Path("a.md")]
    page._main.config = AppConfig(
        llm_providers=[
            LLMProviderConfig(id="p1", name="Ollama (本地)", api_key="", model="llama3")
        ],
        active_provider_id="p1",
    )

    started = {"value": False}

    class _FakeBatchWorker:
        def __init__(self, file_paths, config=None):
            self.file_progress = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.page_progress = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.finished = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.error = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.cancelled = type("_Sig", (), {"connect": lambda self, fn: None})()

        def start(self):
            started["value"] = True

    monkeypatch.setattr("ankismart.ui.import_page.BatchConvertWorker", _FakeBatchWorker)
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert started["value"] is True


def test_start_convert_rejects_empty_deck(monkeypatch):
    page = _make_page()
    page._file_paths = [Path("a.md")]
    page._deck_combo = _DummyCombo("   ")

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr("ankismart.ui.import_page.QMessageBox", _make_warning_box_collector(warnings))
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert len(warnings) == 1
    assert "牌组" in warnings[0][1]


def test_start_convert_rejects_mixed_mode_without_positive_ratio(monkeypatch):
    page = _make_page()
    page._file_paths = [Path("a.md")]
    page._strategy_sliders = [
        ("basic", _DummySlider(0), None),
        ("cloze", _DummySlider(0), None),
    ]

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr("ankismart.ui.import_page.QMessageBox", _make_warning_box_collector(warnings))
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert len(warnings) == 1
    assert "占比" in warnings[0][1]


def test_on_decks_loaded_restores_last_deck_choice():
    page = _make_page()
    page._main.config.last_deck = "MyDeck"
    page._deck_combo = _DummyCombo("TempDeck")

    ImportPage._on_decks_loaded(page, ["Default", "MyDeck", "Other"])

    assert page._deck_combo.currentText() == "MyDeck"
