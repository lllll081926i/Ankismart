from __future__ import annotations

from pathlib import Path

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.import_page import ImportPage

from .import_page_test_utils import (
    DummyCombo,
    DummySlider,
    make_page,
    make_warning_box_collector,
    patch_infobar,
)


def test_start_convert_uses_batch_worker(monkeypatch):
    captured = {}

    class _FakeBatchWorker:
        def __init__(self, file_paths, config=None):
            captured["file_paths"] = file_paths
            self.file_progress = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.file_completed = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.page_progress = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.finished = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.error = type("_Sig", (), {"connect": lambda self, fn: None})()
            self.cancelled = type("_Sig", (), {"connect": lambda self, fn: None})()

        def start(self):
            pass

    monkeypatch.setattr("ankismart.ui.import_page.BatchConvertWorker", _FakeBatchWorker)
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)

    page = make_page()
    page._file_paths = [Path("a.md"), Path("b.docx")]

    ImportPage._start_convert(page)

    assert len(captured["file_paths"]) == 2
    assert captured["file_paths"][0] == Path("a.md")


def test_start_convert_skips_ocr_checks_for_non_ocr_files(monkeypatch):
    page = make_page()
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
            self.file_completed = type("_Sig", (), {"connect": lambda self, fn: None})()
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
    page = make_page()
    page._file_paths = [Path("a.pdf")]

    calls = {"prepare": 0, "ensure": 0}
    monkeypatch.setattr(
        ImportPage,
        "_prepare_local_ocr_runtime",
        lambda self: calls.__setitem__("prepare", calls["prepare"] + 1) or True,
    )
    monkeypatch.setattr(
        ImportPage,
        "_ensure_ocr_models_ready",
        lambda self: calls.__setitem__("ensure", calls["ensure"] + 1) or False,
    )

    ImportPage._start_convert(page)

    assert calls["prepare"] == 1
    assert calls["ensure"] == 1


def test_apply_cuda_strategy_upgrades_lite_once(monkeypatch):
    page = make_page()
    infobar_calls = patch_infobar(monkeypatch)
    page._main.config.ocr_model_tier = "lite"
    page._main.config.ocr_auto_cuda_upgrade = True
    page._main.config.ocr_model_locked_by_user = False
    page._main.config.ocr_cuda_checked_once = False

    monkeypatch.setattr("ankismart.ui.import_page.is_cuda_available", lambda **kwargs: True)
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)
    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox",
        type("_MB", (), {"information": staticmethod(lambda *a, **k: None)}),
    )

    ImportPage._apply_cuda_strategy_once(page)

    assert page._main.config.ocr_model_tier == "standard"
    assert page._main.config.ocr_cuda_checked_once is True
    assert len(infobar_calls["success"]) == 1


def test_start_convert_rejects_empty_api_key_for_non_ollama(monkeypatch):
    page = make_page()
    infobar_calls = patch_infobar(monkeypatch)
    page._file_paths = [Path("a.md")]
    page._main.config = AppConfig(
        llm_providers=[
            LLMProviderConfig(id="p1", name="OpenAI", api_key="", model="gpt-4o")
        ],
        active_provider_id="p1",
    )

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr("ankismart.ui.import_page.QMessageBox", make_warning_box_collector(warnings))
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert len(warnings) == 0
    assert len(infobar_calls["warning"]) == 1
    assert "API" in infobar_calls["warning"][0]["content"]


def test_start_convert_allows_empty_api_key_for_ollama(monkeypatch):
    page = make_page()
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
            self.file_completed = type("_Sig", (), {"connect": lambda self, fn: None})()
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
    page = make_page()
    infobar_calls = patch_infobar(monkeypatch)
    page._file_paths = [Path("a.md")]
    page._deck_combo = DummyCombo("   ")

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr("ankismart.ui.import_page.QMessageBox", make_warning_box_collector(warnings))
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert len(warnings) == 0
    assert len(infobar_calls["warning"]) == 1
    assert "牌组" in infobar_calls["warning"][0]["content"]


def test_start_convert_rejects_mixed_mode_without_positive_ratio(monkeypatch):
    page = make_page()
    infobar_calls = patch_infobar(monkeypatch)
    page._file_paths = [Path("a.md")]
    page._strategy_sliders = [
        ("basic", DummySlider(0), None),
        ("cloze", DummySlider(0), None),
    ]

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr("ankismart.ui.import_page.QMessageBox", make_warning_box_collector(warnings))
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert len(warnings) == 0
    assert len(infobar_calls["warning"]) == 1
    assert "占比" in infobar_calls["warning"][0]["content"]

