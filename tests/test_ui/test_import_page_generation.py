from __future__ import annotations

from pathlib import Path

from ankismart.core.config import AppConfig
from ankismart.core.task_models import build_default_task_run
from ankismart.ui.import_page import _STRATEGY_TEMPLATE_LIBRARY, ImportPage
from ankismart.ui.utils import format_operation_hint
from ankismart.ui.workflows import (
    ConvertWorkflowRequest,
    validate_convert_request,
)

from .import_page_test_utils import (
    DummyCombo,
    DummyLineEdit,
    DummyModeCombo,
    DummySlider,
    DummySwitch,
    make_page,
    patch_infobar,
)


def test_build_generation_config_single_mode() -> None:
    page = make_page()

    config = ImportPage.build_generation_config(page)

    assert config["mode"] == "mixed"
    assert config["target_total"] == 20
    assert config["auto_target_count"] is True
    assert config["strategy_mix"] == [{"strategy": "basic", "ratio": 100}]


def test_start_convert_creates_pending_task_run(monkeypatch) -> None:
    page = make_page()
    page._file_paths = [Path("sample.md")]
    page._cleanup_batch_worker = lambda: None
    page._set_generate_actions_enabled = lambda _enabled: None
    page._files_need_ocr = lambda: False
    page._main.register_task = lambda task, activate=True: task
    created: dict[str, object] = {}

    def _create_task_run(flow: str):
        task = build_default_task_run(flow=flow, task_id="task-import")
        created["flow"] = flow
        created["task"] = task
        return task

    class _SignalStub:
        def connect(self, _callback) -> None:
            return None

    class _WorkerStub:
        def __init__(self, *_args, **_kwargs) -> None:
            self.file_progress = _SignalStub()
            self.file_completed = _SignalStub()
            self.file_warning = _SignalStub()
            self.page_progress = _SignalStub()
            self.ocr_progress = _SignalStub()
            self.finished = _SignalStub()
            self.error = _SignalStub()
            self.cancelled = _SignalStub()

        def start(self) -> None:
            return None

    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda _config: None)
    monkeypatch.setattr("ankismart.ui.import_page.BatchConvertWorker", _WorkerStub)
    page._create_task_run = _create_task_run

    ImportPage._start_convert(page)

    assert created["flow"] == "full_pipeline"
    assert getattr(page, "_current_task_id", "") == "task-import"


def test_build_generation_config_mixed_mode() -> None:
    page = make_page()
    page._auto_target_count_switch = DummySwitch(False)
    page._total_count_input = DummyLineEdit("30")
    page._total_count_mode_combo = DummyModeCombo("custom")
    page._strategy_sliders = [
        ("basic", DummySlider(50), None),
        ("cloze", DummySlider(30), None),
        ("single_choice", DummySlider(0), None),
    ]

    config = ImportPage.build_generation_config(page)

    assert config["mode"] == "mixed"
    assert config["target_total"] == 30
    assert config["auto_target_count"] is False
    assert config["strategy_mix"] == [
        {"strategy": "basic", "ratio": 50},
        {"strategy": "cloze", "ratio": 30},
    ]


def test_on_decks_loaded_restores_last_deck_choice():
    page = make_page()
    page._main.config.last_deck = "MyDeck"
    page._deck_combo.setCurrentText("TempDeck")

    ImportPage._on_decks_loaded(page, ["Default", "MyDeck", "Other"])

    assert page._deck_combo.currentText() == "MyDeck"


def test_load_decks_is_disabled_and_does_not_create_worker(monkeypatch) -> None:
    page = make_page()
    worker_created = {"value": False}

    class _Worker:
        def __init__(self, *_args, **_kwargs):
            worker_created["value"] = True

    monkeypatch.setattr("ankismart.ui.import_page.DeckLoaderWorker", _Worker)

    ImportPage._load_decks(page)

    assert worker_created["value"] is False
    assert page.__dict__.get("_deck_loader") is None


def test_resolve_initial_deck_name_prefers_last_then_default() -> None:
    page = make_page()
    page._main.config.last_deck = "LastDeck"
    page._main.config.default_deck = "DefaultDeck"
    assert ImportPage._resolve_initial_deck_name(page) == "LastDeck"

    page._main.config.last_deck = "   "
    assert ImportPage._resolve_initial_deck_name(page) == "DefaultDeck"

    page._main.config.default_deck = ""
    assert ImportPage._resolve_initial_deck_name(page) == "Default"


def test_persist_ocr_config_updates_prefers_runtime_apply(monkeypatch):
    page = make_page()
    applied: dict[str, object] = {}

    def apply_runtime(config: AppConfig, *, persist: bool = True, changed_fields=None):
        applied["config"] = config
        applied["persist"] = persist
        page._main.config = config
        return set(changed_fields or [])

    page._main.apply_runtime_config = apply_runtime

    def unexpected_save(_):
        raise AssertionError(
            "save_config should not be called directly when runtime apply is available"
        )

    monkeypatch.setattr("ankismart.ui.import_page.save_config", unexpected_save)

    ImportPage._persist_ocr_config_updates(page, ocr_model_tier="accuracy")

    assert "config" in applied
    assert applied["persist"] is True
    assert isinstance(applied["config"], AppConfig)
    assert applied["config"].ocr_model_tier == "accuracy"


def test_strategy_template_change_updates_sliders_immediately(monkeypatch):
    page = make_page()
    calls = patch_infobar(monkeypatch)

    class MutableSlider:
        def __init__(self, value: int = 0) -> None:
            self._value = value

        def value(self) -> int:
            return self._value

        def setValue(self, value: int) -> None:  # noqa: N802
            self._value = value

    class Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:  # noqa: N802
            self.text = text

    page._strategy_sliders = [
        ("basic", MutableSlider(100), Label()),
        ("cloze", MutableSlider(0), Label()),
        ("concept", MutableSlider(0), Label()),
        ("key_terms", MutableSlider(0), Label()),
        ("single_choice", MutableSlider(0), Label()),
        ("multiple_choice", MutableSlider(0), Label()),
    ]
    page._strategy_template_combo = DummyCombo("balanced")

    ImportPage._on_strategy_template_changed(page)

    expected_mix = dict(_STRATEGY_TEMPLATE_LIBRARY["balanced"]["mix"])
    actual_mix = {strategy_id: slider.value() for strategy_id, slider, _ in page._strategy_sliders}
    assert actual_mix["basic"] == expected_mix["basic"]
    assert actual_mix["cloze"] == expected_mix["cloze"]
    assert actual_mix["concept"] == expected_mix["concept"]
    assert actual_mix["key_terms"] == expected_mix["key_terms"]
    assert actual_mix["single_choice"] == expected_mix["single_choice"]
    assert actual_mix["multiple_choice"] == 0
    assert calls["success"] == []


def test_apply_strategy_template_button_keeps_feedback(monkeypatch):
    page = make_page()
    calls = patch_infobar(monkeypatch)

    class MutableSlider:
        def __init__(self, value: int = 0) -> None:
            self._value = value

        def value(self) -> int:
            return self._value

        def setValue(self, value: int) -> None:  # noqa: N802
            self._value = value

    class Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:  # noqa: N802
            self.text = text

    page._strategy_sliders = [
        ("basic", MutableSlider(100), Label()),
        ("cloze", MutableSlider(0), Label()),
        ("concept", MutableSlider(0), Label()),
        ("key_terms", MutableSlider(0), Label()),
        ("single_choice", MutableSlider(0), Label()),
        ("multiple_choice", MutableSlider(0), Label()),
    ]
    page._strategy_template_combo = DummyCombo("language")

    ImportPage._apply_selected_strategy_template(page)

    assert len(calls["success"]) == 1
    assert "语言记忆" in calls["success"][0]["content"]


def test_cloud_ocr_page_progress_updates_progress_bar(monkeypatch):
    page = make_page()
    patch_infobar(monkeypatch)
    page._main.config.ocr_mode = "cloud"
    page._main.config.language = "zh"
    page._file_paths = [Path("sample.pdf")]
    page._file_status = {"sample.pdf": "pending"}
    page._file_name_to_keys = {"sample.pdf": ["sample.pdf"]}
    page._last_ocr_page_status_message = ""

    class Progress:
        def __init__(self) -> None:
            self._value = 0

        def setValue(self, value: int) -> None:  # noqa: N802
            self._value = value

        def value(self) -> int:
            return self._value

    class Status:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:  # noqa: N802
            self.text = text

    page._progress_bar = Progress()
    page._status_label = Status()

    ImportPage._on_file_progress(page, "sample.pdf", 1, 1)
    assert page._progress_bar.value() == 0

    ImportPage._on_page_progress(page, "sample.pdf", 1, 3)
    assert page._progress_bar.value() == 33
    assert "云端 OCR 处理中" in page._status_label.text

    ImportPage._on_page_progress(page, "sample.pdf", 3, 3)
    assert page._progress_bar.value() == 100


def test_ocr_download_finished_uses_page_infobar_helper(monkeypatch):
    page = make_page()
    page._state_tooltip = None
    page._model_check_in_progress = True
    page._last_ocr_progress_message = ""
    calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(page, "_set_generate_actions_enabled", lambda enabled: None)
    monkeypatch.setattr(page, "_cleanup_ocr_download_worker", lambda: None)
    monkeypatch.setattr(
        ImportPage,
        "_show_info_bar",
        lambda *args, **kwargs: calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        "ankismart.ui.import_page.InfoBar.success",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    ImportPage._on_ocr_download_finished(page, ["model-a"])

    assert len(calls) == 1
    assert calls[0][0][1] == "success"


def test_cloud_ocr_message_progress_updates_status_text():
    page = make_page()
    page._main.config.ocr_mode = "cloud"
    page._main.config.language = "zh"
    page._current_file_index = 1
    page._total_files = 1
    page._last_convert_ocr_message = ""

    class Progress:
        def __init__(self) -> None:
            self._value = 66

        def value(self) -> int:
            return self._value

    class Status:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:  # noqa: N802
            self.text = text

    page._progress_bar = Progress()
    page._status_label = Status()

    ImportPage._on_ocr_progress(page, "云端 OCR: 上传文件中...")
    assert "云端 OCR: 上传文件中..." in page._status_label.text


def test_validate_convert_request_rejects_missing_api_key_for_non_ollama() -> None:
    issue = validate_convert_request(
        ConvertWorkflowRequest(
            language="zh",
            file_paths=(Path("a.md"),),
            deck_name="Default",
            strategy_mix=({"strategy": "basic", "ratio": 100},),
            provider_name="OpenAI",
            provider_api_key="",
            allow_keyless_provider=False,
        )
    )

    assert issue is not None
    assert issue.focus_target == "provider"
    assert "API Key" in issue.content


def test_format_operation_hint_includes_last_and_median() -> None:
    config = AppConfig(language="zh")
    config.ops_conversion_durations = [6.0, 10.0, 14.0]
    config.task_history = [
        {
            "event": "batch_convert",
            "status": "success",
            "summary": "转换 3/3，失败 0",
            "payload": {"duration_seconds": 14.0},
        }
    ]

    text = format_operation_hint(config, event="convert", language="zh")

    assert "最近转换 14.0 秒" in text
    assert "P50 10.0 秒" in text


def test_format_operation_hint_reads_batch_push_history() -> None:
    config = AppConfig(language="zh")
    config.ops_push_durations = [4.0, 8.0, 12.0]
    config.task_history = [
        {
            "event": "batch_push",
            "status": "success",
            "summary": "推送成功 12 张，失败 0 张",
            "payload": {"duration_seconds": 12.0},
        }
    ]

    text = format_operation_hint(config, event="push", language="zh")

    assert "最近推送 12.0 秒" in text
    assert "P50 8.0 秒" in text


def test_import_page_refresh_conversion_hint_uses_metrics() -> None:
    page = make_page()

    class _Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:  # noqa: N802
            self.text = text

    page._performance_hint_label = _Label()
    page._main.config.ops_conversion_durations = [8.0, 12.0]
    page._main.config.task_history = [
        {
            "event": "batch_convert",
            "status": "success",
            "summary": "转换 1/1，失败 0",
            "payload": {"duration_seconds": 12.0},
        }
    ]

    ImportPage._refresh_conversion_hint(page)

    assert "最近转换 12.0 秒" in page._performance_hint_label.text
    assert "P50 10.0 秒" in page._performance_hint_label.text
