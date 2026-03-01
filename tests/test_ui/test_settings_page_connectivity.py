from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QUrl
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
    main.config.proxy_mode = "manual"
    main.config.proxy_url = "http://proxy.local:8080"
    page = SettingsPage(main)

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "cloud":
            page._ocr_mode_combo.setCurrentIndex(index)
            break

    class _WorkerStub:
        last_kwargs: dict[str, object] | None = None

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            _WorkerStub.last_kwargs = kwargs
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
    assert _WorkerStub.last_kwargs is not None
    assert _WorkerStub.last_kwargs.get("proxy_url", "") == ""


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


def test_check_for_updates_failure_updates_metadata_and_warns(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    applied: dict[str, object] = {}

    def _apply_runtime(config: AppConfig, *, persist: bool = True, changed_fields=None):
        applied["config"] = config
        applied["persist"] = persist
        applied["changed_fields"] = set(changed_fields or set())
        main.config = config
        return set(changed_fields or set())

    main.apply_runtime_config = _apply_runtime

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr("ankismart.ui.settings_page.httpx.Client", _FailingClient)
    infobar_calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs))
    )

    page._check_for_updates()

    assert "config" in applied
    assert applied["persist"] is True
    assert applied["changed_fields"] == {"last_update_check_at", "last_update_version_seen"}
    assert main.config.last_update_check_at != ""
    assert len(infobar_calls) == 1
    assert infobar_calls[0][0][0] == "warning"


def test_check_for_updates_detects_new_release_and_shows_clickable_infobar(
    _qapp, monkeypatch
) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    applied: dict[str, object] = {}

    def _apply_runtime(config: AppConfig, *, persist: bool = True, changed_fields=None):
        applied["config"] = config
        applied["persist"] = persist
        applied["changed_fields"] = set(changed_fields or set())
        main.config = config
        return set(changed_fields or set())

    main.apply_runtime_config = _apply_runtime

    class _Response:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload
            self.content = b"payload"

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    class _Client:
        request_headers = None

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, _url, headers=None):
            _Client.request_headers = headers
            return _Response(
                200,
                {
                    "tag_name": "v9.9.9",
                    "html_url": "https://github.com/lllll081926i/Ankismart/releases/tag/v9.9.9",
                },
            )

    monkeypatch.setattr("ankismart.ui.settings_page.httpx.Client", _Client)
    update_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        page,
        "_show_update_available_info_bar",
        lambda version, url: update_calls.append((version, url)),
    )
    opened: list[str] = []
    monkeypatch.setattr(
        "ankismart.ui.settings_page.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString() if isinstance(url, QUrl) else str(url)),
    )

    page._check_for_updates()

    assert "config" in applied
    assert applied["persist"] is True
    assert applied["changed_fields"] == {"last_update_check_at", "last_update_version_seen"}
    assert main.config.last_update_version_seen == "9.9.9"
    assert update_calls == [
        ("9.9.9", "https://github.com/lllll081926i/Ankismart/releases/tag/v9.9.9")
    ]
    assert not opened
    assert isinstance(_Client.request_headers, dict)
    assert "User-Agent" in _Client.request_headers
    assert "X-GitHub-Api-Version" in _Client.request_headers


def test_check_for_updates_falls_back_to_tags_api(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)
    main.apply_runtime_config = lambda config, **_kwargs: setattr(main, "config", config) or set()

    class _Response:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload
            self.content = b"payload"

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    class _Client:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            self.calls += 1
            if "releases/latest" in url:
                return _Response(403, {"message": "rate limited"})
            return _Response(200, [{"name": "v1.2.3"}])

    monkeypatch.setattr("ankismart.ui.settings_page.httpx.Client", _Client)
    update_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        page,
        "_show_update_available_info_bar",
        lambda version, url: update_calls.append((version, url)),
    )
    infobar_calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs))
    )

    page._check_for_updates()

    # Should not emit warning in fallback-success path.
    assert not any(call[0][0] == "warning" for call in infobar_calls)
    assert update_calls


def test_show_update_available_info_bar_can_open_release_page(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    class _InfoBarStub:
        def __init__(self) -> None:
            self.widgets = []

        def addWidget(self, widget, stretch=0):  # noqa: N802
            self.widgets.append(widget)

    info_bar_stub = _InfoBarStub()
    monkeypatch.setattr(
        "ankismart.ui.settings_page.InfoBar.info",
        lambda *args, **kwargs: info_bar_stub,
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "ankismart.ui.settings_page.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString() if isinstance(url, QUrl) else str(url)),
    )
    latest_url = "https://github.com/lllll081926i/Ankismart/releases/tag/v9.9.9"

    page._show_update_available_info_bar("9.9.9", latest_url)

    assert info_bar_stub.widgets
    info_bar_stub.widgets[0].click()
    assert opened == [latest_url]


def test_backup_current_config_reports_success(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    backup_path = Path("D:/tmp/config-backup.yaml")
    monkeypatch.setattr(
        "ankismart.ui.settings_page.create_config_backup",
        lambda *_args, **_kwargs: backup_path,
    )
    infobar_calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs))
    )

    page._backup_current_config()

    assert len(infobar_calls) == 1
    assert infobar_calls[0][0][0] == "success"
    assert str(backup_path) in infobar_calls[0][0][2]


def test_restore_config_backup_applies_runtime_config(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    selected_backup = Path("D:/tmp/config-backup.yaml")
    restored_cfg = main.config.model_copy(update={"language": "en"})
    applied: dict[str, object] = {}

    def _apply_runtime(config: AppConfig, *, persist: bool = True, changed_fields=None):
        applied["config"] = config
        applied["persist"] = persist
        main.config = config
        return set(changed_fields or set())

    main.apply_runtime_config = _apply_runtime
    monkeypatch.setattr(
        "ankismart.ui.settings_page.list_config_backups",
        lambda limit=30: [selected_backup],
    )
    monkeypatch.setattr(
        "ankismart.ui.settings_page.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(selected_backup), "YAML Files (*.yaml *.yml)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        "ankismart.ui.settings_page.restore_config_from_backup",
        lambda _path: restored_cfg,
    )
    load_calls: list[bool] = []
    monkeypatch.setattr(page, "_load_config", lambda: load_calls.append(True))
    infobar_calls = []
    monkeypatch.setattr(
        page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs))
    )

    page._restore_config_backup()

    assert "config" in applied
    assert applied["config"].language == "en"
    assert applied["persist"] is False
    assert load_calls == [True]
    assert len(infobar_calls) == 1
    assert infobar_calls[0][0][0] == "success"
