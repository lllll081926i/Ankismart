from __future__ import annotations

from qfluentwidgets import ExpandGroupSettingCard, PrimaryPushButton, PushButton

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.settings_page import SettingsPage

from .settings_page_test_utils import make_main

pytest_plugins = ["tests.test_ui.settings_page_test_utils"]


def _build_settings_page_with_providers(
    _qapp,
    providers: list[LLMProviderConfig],
    *,
    active_provider_id: str,
) -> SettingsPage:
    cfg = AppConfig(llm_providers=providers, active_provider_id=active_provider_id)
    main, _ = make_main(cfg)
    page = SettingsPage(main)
    page.resize(1200, 900)
    page.show()
    _qapp.processEvents()
    return page


def test_provider_summary_panel_uses_theme_neutral_style(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    style = page._provider_summary_panel.styleSheet()
    assert "border: 1px solid" in style
    assert "#FFFFFF" not in style


def test_provider_summary_displays_active_provider_fields(_qapp) -> None:
    providers = [
        LLMProviderConfig(
            id="p1",
            name="Vendor-X",
            model="model-a",
            base_url="https://example.com/v1",
            rpm_limit=120,
        )
    ]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="p1")

    assert page._provider_summary_name_label.text() == "Vendor-X"
    assert "model-a" in page._provider_summary_meta_label.text()
    assert "https://example.com/v1" in page._provider_summary_meta_label.text()
    assert "120" in page._provider_summary_meta_label.text()


def test_provider_list_card_renders_one_group_per_provider(_qapp) -> None:
    providers = [
        LLMProviderConfig(id="p1", name="Vendor-X", model="model-a", base_url="https://a.example/v1"),
        LLMProviderConfig(id="p2", name="Vendor-Y", model="model-b", base_url="https://b.example/v1"),
    ]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="p1")

    assert isinstance(page._provider_list_card, ExpandGroupSettingCard)
    assert list(page._provider_group_widgets) == ["p1", "p2"]
    assert len(page._provider_list_card.widgets) == 2

    first_group = page._provider_group_widgets["p1"]
    assert first_group.titleLabel.text() == "Vendor-X"
    assert "model-a" in first_group.contentLabel.text()
    assert "https://a.example/v1" in first_group.contentLabel.text()


def test_provider_summary_uses_first_provider_when_active_id_missing(_qapp) -> None:
    providers = [
        LLMProviderConfig(id="p1", name="Fallback-A", model="model-a"),
        LLMProviderConfig(id="p2", name="Fallback-B", model="model-b"),
    ]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="missing")

    assert page._provider_summary_name_label.text() == "Fallback-A"


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
    assert (
        page._proxy_edit.y() == page._proxy_mode_combo.y()
        or abs(page._proxy_edit.y() - page._proxy_mode_combo.y()) <= 8
    )
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
        page._network_group,
        page._cache_group,
        page._experimental_group,
    ]
    max_other_y = max(group.y() for group in groups)
    assert page._other_group.y() > max_other_y


def test_settings_page_does_not_render_overview_or_anchor_bar(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    assert not hasattr(page, "_overview_card")
    assert not hasattr(page, "_anchor_bar")


def test_scroll_step_is_tuned_for_faster_following(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    assert page.verticalScrollBar().singleStep() == 64
    assert page.verticalScrollBar().pageStep() == 360


def test_provider_summary_border_switches_with_theme(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    assert "rgba(0, 0, 0, 0.08)" in page._provider_summary_panel.styleSheet()

    monkeypatch.setattr("ankismart.ui.settings_page.isDarkTheme", lambda: True)
    page.update_theme()

    assert "rgba(255, 255, 255, 0.08)" in page._provider_summary_panel.styleSheet()


def test_provider_group_action_buttons_match_active_state(_qapp) -> None:
    providers = [
        LLMProviderConfig(
            id="p1",
            name="OpenAI",
            api_key="k1",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
        ),
        LLMProviderConfig(
            id="p2",
            name="DeepSeek",
            api_key="k2",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        ),
    ]
    cfg = AppConfig(llm_providers=providers, active_provider_id="p1")
    main, _ = make_main(cfg)
    page = SettingsPage(main)

    active_widget = page._provider_action_widgets["p1"]
    inactive_widget = page._provider_action_widgets["p2"]
    active_btn = active_widget.layout().itemAt(0).widget()
    inactive_btn = inactive_widget.layout().itemAt(0).widget()

    assert isinstance(active_btn, PrimaryPushButton)
    assert active_btn.text() == "当前"

    assert type(inactive_btn) is PushButton
    assert inactive_btn.text() == "激活"
