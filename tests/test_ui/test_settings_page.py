from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget
from qfluentwidgets import ScrollArea
from qfluentwidgets import BodyLabel

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui import settings_page as settings_page_module
from ankismart.ui.settings_page import SettingsPage, configure_ocr_runtime

ProviderListItemWidget = getattr(settings_page_module, "ProviderListItemWidget", None)
ProviderListWidget = getattr(settings_page_module, "ProviderListWidget", None)


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


@pytest.mark.skipif(ProviderListWidget is None, reason="legacy provider list widget removed")
def test_provider_list_panel_uses_theme_neutral_style(_qapp) -> None:
    panel = ProviderListWidget()
    assert panel.objectName() == "providerListPanel"
    assert "QWidget#providerListPanel" in panel.styleSheet()
    assert "background-color: transparent" in panel.styleSheet()
    assert "#FFFFFF" not in panel.styleSheet()


@pytest.mark.skipif(ProviderListItemWidget is None, reason="legacy provider list widget removed")
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


@pytest.mark.skipif(ProviderListWidget is None, reason="legacy provider list widget removed")
def test_provider_list_height_auto_adjust(_qapp) -> None:
    panel = ProviderListWidget()
    providers = [LLMProviderConfig(id=f"p{i}", name=f"P{i}") for i in range(5)]

    panel.update_providers(providers[:2], "p1")
    assert panel.height() == 146

    panel.update_providers(providers, "p1")
    assert panel.height() == 290


@pytest.mark.skipif(ProviderListWidget is None, reason="legacy provider list widget removed")
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


@pytest.mark.skipif(ProviderListWidget is None, reason="legacy provider list widget removed")
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


def test_load_config_populates_ocr_controls(_qapp) -> None:
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
        ocr_mode="cloud",
        ocr_model_tier="accuracy",
        ocr_model_source="cn_mirror",
        ocr_auto_cuda_upgrade=False,
    )
    main, _ = _make_main(cfg)
    page = SettingsPage(main)

    assert page._ocr_mode_combo.currentData() == "cloud"
    assert page._ocr_model_tier_combo.currentData() == "accuracy"
    assert page._ocr_source_combo.currentData() == "cn_mirror"
    assert page._ocr_cuda_auto_card.isChecked() is False


def test_save_config_persists_ocr_settings(_qapp, monkeypatch) -> None:
    main, _ = _make_main()
    page = SettingsPage(main)

    captured: dict[str, AppConfig] = {}
    monkeypatch.setattr("ankismart.ui.settings_page.save_config", lambda c: captured.setdefault("cfg", c))
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "local":
            page._ocr_mode_combo.setCurrentIndex(index)
            break
    for index in range(page._ocr_model_tier_combo.count()):
        if page._ocr_model_tier_combo.itemData(index) == "standard":
            page._ocr_model_tier_combo.setCurrentIndex(index)
            break
    for index in range(page._ocr_source_combo.count()):
        if page._ocr_source_combo.itemData(index) == "cn_mirror":
            page._ocr_source_combo.setCurrentIndex(index)
            break
    page._ocr_cuda_auto_card.setChecked(False)

    page._save_config()

    assert "cfg" in captured
    assert captured["cfg"].ocr_mode == "local"
    assert captured["cfg"].ocr_model_tier == "standard"
    assert captured["cfg"].ocr_model_locked_by_user is True


def test_save_config_does_not_override_theme(_qapp, monkeypatch) -> None:
    main, _ = _make_main()
    theme_calls: list[str] = []
    main.switch_theme = lambda theme: theme_calls.append(theme)
    main.switch_language = lambda language: None

    page = SettingsPage(main)

    captured: dict[str, AppConfig] = {}
    monkeypatch.setattr("ankismart.ui.settings_page.save_config", lambda c: captured.setdefault("cfg", c))
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    page._save_config()

    assert "cfg" in captured
    assert captured["cfg"].theme == main.config.theme
    assert theme_calls == []


def test_save_config_prefers_runtime_apply_when_available(_qapp, monkeypatch) -> None:
    main, _ = _make_main()
    applied: dict[str, object] = {}

    def _apply_runtime(config: AppConfig, *, persist: bool = True, changed_fields=None):
        applied["config"] = config
        applied["persist"] = persist
        applied["changed_fields"] = changed_fields
        main.config = config
        return set(changed_fields or [])

    main.apply_runtime_config = _apply_runtime
    page = SettingsPage(main)

    def _unexpected_save(_):
        raise AssertionError("save_config should not be called directly when runtime apply is available")

    monkeypatch.setattr("ankismart.ui.settings_page.save_config", _unexpected_save)
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    page._language_combo.setCurrentIndex(1)  # English
    page._save_config()

    assert "config" in applied
    assert applied["persist"] is True
    assert isinstance(applied["config"], AppConfig)
    assert applied["config"].language == "en"


def test_ocr_connectivity_cloud_mode_shows_developing_message(_qapp, monkeypatch) -> None:
    main, _ = _make_main()
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
    main, _ = _make_main()
    page = SettingsPage(main)

    calls = []
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr("ankismart.ui.settings_page.get_missing_ocr_models", lambda **kwargs: ["PP-OCRv5_mobile_det"])

    page._test_ocr_connectivity()

    assert len(calls) == 1
    assert calls[0][0][0] == "warning"


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


def test_proxy_manual_layout_places_input_left_of_mode_combo(_qapp) -> None:
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
        proxy_mode="manual",
        proxy_url="http://127.0.0.1:7890",
    )
    main, _ = _make_main(cfg)
    page = SettingsPage(main)
    page.resize(1100, 900)
    page.show()
    _qapp.processEvents()

    assert page._proxy_edit.isVisible()
    assert page._proxy_edit.y() == page._proxy_mode_combo.y() or abs(page._proxy_edit.y() - page._proxy_mode_combo.y()) <= 4
    assert page._proxy_edit.x() < page._proxy_mode_combo.x()


def test_other_group_stays_at_bottom(_qapp) -> None:
    main, _ = _make_main()
    page = SettingsPage(main)
    page.resize(1200, 900)
    page.show()
    _qapp.processEvents()

    groups = [
        page._llm_group,
        page._anki_group,
        page._ocr_group,
        page._cache_group,
        page._experimental_group,
    ]
    max_other_y = max(group.y() for group in groups)
    assert page._other_group.y() > max_other_y


def test_scroll_step_is_tuned_for_faster_following(_qapp) -> None:
    main, _ = _make_main()
    page = SettingsPage(main)

    assert page.verticalScrollBar().singleStep() == 64
    assert page.verticalScrollBar().pageStep() == 360
