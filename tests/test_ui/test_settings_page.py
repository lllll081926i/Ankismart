from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
from qfluentwidgets import ScrollArea
from qfluentwidgets import BodyLabel

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.settings_page import ProviderListItemWidget, ProviderListWidget, SettingsPage


@pytest.fixture(scope="session")
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_main(config: AppConfig | None = None):
    if config is None:
        provider = LLMProviderConfig(
            id="p1",
            name="OpenAI",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
        )
        config = AppConfig(llm_providers=[provider], active_provider_id="p1")

    status_calls: list[bool] = []
    main = SimpleNamespace(
        config=config,
        set_connection_status=lambda connected: status_calls.append(connected),
    )
    return main, status_calls


def test_provider_list_panel_uses_white_background_style(_qapp) -> None:
    panel = ProviderListWidget()
    assert panel.objectName() == "providerListPanel"
    assert "QWidget#providerListPanel" in panel.styleSheet()
    assert "background-color: #FFFFFF" in panel.styleSheet()


def test_provider_list_item_has_detailed_provider_fields(_qapp) -> None:
    widget = ProviderListItemWidget(
        LLMProviderConfig(
            id="p1",
            name="Vendor-X",
            model="model-a",
            base_url="https://example.com/v1",
            rpm_limit=120,
        ),
        is_active=True,
        can_delete=True,
    )

    model_label = widget.findChild(BodyLabel, "providerModelLabel")
    url_label = widget.findChild(BodyLabel, "providerUrlLabel")
    rpm_label = widget.findChild(BodyLabel, "providerRpmLabel")

    assert model_label is not None
    assert model_label.text() == "模型：model-a"
    assert url_label is not None
    assert "地址：https://example.com/v1" in url_label.text()
    assert rpm_label is not None
    assert rpm_label.text() == "RPM：120"


def test_provider_list_height_auto_adjust(_qapp) -> None:
    panel = ProviderListWidget()
    providers = [LLMProviderConfig(id=f"p{i}", name=f"P{i}") for i in range(5)]

    panel.update_providers(providers[:2], "p1")
    assert panel.height() == 146

    panel.update_providers(providers, "p1")
    assert panel.height() == 290


def test_provider_list_wheel_forwards_to_parent_scroll_area(_qapp) -> None:
    class _ScrollSpy(ScrollArea):
        def __init__(self):
            super().__init__()
            self.called = 0

        def wheelEvent(self, event):
            self.called += 1

    spy = _ScrollSpy()
    container = QWidget(spy)
    panel = ProviderListWidget(container)
    panel.update_providers([LLMProviderConfig(id="p1", name="OpenAI")], "p1")

    class _Event:
        pass

    panel.wheelEvent(_Event())
    assert spy.called == 1


def test_provider_list_event_filter_forwards_at_scroll_edge(_qapp, monkeypatch) -> None:
    panel = ProviderListWidget()
    panel.update_providers([LLMProviderConfig(id=f"p{i}", name=f"P{i}") for i in range(6)], "p1")

    class _ParentSpy:
        def __init__(self):
            self.called = 0

        def wheelEvent(self, _event):
            self.called += 1

    parent = _ParentSpy()
    monkeypatch.setattr(panel, "_forward_wheel_to_parent", parent.wheelEvent)

    bar = panel._list_widget.verticalScrollBar()
    bar.setValue(bar.minimum())

    class _Wheel:
        def angleDelta(self):
            class _Delta:
                def y(self):
                    return 120

            return _Delta()

    assert panel._should_forward_from_list(_Wheel()) is True
    panel._forward_wheel_to_parent(_Wheel())
    assert parent.called == 1


def test_temperature_load_and_save_uses_slider(_qapp, monkeypatch) -> None:
    provider = LLMProviderConfig(
        id="p1",
        name="OpenAI",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
    )
    cfg = AppConfig(
        llm_providers=[provider],
        active_provider_id="p1",
        llm_temperature=1.2,
    )
    main, _ = _make_main(cfg)
    page = SettingsPage(main)

    assert page._temperature_slider.value() == 12

    captured: dict[str, AppConfig] = {}
    monkeypatch.setattr("ankismart.ui.settings_page.save_config", lambda c: captured.setdefault("cfg", c))
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    page._temperature_slider.setValue(15)
    page._save_config()

    assert "cfg" in captured
    assert captured["cfg"].llm_temperature == 1.5


def test_on_test_result_shows_infobar_and_dialog(_qapp, monkeypatch) -> None:
    main, status_calls = _make_main()
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
    main, _ = _make_main()
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
    main, status_calls = _make_main()
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
    main, _ = _make_main()
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
