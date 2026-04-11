from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel, ExpandGroupSettingCard, PrimaryPushButton, PushButton

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.settings_page import SettingsPage

from .settings_page_test_utils import make_main


@pytest.fixture(scope="session", name="_qapp")
def _qapp_fixture():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


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
    assert "background-color: transparent" in style
    assert "#FFFFFF" not in style


def test_provider_summary_panel_prefers_compact_width(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    policy = page._provider_summary_panel.sizePolicy()

    assert policy.horizontalPolicy() == policy.Policy.Fixed
    assert page._provider_summary_panel.maximumWidth() == 280


def test_settings_page_does_not_keep_legacy_provider_table(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    assert not hasattr(page, "_provider_table")


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

    assert page._provider_summary_name_label.text() == "Vendor-X / model-a"
    assert page._provider_summary_status_label.isHidden()
    assert page._provider_summary_meta_label.isHidden()


def test_provider_ui_uses_english_copy_for_empty_fields(_qapp) -> None:
    providers = [
        LLMProviderConfig(
            id="p1",
            name="",
            api_key="",
            base_url="",
            model="",
        )
    ]
    cfg = AppConfig(language="en", llm_providers=providers, active_provider_id="p1")
    main, _ = make_main(cfg)
    page = SettingsPage(main)

    assert page._provider_summary_name_label.text() == "Unnamed provider / No model configured"
    assert page._provider_summary_status_label.isHidden()
    assert page._provider_summary_meta_label.isHidden()

    detail_widget = page._provider_detail_widgets[0]
    assert detail_widget.findChild(BodyLabel, "providerExpandName") is None
    assert detail_widget.findChild(BodyLabel, "providerExpandModel") is None
    assert detail_widget.findChild(BodyLabel, "providerExpandUrl") is None
    assert detail_widget.findChild(BodyLabel, "providerExpandRpm").text() == "RPM: Unlimited"
    assert "API Key" not in " ".join(
        label.text() for label in detail_widget.findChildren(BodyLabel)
    )

    action_widget = page._provider_action_widgets["p1"]
    assert action_widget.layout().itemAt(0).widget().text() == "Current"
    assert action_widget.layout().itemAt(1).widget().text() == "Edit"
    assert action_widget.layout().itemAt(2).widget().text() == "Test"
    assert action_widget.layout().itemAt(3).widget().text() == "Delete"


def test_provider_list_card_renders_one_group_per_provider(_qapp) -> None:
    providers = [
        LLMProviderConfig(
            id="p1", name="Vendor-X", model="model-a", base_url="https://a.example/v1"
        ),
        LLMProviderConfig(
            id="p2", name="Vendor-Y", model="model-b", base_url="https://b.example/v1"
        ),
    ]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="p1")

    assert isinstance(page._provider_list_card, ExpandGroupSettingCard)
    assert list(page._provider_group_widgets) == ["p1", "p2"]
    assert len(page._provider_list_card.widgets) == 2

    first_group = page._provider_group_widgets["p1"]
    assert first_group.titleLabel.text() == "Vendor-X"
    assert "model-a" in first_group.contentLabel.text()
    assert "https://a.example/v1" in first_group.contentLabel.text()
    assert page._provider_list_card.isExpand is False


def test_provider_expand_group_hides_api_key_and_keeps_actions(_qapp) -> None:
    providers = [
        LLMProviderConfig(
            id="p1",
            name="OpenAI",
            api_key="secret-key",
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
        )
    ]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="p1")

    detail_widget = page._provider_detail_widgets[0]
    labels = detail_widget.findChildren(BodyLabel)
    joined_text = " ".join(label.text() for label in labels)

    assert "API Key" not in joined_text
    assert "secret-key" not in joined_text
    assert detail_widget.findChild(BodyLabel, "providerExpandName") is None
    assert detail_widget.height() <= 56
    assert "background-color: transparent" in detail_widget.styleSheet()
    assert "border: none" in detail_widget.styleSheet()
    assert "border-radius: 0" in detail_widget.styleSheet()


def test_provider_expand_group_keeps_only_rpm_column(_qapp) -> None:
    providers = [
        LLMProviderConfig(
            id="p1",
            name="OpenAI",
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
            rpm_limit=0,
        ),
        LLMProviderConfig(
            id="p2",
            name="DeepSeek",
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            rpm_limit=120,
        ),
    ]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="p1")

    first_detail = page._provider_detail_widgets[0]
    second_detail = page._provider_detail_widgets[1]
    assert first_detail.findChild(BodyLabel, "providerExpandName") is None
    assert first_detail.findChild(BodyLabel, "providerExpandModel") is None
    assert first_detail.findChild(BodyLabel, "providerExpandUrl") is None
    first_rpm = first_detail.findChild(BodyLabel, "providerExpandRpm")
    second_rpm = second_detail.findChild(BodyLabel, "providerExpandRpm")
    assert first_rpm is not None
    assert second_rpm is not None
    assert first_rpm.minimumWidth() == second_rpm.minimumWidth()
    assert "border: none" in first_rpm.styleSheet()
    assert "background-color: transparent" in first_rpm.styleSheet()


def test_provider_summary_uses_first_provider_when_active_id_missing(_qapp) -> None:
    providers = [
        LLMProviderConfig(id="p1", name="Fallback-A", model="model-a"),
        LLMProviderConfig(id="p2", name="Fallback-B", model="model-b"),
    ]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="missing")

    assert page._provider_summary_name_label.text() == "Fallback-A / model-a"


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


def test_activate_provider_refreshes_summary_and_action_widgets(_qapp, monkeypatch) -> None:
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
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="p1")
    monkeypatch.setattr(page, "_save_config_silent", lambda **kwargs: None)

    page._activate_provider(page._providers[1])

    assert page._provider_summary_name_label.text() == "DeepSeek / deepseek-chat"
    p2_activate_btn = page._provider_action_widgets["p2"].layout().itemAt(0).widget()
    p1_activate_btn = page._provider_action_widgets["p1"].layout().itemAt(0).widget()
    assert isinstance(p2_activate_btn, PrimaryPushButton)
    assert type(p1_activate_btn) is PushButton


def test_retranslate_ui_refreshes_provider_copy(_qapp) -> None:
    providers = [
        LLMProviderConfig(
            id="p1",
            name="OpenAI",
            api_key="k1",
            base_url="",
            model="",
        ),
    ]
    cfg = AppConfig(language="zh", llm_providers=providers, active_provider_id="p1")
    main, _ = make_main(cfg)
    page = SettingsPage(main)

    main.config = main.config.model_copy(update={"language": "en"})
    page._main.config = main.config
    page.retranslate_ui()

    assert page._provider_summary_card.titleLabel.text() == "Active Provider"
    assert page._provider_mgmt_card.titleLabel.text() == "LLM Provider"
    assert page._provider_summary_name_label.text() == "OpenAI / No model configured"

    action_widget = page._provider_action_widgets["p1"]
    assert action_widget.layout().itemAt(0).widget().text() == "Current"
    assert action_widget.layout().itemAt(1).widget().text() == "Edit"


def test_retranslate_ui_refreshes_doc_convert_backend_copy(_qapp) -> None:
    cfg = AppConfig(language="zh", doc_convert_backend="markitdown")
    main, _ = make_main(cfg)
    page = SettingsPage(main)

    assert page._doc_convert_backend_card.titleLabel.text() == "非 OCR 文档转 Markdown 后端"
    assert "DOCX / PPTX" in page._doc_convert_backend_card.contentLabel.text()
    assert page._doc_convert_backend_combo.currentText() == "MarkItDown（实验）"

    main.config = main.config.model_copy(update={"language": "en"})
    page._main.config = main.config
    page.retranslate_ui()

    assert page._doc_convert_backend_card.titleLabel.text() == "Non-OCR Markdown Backend"
    assert "PDFs and images still use OCR." in page._doc_convert_backend_card.contentLabel.text()
    assert page._doc_convert_backend_combo.currentText() == "MarkItDown (Experimental)"


def test_save_first_provider_refreshes_summary_and_group_list(_qapp, monkeypatch) -> None:
    cfg = AppConfig(llm_providers=[], active_provider_id="")
    main, _ = make_main(cfg)
    page = SettingsPage(main)
    monkeypatch.setattr(page, "_save_config_silent", lambda **kwargs: None)

    provider = LLMProviderConfig(
        id="p1",
        name="OpenAI",
        api_key="test-key-1234",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
    )

    page._on_provider_saved(provider)

    assert page._provider_summary_name_label.text() == "OpenAI / gpt-4o"
    assert list(page._provider_group_widgets) == ["p1"]
    activate_btn = page._provider_action_widgets["p1"].layout().itemAt(0).widget()
    assert isinstance(activate_btn, PrimaryPushButton)
