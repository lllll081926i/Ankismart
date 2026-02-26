from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.settings_page import SettingsPage

from .settings_page_test_utils import make_main

pytest_plugins = ["tests.test_ui.settings_page_test_utils"]


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
    main, _ = make_main(cfg)
    page = SettingsPage(main)

    assert page._temperature_slider.value() == 12

    captured: dict[str, AppConfig] = {}
    monkeypatch.setattr(
        "ankismart.ui.settings_page.save_config", lambda c: captured.setdefault("cfg", c)
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

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
    main, _ = make_main(cfg)
    page = SettingsPage(main)

    assert page._ocr_mode_combo.currentData() == "cloud"
    assert page._ocr_model_tier_combo.currentData() == "accuracy"
    assert page._ocr_source_combo.currentData() == "cn_mirror"
    assert page._ocr_cuda_auto_card.isChecked() is False
    assert page._ocr_cloud_limit_card.isHidden() is False


def test_ocr_cloud_limit_card_visibility_follows_mode(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "local":
            page._ocr_mode_combo.setCurrentIndex(index)
            break
    assert page._ocr_cloud_limit_card.isHidden() is True

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "cloud":
            page._ocr_mode_combo.setCurrentIndex(index)
            break
    assert page._ocr_cloud_limit_card.isHidden() is False


def test_ocr_cloud_api_key_input_is_wide_enough_for_long_tokens(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    assert page._ocr_cloud_api_key_edit.minimumWidth() >= 460


def test_ocr_cloud_mode_collapses_group_gap_to_cache(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)
    page.resize(1200, 900)
    page.show()

    local_cards = (
        page._ocr_cuda_auto_card,
        page._ocr_model_tier_card,
        page._ocr_source_card,
        page._ocr_cuda_detect_card,
    )
    cloud_cards = (
        page._ocr_cloud_provider_card,
        page._ocr_cloud_endpoint_card,
        page._ocr_cloud_api_key_card,
        page._ocr_cloud_limit_card,
    )

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "local":
            page._ocr_mode_combo.setCurrentIndex(index)
            break
    _qapp.processEvents()
    for card in local_cards:
        assert card.maximumHeight() > 0
    for card in cloud_cards:
        assert card.maximumHeight() == 0

    for index in range(page._ocr_mode_combo.count()):
        if page._ocr_mode_combo.itemData(index) == "cloud":
            page._ocr_mode_combo.setCurrentIndex(index)
            break
    _qapp.processEvents()

    for card in local_cards:
        assert card.maximumHeight() == 0
    for card in cloud_cards:
        assert card.maximumHeight() > 0
    assert page._cache_group.y() - (page._ocr_group.y() + page._ocr_group.height()) <= 12


def test_save_config_persists_ocr_settings(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    captured: dict[str, AppConfig] = {}
    monkeypatch.setattr(
        "ankismart.ui.settings_page.save_config", lambda c: captured.setdefault("cfg", c)
    )
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

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
    main, _ = make_main()
    theme_calls: list[str] = []
    main.switch_theme = lambda theme: theme_calls.append(theme)
    main.switch_language = lambda language: None

    page = SettingsPage(main)

    captured: dict[str, AppConfig] = {}
    monkeypatch.setattr(
        "ankismart.ui.settings_page.save_config", lambda c: captured.setdefault("cfg", c)
    )
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

    page._save_config()

    assert "cfg" in captured
    assert captured["cfg"].theme == main.config.theme
    assert theme_calls == []


def test_save_config_prefers_runtime_apply_when_available(_qapp, monkeypatch) -> None:
    main, _ = make_main()
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
        raise AssertionError(
            "save_config should not be called directly when runtime apply is available"
        )

    monkeypatch.setattr("ankismart.ui.settings_page.save_config", _unexpected_save)
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

    page._language_combo.setCurrentIndex(1)  # English
    page._save_config()

    assert "config" in applied
    assert applied["persist"] is True
    assert isinstance(applied["config"], AppConfig)
    assert applied["config"].language == "en"


def test_parse_version_tuple_ignores_non_numeric_suffix(_qapp) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    assert page._parse_version_tuple("v1.2.3rc1") == (1, 2, 3)
    assert page._parse_version_tuple("2.4.beta") == (2, 4, 0)


def test_save_config_persists_adaptive_concurrency_and_update_flags(_qapp, monkeypatch) -> None:
    main, _ = make_main()
    page = SettingsPage(main)

    captured: dict[str, AppConfig] = {}
    monkeypatch.setattr(
        "ankismart.ui.settings_page.save_config", lambda c: captured.setdefault("cfg", c)
    )
    monkeypatch.setattr("ankismart.ui.settings_page.configure_ocr_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

    page._concurrency_spin.setValue(8)
    page._concurrency_max_spin.setValue(4)
    page._adaptive_concurrency_switch.setChecked(False)
    page._auto_update_card.setChecked(False)
    page._save_config()

    assert "cfg" in captured
    assert captured["cfg"].llm_concurrency == 4
    assert captured["cfg"].llm_concurrency_max == 4
    assert captured["cfg"].llm_adaptive_concurrency is False
    assert captured["cfg"].auto_check_updates is False
