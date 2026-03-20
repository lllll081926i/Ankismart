from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QWidget

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui import import_page
from ankismart.ui.import_page import ImportPage

from .import_page_test_utils import (
    DummyCombo,
    DummySlider,
    make_page,
    make_warning_box_collector,
    patch_infobar,
)

_APP = QApplication.instance() or QApplication([])


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

    monkeypatch.setattr(
        ImportPage,
        "_prepare_local_ocr_runtime",
        lambda self: prepare_called.update(value=True) or True,
    )
    monkeypatch.setattr(
        ImportPage,
        "_ensure_ocr_models_ready",
        lambda self: ensure_called.update(value=True) or True,
    )
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


def test_start_convert_cloud_mode_skips_local_model_check(monkeypatch):
    page = make_page()
    page._file_paths = [Path("a.pdf")]
    page._main.config.ocr_mode = "cloud"
    page._main.config.ocr_cloud_provider = "mineru"
    page._main.config.ocr_cloud_endpoint = "https://mineru.net"
    page._main.config.ocr_cloud_api_key = "token"

    ensure_called = {"value": False}
    started = {"value": False}

    monkeypatch.setattr(
        ImportPage,
        "_ensure_ocr_models_ready",
        lambda self: ensure_called.update(value=True) or True,
    )
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

    assert started["value"] is True
    assert ensure_called["value"] is False


def test_ensure_ocr_models_ready_does_not_create_state_tooltip(monkeypatch):
    page = make_page()
    page._model_check_in_progress = False
    page._set_generate_actions_enabled = lambda _enabled: None
    page._cleanup_ocr_download_worker = lambda: None
    page._persist_ocr_config_updates = lambda **kwargs: None
    info_calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr("ankismart.ui.import_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        "ankismart.ui.import_page.get_missing_ocr_models",
        lambda **kwargs: ["model-a"],
    )
    monkeypatch.setattr(
        ImportPage,
        "_show_info_bar",
        lambda *args, **kwargs: info_calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        ImportPage,
        "_show_progress_info_bar",
        lambda *args, **kwargs: info_calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.StateToolTip",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    class _DialogStub:
        selected_tier = "lite"
        selected_source = "official"

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return import_page.QDialog.DialogCode.Accepted

    class _SignalStub:
        def connect(self, _callback):
            return None

    class _WorkerStub:
        def __init__(self, *args, **kwargs):
            self.progress = _SignalStub()
            self.finished = _SignalStub()
            self.error = _SignalStub()

        def start(self):
            return None

    monkeypatch.setattr("ankismart.ui.import_page.OCRDownloadConfigDialog", _DialogStub)
    monkeypatch.setattr("ankismart.ui.import_page.OCRModelDownloadWorker", _WorkerStub)

    result = ImportPage._ensure_ocr_models_ready(page)

    assert result is False
    assert len(info_calls) == 3


def test_prepare_local_ocr_runtime_cloud_requires_api_key(monkeypatch):
    page = make_page()
    page._main.config.ocr_mode = "cloud"
    page._main.config.ocr_cloud_provider = "mineru"
    page._main.config.ocr_cloud_endpoint = "https://mineru.net"
    page._main.config.ocr_cloud_api_key = ""

    infobar_calls = patch_infobar(monkeypatch)

    assert ImportPage._prepare_local_ocr_runtime(page) is False
    assert len(infobar_calls["warning"]) == 1


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
        llm_providers=[LLMProviderConfig(id="p1", name="OpenAI", api_key="", model="gpt-4o")],
        active_provider_id="p1",
    )

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox", make_warning_box_collector(warnings)
    )
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
    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox", make_warning_box_collector(warnings)
    )
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
    monkeypatch.setattr(
        "ankismart.ui.import_page.QMessageBox", make_warning_box_collector(warnings)
    )
    monkeypatch.setattr(ImportPage, "_ensure_ocr_models_ready", lambda self: True)

    ImportPage._start_convert(page)

    assert len(warnings) == 0
    assert len(infobar_calls["warning"]) == 1
    assert "占比" in infobar_calls["warning"][0]["content"]


def test_download_missing_ocr_models_forwards_progress_callback(monkeypatch):
    captured = {}

    class _StubModule:
        @staticmethod
        def download_missing_ocr_models(**kwargs):
            captured.update(kwargs)
            return ["model-a"]

    monkeypatch.setattr(import_page, "_get_ocr_converter_module", lambda: _StubModule())

    def callback(current, total, msg):  # noqa: ANN001, ANN201
        return None

    result = import_page.download_missing_ocr_models(
        progress_callback=callback,
        model_tier="lite",
        model_source="official",
    )

    assert result == ["model-a"]
    assert captured["progress_callback"] is callback
    assert captured["model_tier"] == "lite"
    assert captured["model_source"] == "official"


def test_ocr_download_progress_shows_infobar_and_deduplicates(monkeypatch):
    page = make_page()
    page._state_tooltip = None
    page._last_ocr_progress_message = ""
    infobar_calls = patch_infobar(monkeypatch)

    ImportPage._on_ocr_download_progress(page, 1, 2, "正在下载模型")
    ImportPage._on_ocr_download_progress(page, 1, 2, "正在下载模型")

    assert len(infobar_calls["info"]) == 1
    assert "[1/2] 正在下载模型" in infobar_calls["info"][0]["content"]


def test_on_page_progress_shows_file_page_infobar_and_deduplicates(monkeypatch):
    page = make_page()
    page._last_ocr_page_status_message = ""
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        ImportPage,
        "_show_progress_info_bar",
        lambda *args, **kwargs: calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        ImportPage,
        "_show_info_bar",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected standard infobar")
        ),
        raising=False,
    )

    ImportPage._on_page_progress(page, "讲义.pdf", 3, 12)
    ImportPage._on_page_progress(page, "讲义.pdf", 3, 12)

    assert len(calls) == 1
    assert calls[0][0][2] == "讲义.pdf 3/12"


def test_create_right_panel_does_not_include_startup_precheck_card():
    page = make_page()
    page._create_config_group = lambda: QWidget()
    page._create_strategy_group = lambda: QWidget()
    page._create_progress_display = lambda: QWidget()

    right_panel = ImportPage._create_right_panel(page)

    assert right_panel is not None
    assert not hasattr(ImportPage, "_create_startup_precheck_card")
    widget_count = sum(
        1
        for index in range(page.expand_layout.count())
        if page.expand_layout.itemAt(index).widget()
    )
    assert widget_count == 3


def test_start_generate_cards_delegates_to_convert_without_auto_generate_flag(monkeypatch):
    page = make_page()
    page._file_paths = [Path("a.md")]
    calls = {"count": 0}

    monkeypatch.setattr(
        ImportPage,
        "_start_convert",
        lambda self: calls.__setitem__("count", calls["count"] + 1),
    )

    ImportPage._start_generate_cards(page)

    assert calls["count"] == 1
    assert "_auto_generate_after_convert" not in page.__dict__


def test_get_start_convert_text_matches_manual_conversion_flow() -> None:
    assert ImportPage._get_start_convert_text("zh") == "开始转换"
    assert ImportPage._get_start_convert_text("en") == "Start Conversion"


def test_on_batch_convert_done_does_not_record_metric_again(monkeypatch) -> None:
    page = make_page()
    page._file_paths = [Path("a.md")]
    page._convert_start_ts = 0.0
    page._main._switched_to_preview = False

    metric_calls = {"count": 0}
    monkeypatch.setattr(
        "ankismart.ui.import_page.append_task_history",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.record_operation_metric",
        lambda *args, **kwargs: metric_calls.__setitem__("count", metric_calls["count"] + 1),
    )
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)
    monkeypatch.setattr("ankismart.ui.import_page.register_cloud_ocr_usage", lambda *args: None)
    monkeypatch.setattr(
        "ankismart.ui.import_page.InfoBar",
        type(
            "_InfoBarStub",
            (),
            {
                "warning": staticmethod(lambda *args, **kwargs: None),
                "success": staticmethod(lambda *args, **kwargs: None),
                "info": staticmethod(lambda *args, **kwargs: None),
                "error": staticmethod(lambda *args, **kwargs: None),
            },
        ),
    )

    ImportPage._on_batch_convert_done(
        page,
        SimpleNamespace(documents=[object()], errors=[], warnings=[]),
    )

    assert metric_calls["count"] == 0
    assert page._main._switched_to_preview is True


def test_on_batch_convert_done_records_metric_when_all_files_failed(monkeypatch) -> None:
    page = make_page()
    page._file_paths = [Path("a.md")]
    page._convert_start_ts = 0.0

    metric_calls = {"count": 0}
    monkeypatch.setattr(
        "ankismart.ui.import_page.append_task_history",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.record_operation_metric",
        lambda *args, **kwargs: metric_calls.__setitem__("count", metric_calls["count"] + 1),
    )
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)
    monkeypatch.setattr("ankismart.ui.import_page.register_cloud_ocr_usage", lambda *args: None)
    monkeypatch.setattr(
        "ankismart.ui.import_page.InfoBar",
        type(
            "_InfoBarStub",
            (),
            {
                "warning": staticmethod(lambda *args, **kwargs: None),
                "success": staticmethod(lambda *args, **kwargs: None),
                "info": staticmethod(lambda *args, **kwargs: None),
                "error": staticmethod(lambda *args, **kwargs: None),
            },
        ),
    )

    ImportPage._on_batch_convert_done(
        page,
        SimpleNamespace(documents=[], errors=["a.md: boom"], warnings=[]),
    )

    assert metric_calls["count"] == 1


def test_on_convert_error_does_not_record_metric_again(monkeypatch) -> None:
    page = make_page()
    page._convert_start_ts = 0.0

    metric_calls = {"count": 0}
    monkeypatch.setattr(
        "ankismart.ui.import_page.append_task_history",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.record_operation_metric",
        lambda *args, **kwargs: metric_calls.__setitem__("count", metric_calls["count"] + 1),
    )
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)
    monkeypatch.setattr(
        "ankismart.ui.import_page.build_error_display",
        lambda error, language: {"title": "失败", "content": error},
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.InfoBar",
        type(
            "_InfoBarStub",
            (),
            {
                "warning": staticmethod(lambda *args, **kwargs: None),
                "success": staticmethod(lambda *args, **kwargs: None),
                "info": staticmethod(lambda *args, **kwargs: None),
                "error": staticmethod(lambda *args, **kwargs: None),
            },
        ),
    )

    ImportPage._on_convert_error(page, "boom")

    assert metric_calls["count"] == 0


def test_on_convert_error_uses_page_infobar_helper(monkeypatch) -> None:
    page = make_page()
    page._convert_start_ts = 0.0
    calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        "ankismart.ui.import_page.append_task_history",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.record_operation_metric",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda cfg: None)
    monkeypatch.setattr(
        "ankismart.ui.import_page.build_error_display",
        lambda error, language: {"title": "失败", "content": error},
    )
    monkeypatch.setattr(
        ImportPage,
        "_show_info_bar",
        lambda *args, **kwargs: calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.InfoBar.error",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    ImportPage._on_convert_error(page, "boom")

    assert len(calls) == 1
    assert calls[0][0][1] == "error"
