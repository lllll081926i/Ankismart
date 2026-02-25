from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QMessageBox

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.error_handler import ErrorCategory, ErrorHandler
from ankismart.ui.settings_page import SettingsPage, configure_ocr_runtime

from .settings_page_test_utils import make_main

pytest_plugins = ["tests.test_ui.settings_page_test_utils"]


class _SignalStub:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _ThreadLikeWorker:
    def __init__(self, *, running: bool) -> None:
        self._running = running
        self.wait_calls: list[int] = []
        self.deleted = False

    def isRunning(self) -> bool:  # noqa: N802
        return self._running

    def wait(self, timeout: int) -> None:
        self.wait_calls.append(timeout)

    def deleteLater(self) -> None:  # noqa: N802
        self.deleted = True


def test_ocr_connectivity_cloud_mode_uses_worker(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    main.config.ocr_cloud_endpoint = "https://mineru.net"
    main.config.ocr_cloud_api_key = "test-token"
    page = SettingsPage(main)

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "cloud":
            page._ocr_mode_combo.setCurrentIndex(index)
            break

    class _WorkerStub:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.finished = _SignalStub()

        def start(self):
            self.finished.emit(True, "")

    monkeypatch.setattr("ankismart.ui.workers.OCRCloudConnectionWorker", _WorkerStub)

    calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    page._test_ocr_connectivity()

    assert len(calls) == 2
    assert calls[0][0][0] == "info"
    assert calls[1][0][0] == "success"


def test_ocr_connectivity_local_reports_missing_models(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        "ankismart.ui.settings_page.get_missing_ocr_models",
        lambda **kwargs: ["PP-OCRv5_mobile_det"],
    )

    page._test_ocr_connectivity()

    assert len(calls) == 1
    assert calls[0][0][0] == "warning"


def test_on_test_result_shows_infobar_and_dialog(_qapp, monkeypatch) -> None:
    main, status_calls = make_main()
    page = SettingsPage(main)

    infobar_calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs))
    )

    info_calls = []
    warn_calls = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: info_calls.append((args, kwargs))
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warn_calls.append((args, kwargs))
    )

    page._on_test_result(True)
    page._on_test_result(False)

    assert len(infobar_calls) == 2
    assert len(info_calls) == 0
    assert len(warn_calls) == 0
    assert status_calls == [True, False]


def test_on_provider_test_result_shows_expected_feedback(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    infobar_calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs))
    )

    info_calls = []
    warn_calls = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: info_calls.append((args, kwargs))
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warn_calls.append((args, kwargs))
    )

    page._on_provider_test_result("OpenAI", True, "")
    page._on_provider_test_result("OpenAI", False, "timeout")
    page._on_provider_test_result("OpenAI", False, "")

    assert len(infobar_calls) == 3
    assert len(info_calls) == 0
    assert len(warn_calls) == 0


def test_test_connection_uses_worker_and_triggers_success_flow(_qapp, monkeypatch) -> None:
    main, status_calls = make_main()
    page = SettingsPage(main)

    class _WorkerStub:
        def __init__(self, url: str, key: str, proxy_url: str = ""):
            self.url = url
            self.key = key
            self.proxy_url = proxy_url
            self.finished = _SignalStub()

        def start(self):
            self.finished.emit(True)

    monkeypatch.setattr("ankismart.ui.workers.ConnectionCheckWorker", _WorkerStub)
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

    page._test_connection()

    assert status_calls == [True]


def test_test_provider_connection_uses_worker_and_triggers_success_flow(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    class _ProviderWorkerStub:
        last_proxy_url = None

        def __init__(self, provider, **kwargs):
            self.provider = provider
            self.kwargs = kwargs
            _ProviderWorkerStub.last_proxy_url = kwargs.get("proxy_url")
            self.finished = _SignalStub()

        def start(self):
            self.finished.emit(True, "")

    monkeypatch.setattr("ankismart.ui.workers.ProviderConnectionWorker", _ProviderWorkerStub)
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

    provider = page._providers[0]
    page._test_provider_connection(provider)

    # Worker may finish synchronously in tests and should then be cleaned up.
    assert page._provider_test_worker is None
    assert _ProviderWorkerStub.last_proxy_url == ""


def test_test_provider_connection_uses_effective_manual_proxy(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)
    page._proxy_mode_combo.setCurrentIndex(1)  # manual
    page._proxy_edit.setText("http://proxy.local:8080")

    class _ProviderWorkerStub:
        last_proxy_url = None

        def __init__(self, provider, **kwargs):
            _ProviderWorkerStub.last_proxy_url = kwargs.get("proxy_url")
            self.finished = _SignalStub()

        def start(self):
            self.finished.emit(True, "")

    monkeypatch.setattr("ankismart.ui.workers.ProviderConnectionWorker", _ProviderWorkerStub)
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

    page._test_provider_connection(page._providers[0])

    assert _ProviderWorkerStub.last_proxy_url == "http://proxy.local:8080"


def test_activate_provider_persists_to_main_config_immediately(_qapp) -> None:
    p1 = LLMProviderConfig(
        id="p1", name="P1", api_key="k1", base_url="https://api.openai.com/v1", model="gpt-4o"
    )
    p2 = LLMProviderConfig(
        id="p2", name="P2", api_key="k2", base_url="https://api.openai.com/v1", model="gpt-4o"
    )
    cfg = AppConfig(llm_providers=[p1, p2], active_provider_id="p1")
    main, _ = make_main(cfg)

    def _apply_runtime(config: AppConfig, *, persist: bool = True, changed_fields=None):
        main.config = config
        return set(changed_fields or [])

    main.apply_runtime_config = _apply_runtime
    page = SettingsPage(main)

    page._activate_provider(page._providers[1])

    assert main.config.active_provider_id == "p2"


def test_cleanup_provider_worker_keeps_reference_when_thread_still_running(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)
    worker = _ThreadLikeWorker(running=True)
    page._provider_test_worker = worker

    page._cleanup_provider_test_worker()

    assert page._provider_test_worker is worker
    assert worker.wait_calls == [200]
    assert worker.deleted is False


def test_cleanup_provider_worker_releases_finished_thread(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)
    worker = _ThreadLikeWorker(running=False)
    page._provider_test_worker = worker

    page._cleanup_provider_test_worker()

    assert page._provider_test_worker is None
    assert worker.deleted is True


def test_cleanup_anki_worker_keeps_reference_when_thread_still_running(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)
    worker = _ThreadLikeWorker(running=True)
    page._anki_test_worker = worker

    page._cleanup_anki_test_worker()

    assert page._anki_test_worker is worker
    assert worker.wait_calls == [200]
    assert worker.deleted is False


def test_cleanup_anki_worker_releases_finished_thread(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)
    worker = _ThreadLikeWorker(running=False)
    page._anki_test_worker = worker

    page._cleanup_anki_test_worker()

    assert page._anki_test_worker is None
    assert worker.deleted is True


def test_configure_ocr_runtime_falls_back_for_legacy_signature(monkeypatch) -> None:
    class _LegacyModule:
        def __init__(self):
            self.calls = []

        def configure_ocr_runtime(self, **kwargs):
            self.calls.append(kwargs)
            if "reset_ocr_instance" in kwargs:
                raise TypeError(
                    "configure_ocr_runtime() got an unexpected keyword argument "
                    "'reset_ocr_instance'"
                )

    module = _LegacyModule()
    monkeypatch.setattr("ankismart.ui.settings_page._get_ocr_converter_module", lambda: module)

    configure_ocr_runtime(model_tier="standard", model_source="official", reset_ocr_instance=True)

    assert len(module.calls) == 2
    assert module.calls[1] == {"model_tier": "standard", "model_source": "official"}


def test_configure_ocr_runtime_reraises_unrelated_type_error(monkeypatch) -> None:
    class _BrokenModule:
        def configure_ocr_runtime(self, **kwargs):
            raise TypeError("bad payload type")

    monkeypatch.setattr(
        "ankismart.ui.settings_page._get_ocr_converter_module", lambda: _BrokenModule()
    )

    with pytest.raises(TypeError, match="bad payload type"):
        configure_ocr_runtime(
            model_tier="standard", model_source="official", reset_ocr_instance=True
        )


def test_error_handler_maps_cloud_ocr_auth_code() -> None:
    handler = ErrorHandler(language="zh")

    info = handler.classify_error(
        "[E_CONFIG_INVALID] Cloud OCR authentication failed. Please check API key."
    )

    assert info.category == ErrorCategory.API_KEY


def test_error_handler_maps_cloud_ocr_rate_limit_code() -> None:
    handler = ErrorHandler(language="zh")

    info = handler.classify_error(
        "[E_OCR_FAILED] Cloud OCR request rate limited. Please retry later."
    )

    assert info.title == "接口限频"


def test_error_handler_maps_cloud_ocr_endpoint_error() -> None:
    handler = ErrorHandler(language="zh")

    info = handler.classify_error(
        "[E_CONFIG_INVALID] Cloud OCR endpoint not found during create upload url."
    )

    assert info.category == ErrorCategory.NETWORK


def test_error_handler_maps_cloud_ocr_file_size_limit_code() -> None:
    handler = ErrorHandler(language="zh")

    info = handler.classify_error("[E_CONFIG_INVALID] Cloud OCR file size exceeds 200MB limit")

    assert info.category == ErrorCategory.FILE_FORMAT
    assert "200MB" in info.message


def test_error_handler_maps_cloud_ocr_page_limit_code() -> None:
    handler = ErrorHandler(language="zh")

    info = handler.classify_error(
        "[E_CONFIG_INVALID] Cloud OCR PDF pages exceed 600-page limit"
    )

    assert info.category == ErrorCategory.FILE_FORMAT
    assert "600" in info.message
