from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QMessageBox

from ankismart.ui.settings_page import SettingsPage, configure_ocr_runtime

from .settings_page_test_utils import _qapp, make_main


def test_ocr_connectivity_cloud_mode_shows_developing_message(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "cloud":
            page._ocr_mode_combo.setCurrentIndex(index)
            break

    calls = []
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: calls.append((args, kwargs)))

    page._test_ocr_connectivity()

    assert len(calls) == 1
    assert calls[0][0][0] == "info"


def test_ocr_connectivity_local_reports_missing_models(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    calls = []
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr("ankismart.ui.settings_page.get_missing_ocr_models", lambda **kwargs: ["PP-OCRv5_mobile_det"])

    page._test_ocr_connectivity()

    assert len(calls) == 1
    assert calls[0][0][0] == "warning"


def test_on_test_result_shows_infobar_and_dialog(_qapp, monkeypatch) -> None:
    main, status_calls = make_main()
    page = SettingsPage(main)

    infobar_calls = []
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs)))

    info_calls = []
    warn_calls = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: info_calls.append((args, kwargs)))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warn_calls.append((args, kwargs)))

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
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: infobar_calls.append((args, kwargs)))

    info_calls = []
    warn_calls = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: info_calls.append((args, kwargs)))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warn_calls.append((args, kwargs)))

    page._on_provider_test_result("OpenAI", True, "")
    page._on_provider_test_result("OpenAI", False, "timeout")
    page._on_provider_test_result("OpenAI", False, "")

    assert len(infobar_calls) == 3
    assert len(info_calls) == 0
    assert len(warn_calls) == 0


def test_test_connection_uses_worker_and_triggers_success_flow(_qapp, monkeypatch) -> None:
    main, status_calls = make_main()
    page = SettingsPage(main)

    class _SignalStub:
        def __init__(self):
            self._callback = None

        def connect(self, callback):
            self._callback = callback

        def emit(self, *args):
            if self._callback:
                self._callback(*args)

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
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    page._test_connection()

    assert status_calls == [True]


def test_test_provider_connection_uses_worker_and_triggers_success_flow(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    class _SignalStub:
        def __init__(self):
            self._callback = None

        def connect(self, callback):
            self._callback = callback

        def emit(self, *args):
            if self._callback:
                self._callback(*args)

    class _ProviderWorkerStub:
        def __init__(self, provider, **kwargs):
            self.provider = provider
            self.kwargs = kwargs
            self.finished = _SignalStub()

        def start(self):
            self.finished.emit(True, "")

    monkeypatch.setattr("ankismart.ui.workers.ProviderConnectionWorker", _ProviderWorkerStub)
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    provider = page._providers[0]
    page._test_provider_connection(provider)

    assert page._provider_test_worker is not None
    assert page._provider_test_worker.provider.id == provider.id


def test_configure_ocr_runtime_falls_back_for_legacy_signature(monkeypatch) -> None:
    class _LegacyModule:
        def __init__(self):
            self.calls = []

        def configure_ocr_runtime(self, **kwargs):
            self.calls.append(kwargs)
            if "reset_ocr_instance" in kwargs:
                raise TypeError("configure_ocr_runtime() got an unexpected keyword argument 'reset_ocr_instance'")

    module = _LegacyModule()
    monkeypatch.setattr("ankismart.ui.settings_page._get_ocr_converter_module", lambda: module)

    configure_ocr_runtime(model_tier="standard", model_source="official", reset_ocr_instance=True)

    assert len(module.calls) == 2
    assert module.calls[1] == {"model_tier": "standard", "model_source": "official"}


def test_configure_ocr_runtime_reraises_unrelated_type_error(monkeypatch) -> None:
    class _BrokenModule:
        def configure_ocr_runtime(self, **kwargs):
            raise TypeError("bad payload type")

    monkeypatch.setattr("ankismart.ui.settings_page._get_ocr_converter_module", lambda: _BrokenModule())

    with pytest.raises(TypeError, match="bad payload type"):
        configure_ocr_runtime(model_tier="standard", model_source="official", reset_ocr_instance=True)

