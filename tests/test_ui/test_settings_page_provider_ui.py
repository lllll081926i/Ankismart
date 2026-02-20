from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import BodyLabel, ScrollArea

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.settings_page import SettingsPage

from .settings_page_test_utils import (
    ProviderListItemWidget,
    ProviderListWidget,
    make_main,
)

pytest_plugins = ["tests.test_ui.settings_page_test_utils"]


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
    main, _ = make_main(cfg)
    page = SettingsPage(main)
    page.resize(1100, 900)
    page.show()
    _qapp.processEvents()

    assert page._proxy_edit.isVisible()
    assert page._proxy_edit.y() == page._proxy_mode_combo.y() or abs(page._proxy_edit.y() - page._proxy_mode_combo.y()) <= 8
    assert page._proxy_edit.x() < page._proxy_mode_combo.x()


def test_other_group_stays_at_bottom(_qapp) -> None:
    main, _ = make_main()
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
    main, _ = make_main()
    page = SettingsPage(main)

    assert page.verticalScrollBar().singleStep() == 64
    assert page.verticalScrollBar().pageStep() == 360


def test_provider_table_border_switches_with_theme(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    assert "rgba(0, 0, 0, 0.08)" in page._provider_table.styleSheet()

    monkeypatch.setattr("ankismart.ui.settings_page.isDarkTheme", lambda: True)
    page.update_theme()

    assert "rgba(255, 255, 255, 0.08)" in page._provider_table.styleSheet()
