from __future__ import annotations

from ankismart.core.config import AppConfig
from ankismart.ui.import_page import ImportPage

from .import_page_test_utils import DummyLineEdit, DummyModeCombo, DummySlider, make_page


def test_build_generation_config_single_mode() -> None:
    page = make_page()

    config = ImportPage.build_generation_config(page)

    assert config["mode"] == "mixed"
    assert config["target_total"] == 20
    assert config["strategy_mix"] == [{"strategy": "basic", "ratio": 100}]


def test_build_generation_config_mixed_mode() -> None:
    page = make_page()
    page._total_count_input = DummyLineEdit("30")
    page._total_count_mode_combo = DummyModeCombo("custom")
    page._strategy_sliders = [
        ("basic", DummySlider(50), None),
        ("cloze", DummySlider(30), None),
        ("single_choice", DummySlider(0), None),
    ]

    config = ImportPage.build_generation_config(page)

    assert config["mode"] == "mixed"
    assert config["target_total"] == 30
    assert config["strategy_mix"] == [
        {"strategy": "basic", "ratio": 50},
        {"strategy": "cloze", "ratio": 30},
    ]


def test_on_decks_loaded_restores_last_deck_choice():
    page = make_page()
    page._main.config.last_deck = "MyDeck"
    page._deck_combo.setCurrentText("TempDeck")

    ImportPage._on_decks_loaded(page, ["Default", "MyDeck", "Other"])

    assert page._deck_combo.currentText() == "MyDeck"


def test_load_decks_is_disabled_and_does_not_create_worker(monkeypatch) -> None:
    page = make_page()
    worker_created = {"value": False}

    class _Worker:
        def __init__(self, *_args, **_kwargs):
            worker_created["value"] = True

    monkeypatch.setattr("ankismart.ui.import_page.DeckLoaderWorker", _Worker)

    ImportPage._load_decks(page)

    assert worker_created["value"] is False
    assert page.__dict__.get("_deck_loader") is None


def test_resolve_initial_deck_name_prefers_last_then_default() -> None:
    page = make_page()
    page._main.config.last_deck = "LastDeck"
    page._main.config.default_deck = "DefaultDeck"
    assert ImportPage._resolve_initial_deck_name(page) == "LastDeck"

    page._main.config.last_deck = "   "
    assert ImportPage._resolve_initial_deck_name(page) == "DefaultDeck"

    page._main.config.default_deck = ""
    assert ImportPage._resolve_initial_deck_name(page) == "Default"


def test_persist_ocr_config_updates_prefers_runtime_apply(monkeypatch):
    page = make_page()
    applied: dict[str, object] = {}

    def apply_runtime(config: AppConfig, *, persist: bool = True, changed_fields=None):
        applied["config"] = config
        applied["persist"] = persist
        page._main.config = config
        return set(changed_fields or [])

    page._main.apply_runtime_config = apply_runtime

    def unexpected_save(_):
        raise AssertionError("save_config should not be called directly when runtime apply is available")

    monkeypatch.setattr("ankismart.ui.import_page.save_config", unexpected_save)

    ImportPage._persist_ocr_config_updates(page, ocr_model_tier="accuracy")

    assert "config" in applied
    assert applied["persist"] is True
    assert isinstance(applied["config"], AppConfig)
    assert applied["config"].ocr_model_tier == "accuracy"
