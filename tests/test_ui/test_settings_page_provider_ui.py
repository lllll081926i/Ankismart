from __future__ import annotations

from qfluentwidgets import PrimaryPushButton, PushButton

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


def test_provider_table_uses_theme_neutral_style(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    style = page._provider_table.styleSheet()
    assert "QTableWidget" in style
    assert "border: 1px solid" in style
    assert "#FFFFFF" not in style


def test_provider_table_displays_provider_fields(_qapp) -> None:
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

    assert page._provider_table.rowCount() == 1
    assert page._provider_table.item(0, 0).text() == "Vendor-X"
    assert page._provider_table.item(0, 1).text() == "model-a"
    assert page._provider_table.item(0, 2).text() == "https://example.com/v1"
    assert page._provider_table.item(0, 3).text() == "120"


def test_provider_table_height_stays_fixed_for_multi_providers(_qapp) -> None:
    providers2 = [LLMProviderConfig(id=f"p{i}", name=f"P{i}") for i in range(2)]
    providers5 = [LLMProviderConfig(id=f"x{i}", name=f"X{i}") for i in range(5)]

    page2 = _build_settings_page_with_providers(_qapp, providers2, active_provider_id="p0")
    page5 = _build_settings_page_with_providers(_qapp, providers5, active_provider_id="x0")

    assert page2._provider_table.height() == page5._provider_table.height()
    assert page5._provider_table.rowCount() == 5


def test_provider_table_uses_internal_scroll_when_rows_overflow(_qapp) -> None:
    providers = [LLMProviderConfig(id=f"p{i}", name=f"P{i}") for i in range(6)]
    page = _build_settings_page_with_providers(_qapp, providers, active_provider_id="p0")

    assert page._provider_table.verticalScrollBar().maximum() > 0


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


def test_provider_table_activation_buttons_match_active_state(_qapp) -> None:
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

    assert page._provider_table.columnCount() == 5
    assert page._provider_table.selectionMode() == page._provider_table.SelectionMode.NoSelection

    active_widget = page._provider_table.cellWidget(0, 4)
    inactive_widget = page._provider_table.cellWidget(1, 4)
    assert active_widget is not None
    assert inactive_widget is not None

    active_btn = active_widget.layout().itemAt(0).widget()
    inactive_btn = inactive_widget.layout().itemAt(0).widget()

    assert isinstance(active_btn, PrimaryPushButton)
    assert active_btn.text() == "当前"

    assert type(inactive_btn) is PushButton
    assert inactive_btn.text() == "激活"
